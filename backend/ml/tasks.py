"""Celery tasks for ML pipeline."""
import json
import logging
from datetime import date, datetime

from celery import shared_task

from events.clickhouse import ch
from ml.services.anomaly_detection import anomaly_detection
from ml.services.churn_risk import churn_risk
from ml.services.revenue_forecast import revenue_forecast

logger = logging.getLogger(__name__)
SNAPSHOT_TABLE = 'user_risk_snapshots'
MODEL_VERSION = 'churn_transformer_v1'


@shared_task(autoretry_for=(Exception,), max_retries=2, default_retry_delay=300)
def nightly_pipeline(project_id, max_users=500, full_shap=False):
    """Nightly: predict + SHAP all users → store in ClickHouse."""
    if not ch.available:
        raise RuntimeError('ClickHouse not available')

    if not churn_risk.load():
        raise RuntimeError('Model not available')

    client = ch.get_client()
    ref = f'{ch._database}.{SNAPSHOT_TABLE}'

    logger.info('Fetching events & predicting for project %s...', project_id)
    predictions = churn_risk.predict_all(project_id)
    if not predictions:
        logger.warning('No predictions for project %s', project_id)
        return

    cohort_size = len(predictions)
    today = date.today()
    now_dt = datetime.now()
    seqs = getattr(churn_risk, '_cache_seqs', None)

    # Determine which users get SHAP (high-risk only, limited by max_users)
    shap_targets = [p for p in predictions if p['risk_level'] == 'high' or full_shap]
    shap_targets = shap_targets[:max_users]
    shap_user_ids = {p['user_id'] for p in shap_targets}

    logger.info('Computing SHAP for %s users...', len(shap_targets))
    batch = []

    for pred in predictions:
        uid = pred['user_id']
        prob = pred['probability']
        risk = pred['risk_level']
        last_active_days = pred.get('last_active_days', 0)

        shap_json = ''
        confidence = 'low'

        if uid in shap_user_ids:
            try:
                explanation = churn_risk.explain_user(uid, project_id)
            except Exception as e:
                logger.warning('SHAP failed for %s: %s', uid, e)
                explanation = None

            if explanation:
                exps = explanation.get('explanations', [])
                shap_json = json.dumps([{
                    'event_name': e['event_name'],
                    'shap_value': e.get('shap_value', 0),
                    'importance': e.get('importance', 0),
                } for e in exps])
                confidence = explanation.get('confidence', 'low')
                last_active_days = explanation.get('last_active_days', 0) or 0
            else:
                # No SHAP available yet — estimate confidence from probability
                certainty = max(prob, 1 - prob)
                confidence = 'high' if certainty >= 0.85 else ('medium' if certainty >= 0.65 else 'low')

        # Generate per-user suggestions
        suggestions = churn_risk._generate_user_suggestions(
            {**pred, 'last_active_days': last_active_days},
            seqs,
        )
        suggestions_json = json.dumps(suggestions)

        batch.append((
            uid,
            project_id,
            round(prob, 4),
            risk,
            pred['total_events'],
            shap_json,
            suggestions_json,
            confidence,
            round(max(prob, 1 - prob), 4),
            cohort_size,
            last_active_days,
            MODEL_VERSION,
            today,
            now_dt,
        ))

    if batch:
        client.insert(ref, batch, column_names=[
            'user_id', 'project_id', 'churn_probability', 'risk_level',
            'total_events', 'shap_explanation', 'suggestions', 'confidence',
            'confidence_score', 'cohort_size', 'last_active_days',
            'model_version', 'snapshot_date', 'computed_at',
        ])
        logger.info('Stored %s snapshots for project %s', len(batch), project_id)

    levels = {'high': 0, 'medium': 0, 'low': 0}
    for p in predictions:
        levels[p['risk_level']] += 1
    logger.info(
        'Nightly pipeline complete: %s users (%sH/%sM/%sL)',
        len(predictions), levels['high'], levels['medium'], levels['low'],
    )


@shared_task(autoretry_for=(Exception,), max_retries=1)
def precompute_shap(project_id, max_users=50):
    """Precompute SHAP for high-risk users after dashboard load."""
    if not churn_risk.load():
        return
    count = churn_risk.precompute_shap(project_id, max_users=max_users, batch_size=5)
    logger.info('Precomputed SHAP for %s users', count)


@shared_task(autoretry_for=(Exception,), max_retries=2, default_retry_delay=300)
def nightly_revenue_aggregation(project_id=14):
    """Aggregate daily revenue metrics from ClickHouse events into revenue_metrics table."""
    if not ch.available:
        raise RuntimeError('ClickHouse not available')

    from analytics.clickhouse_revenue import compute_daily_revenue_snapshot
    snapshot = compute_daily_revenue_snapshot(project_id)
    if not snapshot or not snapshot['rows']:
        logger.warning('No revenue data for project %s', project_id)
        return

    client = ch.get_client()
    ref = f'{ch._database}.revenue_metrics'

    today_rows = [r for r in snapshot['rows'] if r['date']]
    if not today_rows:
        return

    batch = []
    now_dt = datetime.now()
    for row in today_rows[-90:]:
        batch.append((
            project_id,
            row['date'],
            row.get('total_revenue', 0),
            row.get('mrr', 0),
            row.get('transaction_count', 0),
            row.get('subscription_count', 0),
            row.get('refund_count', 0),
            row.get('dau', 0),
            row.get('session_count', 0),
            0.0,  # avg_churn_risk — populated by forecast task
            0,    # high_risk_user_count
            now_dt,
        ))

    if batch:
        client.insert(ref, batch, column_names=[
            'project_id', 'date', 'total_revenue', 'mrr',
            'transaction_count', 'subscription_count', 'refund_count',
            'dau', 'session_count', 'avg_churn_risk',
            'high_risk_user_count', 'computed_at',
        ])
        logger.info('Stored %d revenue metric rows for project %s', len(batch), project_id)

    # Update PostgreSQL cache
    from analytics.models import DailyRevenue
    from projects.models import Project
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return

    for row in today_rows[-90:]:
        DailyRevenue.objects.update_or_create(
            project=project, date=row['date'],
            defaults={
                'total_revenue': row.get('total_revenue', 0),
                'mrr': row.get('mrr', 0),
                'transaction_count': row.get('transaction_count', 0),
                'subscription_count': row.get('subscription_count', 0),
                'refund_count': row.get('refund_count', 0),
                'dau': row.get('dau', 0),
                'session_count': row.get('session_count', 0),
                'avg_churn_risk': 0.0,
                'high_risk_user_count': 0,
            },
        )
    logger.info('Updated %d DailyRevenue cache rows for project %s', len(today_rows[-90:]), project_id)


