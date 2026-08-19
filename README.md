# InsightFlow AI

**Real-time product analytics with machine learning-powered insights**

InsightFlow AI is a full-stack analytics platform that ingests event data via an SDK, processes it through a Kafka pipeline into ClickHouse and PostgreSQL, and surfaces dashboards with ML-driven churn prediction, revenue forecasting, and anomaly detection.

---

## Architecture Overview

```
User's App/Browser
    │
    ├── InsightFlow SDK ──► POST /api/v1/track/ ──► Django ──► Kafka
    │                                                          │
    │                                              ┌───────────┴───────────┐
    │                                              ▼                       ▼
    │                                     ClickHouseConsumer     AggregatorConsumer
    │                                              │                       │
    │                                              ▼                       ▼
    │                                         ClickHouse              PostgreSQL
    │
    ├── Dashboard (React) ──► Django REST API ──► ClickHouse + PostgreSQL
    │
    └── Celery Beat (nightly)
            ├── Churn pipeline (PyTorch Transformer)
            ├── Revenue aggregation & forecast (Temporal Fusion Transformer)
            └── Anomaly detection (Autoencoder)
```

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Frontend** | React 18 + Vite + Recharts | Analytics dashboard with ML visualizations |
| **Backend** | Django 4.2 + DRF | REST API, auth, business logic |
| **Event Pipeline** | Apache Kafka | Buffered event ingestion |
| **Analytics DB** | ClickHouse | Columnar storage for fast aggregations |
| **Operational DB** | PostgreSQL (Supabase) | Users, projects, aggregated metrics |
| **Task Queue** | Redis + Celery | Async ML pipeline execution |
| **Reverse Proxy** | Caddy | TLS termination with auto Let's Encrypt |
| **Client SDK** | Vanilla JS (UMD) | Browser event tracking |
| **Deployment** | Docker Compose + Cloudflare Pages | Backend on AWS EC2, frontend on CF Pages |

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Node.js 18+

### Development

```bash
# 1. Start infrastructure (Kafka, ClickHouse, PostgreSQL)
docker compose up -d

# 2. Backend setup
cd backend
python -m venv venv
venv\Scripts\activate       # Windows
source venv/bin/activate    # Linux/Mac
pip install -r requirements.txt
pip install -r ml/requirements-ml.txt

# 3. Database migrations
cp ../.env.prod.example .env
python manage.py migrate

# 4. Run backend
python manage.py runserver

# 5. Frontend (separate terminal)
cd frontend
npm install
npm run dev                 # Opens on :5173, proxies /api to :8000
```

### Production

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

---

## Project Structure

