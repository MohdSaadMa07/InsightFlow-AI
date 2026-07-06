import json
import random
import uuid
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

from users.models import Organization
from projects.models import Project, APIKey
from events.clickhouse import ch
from analytics.models import DailyRevenue

User = get_user_model()

SEED = 42
random.seed(SEED)

EVENT_NAMES = [
    '$pageview', 'signup', 'login', 'view_product', 'add_to_cart',
    'purchase', 'subscription_created', 'subscription_cancelled',
    'feature_used', 'error_occurred',
]

PAGES = ['/home', '/pricing', '/dashboard', '/settings', '/features', '/docs', '/blog', '/about', '/contact', '/login']
PRODUCTS = [
    {'id': 'prod_basic', 'name': 'Basic Plan', 'price': 19.99, 'category': 'subscription'},
    {'id': 'prod_pro', 'name': 'Pro Plan', 'price': 49.99, 'category': 'subscription'},
    {'id': 'prod_enterprise', 'name': 'Enterprise', 'price': 149.99, 'category': 'subscription'},
    {'id': 'prod_addon_storage', 'name': 'Extra Storage', 'price': 9.99, 'category': 'addon'},
    {'id': 'prod_addon_seats', 'name': 'Extra Seats', 'price': 14.99, 'category': 'addon'},
]

FEATURES = ['export_csv', 'api_access', 'team_collab', 'custom_reports', 'webhook_integration', 'audit_log']
ERROR_TYPES = ['api_timeout', 'validation_error', 'auth_failed', 'rate_limited', 'server_error']

PLANS = ['free', 'basic', 'pro', 'enterprise']

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
]

IPS = ['192.168.1.100', '10.0.0.45', '172.16.0.88', '203.0.113.42', '198.51.100.7', '185.220.101.23', '91.108.56.100', '78.46.89.12', '5.255.84.12', '46.229.168.137']


def generate_event(project_id, user_id, event_name, properties, base_time):
    return {
        'event_id': str(uuid.uuid4()),
        'project_id': project_id,
        'user_id': user_id,
        'event_name': event_name,
        'properties': json.dumps(properties),
        'ip_address': random.choice(IPS),
        'user_agent': random.choice(USER_AGENTS),
        'timestamp': base_time.isoformat(),
        'created_at': base_time.isoformat(),
    }


def user_session_events(project_id, user, base_date, activity_level=1.0):
    events = []
    sessions_per_day = max(1, round(random.gauss(activity_level * 2, 0.5)))
    for _ in range(sessions_per_day):
        session_start = base_date + timedelta(
            hours=random.gauss(14, 3),
            minutes=random.randint(0, 59),
            seconds=random.randint(0, 59),
        )
        if session_start.hour < 0 or session_start.hour > 23:
            continue

        pageview = generate_event(project_id, user['id'], '$pageview', {
            'url': random.choice(PAGES),
            'referrer': random.choice(['https://google.com', 'https://twitter.com', 'https://github.com', '', '']),
        }, session_start)
        events.append(pageview)

        if user.get('behavior') == 'churning' and random.random() < 0.85:
            continue

        if random.random() < 0.3 * activity_level:
            events.append(generate_event(project_id, user['id'], 'feature_used', {
                'feature': random.choice(FEATURES),
                'source': random.choice(['dashboard', 'settings', 'api']),
            }, session_start + timedelta(seconds=random.randint(5, 120))))

        if random.random() < 0.05 * activity_level:
            events.append(generate_event(project_id, user['id'], 'error_occurred', {
                'error_type': random.choice(ERROR_TYPES),
                'endpoint': random.choice(['/api/query', '/api/export', '/api/auth']),
            }, session_start + timedelta(seconds=random.randint(10, 60))))

        if random.random() < 0.08 * activity_level:
            product = random.choice(PRODUCTS)
            events.append(generate_event(project_id, user['id'], 'purchase', {
                'product_id': product['id'],
                'product_name': product['name'],
                'price': product['price'],
                'currency': 'USD',
                'category': product['category'],
            }, session_start + timedelta(seconds=random.randint(20, 200))))

        if random.random() < 0.02 * activity_level:
            plan = random.choice(PLANS)
            events.append(generate_event(project_id, user['id'], 'subscription_created', {
                'plan': plan,
                'billing': 'monthly',
                'amount': {'free': 0, 'basic': 19.99, 'pro': 49.99, 'enterprise': 149.99}[plan],
            }, session_start + timedelta(seconds=random.randint(30, 180))))

    return events


