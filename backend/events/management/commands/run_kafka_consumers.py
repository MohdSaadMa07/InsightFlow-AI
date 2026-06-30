import logging
import signal
import threading

from django.core.management.base import BaseCommand

from events.consumers import ClickHouseConsumer, AggregatorConsumer

logger = logging.getLogger(__name__)

running = True


def handle_signal(signum, frame):
    global running
    running = False


class Command(BaseCommand):
    help = 'Runs Kafka consumers for ClickHouse and aggregator'

    def handle(self, *args, **options):
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        ch_consumer = ClickHouseConsumer()
        agg_consumer = AggregatorConsumer()

        threads = []

        def run_ch():
            ch_consumer.run()

        def run_agg():
            agg_consumer.run()

        t1 = threading.Thread(target=run_ch, daemon=True)
        t2 = threading.Thread(target=run_agg, daemon=True)
        threads.append(t1)
        threads.append(t2)

        self.stdout.write('Starting Kafka consumers...')
        t1.start()
        t2.start()

        try:
            while running:
                signal.pause()
        except AttributeError:
            import time
            while running:
                time.sleep(1)

        self.stdout.write('Shutting down consumers...')
