import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


class EventProducer:
    def __init__(self):
        self._producer = None

    def _lazy_init(self):
        if self._producer is not None:
            return
        cfg = getattr(settings, 'KAFKA', {})
        bootstrap = cfg.get('BOOTSTRAP_SERVERS', 'localhost:9092')
        try:
            from confluent_kafka import Producer
            self._producer = Producer({'bootstrap.servers': bootstrap})
            self._topic = cfg.get('TOPIC_EVENTS', 'events')
        except Exception as e:
            logger.warning('Kafka producer init failed: %s', e)
            self._producer = False

    @property
    def available(self):
        self._lazy_init()
        return self._producer not in (None, False)

    def produce(self, event_data):
        if not self.available:
            logger.warning('Kafka unavailable, event dropped')
            return
        try:
            self._producer.produce(
                self._topic,
                key=str(event_data.get('project_id', '')),
                value=json.dumps(event_data, default=str).encode(),
                callback=self._delivery_report,
            )
            self._producer.poll(0)
        except Exception as e:
            logger.error('Kafka produce failed: %s', e)

    def flush(self):
        if self._producer not in (None, False):
            self._producer.flush()

    @staticmethod
    def _delivery_report(err, msg):
        if err:
            logger.error('Kafka delivery failed: %s', err)


producer = EventProducer()
