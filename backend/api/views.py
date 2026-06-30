from datetime import datetime, timedelta

from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from events.clickhouse import ch
from projects.models import Project


def get_project(request):
    project_id = request.GET.get('project_id')
    if project_id:
        try:
            return request.user.organization.projects.get(id=project_id)
        except (Project.DoesNotExist, ValueError):
            return None
    return request.user.organization.projects.first()


def ch_query(sql, params=None):
    if not ch.available:
        return None
    return ch.get_client().query(sql, parameters=params or {})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def overview(request):
    project = get_project(request)
    if not project:
        return Response({'error': 'No project found'}, status=status.HTTP_404_NOT_FOUND)

    result = ch_query('''
        SELECT
            uniqExact(user_id) FILTER(WHERE toDate(timestamp) = %(today)s) as dau,
            count() as total_events,
            uniqExact(user_id) as total_users
        FROM insightflow.events
        WHERE project_id = %(project_id)s
    ''', {'project_id': project.id, 'today': timezone.now().date().isoformat()})

    if result is None:
        return Response({'dau': 0, 'total_events': 0, 'total_users': 0})

    row = result.result_rows[0]
    return Response({
        'dau': row[0],
        'total_events': row[1],
        'total_users': row[2],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def event_trends(request):
    project = get_project(request)
    if not project:
        return Response({'error': 'No project found'}, status=status.HTTP_404_NOT_FOUND)

    today = timezone.now().date()
    raw_start = request.GET.get('start_date')
    raw_end = request.GET.get('end_date')

    if raw_start:
        start_date = datetime.strptime(raw_start, '%Y-%m-%d').date()
    else:
        days = int(request.GET.get('days', 7))
        start_date = today - timedelta(days=days)
    end_date = datetime.strptime(raw_end, '%Y-%m-%d').date() if raw_end else today

    result = ch_query('''
        SELECT
            toDate(timestamp) as date,
            event_name,
            count() as count
        FROM insightflow.events
        WHERE project_id = %(project_id)s
          AND toDate(timestamp) >= %(start)s
          AND toDate(timestamp) <= %(end)s
        GROUP BY date, event_name
        ORDER BY date, event_name
    ''', {'project_id': project.id, 'start': start_date.isoformat(), 'end': end_date.isoformat()})

    if result is None:
        return Response([])

    return Response([{
        'date': str(r[0]),
        'event_name': r[1],
        'count': r[2],
    } for r in result.result_rows])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def retention(request):
    project = get_project(request)
    if not project:
        return Response({'error': 'No project found'}, status=status.HTTP_404_NOT_FOUND)

    today = timezone.now().date()
    min_date = today - timedelta(days=90)

    result = ch_query('''
        WITH dau AS (
            SELECT toDate(timestamp) as date, user_id
            FROM insightflow.events
            WHERE project_id = %(project_id)s AND toDate(timestamp) >= %(min_date)s
            GROUP BY date, user_id
        )
        SELECT cohort_date, period_days, retained, total
        FROM (
            SELECT a.date as cohort_date, 1 as period_days,
                uniqExact(b.user_id) as retained,
                uniqExact(a.user_id) as total
            FROM dau a LEFT JOIN dau b ON a.user_id = b.user_id AND b.date = a.date + 1
            GROUP BY a.date
            UNION ALL
            SELECT a.date, 7,
                uniqExact(b.user_id), uniqExact(a.user_id)
            FROM dau a LEFT JOIN dau b ON a.user_id = b.user_id AND b.date = a.date + 7
            GROUP BY a.date
            UNION ALL
            SELECT a.date, 30,
                uniqExact(b.user_id), uniqExact(a.user_id)
            FROM dau a LEFT JOIN dau b ON a.user_id = b.user_id AND b.date = a.date + 30
            GROUP BY a.date
        )
        WHERE total > 0
        ORDER BY cohort_date DESC, period_days
        LIMIT 90
    ''', {'project_id': project.id, 'min_date': min_date.isoformat()})

    if result is None:
        return Response([])

    periods = {1: 'D1', 7: 'D7', 30: 'D30'}
    return Response([{
        'cohort_date': str(r[0]),
        'period': periods.get(r[1], f'D{r[1]}'),
        'retained_users': r[2],
        'total_users': r[3],
        'rate': round(r[2] / r[3], 4) if r[3] > 0 else 0,
    } for r in result.result_rows])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def funnels(request):
    project = get_project(request)
    if not project:
        return Response({'error': 'No project found'}, status=status.HTTP_404_NOT_FOUND)

    today = timezone.now().date()
    raw_start = request.GET.get('start_date')
    raw_end = request.GET.get('end_date')
    steps_param = request.GET.get('steps', 'pageview,signup,purchase')

    if raw_start:
        start_date = datetime.strptime(raw_start, '%Y-%m-%d').date()
    else:
        days = int(request.GET.get('days', 30))
        start_date = today - timedelta(days=days)
    end_date = datetime.strptime(raw_end, '%Y-%m-%d').date() if raw_end else today

    step_names = [s.strip() for s in steps_param.split(',')]
    conditions = ', '.join(f"event_name = '{s}'" for s in step_names)

    result = ch_query(f'''
        SELECT level, count() as cnt
        FROM (
            SELECT user_id,
                windowFunnel(86400)(toDateTime(timestamp), {conditions}) as level
            FROM insightflow.events
            WHERE project_id = %(project_id)s
              AND toDate(timestamp) >= %(start)s
              AND toDate(timestamp) <= %(end)s
            GROUP BY user_id
        )
        WHERE level > 0
        GROUP BY level
        ORDER BY level
    ''', {'project_id': project.id, 'start': start_date.isoformat(), 'end': end_date.isoformat()})

    if result is None:
        return Response([])

    level_map = {r[0]: r[1] for r in result.result_rows}
    first_step_count = level_map.get(1, 0)
    rows = []
    for i, name in enumerate(step_names):
        cnt = level_map.get(i + 1, 0)
        cr = 100.0 if i == 0 else round(cnt / first_step_count * 100, 2) if first_step_count > 0 else 0
        rows.append({
            'funnel_name': 'Main Funnel',
            'date': today.isoformat(),
            'step_order': i,
            'step_name': name,
            'count': cnt,
            'conversion_rate': cr,
        })
    return Response(rows)
