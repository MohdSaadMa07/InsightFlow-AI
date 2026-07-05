import json
import logging
import os
from datetime import datetime

import numpy as np

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder


class NumpyJSONEncoder(DjangoJSONEncoder):
    def default(self, o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, (np.ndarray,)):
            return o.tolist()
        return super().default(o)


def json_response(data, status=200):
    return JsonResponse(data, encoder=NumpyJSONEncoder, status=status,         safe=False, json_dumps_params={'default': NumpyJSONEncoder().default})

from ml.services.churn_risk import churn_risk

logger = logging.getLogger(__name__)

CACHE_PATH = os.path.join(settings.BASE_DIR, 'ml', 'models', 'artifacts', 'churn_cache.json')
SNAPSHOT_TABLE = 'user_risk_snapshots'


def _read_cache():
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH) as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Cache read failed: %s", e)
    return None


def _write_cache(data):
    try:
        with open(CACHE_PATH, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        logger.warning("Cache write failed: %s", e)


def _query_snapshots(project_id, limit=500):
    """Read latest risk snapshots from ClickHouse for a project."""
    try:
        from events.clickhouse import ch
        if not ch.available:
            return None
        client = ch.get_client()
        ref = f'{ch._database}.{SNAPSHOT_TABLE}'
        rows = client.query(f"""
            SELECT
                user_id, churn_probability, risk_level, total_events,
                shap_explanation, suggestions, confidence, last_active_days,
                snapshot_date, computed_at
            FROM {ref}
            WHERE project_id = %(pid)s
            ORDER BY churn_probability DESC
            LIMIT %(lim)s
        """, parameters={'pid': project_id, 'lim': limit})
        if not rows or not rows.result_rows:
            return None
        results = []
        for r in rows.result_rows:
            shap = json.loads(r[4]) if r[4] else []
            suggestions = json.loads(r[5]) if r[5] else []
            results.append({
                'user_id': r[0],
                'probability': r[1],
                'risk_level': r[2],
                'total_events': r[3],
                'explanations': shap,
                'suggestions': suggestions,
                'confidence': r[6],
                'last_active_days': r[7] or 0,
                'snapshot_date': str(r[8]),
                'computed_at': str(r[9]),
            })
        return results
    except Exception as e:
        logger.warning("Snapshot query failed: %s", e)
        return None


def _query_user_snapshot(project_id, user_id):
    """Read latest snapshot for a single user from ClickHouse."""
    try:
        from events.clickhouse import ch
        if not ch.available:
            return None
        client = ch.get_client()
        ref = f'{ch._database}.{SNAPSHOT_TABLE}'
        rows = client.query(f"""
            SELECT
                user_id, churn_probability, risk_level, total_events,
                shap_explanation, suggestions, confidence, confidence_score,
                cohort_size, last_active_days
            FROM {ref}
            WHERE project_id = %(pid)s AND user_id = %(uid)s
            ORDER BY computed_at DESC
            LIMIT 1
        """, parameters={'pid': project_id, 'uid': user_id})
        if not rows or not rows.result_rows:
            return None
        r = rows.result_rows[0]
        shap = json.loads(r[4]) if r[4] else []
        suggestions = json.loads(r[5]) if r[5] else []
        return {
            'user_id': r[0],
            'probability': float(r[1]),
            'risk_level': r[2],
            'total_events': int(r[3]),
            'explanations': shap,
            'suggestions': suggestions,
            'confidence': r[6],
            'confidence_score': float(r[7]) if r[7] else 0,
            'cohort_size': int(r[8]) if r[8] else 0,
            'last_active_days': int(r[9]) if r[9] else 0,
            'unique_events': len(set(e.get('event_name', '') for e in shap)) if shap else None,
        }
    except Exception as e:
        logger.warning("User snapshot query failed: %s", e)
        return None


def dashboard(request):
    return render(request, 'dashboard.html')


@require_GET
def churn_dashboard(request):
    return render(request, 'churn_dashboard.html')


@require_GET
def churn_data(request):
    project_id = request.GET.get('project_id', 14)
    try:
        project_id = int(project_id)
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid project_id"}, status=400)

    # Try ClickHouse snapshots first
    snapshots = _query_snapshots(project_id, limit=500)
    if snapshots:
        from ml.services.churn_risk import churn_risk as cr
        overview = cr.get_overview(snapshots) if cr.load() else None
        timeline = cr.get_churn_timeline(snapshots) if cr.load() else None
        return JsonResponse({
            "overview": overview,
            "predictions": snapshots,
            "timeline": timeline,
            "source": "clickhouse",
            "generated_at": datetime.now().isoformat(),
        })

    # Try JSON cache next
    cached = _read_cache()
    if cached:
        return JsonResponse(cached)

    # Fallback: live compute
    from ml.services.churn_risk import churn_risk
    if not churn_risk.load():
        return JsonResponse({"error": "Model not available"}, status=500)

    try:
        predictions = churn_risk.predict_all(project_id)
        if predictions is None:
            return JsonResponse({"error": "No data available"}, status=404)

        overview = churn_risk.get_overview(predictions)
        timeline = churn_risk.get_churn_timeline(predictions)
        recommendations = churn_risk.get_recommendations(predictions, project_id)

        # Precompute SHAP for top high-risk users in background
        from ml.tasks import precompute_shap
        precompute_shap.delay(project_id, 50)

        result = {
            "overview": overview,
            "predictions": predictions[:500],
            "timeline": timeline,
            "recommendations": recommendations,
            "generated_at": datetime.now().isoformat(),
        }
        _write_cache(result)
        return JsonResponse(result)
    except Exception as e:
        logger.exception("Churn data error")
        return JsonResponse({"error": str(e)}, status=500)


@require_GET
def churn_explain(request, user_id):
    project_id = request.GET.get('project_id', 14)
    try:
        project_id = int(project_id)
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid project_id"}, status=400)

    # Fast path: ClickHouse snapshot already has precomputed SHAP
    snapshot = _query_user_snapshot(project_id, user_id)
    if snapshot:
        return JsonResponse(snapshot)

    if not churn_risk.load():
        # Fallback: look up user from cached predictions
        cached = _read_cache()
        if cached:
            for p in cached.get("predictions", []):
                if p["user_id"] == user_id:
                    return JsonResponse({
                        "user_id": user_id,
                        "risk_level": p["risk_level"],
                        "probability": p["probability"],
                        "total_events": p["total_events"],
                        "unique_events": p.get("unique_events", None),
                        "top_events": [],
                        "explanations": [],
                    })
        return JsonResponse({"error": "Model not available"}, status=500)

    # Slow path: live compute (no snapshot found)
    if churn_risk._cache_seqs is None:
        try:
            churn_risk.predict_all(project_id)
        except Exception as e:
            logger.warning("Pre-compute failed: %s", e)

    try:
        explanation = churn_risk.explain_user(user_id, project_id)
        if explanation is not None:
            return JsonResponse(explanation)
    except Exception:
        logger.exception("Churn explain error")

    # Last resort: JSON cache with no explanations
    cached = _read_cache()
    if cached:
        for p in cached.get("predictions", []):
            if p["user_id"] == user_id:
                return JsonResponse({
                    "user_id": user_id,
                    "risk_level": p["risk_level"],
                    "probability": p["probability"],
                    "total_events": p["total_events"],
                    "unique_events": p.get("unique_events", None),
                    "top_events": [],
                    "explanations": [],
                })
    return JsonResponse({"error": "User not found"}, status=404)


def revenue_dashboard(request):
    return render(request, 'revenue_dashboard.html')


@require_GET
def revenue_data(request):
    """Return historical daily revenue metrics."""
    project_id = request.GET.get('project_id', 14)
    days = int(request.GET.get('days', 180))
    try:
        project_id = int(project_id)
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid project_id"}, status=400)

    # ClickHouse first
    from analytics.clickhouse_revenue import get_revenue_time_series
    try:
        data = get_revenue_time_series(project_id, days=days)
        if data and any(r.get('total_revenue', 0) != 0 for r in data):
            return JsonResponse({
                "metrics": data[-days:],
                "source": "clickhouse",
                "generated_at": datetime.now().isoformat(),
            })
    except Exception:
        logger.warning('ClickHouse revenue query failed')

    # PostgreSQL fallback
    from analytics.models import DailyRevenue
    from datetime import timedelta
    start = datetime.now().date() - timedelta(days=days)
    qs = DailyRevenue.objects.filter(project_id=project_id, date__gte=start).order_by('date')
    rows = [
        {
            'date': r.date.isoformat(),
            'total_revenue': float(r.total_revenue),
            'mrr': float(r.mrr),
            'dau': r.dau,
            'session_count': r.session_count,
            'transaction_count': r.transaction_count,
            'subscription_count': r.subscription_count,
            'refund_count': r.refund_count,
        }
        for r in qs
    ]
    if rows:
        return JsonResponse({
            "metrics": rows,
            "source": "postgresql",
            "generated_at": datetime.now().isoformat(),
        })
    return JsonResponse({"error": "No revenue data"}, status=404)


@require_GET
def revenue_forecast_data(request):
    """Return revenue forecasts with uncertainty bounds.

    Serves from nightly cache when available; falls back to live compute.
    """
    project_id = request.GET.get('project_id', 14)
    horizon = int(request.GET.get('horizon', 30))
    try:
        project_id = int(project_id)
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid project_id"}, status=400)

    from ml.services.revenue_forecast import revenue_forecast

    # Try nightly cache first
    cached = revenue_forecast.load_from_cache(project_id)
    if cached:
        return JsonResponse(cached)

    # Fall back to live computation
    result = revenue_forecast.predict(project_id, horizon=horizon)
    if result:
        return JsonResponse(result)
    return JsonResponse({"error": "Forecast not available"}, status=404)


@require_GET
def anomaly_data(request):
    """Return a production-grade behavioral anomaly summary for the selected project.

    Response shape:
    {
        "summary": {...},
        "recent_anomalies": [...],
        "timeline": [...],
        "incident_log": [...],
    }
    """
    project_id = request.GET.get('project_id', 14)
    days = int(request.GET.get('days', 14))
    store_incidents = request.GET.get('store_incidents', 'true').lower() == 'true'
    try:
        project_id = int(project_id)
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid project_id"}, status=400)

    from ml.services.anomaly_detection import anomaly_detection

    result = anomaly_detection.get_summary(
        project_id, days=days, store_incidents=store_incidents
    )
    if result:
        return json_response(result)
    return JsonResponse({"error": "Anomaly data not available"}, status=404)

