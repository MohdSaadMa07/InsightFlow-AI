import json
import logging
import time
from datetime import datetime

from django.conf import settings
from django.utils import timezone

from events.clickhouse import ch
from events.models import Event
from analytics.models import DailyActiveUser, EventCount

logger = logging.getLogger(__name__)


class ClickHouseConsumer:
    def __init__(self):
        self._consumer = None
        self._batch = []
        self._last_flush = 0

    def _lazy_init(self):
        if self._consumer is not None:
            return
        cfg = getattr(settings, 'KAFKA', {})
        try:
            from confluent_kafka import Consumer
            self._consumer = Consumer({
                'bootstrap.servers': cfg.get('BOOTSTRAP_SERVERS', 'localhost:9092'),
                'group.id': cfg.get('CONSUMER_GROUP_CLICKHOUSE', 'insightflow.clickhouse'),
                'auto.offset.reset': 'earliest',
                'enable.auto.commit': False,
            })
            self._topic = cfg.get('TOPIC_EVENTS', 'events')
            self._batch_size = cfg.get('BATCH_SIZE', 1000)
            self._batch_interval = cfg.get('BATCH_INTERVAL_MS', 500) / 1000
            self._consumer.subscribe([self._topic])
        except Exception as e:
            logger.error('ClickHouse consumer init failed: %s', e)
            self._consumer = False

    @property
    def available(self):
        self._lazy_init()
        return self._consumer not in (None, False)

    def _flush(self):
        if not self._batch:
            return
        if ch.available:
            ch.insert_rows(self._batch)
            logger.info('Flushed %d events to ClickHouse', len(self._batch))
        self._batch = []
        self._last_flush = time.time()

    def run(self):
        if not self.available:
            logger.error('ClickHouse consumer not available')
            return
        self._last_flush = time.time()
        try:
            while True:
                msg = self._consumer.poll(1.0)
                if msg is None:
                    now = time.time()
                    if self._batch and (now - self._last_flush) >= self._batch_interval:
                        self._flush()
                        self._consumer.commit(asynchronous=False)
                    continue
                if msg.error():
                    logger.error('Consumer error: %s', msg.error())
                    continue
                try:
                    data = json.loads(msg.value().decode())
                    props = data.get('properties', '{}')
                    if not isinstance(props, str):
                        props = json.dumps(props)
                    self._batch.append({
                        'event_id': str(data.get('event_id', '')),
                        'project_id': int(data.get('project_id', 0)),
                        'user_id': data.get('user_id', ''),
                        'event_name': data.get('event_name', ''),
                        'properties': props,
                        'ip_address': data.get('ip_address', ''),
                        'user_agent': data.get('user_agent', ''),
                        'timestamp': data.get('timestamp', ''),
                    })
                    if len(self._batch) >= self._batch_size:
                        self._flush()
                        self._consumer.commit(asynchronous=False)
                except Exception as e:
                    logger.error('Error processing message: %s', e)
        finally:
            try:
                self._flush()
            except Exception as e:
                logger.error('Error flushing on shutdown: %s', e)
            self._consumer.close()


class AggregatorConsumer:
    def __init__(self):
        self._consumer = None

    def _lazy_init(self):
        if self._consumer is not None:
            return
        cfg = getattr(settings, 'KAFKA', {})
        try:
            from confluent_kafka import Consumer
            self._consumer = Consumer({
                'bootstrap.servers': cfg.get('BOOTSTRAP_SERVERS', 'localhost:9092'),
                'group.id': cfg.get('CONSUMER_GROUP_AGG', 'insightflow.aggregator'),
                'auto.offset.reset': 'earliest',
                'enable.auto.commit': True,
            })
            self._topic = cfg.get('TOPIC_EVENTS', 'events')
            self._consumer.subscribe([self._topic])
        except Exception as e:
            logger.error('Aggregator consumer init failed: %s', e)
            self._consumer = False

    @property
    def available(self):
        self._lazy_init()
        return self._consumer not in (None, False)

    def run(self):
        if not self.available:
            logger.error('Aggregator consumer not available')
            return
        try:
            while True:
                msg = self._consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    logger.error('Consumer error: %s', msg.error())
                    continue
                try:
                    data = json.loads(msg.value().decode())
                    self._process(data)
                except Exception as e:
                    logger.error('Error processing message: %s', e)
        finally:
            self._consumer.close()

    def _process(self, data):
        project_id = int(data.get('project_id', 0))
        event_name = data.get('event_name', '')
        user_id = data.get('user_id', '')
        ts_str = data.get('timestamp', '')
        try:
            ts = datetime.fromisoformat(ts_str) if ts_str else timezone.now()
        except ValueError:
            ts = timezone.now()
        date = ts.date()

        from projects.models import Project
        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return

        DailyActiveUser.objects.update_or_create(
            project=project, date=date,
            defaults={'count': Event._base_manager.filter(project=project, timestamp__date=date).values('user_id').distinct().count()},
        )

        EventCount.objects.update_or_create(
            project=project, event_name=event_name, date=date,
            defaults={'count': Event._base_manager.filter(project=project, event_name=event_name, timestamp__date=date).count()},
        )
