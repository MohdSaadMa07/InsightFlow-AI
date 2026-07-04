"""Celery tasks for ML pipeline."""
import json
import logging
from datetime import date, datetime

from celery import shared_task

from events.clickhouse import ch
from ml.services.churn_risk import churn_risk

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

    # Determine which users get SHAP
    shap_targets = [p for p in predictions
                    if p['risk_level'] == 'high' or full_shap]
    shap_targets = shap_targets[:max_users]

    logger.info('Computing SHAP for %s users...', len(shap_targets))
    batch = []

    for i, pred in enumerate(shap_targets):
        try:
            explanation = churn_risk.explain_user(pred['user_id'], project_id)
        except Exception as e:
            logger.warning('SHAP failed for %s: %s', pred['user_id'], e)
            explanation = None

        shap_json = ''
        confidence = 'low'
        last_active_days = 0
        if explanation:
            exps = explanation.get('explanations', [])
            shap_json = json.dumps([{
                'event_name': e['event_name'],
                'shap_value': e.get('shap_value', 0),
                'importance': e.get('importance', 0),
            } for e in exps])
            confidence = explanation.get('confidence', 'low')
            last_active_days = explanation.get('last_active_days', 0) or 0

        prob = pred['probability']
        batch.append((
            pred['user_id'],
            project_id,
            round(prob, 4),
            pred['risk_level'],
            pred['total_events'],
            shap_json,
            confidence,
            round(max(prob, 1 - prob), 4),
            cohort_size,
            last_active_days,
            MODEL_VERSION,
            today.isoformat(),
            now_dt,
        ))

    if batch:
        client.insert(ref, batch, column_names=[
            'user_id', 'project_id', 'churn_probability', 'risk_level',
            'total_events', 'shap_explanation', 'confidence',
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
