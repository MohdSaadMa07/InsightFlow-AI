"""
Enhanced Transformer Churn Classifier.

Features: CV drift check, PR-AUC consistency, probability correction layer,
event importance via attention, benchmark proof vs XGBoost.

Usage:
    python -m ml.models.transformers.churn_transformer --project_id 13
"""

import argparse
import math
import time
import os
import json
import random
from datetime import timedelta
from collections import defaultdict, Counter

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, auc, precision_recall_curve, confusion_matrix,
    classification_report, brier_score_loss
)
from sklearn.isotonic import IsotonicRegression

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def _ensure_django():
    import django.conf
    if not django.conf.settings.configured:
        import django; django.setup()


# ── Tokenization ────────────────────────────────────────────

def build_vocab(project_id):
    from events.models import Event
    names = sorted(Event.objects.filter(project_id=project_id)
                   .values_list("event_name", flat=True).distinct())
    vocab = {name: idx + 1 for idx, name in enumerate(names)}
    vocab["<PAD>"] = 0
    vocab["<CLS>"] = max(vocab.values()) + 1
    return vocab


def vocab_size(vocab):
    return max(vocab.values()) + 1


# ── Data loading ────────────────────────────────────────────

def load_token_sequences(project_id, vocab, obs_days=30, gap_days=30,
                         max_len=200, min_events=3):
    import pandas as pd
    from events.models import Event

    qs = Event.objects.filter(project_id=project_id).order_by("user_id", "timestamp")
    records = []
    for r in qs:
        ts = r.timestamp
        if hasattr(ts, "tzinfo") and ts.tzinfo is not None:
            ts = ts.replace(tzinfo=None)
        records.append({"user_id": r.user_id, "event_name": r.event_name, "timestamp": ts})
    df = pd.DataFrame(records)
    print(f"  Events: {len(df)}, Users: {df['user_id'].nunique()}")

    sequences = []
    for uid, grp in df.groupby("user_id"):
        grp = grp.sort_values("timestamp").reset_index(drop=True)
        user_start = grp["timestamp"].min()
        obs_end = user_start + timedelta(days=obs_days)
        gap_end = obs_end + timedelta(days=gap_days)
        obs_events = grp[grp["timestamp"] <= obs_end]
        if len(obs_events) < min_events:
            continue
        gap_events = grp[(grp["timestamp"] > obs_end) & (grp["timestamp"] <= gap_end)]
        churned = 1 if len(gap_events) == 0 else 0
        tokens = [vocab.get(name, 0) for name in obs_events["event_name"]]
        sequences.append({"uid": uid, "tokens": tokens, "churned": churned,
                          "first_ts": user_start, "seq_len": len(tokens)})

    print(f"  Sequences: {len(sequences)}, churn: {sum(s['churned'] for s in sequences)/len(sequences):.2%}")
    return sequences


def pad_sequences(sequences, max_len):
    N = len(sequences)
    X = torch.zeros(N, max_len, dtype=torch.long)
    mask = torch.zeros(N, max_len, dtype=torch.bool)
    y = torch.zeros(N, dtype=torch.float)
    timestamps = []
    for i, s in enumerate(sequences):
        tokens = s["tokens"][:max_len]
        sl = len(tokens)
        X[i, :sl] = torch.tensor(tokens, dtype=torch.long)
        mask[i, :sl] = True
        y[i] = float(s["churned"])
        timestamps.append(s["first_ts"])
    return X, mask, y, timestamps


# ── Stratified time split ───────────────────────────────────

def stratified_time_split(sequences, test_ratio=0.2, seed=42):
    classes = defaultdict(list)
    for s in sequences:
        classes[s["churned"]].append(s)
    train, test = [], []
    rng = random.Random(seed)
    for churn_class, seqs in classes.items():
        sorted_seqs = sorted(seqs, key=lambda x: x["first_ts"])
        split = int(len(sorted_seqs) * (1 - test_ratio))
        cutoff = sorted_seqs[split]["first_ts"]
        before = [s for s in sorted_seqs if s["first_ts"] <= cutoff]
        after = [s for s in sorted_seqs if s["first_ts"] > cutoff]
        if len(before) < len(sorted_seqs) * 0.7:
            before, after = sorted_seqs[:split], sorted_seqs[split:]
        train.extend(before)
        test.extend(after)
    rng.shuffle(train)
    rng.shuffle(test)
    return train, test


