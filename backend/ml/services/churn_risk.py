"""
Churn Risk Service — Loads the trained transformer and generates
per-user churn predictions, explanations, and recommendations.
"""

import os
import math
import json
import logging
from datetime import datetime, timedelta
from collections import Counter, defaultdict

import torch
import numpy as np
import pandas as pd

from django.conf import settings

from ..models.transformers.churn_transformer_enhanced import (
    ChurnTransformerEnhanced,
    ProbCorrectionLayer,
    explain_event_importance,
    explain_event_importance_shap,
)

BOT_UA_SUBSTRINGS = ["bot", "crawl", "spider", "scrape", "curl", "wget", "python-requests", "go-http"]
SESSION_GAP_THRESHOLD = 1800

SHAP_CACHE_PATH = os.path.join(
    settings.BASE_DIR, 'ml', 'models', 'artifacts', 'shap_cache.json'
)

logger = logging.getLogger(__name__)


class ChurnRiskService:
    """Singleton service that loads the transformer model once and serves predictions."""

    _instance = None
    _model = None
    _checkpoint = None
    _prob_corr = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _reset_cache(self):
        self._cache_df = None
        self._cache_seqs = None
        self._cache_tensors = None
        self._cache_mask = None
        self._cache_predictions = None
        self._shap_cache = {}

    def _load_shap_cache(self):
        if os.path.exists(SHAP_CACHE_PATH):
            try:
                with open(SHAP_CACHE_PATH) as f:
                    data = json.load(f)
                self._shap_cache = data.get("explanations", {})
                return
            except Exception as e:
                logger.warning("SHAP cache load failed: %s", e)
        self._shap_cache = {}

    def _save_shap_cache(self):
        try:
            with open(SHAP_CACHE_PATH, 'w') as f:
                json.dump({"version": 1, "explanations": self._shap_cache}, f, indent=2, default=str)
        except Exception as e:
            logger.warning("SHAP cache write failed: %s", e)

    def load(self, checkpoint_path=None):
        if self._model is not None:
            return True
        if not checkpoint_path:
            checkpoint_path = os.path.join(
                settings.BASE_DIR, 'ml', 'models', 'artifacts', 'churn_transformer_v1.pt'
            )
        if not os.path.exists(checkpoint_path):
            print(f"Checkpoint not found at {checkpoint_path}")
            return False
        checkpoint = torch.load(checkpoint_path, map_location='cpu', weights_only=False)
        self._checkpoint = checkpoint
        config = checkpoint['model_config']
        config['prior'] = config.get('prior', 0.5)
        model = ChurnTransformerEnhanced(**config)
        model.load_state_dict(checkpoint['model_state_dict'])
        model.eval()
        self._model = model
        self._prob_corr = ProbCorrectionLayer()
        self._cache_df = None
        self._cache_seqs = None
        self._cache_tensors = None
        self._cache_mask = None
        self._cache_predictions = None
        self._shap_cache = {}
        self._load_shap_cache()
        return True

    @property
    def loaded(self):
        return self._model is not None

    @property
    def vocab(self):
        return self._checkpoint['vocab'] if self._checkpoint else None

    @property
    def meta(self):
        return self._checkpoint['meta'] if self._checkpoint else None

    @property
    def event_vocab_reverse(self):
        return self._checkpoint.get('event_vocab_reverse', {}) if self._checkpoint else {}

    def _extract_page_type(self, url):
        if not url:
            return "other"
        url = url.strip("/").split("?")[0].split("/")[0]
        return url or "home"

    def _extract_country(self, lang):
        if not lang:
            return "UNKNOWN"
        if "-" in lang:
            return lang.split("-")[1]
        return lang.upper()

    def _fetch_events(self, project_id):
        from events.clickhouse import ch
        try:
            client = ch.get_client()
            if client:
                rows = client.query("""
                    SELECT user_id, event_name, timestamp,
                           JSONExtractString(properties, '$session_id') AS session_id,
                           JSONExtractString(properties, 'device') AS device,
                           JSONExtractString(properties, 'browser') AS browser,
                           JSONExtractString(properties, 'url') AS url,
                           JSONExtractString(properties, '$language') AS language
                    FROM insightflow.events
                    WHERE project_id = %(pid)s
                    ORDER BY user_id, timestamp
                """, parameters={"pid": project_id})
                if rows and rows.result_rows:
                    df = pd.DataFrame(rows.result_rows, columns=[
                        "user_id", "event_name", "timestamp", "session_id",
                        "device", "browser", "url", "language",
                    ])
                    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.tz_localize(None)
                    return df
        except Exception:
            pass
        from events.models import Event
        qs = Event.objects.filter(project_id=project_id).order_by("user_id", "timestamp")
        records = []
        for r in qs:
            ts = r.timestamp
            if hasattr(ts, "tzinfo") and ts.tzinfo is not None:
                ts = ts.replace(tzinfo=None)
            props = r.properties or {}
            records.append({
                "user_id": r.user_id,
                "event_name": r.event_name,
                "timestamp": ts,
                "session_id": props.get("$session_id", ""),
                "device": props.get("device", ""),
                "browser": props.get("browser", ""),
                "url": props.get("url", ""),
                "language": props.get("$language", ""),
            })
        return pd.DataFrame(records)

    def _build_sequences(self, df, project_id, max_len=100):
        """Build sequences using the saved vocab from the checkpoint."""
        if not self.loaded:
            return None
        vocab = self.vocab
        meta = self.meta
        ev_vocab = vocab["event"]
        dev_vocab = vocab["device"]
        br_vocab = vocab["browser"]
        co_vocab = vocab["country"]
        pg_vocab = vocab["page_type"]
        sess_start_id = meta["sess_start_id"]
        sess_end_id = meta["sess_end_id"]

        sequences = []
        for uid, grp in df.groupby("user_id"):
            grp = grp.sort_values("timestamp").reset_index(drop=True)
            features = []
            prev_ts = None
            prev_sid = None

            for _, row in grp.iterrows():
                et = row["event_name"]
                ts = row["timestamp"]
                sid = row.get("session_id", "")

                time_delta = 0
                if prev_ts is not None:
                    time_delta = (ts - prev_ts).total_seconds()
                time_delta = max(0, time_delta)

                is_new_session = False
                if prev_sid is not None and sid != prev_sid:
                    is_new_session = True
                elif prev_sid is None and sid:
                    is_new_session = True
                elif prev_ts is not None and time_delta > SESSION_GAP_THRESHOLD:
                    is_new_session = True

                if is_new_session:
                    features.append({
                        "event": sess_end_id,
                        "hour": 0,
                        "weekday": 0,
                        "device": 0,
                        "browser": 0,
                        "country": 0,
                        "page_type": 0,
                        "time_gap_seconds": time_delta,
                    })
                    features.append({
                        "event": sess_start_id,
                        "hour": 0,
                        "weekday": 0,
                        "device": 0,
                        "browser": 0,
                        "country": 0,
                        "page_type": 0,
                        "time_gap_seconds": 0,
                    })
                    time_delta = 0

                features.append({
                    "event": ev_vocab.get(et, 0),
                    "hour": ts.hour,
                    "weekday": ts.weekday(),
                    "device": dev_vocab.get(row.get("device", ""), 0),
                    "browser": br_vocab.get(row.get("browser", ""), 0),
                    "country": co_vocab.get(self._extract_country(row.get("language", "")), 0),
                    "page_type": pg_vocab.get(self._extract_page_type(row.get("url", "")), 0),
                    "time_gap_seconds": time_delta,
                })
                prev_ts = ts
                prev_sid = sid

            if features:
                features.insert(0, {
                    "event": sess_start_id,
                    "hour": 0, "weekday": 0, "device": 0,
                    "browser": 0, "country": 0, "page_type": 0,
                    "time_gap_seconds": 0,
                })
                features.append({
                    "event": sess_end_id,
                    "hour": 0, "weekday": 0, "device": 0,
                    "browser": 0, "country": 0, "page_type": 0,
                    "time_gap_seconds": 0,
                })

            sequences.append({
                "uid": str(uid),
                "features": features[:max_len],
                "first_ts": grp["timestamp"].min(),
                "last_ts": grp["timestamp"].max(),
                "total_events": len(grp),
            })
        return sequences

    def _pad_sequences(self, sequences, max_len=100):
        """Pad sequences to tensors matching model input format."""
        N = len(sequences)
        feature_names = ["event", "hour", "weekday",
                         "device", "browser", "country", "page_type"]
        tensors = {f: torch.zeros(N, max_len, dtype=torch.long) for f in feature_names}
        time_gap = torch.zeros(N, max_len, dtype=torch.float)
        mask = torch.zeros(N, max_len, dtype=torch.bool)
        uids = []
        first_ts_list = []

        for i, s in enumerate(sequences):
            feats = s["features"][:max_len]
            sl = len(feats)
            for f in feature_names:
                vals = [e[f] for e in feats]
                tensors[f][i, :sl] = torch.tensor(vals, dtype=torch.long)
            gap_vals = [e["time_gap_seconds"] for e in feats]
            time_gap[i, :sl] = torch.tensor(gap_vals, dtype=torch.float)
            mask[i, :sl] = True
            uids.append(s["uid"])
            first_ts_list.append(s["first_ts"])

        tensors["time_gap_seconds"] = time_gap
        return tensors, mask, uids, first_ts_list

    def predict_all(self, project_id, max_len=100):
        """Generate churn predictions for all users in a project.

        Returns list of predictions. Also caches sequences/df internally
        for reuse by explain_user and get_recommendations.
        """
        if not self.load():
            return None

        self._cache_df = self._fetch_events(project_id)
        if self._cache_df is None or len(self._cache_df) == 0:
            return None

        total_events = len(self._cache_df)
        print(f"  Events: {total_events}, Users: {self._cache_df['user_id'].nunique()}")

        self._cache_seqs = self._build_sequences(self._cache_df, project_id, max_len)
        if not self._cache_seqs:
            return None

        tensors, mask, uids, first_ts_list = self._pad_sequences(self._cache_seqs, max_len)
        self._cache_tensors = tensors
        self._cache_mask = mask

        with torch.no_grad():
            logits = self._model(tensors, mask)
            probs = torch.sigmoid(logits).cpu().numpy()

        results = []
        for i, uid in enumerate(uids):
            p = float(probs[i])
            if p >= 0.7:
                risk = "high"
            elif p >= 0.3:
                risk = "medium"
            else:
                risk = "low"
            results.append({
                "user_id": uid,
                "probability": round(p, 4),
                "risk_level": risk,
                "total_events": self._cache_seqs[i]["total_events"],
                "first_ts": first_ts_list[i].isoformat() if hasattr(first_ts_list[i], 'isoformat') else str(first_ts_list[i]),
            })

        # Sort by probability descending
        results.sort(key=lambda x: x["probability"], reverse=True)
        self._cache_predictions = results
        self._shap_cache = {}
        # Remove stale disk cache so precomputed results are fresh
        if os.path.exists(SHAP_CACHE_PATH):
            try:
                os.remove(SHAP_CACHE_PATH)
            except Exception:
                pass
        return results

    def precompute_shap(self, project_id, max_users=100, batch_size=5):
        """Precompute SHAP explanations for the highest-risk users.

        Runs in a throttled loop so it doesn't block too long. Each batch is
        computed synchronously; call this after predict_all() in a background
        thread or lightweight async context.

        Returns the number of explanations computed.
        """
        predictions = self._cache_predictions
        if not predictions or not self._cache_seqs:
            return 0

        # Focus on highest-risk users that don't have cached SHAP yet
        candidates = [p for p in predictions if p["risk_level"] == "high"
                      and str(p["user_id"]) not in self._shap_cache]
        candidates = candidates[:max_users]

        if not candidates:
            return 0

        import time
        vr = self.event_vocab_reverse
        device = next(self._model.parameters()).device
        count = 0

        for i, p in enumerate(candidates):
            uid = str(p["user_id"])
            try:
                explanation = self.explain_user(uid, project_id)
                if explanation and explanation.get("explanations"):
                    count += 1
            except Exception:
                logger.warning("SHAP precompute failed for %s", uid, exc_info=True)

            # Save to disk every batch_size users so partial results persist
            if (i + 1) % batch_size == 0:
                self._save_shap_cache()

        if count:
            self._save_shap_cache()

        logger.info("Precomputed SHAP for %d / %d high-risk users", count, len(candidates))
        return count

    def explain_user(self, user_id, project_id, max_len=100):
        """Generate explanation for a single user's churn prediction.

        Uses cached sequences from last predict_all() if available,
        otherwise computes from scratch.
        """
        if not self.load():
            return None

        # Try using cached sequences first
        user_seq = None
        seqs = getattr(self, '_cache_seqs', None)
        if seqs:
            for s in seqs:
                if s["uid"] == str(user_id):
                    user_seq = s
                    break

        if user_seq is None:
            # Fall back to building sequences for this user only
            df = self._fetch_events(project_id)
            if df is None or len(df) == 0:
                return None
            user_df = df[df["user_id"].astype(str) == str(user_id)]
            if len(user_df) == 0:
                return None
            sequences = self._build_sequences(pd.concat([user_df, df[df["user_id"] != str(user_id)]]), project_id, max_len)
            for s in sequences:
                if s["uid"] == str(user_id):
                    user_seq = s
                    break
            if user_seq is None:
                return None

        tensors, mask, _, _ = self._pad_sequences([user_seq], max_len)

        with torch.no_grad():
            logits = self._model(tensors, mask)
            prob = float(torch.sigmoid(logits[0]).item())

        vr = self.event_vocab_reverse

        # Check SHAP cache (in-memory first, then disk)
        shap_cache = getattr(self, '_shap_cache', None)
        if shap_cache is None:
            self._load_shap_cache()
            shap_cache = self._shap_cache

        uid_str = str(user_id)
        if uid_str in shap_cache:
            raw_explanations = shap_cache[uid_str]
        else:
            # Use SHAP for explanation, fall back to L2-norm heuristic
            try:
                device = next(self._model.parameters()).device
                raw_explanations = explain_event_importance_shap(
                    self._model, tensors, mask[0], vr,
                    background_seqs=getattr(self, '_cache_seqs', None),
                    n_background=30, n_samples=512, device=device,
                )
                # Cache raw results (before normalization)
                shap_cache[uid_str] = raw_explanations
                self._save_shap_cache()
            except Exception:
                logger.warning("SHAP explanation failed, falling back to L2-norm", exc_info=True)
                raw_explanations = explain_event_importance(self._model, tensors, mask[0], vr)

        # Take top explanations by importance (abs SHAP value)
        top_explanations = raw_explanations[:10]
        total_abs = sum(e.get("importance", abs(e.get("shap_value", 0))) for e in top_explanations) or 1.0
        for e in top_explanations:
            raw_imp = e.get("shap_value", e.get("importance", 0))
            e["importance"] = round(abs(raw_imp) / total_abs * 100, 1)
            if "shap_value" in e:
                e["shap_value"] = round(float(e["shap_value"]), 4)

        # Prediction confidence based on certainty
        certainty = max(prob, 1 - prob)
        if certainty >= 0.85:
            confidence = "high"
        elif certainty >= 0.65:
            confidence = "medium"
        else:
            confidence = "low"

        # Cohort size from cached sequences
        cohort_size = len(self._cache_seqs) if getattr(self, '_cache_seqs', None) else 0

        # Days since last active
        last_active_days = None
        last_ts = user_seq.get("last_ts")
        if last_ts is not None:
            now = datetime.now()
            if hasattr(last_ts, 'tzinfo') and last_ts.tzinfo is not None:
                last_ts = last_ts.replace(tzinfo=None)
            last_active_days = (now - last_ts).days

        # Get event name distribution
        event_names = []
        for f in user_seq["features"]:
            event_names.append(vr.get(f["event"], f"tok_{f['event']}"))
        event_counts = Counter(event_names)
        top_events = event_counts.most_common(10)

        return {
            "user_id": user_id,
            "probability": round(prob, 4),
            "risk_level": "high" if prob >= 0.7 else ("medium" if prob >= 0.3 else "low"),
            "confidence": confidence,
            "cohort_size": cohort_size,
            "last_active_days": last_active_days,
            "total_events": user_seq["total_events"],
            "unique_events": len(event_counts),
            "top_events": [{"event": e, "count": c} for e, c in top_events],
            "explanations": top_explanations,
        }

    def get_overview(self, predictions):
        """Summarize predictions into overview stats."""
        if not predictions:
            return None
        total = len(predictions)
        high = sum(1 for p in predictions if p["risk_level"] == "high")
        medium = sum(1 for p in predictions if p["risk_level"] == "medium")
        low = sum(1 for p in predictions if p["risk_level"] == "low")
        avg_prob = sum(p["probability"] for p in predictions) / total
        return {
            "total_users": total,
            "high_risk": high,
            "medium_risk": medium,
            "low_risk": low,
            "avg_risk_probability": round(avg_prob, 4),
            "high_risk_pct": round(high / total * 100, 1) if total else 0,
        }

    def get_churn_timeline(self, predictions):
        """Build churn timeline by risk level for visualization."""
        if not predictions:
            return None
        # Simulate timeline based on current predictions
        high = sum(1 for p in predictions if p["risk_level"] == "high")
        medium = sum(1 for p in predictions if p["risk_level"] == "medium")
        low = sum(1 for p in predictions if p["risk_level"] == "low")
        churned_30d = high  # predicted to churn within 30 days
        churned_60d = high + int(medium * 0.3)
        churned_90d = high + int(medium * 0.6) + int(low * 0.1)
        return {
            "next_30_days": churned_30d,
            "next_60_days": churned_60d,
            "next_90_days": churned_90d,
            "timeline": [
                {"period": "Next 30 Days", "churned": churned_30d, "active": len(predictions) - churned_30d},
                {"period": "Next 60 Days", "churned": churned_60d, "active": len(predictions) - churned_60d},
                {"period": "Next 90 Days", "churned": churned_90d, "active": len(predictions) - churned_90d},
            ],
        }

    def get_recommendations(self, predictions, project_id=None):
        """Generate AI recommendations based on high-risk user patterns.

        Uses cached sequences from last predict_all() call — does NOT
        re-run explain_user for every user.
        """
        if not predictions:
            return []

        high_risk = [p for p in predictions if p["risk_level"] == "high"]
        if not high_risk:
            return {"recommendations": [{"type": "info", "title": "All Clear", "event": "", "message": "No high-risk users detected. Keep up the good work!", "action": ""}], "top_churn_events": []}

        # Analyze event patterns from cached sequences
        event_counter = Counter()
        seqs = getattr(self, '_cache_seqs', [])
        for s in seqs:
            uid = s["uid"]
            if any(p["user_id"] == uid and p["risk_level"] == "high" for p in high_risk):
                vr = self.event_vocab_reverse
                for f in s["features"]:
                    name = vr.get(f["event"], f"tok_{f['event']}")
                    if name not in ("<SESS_START>", "<SESS_END>", "<PAD>", "<MASK>"):
                        event_counter[name] += 1

        important_counter = event_counter
        top_events = [{"event": e, "count": c} for e, c in important_counter.most_common(8)]

        recs = []
        top_names = {e for e, _ in important_counter.most_common(5)}

        if "exit" in top_names:
            recs.append({
                "type": "critical",
                "title": "High Exit Rate Detected",
                "event": "exit",
                "message": "Users who churn frequently trigger exit events. Consider implementing exit-intent popups with personalized offers or feedback forms to capture user intent before they leave.",
                "action": "Add exit-intent surveys and retention offers on key pages.",
            })
        if "purchase" in top_names:
            recs.append({
                "type": "opportunity",
                "title": "Purchase Event Analysis",
                "event": "purchase",
                "message": "Purchase events contribute significantly to churn predictions. Analyze the user journey after purchase — users who stop engaging after buying may need re-engagement campaigns or post-purchase support.",
                "action": "Implement post-purchase email sequences and loyalty programs.",
            })
        if "search" in top_names:
            recs.append({
                "type": "suggestion",
                "title": "Unsuccessful Search Patterns",
                "event": "search",
                "message": "High search activity coupled with churn suggests users may not find what they're looking for. Review search relevance, add filters, and consider personalized recommendations.",
                "action": "Improve search relevance, add auto-suggest, and track zero-result searches.",
            })
        if "add_to_cart" in top_names:
            recs.append({
                "type": "critical",
                "title": "Cart Abandonment Risk",
                "event": "add_to_cart",
                "message": "Users who add items to cart but later churn indicate cart abandonment issues. Simplify checkout, offer guest checkout, and send cart recovery reminders.",
                "action": "Add cart abandonment emails and streamline checkout flow.",
            })
        if "view_product" in top_names:
            recs.append({
                "type": "suggestion",
                "title": "Product Page Engagement",
                "event": "view_product",
                "message": "Product page views without conversion suggest pricing, content, or UX issues. Consider A/B testing product page layouts, adding social proof, and simplifying the path to purchase.",
                "action": "A/B test product page layouts and add customer reviews.",
            })

        high_pct = len(high_risk) / len(predictions) * 100 if predictions else 0
        if high_pct > 30:
            recs.append({
                "type": "warning",
                "title": "Elevated Churn Risk",
                "event": "",
                "message": f"{high_pct:.0f}% of users are at high churn risk. Consider a comprehensive retention strategy including onboarding optimization, personalized notifications, and proactive customer support.",
                "action": "Launch a retention campaign targeting the top 20% highest-risk users.",
            })

        return {
            "recommendations": recs,
            "top_churn_events": top_events,
        }


# Singleton instance
churn_risk = ChurnRiskService()
