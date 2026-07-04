"""
XGBoost churn classifier — baseline on large noisy dataset.

Label: observation=first 60d, gap=next 30d, zero events in gap => churned=1.
Split: time-based (train on older users, test on newer) to avoid leakage.
Noise features: is_bot, has_returned, night_ratio, weekend_ratio, etc.

Usage:
    python -m ml.training.train_xgboost_churn --project_id 13
"""

import argparse
import logging
import os

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, classification_report, confusion_matrix,
)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

logger = logging.getLogger(__name__)


def _ensure_django():
    import django.conf
    if not django.conf.settings.configured:
        import django; django.setup()


def load_data(project_id: int, obs_days: int = 60, gap_days: int = 30, min_events: int = 3):
    from ml.datasets.churn_loader import load_event_sequences
    return load_event_sequences(project_id=project_id, obs_days=obs_days, gap_days=gap_days, min_events=min_events)


def train_xgboost(X_train, y_train, X_test, y_test, seed=42):
    import xgboost as xgb

    neg = (y_train == 0).sum()
    pos = (y_train == 1).sum()
    scale_pos_weight = neg / pos if pos > 0 else 1.0

    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,
        eval_metric="logloss",
        use_label_encoder=False,
        random_state=seed,
        verbosity=0,
    )

    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    metrics = {
        "accuracy": round(accuracy_score(y_test, y_pred), 4),
        "precision": round(precision_score(y_test, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_test, y_pred, zero_division=0), 4),
        "f1": round(f1_score(y_test, y_pred, zero_division=0), 4),
        "roc_auc": round(roc_auc_score(y_test, y_proba), 4),
        "churn_rate_test": float(y_test.mean()),
        "churn_rate_train": float(y_train.mean()),
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "scale_pos_weight": round(scale_pos_weight, 2),
    }

    importance = pd.DataFrame({
        "feature": X_train.columns,
        "importance": model.feature_importances_,
    }).sort_values("importance", ascending=False)

    return model, metrics, importance, y_pred, y_proba


def print_results(metrics, importance, y_test, y_pred, y_proba, train_df, test_df):
    dash = "-" * 60
    eq = "=" * 60

    print(f"\n{eq}")
    print(f"{'XGBoost Churn Classifier -- Baseline Results':^60}")
    print(eq)

    print(f"\n{dash}")
    print(f"{'Dataset Distribution':^60}")
    print(dash)
    print(f"  Train samples : {metrics['train_samples']:>8d}")
    print(f"  Test samples  : {metrics['test_samples']:>8d}")
    print(f"  Churn rate (train): {metrics['churn_rate_train']:>7.2%}")
    print(f"  Churn rate (test) : {metrics['churn_rate_test']:>7.2%}")
    print(f"  Scale pos weight  : {metrics['scale_pos_weight']:>8.2f}")

    # Distribution comparison
    feat_cols = [c for c in train_df.columns if c not in ("user_id", "first_ts", "last_ts", "churned")]
    print(f"\n  {'Feature':<28} {'Train Mean':>10} {'Test Mean':>10} {'Diff':>10}")
    print(f"  {'-' * 58}")
    for col in feat_cols[:10]:
        t_mean = train_df[col].mean()
        te_mean = test_df[col].mean()
        diff = t_mean - te_mean
        print(f"  {col:<28} {t_mean:>10.4f} {te_mean:>10.4f} {diff:>10.4f}")

    print(f"\n{dash}")
    print(f"{'Performance Metrics':^60}")
    print(dash)
    print(f"  Accuracy  : {metrics['accuracy']:>8.4f}")
    print(f"  Precision : {metrics['precision']:>8.4f}")
    print(f"  Recall    : {metrics['recall']:>8.4f}")
    print(f"  F1 Score  : {metrics['f1']:>8.4f}")
    print(f"  ROC-AUC   : {metrics['roc_auc']:>8.4f}")

    print(f"\n{dash}")
    print(f"{'Classification Report':^60}")
    print(dash)
    labels = sorted(y_test.unique())
    target_names = ["active", "churned"] if len(labels) == 2 else [str(l) for l in labels]
    print(classification_report(y_test, y_pred, labels=labels, target_names=target_names, digits=4))

    print(f"\n{dash}")
    print(f"{'Confusion Matrix':^60}")
    print(dash)
    cm = confusion_matrix(y_test, y_pred, labels=[0, 1])
    if cm.size == 4:
        tn, fp, fn, tp = cm.ravel()
        print(f"                 | {'Predicted':^20} |")
        print(f"                 | {'Active':^8} | {'Churned':^8} |")
        print(f"{'-' * 47}+")
        print(f"{'Actual Active ':<16} | {tn:>8d} | {fp:>8d} |")
        print(f"{'Actual Churned' :<16} | {fn:>8d} | {tp:>8d} |")
        print(f"{'-' * 47}")
    else:
        print(cm)

    print(f"\n{dash}")
    print(f"{'Top 10 Feature Importances':^60}")
    print(dash)
    print(f"  {'Feature':<30} {'Importance':>10}")
    print(f"  {'-' * 40}")
    for _, row in importance.head(10).iterrows():
        print(f"  {row['feature']:<30} {row['importance']:>10.4f}")

    print(f"\n{eq}\n")


def main():
    parser = argparse.ArgumentParser(description="Train XGBoost churn classifier on noisy data")
    parser.add_argument("--project_id", type=int, default=13)
    parser.add_argument("--obs_days", type=int, default=60)
    parser.add_argument("--gap_days", type=int, default=30)
    parser.add_argument("--min_events", type=int, default=3)
    parser.add_argument("--test_size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    _ensure_django()
    from ml.datasets.churn_loader import time_based_split

    print(f"\nLoading data for project {args.project_id} ...")
    df = load_data(args.project_id, args.obs_days, args.gap_days, args.min_events)
    print(f"  Loaded {len(df)} users")
    print(f"  Churn rate: {df['churned'].mean():.2%}")

    # Time-based split
    train_df, test_df = time_based_split(df, test_ratio=args.test_size, seed=args.seed)

    feature_cols = [c for c in df.columns if c not in ("user_id", "first_ts", "last_ts", "churned")]
    X_train = train_df[feature_cols]
    y_train = train_df["churned"]
    X_test = test_df[feature_cols]
    y_test = test_df["churned"]

    print(f"\n  Train period: {train_df['first_ts'].min().date()} to {train_df['last_ts'].max().date()}")
    print(f"  Test period : {test_df['first_ts'].min().date()} to {test_df['last_ts'].max().date()}")
    print(f"  Train: {len(X_train)} samples ({y_train.mean():.2%} churned)")
    print(f"  Test:  {len(X_test)} samples ({y_test.mean():.2%} churned)")
    print(f"  Features: {len(feature_cols)}")
    print()

    model, metrics, importance, y_pred, y_proba = train_xgboost(
        X_train, y_train, X_test, y_test, seed=args.seed,
    )

    print_results(metrics, importance, y_test, y_pred, y_proba, train_df, test_df)

    from ml.models.registry import get_registry
    registry = get_registry()
    version = registry.save(model, "xgboost_churn", metrics=metrics)
    print(f"Model saved to registry: {version}\n")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