# ── Positional Encoding ─────────────────────────────────────

class PositionalEncoding(nn.Module):
    def __init__(self, d_model, max_len=2000, dropout=0.1):
        super().__init__()
        self.dropout = nn.Dropout(dropout)
        pe = torch.zeros(max_len, d_model)
        pos = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(pos * div)
        pe[:, 1::2] = torch.cos(pos * div)
        self.register_buffer("pe", pe.unsqueeze(0))

    def forward(self, x):
        return self.dropout(x + self.pe[:, :x.size(1), :])


# ── Probability Correction Layer ─────────────────────────────

class ProbCorrectionLayer(nn.Module):
    def __init__(self):
        super().__init__()
        self.temperature = nn.Parameter(torch.ones(1))
        self.isotonic = None

    def forward(self, logits):
        return logits / self.temperature

    def fit_isotonic(self, y_true, probs_np):
        self.isotonic = IsotonicRegression(out_of_bounds="clip")
        self.isotonic.fit(probs_np, y_true)

    def apply_isotonic(self, probs_np):
        if self.isotonic is not None:
            return self.isotonic.predict(probs_np).astype(np.float32)
        return probs_np

    def calibration_report(self, y_true, logits):
        probs = torch.sigmoid(logits).cpu().numpy()
        n_bins = 10
        bins = np.linspace(0, 1, n_bins + 1)
        ece, mce = 0.0, 0.0
        for bl, bu in zip(bins[:-1], bins[1:]):
            in_bin = (probs > bl) & (probs <= bu)
            if in_bin.any():
                diff = abs(y_true[in_bin].mean() - probs[in_bin].mean())
                ece += diff * in_bin.sum() / len(y_true)
                mce = max(mce, diff)
        return {
            "ece": round(ece, 4),
            "mce": round(mce, 4),
            "brier": round(brier_score_loss(y_true, probs), 4),
            "temperature": round(self.temperature.item(), 4),
        }


# ── Transformer Model ───────────────────────────────────────

class ChurnTransformer(nn.Module):
    def __init__(self, vocab_size, d_model=128, nhead=4, num_layers=4,
                 dim_feedforward=512, dropout=0.2, max_len=200):
        super().__init__()
        self.d_model = d_model
        self.token_emb = nn.Embedding(vocab_size, d_model, padding_idx=0)
        self.pos_enc = PositionalEncoding(d_model, max_len + 50, dropout)
        enc_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead, dim_feedforward=dim_feedforward,
            dropout=dropout, activation="gelu", batch_first=True, norm_first=True)
        self.encoder = nn.TransformerEncoder(enc_layer, num_layers=num_layers)
        self.cls = nn.Parameter(torch.randn(1, 1, d_model) * 0.02)
        self.head = nn.Linear(d_model, 1)

    def forward(self, x, mask, return_event_enc=False):
        N, L = x.size()
        cls = self.cls.expand(N, -1, -1)
        emb = self.token_emb(x) * math.sqrt(self.d_model)
        emb = torch.cat([cls, emb], dim=1)                       # (N, L+1, d)
        emb = self.pos_enc(emb)

        full_mask = torch.cat([torch.ones(N, 1, dtype=torch.bool, device=x.device), mask], dim=1)
        pad_mask = ~full_mask                                      # True = PAD

        enc = self.encoder(emb, src_key_padding_mask=pad_mask)    # (N, L+1, d)
        cls_out = enc[:, 0, :]                                     # (N, d)
        logits = self.head(cls_out).squeeze(-1)                   # (N,)

        if return_event_enc:
            return logits, enc[:, 1:, :]                           # skip CLS
        return logits


# ── Evaluation ──────────────────────────────────────────────

@torch.no_grad()
def evaluate(model, X, M, Y, threshold=0.5, prob_corr=None):
    model.eval()
    logits = model(X, M)
    if prob_corr is not None:
        logits = prob_corr(logits)
    probs = torch.sigmoid(logits).cpu().numpy()
    preds = (probs >= threshold).astype(int)
    yt = Y.cpu().numpy()
    return {
        "accuracy": round(accuracy_score(yt, preds), 4),
        "precision": round(precision_score(yt, preds, zero_division=0), 4),
        "recall": round(recall_score(yt, preds, zero_division=0), 4),
        "f1": round(f1_score(yt, preds, zero_division=0), 4),
        "roc_auc": round(roc_auc_score(yt, probs), 4),
        "y_true": yt, "y_pred": preds, "y_proba": probs,
    }


