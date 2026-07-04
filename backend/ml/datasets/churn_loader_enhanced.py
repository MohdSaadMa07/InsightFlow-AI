"""
Enhanced per-event multi-feature loader for churn prediction.

Extracts per-event features:
  - event_token (from event_name, includes <MASK>/<SESS_START>/<SESS_END>)
  - hour (0-23)
  - weekday (0-6)
  - device (desktop/mobile/tablet/bot)
  - browser (Chrome/Safari/Firefox/Edge/Bot)
  - page_type (home/products/pricing/blog/etc)
  - country (US/GB/FR/etc)
  - time_gap_seconds (raw seconds for sinusoidal encoding)
  - session boundary tokens inserted at session starts/stops
"""

import torch
import numpy as np
import pandas as pd
from datetime import timedelta
from collections import defaultdict, Counter
from typing import Optional

from events.models import Event
from ..config import settings

BOT_UA_SUBSTRINGS = ["bot", "crawl", "spider", "scrape", "curl", "wget", "python-requests", "go-http"]
SESSION_GAP_THRESHOLD = 1800  # 30 minutes in seconds


def build_multi_vocab(project_id):
    from events.models import Event
    qs = Event.objects.filter(project_id=project_id)

    event_names = sorted(qs.values_list("event_name", flat=True).distinct().order_by())
    event_vocab = {n: i+1 for i, n in enumerate(event_names)}

    # Special token indices
    mask_id = len(event_vocab) + 1
    sess_start_id = len(event_vocab) + 2
    sess_end_id = len(event_vocab) + 3

    props_list = qs.values_list("properties", flat=True)[:100000]
    devices = set()
    browsers = set()
    page_types = set()
    countries = set()
    for p in props_list:
        if not p: continue
        d = p.get("device"); b = p.get("browser");
        url = p.get("url", ""); lang = p.get("$language", "")
        if d: devices.add(d)
        if b: browsers.add(b)
        if url:
            pt = url.strip("/").split("?")[0].split("/")[0] or "home"
            page_types.add(pt)
        if lang and "-" in lang:
            countries.add(lang.split("-")[1])
        elif lang:
            countries.add(lang.upper())

    device_vocab = {v: i+1 for i, v in enumerate(sorted(devices))}
    browser_vocab = {v: i+1 for i, v in enumerate(sorted(browsers))}
    country_vocab = {v: i+1 for i, v in enumerate(sorted(countries))}
    page_vocab = {v: i+1 for i, v in enumerate(sorted(page_types))}

    vocab = {
        "event": event_vocab,
        "device": device_vocab,
        "browser": browser_vocab,
        "country": country_vocab,
        "page_type": page_vocab,
    }
    vocab["_meta"] = {
        "num_events": len(event_vocab) + 4,  # PAD=0, events=1..N, MASK=N+1, SESS_START=N+2, SESS_END=N+3
        "num_devices": len(device_vocab) + 1,
        "num_browsers": len(browser_vocab) + 1,
        "num_countries": len(country_vocab) + 1,
        "num_pages": len(page_vocab) + 1,
        "num_hours": 24,
        "num_weekdays": 7,
        "mask_id": mask_id,
        "sess_start_id": sess_start_id,
        "sess_end_id": sess_end_id,
    }
    return vocab


def extract_page_type(url):
    if not url:
        return "other"
    url = url.strip("/").split("?")[0].split("/")[0]
    return url or "home"


def extract_country(lang):
    if not lang:
        return "UNKNOWN"
    if "-" in lang:
        return lang.split("-")[1]
    return lang.upper()


def _fetch_events_ch(project_id):
    """Fetch events from ClickHouse."""
    from events.clickhouse import ch

    try:
        client = ch.get_client()
        if not client:
            return None
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
        if not rows or not rows.result_rows:
            return None
        df = pd.DataFrame(rows.result_rows, columns=[
            "user_id", "event_name", "timestamp", "session_id",
            "device", "browser", "url", "language",
        ])
        df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.tz_localize(None)
        return df
    except Exception:
        return None


