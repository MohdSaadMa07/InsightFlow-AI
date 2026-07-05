"""Load daily revenue data as TimeSeriesDataSet for TFT training."""
import logging
from datetime import date, timedelta

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def load_daily_revenue(project_id, days=365):
    """Return DataFrame of daily revenue metrics for TFT training."""
    from analytics.clickhouse_revenue import get_revenue_time_series
    try:
        data = get_revenue_time_series(project_id, days=days)
        if data:
            has_revenue = any(r.get('total_revenue', 0) != 0 for r in data)
            if has_revenue:
                return _dataframe_from_rows(data)
    except Exception:
        logger.warning('ClickHouse query failed, falling back to PG')

    # Fallback: PostgreSQL
    from analytics.models import DailyRevenue
    end = date.today()
    start = end - timedelta(days=days)
    qs = DailyRevenue.objects.filter(project_id=project_id, date__gte=start).order_by('date')
    return _dataframe_from_qs(qs)


def _dataframe_from_rows(rows):
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    _add_features(df)
    return df


def _dataframe_from_qs(qs):
    records = []
    for r in qs:
        records.append({
            'date': r.date,
            'total_revenue': float(r.total_revenue),
            'mrr': float(r.mrr),
            'dau': r.dau,
            'session_count': r.session_count,
            'transaction_count': r.transaction_count,
            'subscription_count': r.subscription_count,
            'refund_count': r.refund_count,
        })
    df = pd.DataFrame(records)
    if df.empty:
        return df
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    _add_features(df)
    return df


def _add_features(df):
    df['day_of_week'] = df['date'].dt.dayofweek.astype(int)
    df['day_of_month'] = df['date'].dt.day.astype(int)
    df['month'] = df['date'].dt.month.astype(int)
    df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
    df['time_idx'] = np.arange(len(df), dtype=int)
    df['group_id'] = 0  # single time series per project
    df = df.fillna(0)
    return df
