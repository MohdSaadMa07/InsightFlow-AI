"""
Migrate ClickHouse events table from MergeTree to ReplacingMergeTree.

Drops the old table and recreates with:
  - ENGINE = ReplacingMergeTree(created_at)
  - ORDER BY (project_id, user_id, timestamp, event_id)

After migration, re-sync data by replaying through Kafka:
  python ml/seed_to_kafka.py --project_id 14

Usage:
    python ml/migrate_clickhouse.py [--project_id 14]
"""

import argparse
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django
django.setup()

from events.clickhouse import ch


def migrate(project_id=None):
    if not ch.available:
        print('ERROR: ClickHouse not available!')
        sys.exit(1)

    client = ch.get_client()
    table = ch.table_ref
    database = ch._database

    # Check current engine
    try:
        rows = client.query(f"""
            SELECT engine FROM system.tables
            WHERE database = '{database}' AND name = '{ch._table}'
        """)
        if rows and rows.result_rows:
            current_engine = rows.result_rows[0][0]
            print(f'Current engine: {current_engine}')
            if current_engine == 'ReplacingMergeTree':
                print('Table already uses ReplacingMergeTree — nothing to do.')
                return
    except Exception as e:
        print(f'Could not check engine: {e}')

    # Count existing rows
    try:
        rows = client.query(f'SELECT count() FROM {table}')
        count = rows.result_rows[0][0] if rows and rows.result_rows else 0
        print(f'Existing rows: {count}')
    except Exception:
        count = 0
        print('Table does not exist yet, will create fresh.')

    # Drop and recreate
    print(f'Dropping table {table}...')
    client.command(f'DROP TABLE IF EXISTS {table}')

    print(f'Creating {table} with ReplacingMergeTree...')
    client.command(f'''
        CREATE TABLE IF NOT EXISTS {table} (
            event_id         String,
            project_id       UInt32,
            user_id          String,
            event_name       String,
            properties       String,
            ip_address       String,
            user_agent       String,
            timestamp        DateTime64(6),
            created_at       DateTime64(6)
        ) ENGINE = ReplacingMergeTree(created_at)
        ORDER BY (project_id, user_id, timestamp, event_id)
    ''')

    print('Migration complete!')
    if count > 0 and project_id:
        print(f'\nReplay data through Kafka:')
        print(f'  python ml/seed_to_kafka.py --project_id {project_id}')
    elif count > 0:
        print(f'\n{count} rows were dropped. Re-sync data through Kafka (see seed_to_kafka.py).')


if __name__ == '__main__':
    pa = argparse.ArgumentParser()
    pa.add_argument('--project_id', type=int, default=None,
                    help='Project ID for re-sync hint')
    args = pa.parse_args()
    migrate(args.project_id)
