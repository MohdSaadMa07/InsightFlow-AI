"""Debug v3: longer delays, check consumer group"""
import json, time
from confluent_kafka import Consumer, Producer

group = 'debug_group_03'
c = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': group,
    'auto.offset.reset': 'latest',
    'enable.auto.commit': False,
})
c.subscribe(['events'])
time.sleep(5)

pid = Producer({'bootstrap.servers': 'localhost:9092'})
pid.produce('events', key='dbg3', value='{"user_id":"debug_connect_03"}')
pid.flush(5)
print('Produced')

time.sleep(5)

found = False
for i in range(20):
    m = c.poll(1.0)
    if m is None:
        continue
    if m.error():
        print(f'poll {i}: error {m.error()}')
        continue
    data = json.loads(m.value().decode())
    print(f'poll {i}: {data.get("user_id")}')
    if data.get('user_id') == 'debug_connect_03':
        found = True
        break
c.close()
print('FOUND!' if found else 'NOT FOUND')
