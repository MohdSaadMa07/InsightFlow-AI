import pandas as pd
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Count, Min, Max, Q
from typing import Optional

from events.models import Event
from analytics.models import FunnelAnalysis, RetentionCurve
from ..config import settings


def load_events(
    project_id: int,
    days: Optional[int] = None,
    as_df: bool = True,
) -> pd.DataFrame:
    days = days or settings.lookback_days
    since = timezone.now() - timedelta(days=days)
    qs = (
        Event.objects
        .filter(project_id=project_id, timestamp__gte=since)
        .values("user_id", "event_name", "timestamp", "properties")
    )
    df = pd.DataFrame.from_records(qs)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["date"] = df["timestamp"].dt.date
    return df


def load_users(
    project_id: int,
    days: Optional[int] = None,
    as_df: bool = True,
) -> pd.DataFrame:
    days = days or settings.lookback_days
    since = timezone.now() - timedelta(days=days)
    qs = (
        Event.objects
        .filter(project_id=project_id, timestamp__gte=since)
        .values("user_id")
        .annotate(
            event_count=Count("id"),
            first_seen=Count("id"),
        )
    )
    df = pd.DataFrame.from_records(qs)
    if not df.empty:
        from django.db.models import Min
        first = (
            Event.objects
            .filter(project_id=project_id, timestamp__gte=since)
            .values("user_id")
            .annotate(fs=Min("timestamp"))
        )
        first_map = {r["user_id"]: r["fs"] for r in first}
        df["first_seen"] = df["user_id"].map(first_map)
    return df


def load_sessions(
    project_id: int,
    days: Optional[int] = None,
    as_df: bool = True,
) -> pd.DataFrame:
    days = days or settings.lookback_days
    since = timezone.now() - timedelta(days=days)
    qs = (
        Event.objects
        .filter(
            project_id=project_id,
            timestamp__gte=since,
            properties__has_key="$session_id",
        )
        .values("properties__$session_id")
        .annotate(
            event_count=Count("id"),
            first_ts=Min("timestamp"),
            last_ts=Max("timestamp"),
            user_count=Count("user_id", distinct=True),
        )
    )
    df = pd.DataFrame.from_records(qs)
    if not df.empty:
        df.columns = ["session_id", "event_count", "first_ts", "last_ts", "user_count"]
        df["duration_seconds"] = (df["last_ts"] - df["first_ts"]).dt.total_seconds()
    return df


def load_funnels(
    project_id: int,
    days: Optional[int] = None,
    as_df: bool = True,
) -> pd.DataFrame:
    days = days or settings.lookback_days
    since = timezone.now().date() - timedelta(days=days)
    qs = FunnelAnalysis.objects.filter(
        project_id=project_id, date__gte=since
    ).order_by("date", "step_order")
    df = pd.DataFrame.from_records(
        qs.values("funnel__name", "date", "step_order", "step_name", "count", "conversion_rate")
    )
    return df


def train_test_split(
    df: pd.DataFrame,
    user_col: str = "user_id",
    test_ratio: float = None,
    seed: int = None,
):
    test_ratio = test_ratio or settings.test_split_ratio
    seed = seed or settings.random_seed
    users = df[user_col].unique()
    rng = __import__("numpy").random.default_rng(seed)
    rng.shuffle(users)
    split = int(len(users) * (1 - test_ratio))
    train_users = set(users[:split])
    train_df = df[df[user_col].isin(train_users)].copy()
    test_df = df[~df[user_col].isin(train_users)].copy()
    return train_df, test_df
