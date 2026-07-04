"""
Nightly User Risk Snapshot Pipeline.

Pulls events → builds sequences → runs churn model → computes SHAP →
stores results in ClickHouse.

Usage:
    python ml/pipeline_nightly.py --project_id 14 [--max_users 500]
    python ml/pipeline_nightly.py --project_id 14 --full-shap   # SHAP for all risk levels
"""

import argparse
import json
import os
import sys
import time
from datetime import date, datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django; django.setup()
import torch
import numpy as np

from django.conf import settings
from events.clickhouse import ch
from ml.services.churn_risk import churn_risk
from ml.models.transformers.churn_transformer_enhanced import explain_event_importance_shap

SNAPSHOT_TABLE = 'user_risk_snapshots'
MODEL_VERSION = 'churn_transformer_v1'


def store_snapshot(client, table, records):
    """Insert risk snapshots into ClickHouse."""
    if not records:
        return

    client.insert(
        table,
        records,
        column_names=[
            'user_id', 'project_id', 'churn_probability', 'risk_level',
            'total_events', 'shap_explanation', 'confidence',
            'confidence_score', 'cohort_size', 'last_active_days',
            'model_version', 'snapshot_date', 'computed_at',
        ],
    )


def run_pipeline(project_id, max_users=500, full_shap=False):
    if not ch.available:
        print('ERROR: ClickHouse not available')
        return

    print(f'[{datetime.now():%H:%M:%S}] Loading model...')
    if not churn_risk.load():
        print('ERROR: Model not available')
        return

    client = ch.get_client()
    snapshot_ref = f'{ch._database}.{SNAPSHOT_TABLE}'

    # 1. Fetch events and predict
    print(f'[{datetime.now():%H:%M:%S}] Fetching events & predicting...')
    t0 = time.time()
    predictions = churn_risk.predict_all(project_id)
    if not predictions:
        print('No predictions generated')
        return
    print(f'  {len(predictions)} users in {time.time()-t0:.1f}s')

    vr = churn_risk.event_vocab_reverse
    device = next(churn_risk._model.parameters()).device
    cohort_size = len(predictions)
    today = date.today()
    now_dt = datetime.now()
    batch = []

    # 2. Compute SHAP + snapshot for each user
    shap_targets = [p for p in predictions
                    if p['risk_level'] == 'high' or full_shap]
    shap_targets = shap_targets[:max_users]

    print(f'[{datetime.now():%H:%M:%S}] Computing SHAP for {len(shap_targets)} users...')
    shap_count = 0

    for i, pred in enumerate(shap_targets):
        uid = pred['user_id']
        t1 = time.time()

        try:
            explanation = churn_risk.explain_user(uid, project_id)
        except Exception:
            explanation = None

        shap_json = ''
        confidence = 'low'
        confidence_score = 0.0
        last_active_days = 0

        if explanation:
            # Extract shap explanations
            exps = explanation.get('explanations', [])
            shap_json = json.dumps([{
                'event_name': e['event_name'],
                'shap_value': e.get('shap_value', 0),
                'importance': e.get('importance', 0),
            } for e in exps])

            confidence = explanation.get('confidence', 'low')
            last_active_days = explanation.get('last_active_days', 0) or 0

        # Confidence score from prediction certainty
        prob = pred['probability']
        confidence_score = round(max(prob, 1 - prob), 4)

        batch.append((
            uid,
            project_id,
            round(prob, 4),
            pred['risk_level'],
            pred['total_events'],
            shap_json,
            confidence,
            confidence_score,
            cohort_size,
            last_active_days,
            MODEL_VERSION,
            today.isoformat(),
            now_dt,
        ))

        shap_count += 1
        elapsed = time.time() - t1

        if (i + 1) % 10 == 0:
            print(f'  [{datetime.now():%H:%M:%S}] {i+1}/{len(shap_targets)} '
                  f'({elapsed:.1f}s/user)')

    # 3. Bulk insert into ClickHouse
    if batch:
        print(f'[{datetime.now():%H:%M:%S}] Storing {len(batch)} snapshots...')
        store_snapshot(client, snapshot_ref, batch)
        print(f'  Done — {len(batch)} rows inserted')

    # 4. Summary
    levels = {'high': 0, 'medium': 0, 'low': 0}
    for p in predictions:
        levels[p['risk_level']] += 1
    print(f'\nSummary for project {project_id}:')
    print(f'  Total users:  {len(predictions)}')
    print(f'  High risk:    {levels["high"]}')
    print(f'  Medium risk:  {levels["medium"]}')
    print(f'  Low risk:     {levels["low"]}')
    print(f'  SHAP cached:  {shap_count}')
    print(f'  Model:        {MODEL_VERSION}')
    print(f'  Completed:    {datetime.now():%Y-%m-%d %H:%M:%S}')


if __name__ == '__main__':
    pa = argparse.ArgumentParser()
    pa.add_argument('--project_id', type=int, required=True)
    pa.add_argument('--max-users', type=int, default=500)
    pa.add_argument('--full-shap', action='store_true')
    args = pa.parse_args()
    run_pipeline(args.project_id, args.max_users, args.full_shap)
