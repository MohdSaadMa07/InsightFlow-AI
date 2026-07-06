import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-dev-key-change-in-production')

DEBUG = os.getenv('DJANGO_DEBUG', 'True').lower() == 'true'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '*').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third party
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    # Local apps
    'users',
    'projects',
    'events',
    'analytics',
    'api',
    'dashboard',
    'semantic',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Anomaly severity thresholds (ratio = reconstruction_error / threshold)
ANOMALY_SEVERITY_THRESHOLDS = {
    'low': 1.0,      # ratio >= 1.0
    'medium': 1.2,   # ratio >= 1.2
    'high': 1.5,     # ratio >= 1.5
    'critical': 2.0, # ratio >= 2.0
}

DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    DATABASES = {'default': dj_database_url.parse(DATABASE_URL, ssl_require=True)}
else:
    DATABASES = {
        'default': {
            'ENGINE': os.getenv('DB_ENGINE', 'django.db.backends.sqlite3'),
            'NAME': os.getenv('DB_NAME', BASE_DIR / 'db.sqlite3'),
            'USER': os.getenv('DB_USER', ''),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', ''),
            'PORT': os.getenv('DB_PORT', ''),
            'OPTIONS': {
                'sslmode': os.getenv('DB_SSLMODE', 'disable'),
            },
        },
    }

DATABASE_ROUTERS = ['config.router.DatabaseRouter']

# ClickHouse config (used by events.clickhouse when ClickHouse is reachable)
CLICKHOUSE = {
    'HOST': os.getenv('CH_HOST', 'localhost'),
    'PORT': int(os.getenv('CH_PORT', '8123')),
    'USER': os.getenv('CH_USER', 'default'),
    'PASSWORD': os.getenv('CH_PASSWORD', ''),
    'DATABASE': os.getenv('CH_DATABASE', 'insightflow'),
    'TABLE': os.getenv('CH_TABLE', 'events'),
    'SECURE': os.getenv('CH_SECURE', 'false').lower() == 'true',
}

# Kafka config
KAFKA = {
    'BOOTSTRAP_SERVERS': os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092'),
    'TOPIC_EVENTS': os.getenv('KAFKA_TOPIC_EVENTS', 'events'),
    'CONSUMER_GROUP_CLICKHOUSE': os.getenv('KAFKA_CG_CLICKHOUSE', 'insightflow.clickhouse'),
    'CONSUMER_GROUP_AGG': os.getenv('KAFKA_CG_AGG', 'insightflow.aggregator'),
    'BATCH_SIZE': int(os.getenv('KAFKA_BATCH_SIZE', '1000')),
    'BATCH_INTERVAL_MS': int(os.getenv('KAFKA_BATCH_INTERVAL_MS', '500')),
}

AUTH_USER_MODEL = 'users.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# DRF
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}

# CORS
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', '').split(',') if os.getenv('CORS_ALLOWED_ORIGINS') else []

CSRF_TRUSTED_ORIGINS = os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if os.getenv('CSRF_TRUSTED_ORIGINS') else [
    'http://localhost:5173',
    'http://localhost:5174',
    'http://localhost:5175',
    'http://127.0.0.1:5173',
    'http://127.0.0.1:5174',
    'http://127.0.0.1:5175',
]

# Celery
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    'nightly-churn-pipeline': {
        'task': 'ml.tasks.nightly_pipeline',
        'schedule': crontab(hour=3, minute=0),  # 3 AM daily
        'args': (14, 500, False),
    },
    'nightly-revenue-aggregation': {
        'task': 'ml.tasks.nightly_revenue_aggregation',
        'schedule': crontab(hour=3, minute=30),  # 3:30 AM
        'args': (14,),
    },
    'nightly-revenue-forecast': {
        'task': 'ml.tasks.nightly_revenue_forecast',
        'schedule': crontab(hour=4, minute=0),  # 4 AM
        'args': (14, 30),
    },
}