@shared_task(autoretry_for=(Exception,), max_retries=2, default_retry_delay=300)
def nightly_revenue_forecast(project_id=14, horizon=30):
    """Generate revenue forecast and store to ClickHouse."""
    if not ch.available:
        raise RuntimeError('ClickHouse not available')

    # Enrich revenue_metrics with churn data from prior pipeline run
    _enrich_revenue_metrics(project_id)

    if not revenue_forecast.load():
        logger.warning('Revenue TFT model not loaded, using heuristic')
    else:
        logger.info('Revenue TFT model loaded')

    result = revenue_forecast.predict(project_id, horizon=horizon)
    if not result:
        logger.warning('No forecast result for project %s', project_id)
        return

    client = ch.get_client()
    ref = f'{ch._database}.revenue_forecasts'
    now_dt = datetime.now()
    today = date.today()
    model_ver = result.get('model_version', 'heuristic_v1')
    feature_imp = json.dumps(result.get('feature_importance', {}))

    batch = []
    for f in result.get('forecasts', []):
        batch.append((
            project_id, today, f['forecast_date'],
            f['predicted_revenue'], f['lower_bound'], f['upper_bound'],
            0.0, None, feature_imp, model_ver, now_dt,
        ))

    # Merge MRR forecasts
    mrr_map = {m['forecast_date']: m['predicted_mrr'] for m in result.get('mrr_forecasts', [])}
    for row in batch:
        fd = row[2]
        if fd in mrr_map:
            # row[6] is predicted_mrr
            batch[batch.index(row)] = (
                row[0], row[1], row[2], row[3], row[4], row[5],
                mrr_map[fd], row[7], row[8], row[9], row[10],
            )

    if batch:
        client.insert(ref, batch, column_names=[
            'project_id', 'snapshot_date', 'forecast_date',
            'predicted_revenue', 'lower_bound', 'upper_bound',
            'predicted_mrr', 'actual_revenue', 'feature_importance',
            'model_version', 'computed_at',
        ])
        logger.info('Stored %d forecast rows for project %s', len(batch), project_id)


@shared_task(autoretry_for=(Exception,), max_retries=2, default_retry_delay=300)
def nightly_anomaly_detection(project_id=14, days=60):
    """Score behavioral anomalies and store them in ClickHouse."""
    if not ch.available:
        raise RuntimeError('ClickHouse not available')

    result = anomaly_detection.run_batch(project_id, days=days, store=True)
    if not result:
        logger.warning('No anomaly scores for project %s', project_id)
        return

    summary = result['summary']
    logger.info(
        'Stored anomaly scores for project %s: %s/%s flagged',
        project_id,
        summary.get('anomaly_count', 0),
        summary.get('total_scored', 0),
    )


def _enrich_revenue_metrics(project_id):
    """Pull churn risk data into revenue_metrics for TFT multivariate features."""
    try:
        from events.clickhouse import ch
        if not ch.available:
            return
        client = ch.get_client()

        snap_ref = f'{ch._database}.user_risk_snapshots'
        rev_ref = f'{ch._database}.revenue_metrics'

        # Update avg_churn_risk and high_risk_user_count per date
        client.command(f"""
            ALTER TABLE {rev_ref}
            UPDATE
                avg_churn_risk = (
                    SELECT avg(churn_probability)
                    FROM {snap_ref}
                    WHERE project_id = {project_id}
                        AND snapshot_date = (SELECT max(snapshot_date) FROM {snap_ref} WHERE project_id = {project_id})
                ),
                high_risk_user_count = (
                    SELECT count()
                    FROM {snap_ref}
                    WHERE project_id = {project_id}
                        AND risk_level = 'high'
                        AND snapshot_date = (SELECT max(snapshot_date) FROM {snap_ref} WHERE project_id = {project_id})
                )
            WHERE project_id = {project_id}
        """)
        logger.info('Enriched revenue_metrics with churn data for project %s', project_id)
    except Exception as e:
        logger.warning('Enrich revenue_metrics failed: %s', e)


@shared_task(autoretry_for=(Exception,), max_retries=2, default_retry_delay=300)
def nightly_revenue_forecast(project_id=14, horizon=30):
    """Precompute revenue forecast and cache it for instant dashboard loads."""
    from ml.services.revenue_forecast import revenue_forecast

    logger.info('Precomputing revenue forecast for project %s...', project_id)
    result = revenue_forecast.predict(project_id, horizon=horizon)
    if not result:
        logger.warning('No forecast generated for project %s', project_id)
        return

    revenue_forecast.save_to_cache(project_id, result)
    logger.info('Revenue forecast cached for project %s (%d horizon)', project_id, horizon)
