import json
from copy import deepcopy
from datetime import datetime, date as date_type

from django.db import models
from django.db.models import Q

from events.bigquery import bq


class FakeEvent:
    """Minimal object returned by BigQuery path for .create() and .get()."""

    def __init__(self, data):
        self.id = data.get('event_id') or data.get('id')
        self.project_id = data.get('project_id')
        self.user_id = data.get('user_id', '')
        self.event_name = data.get('event_name', '')
        self.properties = data.get('properties', '{}')
        self.timestamp = data.get('timestamp')
        self._data = data

    def __repr__(self):
        return f'<FakeEvent: {self.event_name}>'


class EventBigQueryQuerySet:
    """
    Translates Django-ORM chained queries to BigQuery SQL.

    Supports the subset of operations used across the codebase.
    Falls back to Django ORM when BigQuery is not configured.
    """

    FIELD_MAP = {
        'id': 'event_id',
        'project_id': 'project_id',
        'user_id': 'user_id',
        'event_name': 'event_name',
        'properties': 'properties',
        'timestamp': 'timestamp',
        'created_at': 'created_at',
    }
    REV_FIELD_MAP = {v: k for k, v in FIELD_MAP.items()}

    def __init__(self, model=None, using=None):
        self._model = model
        self._db = using
        self._filters = {}
        self._exclude_pairs = []
        self._select_fields = None
        self._flat = False
        self._distinct = False
        self._limit = None
        self._offset = 0
        self._ordering = []
        self._select_related_fields = None

    def _clone(self):
        c = EventBigQueryQuerySet(model=self._model, using=self._db)
        c._filters = deepcopy(self._filters)
        c._exclude_pairs = deepcopy(self._exclude_pairs)
        c._select_fields = self._select_fields
        c._flat = self._flat
        c._distinct = self._distinct
        c._limit = self._limit
        c._offset = self._offset
        c._ordering = list(self._ordering)
        c._select_related_fields = self._select_related_fields
        return c

    def _using(self, db):
        c = self._clone()
        c._db = db
        return c

    def filter(self, **kwargs):
        c = self._clone()
        c._filters.update(kwargs)
        return c

    def exclude(self, *args, **kwargs):
        c = self._clone()
        if args:
            for a in args:
                if isinstance(a, Q):
                    for child in a.children:
                        c._exclude_pairs.append((child[0], child[1], a.connector))
                else:
                    c._exclude_pairs.append((None, a, 'AND'))
        if kwargs:
            for k, v in kwargs.items():
                c._exclude_pairs.append((k, v, 'AND'))
        return c

    def select_related(self, *fields):
        c = self._clone()
        c._select_related_fields = fields
        return c

    def values_list(self, *fields, flat=False):
        c = self._clone()
        c._select_fields = list(fields) if fields else None
        c._flat = flat
        return c

    def values(self, *fields):
        c = self._clone()
        c._select_fields = list(fields) if fields else None
        c._flat = False
        return c

    def distinct(self):
        c = self._clone()
        c._distinct = True
        return c

    def order_by(self, *fields):
        c = self._clone()
        c._ordering = list(fields)
        return c

    def count(self):
        if not bq.available:
            return self._fallback_qs().count()
        return self._run_count()

    def get(self, **kwargs):
        if not bq.available:
            return self._fallback_qs().get(**kwargs)
        c = self.filter(**kwargs)
        c._limit = 1
        rows = c._run_select()
        if not rows:
            raise self._model.DoesNotExist(
                f'{self._model.__name__} matching query does not exist.'
            )
        return self._row_to_obj(rows[0])

    def first(self):
        rows = self[:1]
        return rows[0] if rows else None

    def __getitem__(self, key):
        if isinstance(key, slice):
            c = self._clone()
            c._limit = key.stop
            c._offset = key.start or 0
            return c._run_select()
        return self._run_select()[key]

    def __iter__(self):
        return iter(self._run_select())

    def __len__(self):
        return self.count()

    def create(self, **kwargs):
        if bq.available:
            row = {
                'project_id': getattr(kwargs.get('project'), 'id', None) if not isinstance(kwargs.get('project'), int) else kwargs['project'],
                'user_id': kwargs.get('user_id', '') or '',
                'event_name': kwargs.get('event_name', ''),
                'properties': json.dumps(kwargs.get('properties', {})),
                'timestamp': self._to_iso(kwargs.get('timestamp')),
            }
            bq.insert_rows([row])
            return FakeEvent(row)
        return self._model.objects.db_manager(self._db).create(**kwargs)

    # -- internals --

    def _to_iso(self, v):
        if hasattr(v, 'isoformat'):
            return v.isoformat()
        return str(v)

    def _col(self, django_name):
        return self.FIELD_MAP.get(django_name, django_name)

    def _run_count(self):
        cols = '*'
        if self._distinct and self._select_fields:
            cols = 'DISTINCT ' + ', '.join(
                self._col(f) for f in self._select_fields if self._col(f) != 'event_id'
            ) or 'event_id'

        where, params = self._build_where()
        sql = f'SELECT COUNT({cols}) FROM `{bq.table()}` WHERE {where}'
        client = bq.get_client()
        job = client.query(sql, job_config=self._make_config(params))
        return list(job)[0][0]

    def _run_select(self):
        if not bq.available:
            return list(self._fallback_qs())

        select = 'SELECT *'
        if self._select_fields:
            cols = ', '.join(self._col(f) for f in self._select_fields)
            if self._distinct:
                select = f'SELECT DISTINCT {cols}'
            else:
                select = f'SELECT {cols}'
        elif self._distinct:
            select = 'SELECT DISTINCT *'

        where, params = self._build_where()
        sql = f'{select} FROM `{bq.table()}` WHERE {where}'

        if self._ordering:
            sql += ' ORDER BY ' + ', '.join(
                ('-' + self._col(f[1:])) if f.startswith('-') else self._col(f)
                for f in self._ordering
            )
        if self._limit is not None:
            sql += f' LIMIT {self._limit}'
            if self._offset:
                sql += f' OFFSET {self._offset}'

        client = bq.get_client()
        job = client.query(sql, job_config=self._make_config(params))
        raw = [dict(r) for r in job]

        if self._flat and self._select_fields and len(self._select_fields) == 1:
            col = self._col(self._select_fields[0])
            return [r.get(col) for r in raw]

        if self._select_fields:
            return [{k: r.get(self._col(k)) for k in self._select_fields} for r in raw]

        return [self._row_to_obj(r) for r in raw]

    def _row_to_obj(self, row):
        mapped = {}
        for bq_col, val in row.items():
            django_key = self.REV_FIELD_MAP.get(bq_col, bq_col)
            mapped[django_key] = val
        return FakeEvent(mapped)

    def _build_where(self):
        clauses = []
        params = {}
        idx = [0]

        def add(expr, val):
            idx[0] += 1
            p = f'p{idx[0]}'
            clauses.append(f'{expr} @{p}')
            params[p] = val

        def add_raw(expr):
            clauses.append(expr)

        def in_clause(col, vals):
            idx[0] += 1
            p = f'p{idx[0]}'
            items = ', '.join(f'@{p}_{i}' for i in range(len(vals)))
            clauses.append(f'{col} IN ({items})')
            for i, v in enumerate(vals):
                params[f'{p}_{i}'] = self._to_iso(v) if isinstance(v, (datetime, date_type)) else v

        # filters
        for key, val in self._filters.items():
            if key == 'project':
                add('project_id =', val.id if hasattr(val, 'id') else val)
            elif key == 'project_id':
                add('project_id =', val)
            elif key == 'event_name':
                add('event_name =', val)
            elif key == 'event_name__in':
                in_clause('event_name', list(val) if not isinstance(val, (set, list)) else val)
            elif key == 'timestamp__date__gte':
                add('timestamp >=', val.isoformat() if hasattr(val, 'isoformat') else val)
            elif key == 'timestamp__date':
                add('DATE(timestamp) =', val.isoformat() if hasattr(val, 'isoformat') else val)
            elif key == 'timestamp__gte':
                add('timestamp >=', val.isoformat() if hasattr(val, 'isoformat') else val)
            elif key == 'timestamp__lte':
                add('timestamp <=', val.isoformat() if hasattr(val, 'isoformat') else val)
            elif key == 'id':
                add('event_id =', val)
            else:
                add(f'{key} =', val)

        # excludes
        for field, val, connector in self._exclude_pairs:
            if field == 'user_id__isnull' and val is True:
                add_raw('user_id IS NOT NULL')
            elif field == 'user_id' and val == '':
                add_raw("user_id != ''")
            elif field is None and isinstance(val, Q):
                children = []
                for child_field, child_val in val.children:
                    if child_field == 'user_id__isnull' and child_val is True:
                        children.append('user_id IS NOT NULL')
                    elif child_field == 'user_id' and child_val == '':
                        children.append("user_id != ''")
                    else:
                        children.append(f'{child_field} IS NOT NULL')
                if children:
                    joiner = ' AND ' if val.connector == Q.AND else ' OR '
                    add_raw(f'NOT ({joiner.join(children)})')
            else:
                add(f'{field} !=', val)

        return ' AND '.join(clauses) if clauses else 'TRUE', params

    def _make_config(self, params):
        from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter
        if not params:
            return QueryJobConfig()
        qp = []
        for name, val in params.items():
            if isinstance(val, bool):
                t = 'BOOL'
            elif isinstance(val, int):
                t = 'INT64'
            elif isinstance(val, float):
                t = 'FLOAT64'
            else:
                t = 'STRING'
            qp.append(ScalarQueryParameter(name, t, val))
        return QueryJobConfig(query_parameters=qp)

    def _fallback_qs(self):
        qs = self._model.objects.db_manager(self._db).all()
        for key, val in self._filters.items():
            qs = qs.filter(**{key: val})
        for field, val, connector in self._exclude_pairs:
            if field is None and isinstance(val, Q):
                qs = qs.exclude(val)
            elif field:
                qs = qs.exclude(**{field: val})
        if self._select_fields:
            if self._flat and len(self._select_fields) == 1:
                qs = qs.values_list(*self._select_fields, flat=True)
            else:
                qs = qs.values_list(*self._select_fields, flat=self._flat)
        if self._distinct:
            qs = qs.distinct()
        if self._ordering:
            qs = qs.order_by(*self._ordering)
        if self._select_related_fields:
            qs = qs.select_related(*self._select_related_fields)
        if self._limit is not None:
            qs = qs[self._offset:self._offset + self._limit]
        return qs

    def __repr__(self):
        return f'<EventBigQueryQuerySet bigquery={bq.available}>'


class EventManager(models.Manager):
    """Manager that routes queries to BigQuery when the service is available."""

    def get_queryset(self):
        if bq.available:
            return EventBigQueryQuerySet(model=self.model, using=self._db)
        return super().get_queryset()

    def create(self, **kwargs):
        if bq.available:
            return EventBigQueryQuerySet(model=self.model).create(**kwargs)
        return super().create(**kwargs)

    def filter(self, **kwargs):
        return self.get_queryset().filter(**kwargs)

    def exclude(self, *args, **kwargs):
        return self.get_queryset().exclude(*args, **kwargs)

    def get(self, **kwargs):
        return self.get_queryset().get(**kwargs)

    def select_related(self, *fields):
        return self.get_queryset().select_related(*fields)

    def count(self):
        return self.get_queryset().count()

    def first(self):
        return self.get_queryset().first()

    def order_by(self, *fields):
        return self.get_queryset().order_by(*fields)

    def values_list(self, *fields, flat=False):
        return self.get_queryset().values_list(*fields, flat=flat)

    def values(self, *fields):
        return self.get_queryset().values(*fields)

    def distinct(self):
        return self.get_queryset().distinct()

    def using(self, db):
        c = self.get_queryset()
        c._db = db
        return c
