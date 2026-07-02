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

        pages = ['/home', '/products', '/pricing', '/blog', '/docs', '/about', '/contact', '/signup', '/features', '/login']
        languages = ['en-US', 'en-GB', 'es', 'fr', 'de', 'pt-BR', 'ja', 'en-CA', 'it', 'nl']
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/605.1.15 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148',
            'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/120.0.6099.144 Mobile Safari/537.36',
            'Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        ]
        session_id = f'session_{uid}_{day_offset}_{rng.randint(10000, 99999)}'
        lang = rng.choice(languages)
        ua = rng.choice(user_agents)

        for step_idx, event_name in enumerate(session_seq):
            ts = base_ts + timedelta(seconds=step_idx * rng.randint(3, 60))
            props = {
                'seed': True,
                'session_step': step_idx + 1,
                '$session_id': session_id,
                '$language': lang,
                '$user_agent': ua,
                '$screen_width': rng.choice([1920, 1440, 1366, 768, 390, 414]),
                '$screen_height': rng.choice([1080, 900, 768, 1024, 844, 896]),
            }
            if event_name == 'pageview':
                props['url'] = rng.choice(pages)
            batch.append(Event(
                project=project,
                user_id=uid,
                event_name=event_name,
                properties=props,
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

print()
print('Computing analytics...')

today = datetime.utcnow().date()
from analytics.models import DailyActiveUser, EventCount, RetentionCurve

# DailyActiveUser + EventCount for each day
for day_offset in range(90):
    date = today - timedelta(days=day_offset)
    dau = Event.objects.filter(
        project=project, timestamp__date=date
    ).values('user_id').distinct().count()
    DailyActiveUser.objects.update_or_create(
        project=project, date=date, defaults={'count': dau}
    )
    for name in event_names:
        cnt = Event.objects.filter(
            project=project, event_name=name, timestamp__date=date
        ).count()
        if cnt > 0:
            EventCount.objects.update_or_create(
                project=project, event_name=name, date=date,
                defaults={'count': cnt}
            )

# RetentionCurve for each day
for day_offset in range(90):
    check_date = today - timedelta(days=day_offset)
    for period_days, label in [(1, 'D1'), (7, 'D7'), (30, 'D30')]:
        cohort_date = check_date - timedelta(days=period_days)
        min_date = today - timedelta(days=90)
        if cohort_date < min_date:
            continue
        total = Event.objects.filter(
            project=project, timestamp__date=cohort_date
        ).values('user_id').distinct().count()
        if total == 0:
            continue
        retained = Event.objects.filter(
            project=project, timestamp__date=check_date,
            user_id__in=Event.objects.filter(
                project=project, timestamp__date=cohort_date
            ).values('user_id')
        ).values('user_id').distinct().count()
        if retained > 0:
            RetentionCurve.objects.update_or_create(
                project=project, cohort_date=cohort_date, period=label,
                defaults={
                    'total_users': total,
                    'retained_users': retained,
                    'rate': round(retained / total, 4),
                }
            )

dau_count = DailyActiveUser.objects.filter(project=project).count()
ec_count = EventCount.objects.filter(project=project).count()
rc_count = RetentionCurve.objects.filter(project=project).count()
print(f'Created {dau_count} DAU records, {ec_count} event count records, {rc_count} retention records')
