import logging
from datetime import datetime
from typing import Optional

import pandas as pd
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix,
)

from ..config import settings
from ..datasets.loader import load_events, train_test_split
from ..preprocessing.features import build_user_features
from ..models.registry import get_registry

logger = logging.getLogger(__name__)


def train_churn_model(
    project_id: int,
    model_pipeline,
    days: Optional[int] = None,
    label_days: int = 30,
) -> dict:
    """End-to-end churn model training."""
    days = days or settings.lookback_days

    logger.info("Loading events for project %s (last %d days)", project_id, days)
    events = load_events(project_id, days=days)
    if events.empty:
        raise ValueError("No events found")

    features = build_user_features(events)
    if features.empty:
        raise ValueError("No user features generated")

    # Label: user is churned if no events in last `label_days`
    cutoff = events["timestamp"].max() - pd.Timedelta(days=label_days)
    active_users = set(
        events[events["timestamp"] >= cutoff]["user_id"].unique()
    )
    features["churned"] = (~features["user_id"].isin(active_users)).astype(int)

    train_df, test_df = train_test_split(features, user_col="user_id")

    X_train = train_df.drop(columns=["user_id", "churned"])
    y_train = train_df["churned"]
    X_test = test_df.drop(columns=["user_id", "churned"])
    y_test = test_df["churned"]

    logger.info("Training on %d samples, testing on %d", len(X_train), len(X_test))
    model_pipeline.fit(X_train, y_train)

    y_pred = model_pipeline.predict(X_test)
    y_proba = model_pipeline.predict_proba(X_test)[:, 1]

    metrics = {
        "accuracy": round(accuracy_score(y_test, y_pred), 4),
        "precision": round(precision_score(y_test, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_test, y_pred, zero_division=0), 4),
        "f1": round(f1_score(y_test, y_pred, zero_division=0), 4),
        "roc_auc": round(roc_auc_score(y_test, y_proba), 4),
        "churn_rate": float(y_test.mean()),
        "train_samples": len(X_train),
        "test_samples": len(X_test),
    }
    logger.info("Metrics: %s", metrics)

    registry = get_registry()
    version = registry.save(model_pipeline, "churn_classifier", metrics=metrics)
    metrics["model_version"] = version

    return metrics


def train_funnel_model(
    project_id: int,
    model_pipeline,
    days: Optional[int] = None,
) -> dict:
    days = days or settings.lookback_days
    events = load_events(project_id, days=days)
    if events.empty:
        raise ValueError("No events found")

    from ..preprocessing.features import build_event_features
    events = build_event_features(events)

    events["converted"] = (
        events["event_name"].str.contains("purchase|buy|order|success", case=False)
    ).astype(int)

    train_df, test_df = train_test_split(events, user_col="user_id")
    feature_cols = [
        "hour", "day_of_week", "is_weekend", "is_business_hours",
    ]

    X_train = train_df[feature_cols]
    y_train = train_df["converted"]
    X_test = test_df[feature_cols]
    y_test = test_df["converted"]

    model_pipeline.fit(X_train, y_train)
    y_pred = model_pipeline.predict(X_test)
    y_proba = model_pipeline.predict_proba(X_test)[:, 1]

    metrics = {
        "accuracy": round(accuracy_score(y_test, y_pred), 4),
        "precision": round(precision_score(y_test, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_test, y_pred, zero_division=0), 4),
        "f1": round(f1_score(y_test, y_pred, zero_division=0), 4),
        "roc_auc": round(roc_auc_score(y_test, y_proba), 4),
        "train_samples": len(X_train),
        "test_samples": len(X_test),
    }

    registry = get_registry()
    version = registry.save(model_pipeline, "funnel_conversion", metrics=metrics)
    metrics["model_version"] = version
    return metrics
