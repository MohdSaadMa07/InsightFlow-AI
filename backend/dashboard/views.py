import json
import logging
import os
from datetime import datetime

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.conf import settings

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
                shap_explanation, confidence, last_active_days,
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
            results.append({
                'user_id': r[0],
                'probability': r[1],
                'risk_level': r[2],
                'total_events': r[3],
                'explanations': shap,
                'confidence': r[5],
                'last_active_days': r[6] or 0,
                'snapshot_date': str(r[7]),
                'computed_at': str(r[8]),
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
                shap_explanation, confidence, confidence_score,
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
        return {
            'user_id': r[0],
            'probability': float(r[1]),
            'risk_level': r[2],
            'total_events': int(r[3]),
            'explanations': shap,
            'confidence': r[5],
            'confidence_score': float(r[6]) if r[6] else 0,
            'cohort_size': int(r[7]) if r[7] else 0,
            'last_active_days': int(r[8]) if r[8] else 0,
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
        from ml.services.churn_risk import churn_risk
        overview = churn_risk.get_overview(snapshots) if churn_risk.load() else None
        timeline = churn_risk.get_churn_timeline(snapshots) if churn_risk.load() else None
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
