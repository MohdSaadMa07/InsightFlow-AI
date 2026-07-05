"""
Create the user_risk_snapshots table in ClickHouse.

Run once:
    python ml/migrate_snapshots.py
"""

import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django; django.setup()
from events.clickhouse import ch

TABLE = 'user_risk_snapshots'


def migrate():
    if not ch.available:
        print('ERROR: ClickHouse not available!')
        sys.exit(1)

    client = ch.get_client()
    ref = f'{ch._database}.{TABLE}'

    client.command(f'''
        CREATE TABLE IF NOT EXISTS {ref} (
            user_id          String,
            project_id       UInt32,
            churn_probability Float32,
            risk_level       String,
            total_events     UInt32,
            shap_explanation String,
            suggestions      String,
            confidence       String,
            confidence_score Float32,
            cohort_size      UInt32,
            last_active_days UInt32,
            model_version    String,
            snapshot_date    Date,
            computed_at      DateTime64(6)
        ) ENGINE = ReplacingMergeTree(computed_at)
        ORDER BY (project_id, snapshot_date, user_id)
    ''')

    print(f'Table {ref} ready.')


if __name__ == '__main__':
    migrate()
