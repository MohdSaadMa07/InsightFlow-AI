"""Full pipeline E2E test: Kafka -> Consumer -> ClickHouse
   Ensures producer, consumer, and ClickHouse write all work in sequence."""
import os, sys, json, time, uuid

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
sys.path.insert(0, os.path.abspath('.'))
import django
django.setup()

from events.kafka import producer as event_producer
from events.clickhouse import ch
from confluent_kafka import Consumer
from django.conf import settings

test_id = str(uuid.uuid4())[:8]

# 1. Start consumer with latest offset (only new messages)
cfg = settings.KAFKA
consumer = Consumer({
    'bootstrap.servers': cfg['BOOTSTRAP_SERVERS'],
    'group.id': 'e2e_final_' + test_id,
    'auto.offset.reset': 'latest',
    'enable.auto.commit': False,
})
consumer.subscribe(['events'])

# Wait for partition assignment
assigned = False
for _ in range(10):
    consumer.poll(0.5)
    # Check if we got assignment by examining metadata
    metadata = consumer.committed([consumer.assignment()[0]]) if consumer.assignment() else []
    if consumer.assignment():
        assigned = True
        break

if not assigned:
    print('FAIL: Consumer never assigned partition')
    consumer.close()
    exit(1)

# 2. Produce event
event_producer.produce({
    'event_id': str(uuid.uuid4()),
    'project_id': 11,
    'user_id': 'e2e_final_' + test_id,
    'event_name': 'e2e_final_test',
    'properties': '{}',
    'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S.000000', time.gmtime()),
    'created_at': time.strftime('%Y-%m-%dT%H:%M:%S.000000', time.gmtime()),
})
event_producer.flush()
print('1. Produced to Kafka')

# 3. Consume
found = None
for _ in range(15):
    m = consumer.poll(1.0)
    if m and not m.error():
        data = json.loads(m.value().decode())
        if data.get('user_id') == 'e2e_final_' + test_id:
            found = data
            break
consumer.close()

if not found:
    print('2. FAIL - message not consumed from Kafka')
    exit(1)
print('2. Consumed from Kafka')

# 4. Write to ClickHouse
ch.insert_rows([{
    'event_id': str(found['event_id']),
    'project_id': int(found['project_id']),
    'user_id': found['user_id'],
    'event_name': found['event_name'],
    'properties': found.get('properties', '{}'),
    'timestamp': found.get('timestamp'),
    'created_at': found.get('created_at'),
}])

# 5. Verify in ClickHouse
rows = ch._client.query(
    "SELECT count(1) FROM insightflow.events WHERE user_id = 'e2e_final_%s'" % test_id
).result_rows[0][0]

print('3. In ClickHouse: %d rows' % rows)

if rows > 0:
    print('4. PASS - Full pipeline verified')
else:
    print('4. FAIL - event not in ClickHouse')
