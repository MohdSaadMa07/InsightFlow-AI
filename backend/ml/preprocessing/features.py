import pandas as pd
import numpy as np
from datetime import timedelta
from typing import Optional


def build_user_features(events: pd.DataFrame) -> pd.DataFrame:
    """Aggregate event-level data into per-user feature vectors."""
    features = []

    for uid, grp in events.groupby("user_id"):
        grp = grp.sort_values("timestamp")
        total_events = len(grp)
        unique_events = grp["event_name"].nunique()
        days_active = grp["date"].nunique()
        span_days = (grp["timestamp"].max() - grp["timestamp"].min()).days + 1
        event_density = total_events / span_days if span_days > 0 else 0
        sessions = grp["session_id"].nunique() if "session_id" in grp.columns else 0

        # Recency: hours since last event
        now = pd.Timestamp.now(tz=grp["timestamp"].dt.tz)
        hours_since_last = (now - grp["timestamp"].max()).total_seconds() / 3600

        # Event type distribution
        pageviews = (grp["event_name"].str.contains("pageview", case=False)).sum()
        purchases = (grp["event_name"].str.contains("purchase|buy|order", case=False)).sum()

        features.append({
            "user_id": uid,
            "total_events": total_events,
            "unique_event_types": unique_events,
            "days_active": days_active,
            "event_density": round(event_density, 4),
            "session_count": sessions,
            "hours_since_last_event": round(hours_since_last, 1),
            "pageview_ratio": round(pageviews / total_events, 4) if total_events else 0,
            "purchase_count": purchases,
            "is_purchaser": int(purchases > 0),
        })

    return pd.DataFrame(features)


def build_session_features(events: pd.DataFrame) -> pd.DataFrame:
    if "session_id" not in events.columns:
        return pd.DataFrame()
    features = []
    for sid, grp in events.groupby("session_id"):
        grp = grp.sort_values("timestamp")
        dur = (grp["timestamp"].max() - grp["timestamp"].min()).total_seconds()
        features.append({
            "session_id": sid,
            "user_id": grp["user_id"].iloc[0],
            "event_count": len(grp),
            "duration_seconds": dur,
            "bounced": int(len(grp) == 1),
            "unique_pages": grp["url"].nunique() if "url" in grp.columns else 0,
            "has_purchase": int(grp["event_name"].str.contains("purchase", case=False).any()),
        })
    return pd.DataFrame(features)


def build_event_features(events: pd.DataFrame) -> pd.DataFrame:
    df = events.copy()
    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)
    df["is_business_hours"] = df["hour"].between(9, 17).astype(int)
    return df


def build_time_features(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df["day_of_week"] = df[date_col].dt.dayofweek
    df["day_of_month"] = df[date_col].dt.day
    df["month"] = df[date_col].dt.month
    df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)
    return df