class Command(BaseCommand):
    help = 'Seed demo data with realistic events, users, and ML predictions'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=60)
        parser.add_argument('--users', type=int, default=50)
        parser.add_argument('--skip-ml', action='store_true')

    def handle(self, *args, **options):
        days = options['days']
        num_users = options['users']
        t0 = datetime.utcnow()

        self.stdout.write('=== InsightFlow Demo Data Seeder ===\n')

        with transaction.atomic():
            org, _ = Organization.objects.get_or_create(
                name='Demo Company',
                defaults={'slug': 'demo-company'}
            )

            demo_user = User.objects.filter(username='demo').first()
            if not demo_user:
                demo_user = User.objects.create_user(
                    username='demo', email='demo@example.com',
                    password='demo123456', organization=org, role='admin'
                )
                self.stdout.write(f'  Created user: demo / demo123456')
            else:
                self.stdout.write(f'  User "demo" already exists')

            project, _ = Project.objects.get_or_create(
                organization=org, name='Demo SaaS App'
            )
            api_key_obj, _ = APIKey.objects.get_or_create(
                project=project, name='Default'
            )
            project_id = project.id

        self.stdout.write(f'  Project ID: {project_id}')
        self.stdout.write(f'  API Key: {api_key_obj.key}\n')

        if not ch.available:
            self.stderr.write('ERROR: ClickHouse not available')
            return

        self.stdout.write('Generating users and events...')

        user_profiles = []
        for i in range(num_users):
            behavior = 'active' if random.random() < 0.6 else ('churning' if random.random() < 0.5 else 'casual')
            activity = {
                'active': 1.0 + random.gauss(0, 0.3),
                'casual': 0.3 + random.gauss(0, 0.15),
                'churning': 0.1 + random.gauss(0, 0.08),
            }[behavior]
            user_profiles.append({
                'id': f'demo_user_{i:03d}',
                'behavior': behavior,
                'activity': max(0.05, activity),
            })

        batch = []
        for day_offset in range(days):
            base_date = t0 - timedelta(days=days - day_offset)
            for user in user_profiles:
                if random.random() < 0.05:
                    continue
                session_events = user_session_events(project_id, user, base_date, user['activity'])
                batch.extend(session_events)

                if len(batch) >= 500:
                    ch.insert_rows(batch)
                    batch = []

        if batch:
            ch.insert_rows(batch)

        self.stdout.write(f'  Events inserted into ClickHouse for {num_users} users over {days} days\n')

        self.stdout.write('Computing daily revenue aggregates...')
        try:
            from analytics.clickhouse_revenue import aggregate_daily_revenue
            aggregate_daily_revenue(project_id, days=days)
            self.stdout.write('  Daily revenue aggregates computed\n')
        except Exception as e:
            self.stdout.write(f'  Revenue aggregation: {e}\n')

        if not options['skip_ml']:
            self.stdout.write('Running churn predictions...')
            try:
                from ml.services.churn_risk import churn_risk
                if churn_risk.load():
                    predictions = churn_risk.predict_all(project_id)
                    if predictions:
                        self.stdout.write(f'  Churn predictions: {len(predictions)} users scored')
                        overview = churn_risk.get_overview(predictions)
                        self.stdout.write(f"    High risk: {overview['high_risk']} Medium: {overview['medium_risk']} Low: {overview['low_risk']}")
                else:
                    self.stdout.write('  Churn model not available, skipping')
            except Exception as e:
                self.stdout.write(f'  Churn prediction error: {e}')

            self.stdout.write('Running anomaly detection...')
            try:
                from ml.services.anomaly_detection import anomaly_detection
                result = anomaly_detection.get_summary(project_id, days=14, store_incidents=True)
                if result:
                    self.stdout.write(f"  Anomaly summary: {result.get('anomaly_count', 0)} anomalies, rate: {result.get('anomaly_rate', 0):.3f}")
            except Exception as e:
                self.stdout.write(f'  Anomaly detection error: {e}')

            self.stdout.write('Computing revenue forecast...')
            try:
                from ml.services.revenue_forecast import revenue_forecast
                forecast = revenue_forecast.predict(project_id, horizon=30)
                if forecast:
                    self.stdout.write(f'  Revenue forecast generated')
            except Exception as e:
                self.stdout.write(f'  Revenue forecast error: {e}')

        self.stdout.write(f'\n=== Demo setup complete in {(datetime.utcnow() - t0).total_seconds():.1f}s ===')
        self.stdout.write(f'Login: demo / demo123456')
        self.stdout.write(f'Project: {project.name} (ID: {project_id})')
