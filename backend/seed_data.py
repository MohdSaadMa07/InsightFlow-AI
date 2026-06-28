import django, os, random
from datetime import datetime, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.chdir(os.path.dirname(__file__))
django.setup()

from events.models import Event
from projects.models import Project, APIKey

project = Project.objects.get(name='fwfwf')
key = APIKey.objects.filter(project=project, is_active=True).first()
print(f'Project: {project.name} (key: {key.key[:16]}...)')

today = datetime.utcnow()
old_events = Event.objects.filter(project=project).count()
print(f'Existing events: {old_events}')

# Generate 90 days of events
users = {
    f'buyer_{i}': {
        'behavior': 'full',  # discover -> signup -> add_to_cart -> purchase
        'frequency': random.randint(3, 12),
    }
    for i in range(1, 11)
}
for i in range(1, 9):
    users[f'user_alice_{i}'] = {'behavior': 'bounce', 'frequency': random.randint(1, 5)}  # just pageviews, exit
for i in range(1, 9):
    users[f'user_bob_{i}'] = {'behavior': 'engage', 'frequency': random.randint(2, 8)}  # discover, signup, browse
for i in range(1, 7):
    users[f'user_charlie_{i}'] = {'behavior': 'cart_abandon', 'frequency': random.randint(2, 6)}  # discover, signup, add_to_cart, leave

event_names = ['pageview', 'view_product', 'signup', 'add_to_cart', 'purchase', 'exit']
weights = {
    'full': {
        'day': [('pageview', 40), ('view_product', 35), ('signup', 10), ('add_to_cart', 8), ('purchase', 5), ('exit', 2)],
        'session': ['pageview', 'view_product', 'signup', 'add_to_cart', 'purchase', 'exit'],
    },
    'bounce': {
        'day': [('pageview', 50), ('view_product', 40), ('exit', 10)],
        'session': ['pageview', 'view_product', 'exit'],
    },
    'engage': {
        'day': [('pageview', 30), ('view_product', 30), ('signup', 25), ('exit', 15)],
        'session': ['pageview', 'view_product', 'signup'],
    },
    'cart_abandon': {
        'day': [('pageview', 25), ('view_product', 25), ('signup', 20), ('add_to_cart', 20), ('exit', 10)],
        'session': ['pageview', 'view_product', 'signup', 'add_to_cart'],
    },
}

events = []
batch = []
for day_offset in range(90):
    date = today - timedelta(days=day_offset)
    seed = sum(ord(c) for c in f'{date}')
    rng = random.Random(seed)

    for uid, cfg in users.items():
        if rng.random() > cfg['frequency'] / 15:
            continue

        behavior = cfg['behavior']
        session_seq = weights[behavior]['session']

        # Each session starts at a random hour
        hour = rng.randint(6, 23)
        minute = rng.randint(0, 59)
        base_ts = date.replace(hour=hour, minute=minute)

        for step_idx, event_name in enumerate(session_seq):
            ts = base_ts + timedelta(seconds=step_idx * rng.randint(3, 60))
            batch.append(Event(
                project=project,
                user_id=uid,
                event_name=event_name,
                properties={'seed': True, 'session_step': step_idx + 1},
                timestamp=ts,
            ))

            if len(batch) >= 500:
                Event.objects.bulk_create(batch)
                events.extend(batch)
                batch = []

if batch:
    Event.objects.bulk_create(batch)
    events.extend(batch)

new_count = Event.objects.filter(project=project).count()
print(f'Created {len(events)} new events')
print(f'Total events: {new_count}')

from django.db.models import Count
for name in event_names:
    cnt = Event.objects.filter(project=project, event_name=name).count()
    users_cnt = Event.objects.filter(project=project, event_name=name).values('user_id').distinct().count()
    print(f'  {name:15s}: {cnt:4d} events, {users_cnt:3d} unique users')
