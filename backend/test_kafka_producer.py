from confluent_kafka import Producer
p = Producer({'bootstrap.servers': 'localhost:9092'})
p.produce('events', key='test', value='{"test":1,"user_id":"e2e_direct"}', callback=lambda err, msg: print(f'OK: p{msg.partition()}[{msg.offset()}]') if not err else print(f'ERR: {err}'))
p.flush(5)
print('Flush done')