def load_multi_feature_sequences(project_id, vocab, obs_days=30, gap_days=30,
                                  max_len=200, min_events=3):
    """Load per-event multi-feature sequences with churn labels and session tokens."""
    import pandas as pd

    df = _fetch_events_ch(project_id)
    if df is None:
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
        df = pd.DataFrame(records)
    print(f"  Events: {len(df)}, Users: {df['user_id'].nunique()}")

    ev_vocab = vocab["event"]
    dev_vocab = vocab["device"]
    br_vocab = vocab["browser"]
    co_vocab = vocab["country"]
    pg_vocab = vocab["page_type"]
    meta = vocab["_meta"]
    sess_start_id = meta["sess_start_id"]
    sess_end_id = meta["sess_end_id"]

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

        features = []
        prev_ts = None
        prev_sid = None

        for _, row in obs_events.iterrows():
            et = row["event_name"]
            ts = row["timestamp"]
            sid = row.get("session_id", "")

            time_delta = 0
            if prev_ts is not None:
                time_delta = (ts - prev_ts).total_seconds()
            time_delta = max(0, time_delta)

            # Detect session boundary
            is_new_session = False
            if prev_sid is not None and sid != prev_sid:
                is_new_session = True
            elif prev_sid is None and sid:
                is_new_session = True
            elif prev_ts is not None and time_delta > SESSION_GAP_THRESHOLD:
                is_new_session = True

            if is_new_session:
                # End previous session, start new one: insert <SESS_END> + <SESS_START>
                # The <SESS_END> gets the time gap from the last event
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
                # The <SESS_START> after <SESS_END> has 0 time gap
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
                time_delta = 0  # The actual event follows SESS_START immediately

            features.append({
                "event": ev_vocab.get(et, 0),
                "hour": ts.hour,
                "weekday": ts.weekday(),
                "device": dev_vocab.get(row.get("device", ""), 0),
                "browser": br_vocab.get(row.get("browser", ""), 0),
                "country": co_vocab.get(extract_country(row.get("language", "")), 0),
                "page_type": pg_vocab.get(extract_page_type(row.get("url", "")), 0),
                "time_gap_seconds": time_delta,
            })
            prev_ts = ts
            prev_sid = sid

        # Wrap with session start/end tokens
        if features:
            features.insert(0, {
                "event": sess_start_id,
                "hour": 0,
                "weekday": 0,
                "device": 0,
                "browser": 0,
                "country": 0,
                "page_type": 0,
                "time_gap_seconds": 0,
            })
            features.append({
                "event": sess_end_id,
                "hour": 0,
                "weekday": 0,
                "device": 0,
                "browser": 0,
                "country": 0,
                "page_type": 0,
                "time_gap_seconds": 0,
            })

        sequences.append({
            "uid": uid,
            "features": features,
            "churned": churned,
            "first_ts": user_start,
            "seq_len": len(features),
        })

    churn_rate = sum(s["churned"] for s in sequences) / len(sequences)
    print(f"  Sequences: {len(sequences)}, churn: {churn_rate:.2%}")
    return sequences


def pad_multi_sequences(sequences, max_len):
    """Convert multi-feature sequences to padded tensors.

    Returns dict of feature tensors, time_gap float tensor, mask, labels.
    Features: event, hour, weekday, device, browser, country, page_type
    """
    N = len(sequences)
    feature_names = ["event", "hour", "weekday",
                     "device", "browser", "country", "page_type"]
    tensors = {f: torch.zeros(N, max_len, dtype=torch.long) for f in feature_names}
    time_gap = torch.zeros(N, max_len, dtype=torch.float)
    mask = torch.zeros(N, max_len, dtype=torch.bool)
    y = torch.zeros(N, dtype=torch.float)
    timestamps = []

    for i, s in enumerate(sequences):
        feats = s["features"][:max_len]
        sl = len(feats)
        for f in feature_names:
            vals = [e[f] for e in feats]
            tensors[f][i, :sl] = torch.tensor(vals, dtype=torch.long)
        gap_vals = [e["time_gap_seconds"] for e in feats]
        time_gap[i, :sl] = torch.tensor(gap_vals, dtype=torch.float)
        mask[i, :sl] = True
        y[i] = float(s["churned"])
        timestamps.append(s["first_ts"])

    tensors["time_gap_seconds"] = time_gap
    return tensors, mask, y, timestamps
