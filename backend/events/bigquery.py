import json
from copy import deepcopy

from django.conf import settings


class BigQueryService:
    """Thin wrapper around google-cloud-bigquery for event data."""

    def __init__(self):
        self._client = None
        self._table_ref = None

    def _lazy_init(self):
        if self._client is not None:
            return
        import os
        if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
            self._client = False
            return
        from google.cloud import bigquery
        bq_cfg = getattr(settings, 'BIGQUERY', {})
        ds = bq_cfg.get('DATASET', 'insightflow')
        tbl = bq_cfg.get('TABLE', 'events')
        project = os.getenv('BQ_PROJECT', '')
        self._client = bigquery.Client(project=project) if project else bigquery.Client()
        self._table_ref = f'{project}.{ds}.{tbl}' if project else f'{ds}.{tbl}'

    @property
    def available(self):
        self._lazy_init()
        return self._client not in (None, False)

    def get_client(self):
        self._lazy_init()
        return self._client if self._client not in (None, False) else None

    def table(self):
        self._lazy_init()
        return self._table_ref

    def insert_rows(self, rows):
        """Insert a list of dict rows into the BigQuery events table."""
        if not self.available:
            return
        client = self.get_client()
        errors = client.insert_rows_json(self._table_ref, rows)
        if errors:
            raise Exception(f'BigQuery insert errors: {errors}')


# Module-level singleton
bq = BigQueryService()
