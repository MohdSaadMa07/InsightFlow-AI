"""Test: consume from inside Docker"""
import json, time
from confluent_kafka import Consumer, Producer

# Produce first
pid = Producer({'bootstrap.servers': 'localhost:9092'})
pid.produce('events', key='docker_test', value='{"user_id":"docker_test_msg"}')
pid.flush(5)
print('1. Produced')

# Consume with known offset 212008+
c = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'docker_test_group',
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': False,
})
c.subscribe(['events'])

# Fast-forward through old messages
skipped = 0
found = False
for i in range(500):
    m = c.poll(0.5)
    if m is None:
        continue
    if m.error():
        continue
    data = json.loads(m.value().decode())
    if data.get('user_id') == 'docker_test_msg':
        found = True
        print(f'2. Found after {skipped} skips')
        break
    skipped += 1
    if skipped % 100 == 0:
        print(f'  skipped {skipped}')

c.close()
if not found:
    print(f'2. Not found after {skipped} skips')
print('3. Done')