```
InsightFlowAI/
├── backend/
│   ├── config/                  # Django project config
│   │   ├── settings.py          # All settings (DBs, Celery, CORS, etc.)
│   │   ├── urls.py              # Root URL routing
│   │   ├── wsgi.py              # WSGI app for Gunicorn
│   │   └── celery.py            # Celery app configuration
│   ├── users/                   # Authentication & user management
│   │   ├── models.py            # User (AbstractUser), Organization
│   │   ├── views.py             # signup, login, me endpoints
│   │   ├── serializers.py
│   │   ├── urls.py
│   │   └── authentication.py    # DRF Token auth
│   ├── projects/                # Project & API key management
│   │   ├── models.py            # Project, APIKey
│   │   ├── views.py
│   │   ├── serializers.py
│   │   └── urls.py
│   ├── events/                  # Event ingestion pipeline
│   │   ├── models.py            # Event model
│   │   ├── views.py             # Track endpoint
│   │   ├── kafka.py             # Kafka producer
│   │   ├── clickhouse.py        # ClickHouse service layer
│   │   ├── consumers.py         # Kafka → ClickHouse + Aggregator
│   │   ├── urls.py
│   │   └── management/commands/
│   │       └── run_kafka_consumers.py
│   ├── analytics/               # Aggregations & insights
│   │   ├── models.py            # DAU, EventCount, Funnel, Retention, Revenue
│   │   ├── clickhouse_revenue.py
│   │   └── insights.py          # ML-powered insight generation
│   ├── api/                     # Dashboard REST endpoints
│   │   ├── views.py             # overview, events, retention, funnels, etc.
│   │   └── urls.py
│   ├── dashboard/               # ML dashboard endpoints
│   │   ├── views.py             # churn, revenue, anomaly endpoints
│   │   ├── models.py            # AnomalyIncident
│   │   └── management/commands/
│   │       └── update_churn_cache.py
│   ├── semantic/                # Event mapping & categorization
│   │   ├── models.py            # EventMapping
│   │   ├── views.py             # detect, list, update, compute_funnel
│   │   └── urls.py
│   ├── ml/                      # Machine learning engine
│   │   ├── services/            # Inference services (singleton)
│   │   │   ├── churn_risk.py            # ChurnTransformerEnhanced
│   │   │   ├── anomaly_detection.py     # Autoencoder + heuristic
│   │   │   └── revenue_forecast.py      # TFT + heuristic
│   │   ├── models/              # ML model definitions
│   │   │   ├── transformers/
│   │   │   │   ├── churn_transformer.py
│   │   │   │   └── churn_transformer_enhanced.py
│   │   │   ├── classifiers/
│   │   │   │   ├── churn.py
│   │   │   │   └── funnel_conversion.py
│   │   │   ├── forecasting/
│   │   │   │   └── event_forecast.py
│   │   │   ├── baselines/
│   │   │   │   ├── heuristic.py
│   │   │   │   └── rules.py
│   │   │   └── registry.py
│   │   ├── inference/           # Model serving
│   │   │   ├── predictor.py
│   │   │   ├── batch.py
│   │   │   └── explainer.py
│   │   ├── preprocessing/       # Feature engineering
│   │   │   ├── features.py
│   │   │   ├── transformers.py
│   │   │   └── validators.py
│   │   ├── datasets/            # Data loading
│   │   │   ├── loader.py
│   │   │   ├── churn_loader.py
│   │   │   ├── churn_loader_enhanced.py
│   │   │   ├── revenue_loader.py
│   │   │   ├── schemas.py
│   │   │   └── versioning.py
│   │   └── tasks.py             # Celery tasks (nightly pipeline)
│   ├── requirements.txt
│   ├── ml/requirements-ml.txt
│   ├── Dockerfile
│   └── manage.py
├── frontend/
│   ├── src/
│   │   ├── api.js               # HTTP client (all API calls)
│   │   ├── App.jsx              # Router setup
│   │   ├── style.css            # Dark theme CSS
│   │   ├── main.jsx             # Entry point
│   │   └── pages/
│   │       ├── Landing.jsx            # Auth (login/signup)
│   │       ├── ProjectHub.jsx         # Project listing
│   │       ├── Dashboard.jsx          # Main analytics dashboard
│   │       ├── Funnels.jsx            # Funnel analysis
│   │       ├── ChurnDashboard.jsx     # Churn predictions
│   │       ├── RevenueForecast.jsx    # Revenue forecasting
│   │       ├── Mapping.jsx            # Semantic event mapping
│   │       ├── AnomalyMonitor.jsx     # Anomaly detection
│   │       ├── Settings.jsx           # API keys & project config
│   │       └── SystemHealth.jsx       # System monitoring
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── .env.production
├── sdk/
│   ├── package.json
│   └── insightflow.js           # Browser SDK (UMD, sendBeacon)
├── docker-compose.yml           # Dev services
├── docker-compose.prod.yml      # Production deployment
├── Caddyfile                    # Reverse proxy config
└── .env.prod                    # Production environment variables
```

---

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/signup/` | Create account (email, password, org_name) |
| POST | `/api/v1/auth/login/` | Login, returns token |
| GET | `/api/v1/auth/me/` | Current user profile |

### Projects
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/projects/` | List projects |
| POST | `/api/v1/projects/` | Create project |
| GET | `/api/v1/projects/:id/` | Project details |
| GET | `/api/v1/projects/:id/keys/` | List API keys |
| POST | `/api/v1/projects/:id/regenerate-key/` | Rotate API key |

### Event Ingestion
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/track/` | Track event (API key in header) |

### Dashboard
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/dashboard/overview/?project_id=` | Key metrics snapshot |
| GET | `/api/v1/dashboard/events/?project_id=` | Event trend data |
| GET | `/api/v1/dashboard/funnels/?project_id=` | Funnel conversion |
| GET | `/api/v1/dashboard/retention/?project_id=` | Retention curves |
| GET | `/api/v1/dashboard/realtime/?project_id=` | Live event count |
| GET | `/api/v1/dashboard/pages/?project_id=` | Page view breakdown |
| GET | `/api/v1/dashboard/countries/?project_id=` | Geographic distribution |
| GET | `/api/v1/dashboard/devices/?project_id=` | Device/browser stats |
| GET | `/api/v1/dashboard/sessions/?project_id=` | Session analysis |
| GET | `/api/v1/dashboard/insights/?project_id=` | AI-generated insights |
| GET | `/api/v1/dashboard/anomalies/?project_id=` | Anomaly incidents |
| GET | `/api/v1/dashboard/churn-risk/?project_id=` | Churn predictions |
| GET | `/api/v1/dashboard/churn-factors/?project_id=` | SHAP explanations |
| GET | `/api/v1/dashboard/revenue-metrics/?project_id=` | Revenue aggregation |
| GET | `/api/v1/dashboard/revenue-forecast/?project_id=` | Revenue forecast |