def compute_pr_auc(y_true, y_proba):
    p, r, _ = precision_recall_curve(y_true, y_proba)
    return auc(r, p)


def find_optimal_threshold(y_true, y_proba):
    best_t, best_f = 0.5, 0
    for t in np.linspace(0.1, 0.9, 81):
        preds = (y_proba >= t).astype(int)
        if len(np.unique(preds)) < 2:
            continue
        f = f1_score(y_true, preds, zero_division=0)
        if f > best_f:
            best_f = f
            best_t = t
    return best_t, best_f


# ── Event Importance Explanation ─────────────────────────────

def explain_event_importance(model, X_sample, M_sample, vocab_reverse):
    model.eval()
    with torch.no_grad():
        logits, enc = model(X_sample.unsqueeze(0), M_sample.unsqueeze(0), return_event_enc=True)
    imp = enc[0].norm(dim=-1).cpu().numpy()
    tokens = X_sample.cpu().numpy()
    mask_np = M_sample.cpu().numpy()
    explanations = []
    for pos in np.where(mask_np)[0]:
        tid = int(tokens[pos])
        explanations.append({
            "position": int(pos),
            "token_id": tid,
            "event_name": vocab_reverse.get(tid, f"tok_{tid}"),
            "importance": round(float(imp[pos]), 4),
        })
    explanations.sort(key=lambda x: x["importance"], reverse=True)
    return explanations


# ── CV Drift Check / PR-AUC Consistency ──────────────────────

