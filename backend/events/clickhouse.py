from datetime import datetime

from django.conf import settings


class ClickHouseService:
    def __init__(self):
        self._client = None

    def _lazy_init(self):
        if self._client is not None:
            return
        cfg = getattr(settings, 'CLICKHOUSE', {})
        host = cfg.get('HOST', 'localhost')
        port = cfg.get('PORT', 8123)
        username = cfg.get('USER', 'default')
        password = cfg.get('PASSWORD', '')
        database = cfg.get('DATABASE', 'insightflow')
        try:
            from clickhouse_connect import get_client
            self._client = get_client(
                host=host, port=port, username=username,
                password=password, connect_timeout=5,
            )
            self._database = database
            self._table = cfg.get('TABLE', 'events')
            self._client.command(f'CREATE DATABASE IF NOT EXISTS {database}')
            self._ensure_table()
        except Exception:
            self._client = False

    def _ensure_table(self):
        self._client.command(f'''
            CREATE TABLE IF NOT EXISTS {self._database}.{self._table} (
                event_id         String,
                project_id       UInt32,
                user_id          String,
                event_name       String,
                properties       String,
                ip_address       String,
                user_agent       String,
                timestamp        DateTime64(6),
                created_at       DateTime64(6)
            ) ENGINE = MergeTree()
            ORDER BY (project_id, event_name, timestamp)
        ''')

    @property
    def available(self):
        self._lazy_init()
        return self._client not in (None, False)

    def get_client(self):
        self._lazy_init()
        return self._client if self._client not in (None, False) else None

    @property
    def table_ref(self):
        self._lazy_init()
        if self._client:
            return f'{self._database}.{self._table}'
        return None

    def _to_dt(self, val):
        if val is None:
            return None
        if isinstance(val, datetime):
            if val.tzinfo is not None:
                val = val.replace(tzinfo=None)
            return val
        if isinstance(val, str):
            for fmt in [
                '%Y-%m-%dT%H:%M:%S.%f',
                '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%d %H:%M:%S.%f',
                '%Y-%m-%d %H:%M:%S',
            ]:
                try:
                    return datetime.strptime(val[:26], fmt)
                except ValueError:
                    continue
        return None

    def insert_rows(self, rows):
        if not self.available:
            return
        client = self.get_client()
        now = datetime.utcnow()
        data = []
        for row in rows:
            data.append((
                str(row.get('event_id', '')),
                int(row.get('project_id', 0)),
                row.get('user_id', ''),
                row.get('event_name', ''),
                row.get('properties', '{}'),
                row.get('ip_address', ''),
                row.get('user_agent', ''),
                self._to_dt(row.get('timestamp')) or now,
                self._to_dt(row.get('created_at')) or now,
            ))
        client.insert(
            self.table_ref,
            data,
            column_names=[
                'event_id', 'project_id', 'user_id', 'event_name',
                'properties', 'ip_address', 'user_agent',
                'timestamp', 'created_at',
            ],
        )


ch = ClickHouseService()