### Semantic Mapping
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/semantic/mappings/?project_id=` | List mappings |
| POST | `/api/v1/semantic/detect/` | Auto-detect event types |
| PUT | `/api/v1/semantic/mappings/:id/` | Update mapping |
| POST | `/api/v1/semantic/compute-funnel/` | Build funnel from mapping |

---

## ML Models

### Churn Prediction
- **Model**: `ChurnTransformerEnhanced` — custom PyTorch Transformer
- **Input**: User event sequences (30+ day history, 20+ features)
- **Output**: Churn probability per user
- **Explainability**: SHAP values for top contributing factors
- **Schedule**: Nightly at 3:00 AM (Celery Beat)

### Anomaly Detection
- **Model**: PyTorch Autoencoder with heuristic fallback
- **Input**: Daily behavioral metrics per user/project
- **Output**: Anomaly score with severity classification
  - `low` (ratio ≥ 1.0), `medium` (≥ 1.2), `high` (≥ 1.5), `critical` (≥ 2.0)
- **Schedule**: On-demand via /api

### Revenue Forecast
- **Model**: Temporal Fusion Transformer (PyTorch) with heuristic fallback
- **Input**: Historical daily revenue data
- **Output**: Future revenue with P10/P50/P90 uncertainty bounds
- **Schedule**: Nightly at 4:00 AM

---

## Data Flow

```
1. User Action → InsightFlow SDK (browser)
2. SDK sends POST /api/v1/track/ with event data + API key
3. Django validates key, produces message to Kafka ("events" topic)
4. Two Kafka consumers process in parallel:
   ├── ClickHouseConsumer — batch inserts to ClickHouse (analytics queries)
   └── AggregatorConsumer — updates PostgreSQL aggregations (DAU, counts, revenue)
5. Dashboard API queries ClickHouse (primary) with PostgreSQL fallback
6. Nightly Celery tasks run ML pipelines, store results in ClickHouse
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `SECRET_KEY` | Yes | Django secret key |
| `CH_HOST` | Yes | ClickHouse host |
| `CH_PORT` | Yes | ClickHouse port |
| `CH_USER` | Yes | ClickHouse username |
| `CH_PASSWORD` | Yes | ClickHouse password |
| `KAFKA_BOOTSTRAP_SERVERS` | Yes | Kafka broker address |
| `CELERY_BROKER_URL` | Yes | Redis URL for Celery |
| `CORS_ALLOWED_ORIGINS` | Yes | Comma-separated allowed origins |
| `CSRF_TRUSTED_ORIGINS` | Yes | Django CSRF trust origins |
| `DJANGO_SETTINGS_MODULE` | No | Default: `config.settings` |

---

## Deployment

### Backend (AWS EC2 + Docker)

```bash
git clone https://github.com/MohdSaadMa07/InsightFlow-AI.git
cd InsightFlow-AI
cp .env.prod.example .env.prod
# Edit .env.prod with your credentials
docker compose -f docker-compose.prod.yml up -d --build
```

Caddy serves the Let's Encrypt certificate for `34.207.37.93.nip.io`.

### Frontend (Cloudflare Pages)

1. Connect repo `MohdSaadMa07/InsightFlow-AI` to Cloudflare Pages
2. **Root directory**: `frontend`
3. **Build command**: `npm run build`
4. **Output directory**: `dist`

---

## Client SDK

```html
<script src="https://cdn.jsdelivr.net/npm/insightflow-sdk"></script>
<script>
  InsightFlow.init('YOUR_API_KEY', {
    host: 'https://34.207.37.93.nip.io'
  });
</script>
```

The SDK automatically tracks pageviews via `DOMContentLoaded` using `navigator.sendBeacon` with XHR fallback.

---

## Tech Stack

**Backend**: Django 4.2, DRF, Celery, Gunicorn, psycopg2, clickhouse-connect, confluent-kafka  
**Frontend**: React 18, React Router 7, Recharts, Vite 8  
**ML**: PyTorch (CPU), scikit-learn, XGBoost, SHAP, imbalanced-learn  
**Infrastructure**: Docker, Caddy, Redis, Kafka, ClickHouse, PostgreSQL (Supabase)  
**Cloud**: AWS EC2, Cloudflare Pages, ClickHouse Cloud