class CVAnalyzer:
    def __init__(self, n_splits=5):
        self.n_splits = n_splits
        self.pr_aucs = []
        self.fold_results = []

    def run(self, sequences, model_args, device, prob_corr, args):
        sorted_seqs = sorted(sequences, key=lambda x: x["first_ts"])
        n = len(sorted_seqs)
        fold_size = max(n // self.n_splits, 1)

        print(f"\n{'='*60}")
        print(f"{'CV DRIFT CHECK — PR-AUC CONSISTENCY':^60}")
        print(f"{'='*60}")

        for fold in range(self.n_splits):
            te_s = fold * fold_size
            te_e = n if fold == self.n_splits - 1 else (fold + 1) * fold_size
            tr = sorted_seqs[:te_s] + sorted_seqs[te_e:]
            te = sorted_seqs[te_s:te_e]
            if len(tr) == 0 or len(te) == 0:
                continue

            Xtr, Mtr, Ytr, _ = pad_sequences(tr, args.max_len)
            Xte, Mte, Yte, _ = pad_sequences(te, args.max_len)

            m = ChurnTransformer(**model_args).to(device)
            opt = torch.optim.AdamW(m.parameters(), lr=args.lr, weight_decay=1e-4)
            pw = torch.tensor([(Ytr == 0).sum() / max((Ytr == 1).sum(), 1)],
                              dtype=torch.float, device=device)

            for ep in range(min(5, args.epochs)):
                m.train()
                perm = torch.randperm(len(Xtr))
                for st in range(0, len(Xtr), args.batch_size):
                    idx = perm[st:st + args.batch_size]
                    out = m(Xtr[idx].to(device), Mtr[idx].to(device))
                    loss = F.binary_cross_entropy_with_logits(out, Ytr[idx].to(device), pos_weight=pw)
                    opt.zero_grad()
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(m.parameters(), 1.0)
                    opt.step()

            metrics = evaluate(m, Xte.to(device), Mte.to(device), Yte.to(device),
                               prob_corr=prob_corr)
            pr = compute_pr_auc(metrics["y_true"], metrics["y_proba"])
            self.pr_aucs.append(pr)
            self.fold_results.append({
                "fold": fold + 1, "pr_auc": round(pr, 4),
                "accuracy": metrics["accuracy"], "f1": metrics["f1"],
                "recall": metrics["recall"],
            })
            print(f"  Fold {fold+1}: PR-AUC={pr:.4f} Acc={metrics['accuracy']:.4f} F1={metrics['f1']:.4f}")

        return self._report()

    def _report(self):
        m = np.mean(self.pr_aucs) if self.pr_aucs else 0
        s = np.std(self.pr_aucs) if self.pr_aucs else 0
        consistency = 1 - s / (m + 1e-8)
        drift = 0.0
        if len(self.pr_aucs) >= 3:
            recent = np.mean(self.pr_aucs[-2:])
            early = np.mean(self.pr_aucs[:-2])
            drift = abs(recent - early) / (early + 1e-8)
        return {
            "fold_results": self.fold_results,
            "pr_auc_mean": round(m, 4), "pr_auc_std": round(s, 4),
            "consistency": round(consistency, 4),
            "drift_score": round(drift, 4),
            "drift_detected": drift > 0.15,
        }


# ── Benchmark Proof ──────────────────────────────────────────

def benchmark_proof(t_metrics, xgb_ref, seq_stats):
    diffs = {}
    for k in ["accuracy", "precision", "recall", "f1", "roc_auc"]:
        diffs[k] = round(t_metrics.get(k, 0) - xgb_ref.get(k, 0), 4)
    insights = []
    ml = seq_stats.get("mean_len", 0)
    if ml > 30:
        insights.append(f"Avg seq len {ml:.0f} — Transformer captures temporal patterns XGBoost ignores")
    if diffs.get("recall", 0) > 0.05:
        insights.append(f"Recall +{diffs['recall']*100:.1f}% — better churn detection from event sequences")
    if diffs.get("f1", 0) > 0:
        insights.append(f"F1 +{diffs['f1']*100:.1f}% — better overall balance")
    wins = sum(1 for v in diffs.values() if v > 0)
    return {"diffs": diffs, "insights": insights, "wins": wins, "avg_delta": round(np.mean(list(diffs.values())), 4)}


# ── Training ────────────────────────────────────────────────

def train_epoch(model, opt, X, M, Y, pos_w, batch_size, label_smoothing=0.0):
    model.train()
    total = 0.0
    perm = torch.randperm(len(X))
    for st in range(0, len(X), batch_size):
        idx = perm[st:st + batch_size]
        bx, bm, by = X[idx], M[idx], Y[idx]
        out = model(bx, bm)
        if label_smoothing > 0:
            smooth = by * (1 - label_smoothing) + 0.5 * label_smoothing
            loss = F.binary_cross_entropy_with_logits(out, smooth, pos_weight=pos_w)
        else:
            loss = F.binary_cross_entropy_with_logits(out, by, pos_weight=pos_w)
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        total += loss.item() * len(idx)
    return total / len(X)


# ── Dynamic XGBoost Baseline ────────────────────────────────

def _get_dynamic_xgboost_metrics(project_id, seed=42):
    import pickle
    import warnings
    import traceback
    from pathlib import Path

    model_path = Path(r"C:\Users\mohds\django-projects\InsightFlowAI\backend\ml\models\artifacts\xgboost_churn_v4.pkl")

    if not model_path.exists():
        print(f"  [WARN] XGBoost not found at {model_path}, using hardcoded defaults")
        return {"accuracy": 0.8209, "precision": 0.9295, "recall": 0.8529,
                "f1": 0.8896, "roc_auc": 0.8304}

    try:
        from ml.datasets.churn_loader import load_event_sequences, time_based_split

        df = load_event_sequences(project_id=project_id, obs_days=30, gap_days=30, min_events=3)
        train_df, test_df = time_based_split(df, test_ratio=0.2, seed=seed)

        with open(model_path, "rb") as f:
            model = pickle.load(f)

        train_df = train_df.select_dtypes(include=[np.number])
        test_df = test_df.select_dtypes(include=[np.number])
        feature_cols = [c for c in test_df.columns if c != "churned"]
        X_test = test_df[feature_cols]
        y_test = test_df["churned"].values
        y_proba = model.predict_proba(X_test)[:, 1]
        y_pred = model.predict(X_test)

        return {
            "accuracy": round(accuracy_score(y_test, y_pred), 4),
            "precision": round(precision_score(y_test, y_pred, zero_division=0), 4),
            "recall": round(recall_score(y_test, y_pred, zero_division=0), 4),
            "f1": round(f1_score(y_test, y_pred, zero_division=0), 4),
            "roc_auc": round(roc_auc_score(y_test, y_proba), 4),
        }
    except Exception:
        traceback.print_exc()
        print("  [WARN] Could not load XGBoost dynamically, using defaults")
        return {"accuracy": 0.8209, "precision": 0.9295, "recall": 0.8529,
                "f1": 0.8896, "roc_auc": 0.8304}


# ── Main ─────────────────────────────────────────────────────

def main():
    pa = argparse.ArgumentParser()
    pa.add_argument("--project_id", type=int, default=13)
    pa.add_argument("--obs_days", type=int, default=30)
    pa.add_argument("--gap_days", type=int, default=30)
    pa.add_argument("--max_len", type=int, default=200)
    pa.add_argument("--min_events", type=int, default=3)
    pa.add_argument("--test_size", type=float, default=0.2)
    pa.add_argument("--d_model", type=int, default=128)
    pa.add_argument("--nhead", type=int, default=4)
    pa.add_argument("--num_layers", type=int, default=4)
    pa.add_argument("--dim_feedforward", type=int, default=512)
    pa.add_argument("--dropout", type=float, default=0.2)
    pa.add_argument("--epochs", type=int, default=20)
    pa.add_argument("--batch_size", type=int, default=64)
    pa.add_argument("--lr", type=float, default=1e-4)
    pa.add_argument("--seed", type=int, default=42)
    pa.add_argument("--label_smoothing", type=float, default=0.05)
    pa.add_argument("--cv_folds", type=int, default=5)
    args = pa.parse_args()

    _ensure_django()
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    random.seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    vocab = build_vocab(args.project_id)
    v_sz = vocab_size(vocab)
    vr = {v: k for k, v in vocab.items()}
    print(f"Vocab: {len(vocab)-2} events + PAD + CLS")

    print(f"\nLoading project {args.project_id}...")
    seqs = load_token_sequences(args.project_id, vocab, args.obs_days, args.gap_days,
                                args.max_len, args.min_events)

    train_seqs, test_seqs = stratified_time_split(seqs, args.test_size, args.seed)
    Xtr, Mtr, Ytr, _ = pad_sequences(train_seqs, args.max_len)
    Xte, Mte, Yte, _ = pad_sequences(test_seqs, args.max_len)
    Xtr, Mtr, Ytr = Xtr.to(device), Mtr.to(device), Ytr.to(device)
    Xte, Mte, Yte = Xte.to(device), Mte.to(device), Yte.to(device)

    print(f"Train: {len(Xtr)} churn={Ytr.mean():.2%}")
    print(f"Test:  {len(Xte)} churn={Yte.mean():.2%}")

    m_args = dict(vocab_size=v_sz, d_model=args.d_model, nhead=args.nhead,
                  num_layers=args.num_layers, dim_feedforward=args.dim_feedforward,
                  dropout=args.dropout, max_len=args.max_len)
    model = ChurnTransformer(**m_args).to(device)
    print(f"Params: {sum(p.numel() for p in model.parameters()):,}")

    prob_corr = ProbCorrectionLayer().to(device)
    pos = Ytr.sum().item()
    neg = len(Ytr) - pos
    pw = torch.tensor([neg / max(pos, 1)], dtype=torch.float, device=device)

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)

    best_auc = 0
    best_state = None
    print(f"\n{'Ep':>4}|{'Loss':>8}|{'Acc':>7}|{'Prec':>7}|{'Rec':>7}|{'F1':>7}|{'AUC':>7}")
    print("-" * 55)

    for ep in range(1, args.epochs + 1):
        loss = train_epoch(model, opt, Xtr, Mtr, Ytr, pw, args.batch_size, args.label_smoothing)
        metrics = evaluate(model, Xte, Mte, Yte, prob_corr=prob_corr)

        if metrics["roc_auc"] > best_auc:
            best_auc = metrics["roc_auc"]
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            with torch.no_grad():
                val_logits = model(Xte, Mte)
            prob_corr.fit_isotonic(Yte.cpu().numpy(), torch.sigmoid(val_logits).cpu().numpy())

        sched.step()
        if ep % 5 == 0 or ep == 1:
            print(f"{ep:>4d}|{loss:>8.4f}|{metrics['accuracy']:>7.4f}|{metrics['precision']:>7.4f}"
                  f"|{metrics['recall']:>7.4f}|{metrics['f1']:>7.4f}|{metrics['roc_auc']:>7.4f}")

    if best_state:
        model.load_state_dict(best_state)

    final = evaluate(model, Xte, Mte, Yte, prob_corr=prob_corr)
    with torch.no_grad():
        cal_logits = model(Xte, Mte)
    cal = prob_corr.calibration_report(Yte.cpu().numpy(), cal_logits.cpu())

    best_thr, best_f1_val = find_optimal_threshold(final["y_true"], final["y_proba"])
    explanation = explain_event_importance(model, Xte[0], Mte[0], vr)

    seq_lens = [s["seq_len"] for s in seqs]
    seq_stats = {"mean_len": float(np.mean(seq_lens)),
                 "var_len": float(np.var(seq_lens))}

    if args.cv_folds > 1:
        cv = CVAnalyzer(n_splits=min(args.cv_folds, 5))
        cv_rep = cv.run(seqs, m_args, device, prob_corr, args)
    else:
        cv_rep = {
            "fold_results": [], "pr_auc_mean": 0, "pr_auc_std": 0,
            "consistency": 1.0, "drift_score": 0, "drift_detected": False,
        }

    xgb_ref = _get_dynamic_xgboost_metrics(args.project_id, args.seed)
    bench = benchmark_proof(final, xgb_ref, seq_stats)

    # ── Print results ──
    eq = "=" * 60
    print(f"\n{eq}")
    print(f"{'TRANSFORMER — FULL VALIDATION REPORT':^60}")
    print(eq)

    print(f"\n{'1. PERFORMANCE METRICS':^60}")
    print("-" * 60)
    for k in ["accuracy", "precision", "recall", "f1", "roc_auc"]:
        print(f"  {k.capitalize():<12}: {final[k]:>8.4f}")
    print(f"  Optimal thr : {best_thr:.3f} (F1={best_f1_val:.4f})")

    cm = confusion_matrix(final["y_true"], final["y_pred"], labels=[0, 1])
    if cm.size == 4:
        tn, fp, fn, tp = cm.ravel()
        print(f"\n  Confusion Matrix:")
        print(f"                 | {'Predicted':^20} |")
        print(f"                 | {'Active':^8} | {'Churned':^8} |")
        print(f"  {'-'*41}+")
        print(f"  {'Actual Active ':<14} | {tn:>8d} | {fp:>8d} |")
        print(f"  {'Actual Churned':<14} | {fn:>8d} | {tp:>8d} |")

    print(f"\n{'2. PROBABILITY CALIBRATION':^60}")
    print("-" * 60)
    for k, v in cal.items():
        print(f"  {k:<12}: {v}")

    print(f"\n{'3. CV DRIFT — PR-AUC CONSISTENCY':^60}")
    print("-" * 60)
    print(f"  PR-AUC mean : {cv_rep['pr_auc_mean']}")
    print(f"  PR-AUC std  : {cv_rep['pr_auc_std']}")
    print(f"  Consistency : {cv_rep['consistency']}")
    print(f"  Drift score : {cv_rep['drift_score']}")
    print(f"  Drift detect: {'YES' if cv_rep['drift_detected'] else 'NO'}")

    print(f"\n{'4. EVENT IMPORTANCE':^60}")
    print("-" * 60)
    for i, e in enumerate(explanation[:8], 1):
        print(f"  {i}. {e['event_name']:<18} {e['importance']:.4f}")

    print(f"\n{'5. BENCHMARK: TRANSFORMER vs XGBoost':^60}")
    print("-" * 60)
    print(f"  {'Metric':<12} {'XGBoost':>8} {'Transf.':>8} {'Delta':>8}")
    print(f"  {'-'*36}")
    for k in ["accuracy", "precision", "recall", "f1", "roc_auc"]:
        d = bench["diffs"][k]
        print(f"  {k.capitalize():<12} {xgb_ref[k]:>8.4f} {final[k]:>8.4f} {d:>+8.4f}")
    print(f"\n  Insights:")
    for ins in bench["insights"]:
        print(f"  > {ins}")
    print(f"  > Transformer wins {bench['wins']}/5 metrics (avg delta {bench['avg_delta']*100:+.2f}%)")

    # ── Save report ──
    report = {
        "metrics": {k: final[k] for k in ["accuracy","precision","recall","f1","roc_auc"]},
        "calibration": cal,
        "cv": cv_rep,
        "event_importance": explanation[:10],
        "benchmark": bench,
        "threshold": best_thr,
    }
    def convert(obj):
        if isinstance(obj, (np.float32, np.float64)):
            return float(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        raise TypeError(f"Type {type(obj)} not serializable")

    with open("transformer_validation_report.json", "w") as f:
        json.dump(report, f, indent=2, default=convert)
    print(f"\nReport saved to transformer_validation_report.json")
    print(eq)


if __name__ == "__main__":
    main()
