"""ClickHouse revenue aggregation queries."""
import json
import logging
from datetime import date, datetime

logger = logging.getLogger(__name__)

PURCHASE_PATTERNS = "purchase|order|checkout_complete|subscribe|upgrade|paid|refund"


def _ch():
    from events.clickhouse import ch
    return ch


def _get_ref():
    ch = _ch()
    if not ch.available:
        return None
    return f'{ch._database}.{ch._table}'


def aggregate_daily_revenue(project_id, start_date=None, end_date=None):
    """Aggregate revenue metrics from events table for a project."""
    ref = _get_ref()
    if not ref:
        return None
    ch = _ch()
    client = ch.get_client()

    clauses = ['project_id = %(pid)s']
    params = {'pid': project_id}
    if start_date:
        clauses.append('toDate(timestamp) >= %(start)s')
        params['start'] = start_date.isoformat() if isinstance(start_date, date) else start_date
    if end_date:
        clauses.append('toDate(timestamp) <= %(end)s')
        params['end'] = end_date.isoformat() if isinstance(end_date, date) else end_date

    where = ' AND '.join(clauses)
    rows = client.query(f"""
        SELECT
            toDate(timestamp) AS d,
            countDistinct(user_id) AS dau,
            count() AS session_count,
            countDistinct(if(event_name != 'exit', user_id, NULL)) AS active_users,
            sum(if(properties LIKE '%%$revenue_type%%subscription%%', 1, 0)) AS subscription_count,
            sum(if(properties LIKE '%%$revenue_type%%refund%%', 1, 0)) AS refund_count,
            sum(if(match(event_name, '{PURCHASE_PATTERNS}'),
                multiply(
                    coalesce(JSONExtractFloat(properties, '$."$revenue"'), 0),
                    multiIf(properties LIKE '%%$revenue_type%%refund%%', -1, 1)
                ),
                0
            )) AS total_revenue,
            sum(if(properties LIKE '%%$revenue_type%%subscription%%',
                coalesce(JSONExtractFloat(properties, '$."$revenue"'), 0), 0
            )) AS mrr,
            countIf(match(event_name, '{PURCHASE_PATTERNS}')) AS transaction_count
        FROM {ref}
        WHERE {where}
        GROUP BY d
        ORDER BY d
    """, parameters=params)

    if not rows or not rows.result_rows:
        return []

    results = []
    for r in rows.result_rows:
        results.append({
            'date': str(r[0]),
            'dau': r[1],
            'session_count': r[2],
            'active_users': r[3],
            'subscription_count': r[4],
            'refund_count': r[5],
            'total_revenue': round(r[6], 2),
            'mrr': round(r[7], 2),
            'transaction_count': r[8],
        })
    return results


def get_revenue_time_series(project_id, days=365):
    """Return daily revenue time series for TFT training."""
    from datetime import timedelta
    end = date.today()
    start = end - timedelta(days=days)
    return aggregate_daily_revenue(project_id, start_date=start, end_date=end)


def get_recent_revenue(project_id, days=90):
    """Return recent revenue summary."""
    data = aggregate_daily_revenue(project_id, end_date=date.today())
    if not data:
        return None
    recent = [d for d in data if d['date']]
    return recent[-days:] if len(recent) > days else recent


def compute_daily_revenue_snapshot(project_id):
    """Compute today's revenue metrics and return dict for Celery task."""
    from datetime import timedelta
    start = date.today() - timedelta(days=1)
    rows = aggregate_daily_revenue(project_id, start_date=start)
    today_row = None
    yesterday_row = None
    for r in (rows or []):
        if r['date'] == date.today().isoformat():
            today_row = r
        elif r['date'] == (date.today() - timedelta(days=1)).isoformat():
            yesterday_row = r
    return {
        'today': today_row,
        'yesterday': yesterday_row,
        'rows': rows[-90:] if rows else [],
    }
