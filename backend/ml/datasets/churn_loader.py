"""Load event sequences and generate churn labels per-user.

Label rule (per user):
  - Observation: first `obs_days` days of the user's events.
  - Gap: next `gap_days` after observation.
  - Zero events in gap window => churned=1, else churned=0.

Noise features:
  - is_bot: detected from user_agent
  - has_returned: user had a 30+ day gap then resumed
  - night_ratio: fraction of events during 00:00-06:00
  - weekend_ratio: fraction on Sat/Sun
  - hour_std: std dev of event hour distribution
  - session_regularity: std dev of inter-session gaps (hours)
  - session_length_avg: avg events per session
"""

import pandas as pd
import numpy as np
from datetime import timedelta
from typing import Optional

from django.db.models import Min, Max

from events.models import Event
from events.clickhouse import ch
from ..config import settings

BOT_UA_SUBSTRINGS = ["bot", "crawl", "spider", "scrape", "curl", "wget", "python-requests", "go-http"]


def _fetch_all(project_id: int) -> pd.DataFrame:
    drange = Event.objects.filter(project_id=project_id).aggregate(
        min=Min("timestamp"), max=Max("timestamp"),
    )
    if not drange["min"] or not drange["max"]:
        raise ValueError(f"No events for project {project_id}")

    ref_start = drange["min"].date()
    ref_end = drange["max"].date()

    try:
        client = ch.get_client()
        if client:
            rows = client.query(
                """SELECT user_id, event_name, timestamp,
                          JSONExtractString(properties, '$session_id') AS session_id,
                          user_agent
                   FROM insightflow.events
                   WHERE project_id = %(pid)s
                   ORDER BY user_id, timestamp""",
                parameters={"pid": project_id},
            )
            if rows and rows.result_rows:
                df = pd.DataFrame(rows.result_rows, columns=["user_id", "event_name", "timestamp", "session_id", "user_agent"])
                df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.tz_localize(None)
                return df
    except Exception:
        pass

    qs = Event.objects.filter(project_id=project_id).order_by("user_id", "timestamp")
    records = []
    for r in qs:
        props = r.properties or {}
        ts = r.timestamp
        if hasattr(ts, "tzinfo") and ts.tzinfo is not None:
            ts = ts.replace(tzinfo=None)
        records.append({
            "user_id": r.user_id,
            "event_name": r.event_name,
            "timestamp": ts,
            "session_id": props.get("$session_id", ""),
            "user_agent": props.get("$user_agent", ""),
        })
    return pd.DataFrame(records)


def _is_bot(ua: str) -> bool:
    ua_lower = ua.lower()
    return any(sub in ua_lower for sub in BOT_UA_SUBSTRINGS)


def load_event_sequences(
    project_id: int,
    obs_days: Optional[int] = None,
    gap_days: Optional[int] = None,
    min_events: Optional[int] = None,
) -> pd.DataFrame:
    """Per-user churn labeling with noise-aware features.

    Returns DataFrame with per-user features + churned label.
    """
    obs_days = obs_days or settings.observation_days
    gap = gap_days or settings.gap_days
    min_ev = min_events or settings.min_events_per_user

    print("  Fetching events...")
    df_all = _fetch_all(project_id)
    total_events = len(df_all)
    total_users = df_all["user_id"].nunique()
    print(f"  Total: {total_events} events, {total_users} users")

    features = []

    for uid, grp in df_all.groupby("user_id"):
        grp = grp.sort_values("timestamp")
        user_start = grp["timestamp"].min()
        obs_end = user_start + timedelta(days=obs_days)
        gap_start = obs_end
        gap_end = gap_start + timedelta(days=gap)

        obs_mask = grp["timestamp"] <= obs_end
        df_obs = grp[obs_mask]
        n_obs = len(df_obs)

        if n_obs < min_ev:
            continue

        gap_mask = (grp["timestamp"] > obs_end) & (grp["timestamp"] <= gap_end)
        n_gap = gap_mask.sum()

        churned = 1 if n_gap == 0 else 0

        unique_events = df_obs["event_name"].nunique()
        days_active = df_obs["timestamp"].dt.date.nunique()
        span = (df_obs["timestamp"].max() - df_obs["timestamp"].min()).days + 1
        event_density = round(n_obs / span, 4) if span > 0 else 0
        n_sessions = df_obs["session_id"].nunique()
        hours_since_last = (pd.Timestamp(obs_end) - df_obs["timestamp"].max()).total_seconds() / 3600
        pageviews = int(df_obs["event_name"].str.contains("pageview", case=False).sum())
        purchases = int(df_obs["event_name"].str.contains("purchase|buy|order|success", case=False).sum())

        # ── Noise features ──
        uas = df_obs["user_agent"].dropna().unique()
        is_bot = 1 if any(_is_bot(ua) for ua in uas) else 0

        hours = df_obs["timestamp"].dt.hour
        night_ratio = round((hours < 6).sum() / n_obs, 4)
        weekend_ratio = round(df_obs["timestamp"].dt.dayofweek.isin([5, 6]).sum() / n_obs, 4)
        hour_std = round(hours.std(), 2) if len(hours) > 1 else 0.0

        if n_sessions > 1:
            sess_times = df_obs[df_obs["session_id"] != ""].drop_duplicates("session_id")["timestamp"].sort_values()
            if len(sess_times) > 1:
                sess_gaps = sess_times.diff().dt.total_seconds().dropna()
                session_regularity = round(sess_gaps.std() / 3600, 2) if len(sess_gaps) > 0 else 0.0
            else:
                session_regularity = 0.0
        else:
            session_regularity = 0.0

        if n_sessions > 0:
            sess_lens = df_obs.groupby("session_id").size()
            session_length_avg = round(sess_lens.mean(), 2)
        else:
            session_length_avg = 0.0

        if len(grp) > 1:
            time_gaps = grp["timestamp"].diff().dt.days.dropna()
            has_returned = 1 if (time_gaps >= 30).any() else 0
        else:
            has_returned = 0

        features.append({
            "user_id": uid,
            "first_ts": user_start,
            "last_ts": grp["timestamp"].max(),
            "total_events": n_obs,
            "unique_event_types": unique_events,
            "days_active": days_active,
            "event_density": event_density,
            "session_count": n_sessions,
            "hours_since_last_event": round(max(hours_since_last, 0), 1),
            "pageview_ratio": round(pageviews / n_obs, 4) if n_obs else 0,
            "purchase_count": purchases,
            "is_purchaser": int(purchases > 0),
            "is_bot": is_bot,
            "has_returned": has_returned,
            "night_ratio": night_ratio,
            "weekend_ratio": weekend_ratio,
            "hour_std": hour_std,
            "session_regularity": session_regularity,
            "session_length_avg": session_length_avg,
            "churned": churned,
        })

    result = pd.DataFrame(features)
    if result.empty:
        raise ValueError("No user features after filtering")

    return result


def time_based_split(
    df: pd.DataFrame,
    test_ratio: float = 0.2,
    seed: int = 42,
):
    """Time-based split using first_ts: train on older users, test on newer.

    This prevents distribution mismatch between train/test sets.
    """
    rng = np.random.default_rng(seed)
    sorted_df = df.sort_values("first_ts").reset_index(drop=True)
    n = len(sorted_df)

    # Take the oldest test_ratio fraction as train, newest as test
    split_idx = int(n * (1 - test_ratio))
    train_df = sorted_df.iloc[:split_idx].copy()
    test_df = sorted_df.iloc[split_idx:].copy()

    return train_df, test_df
