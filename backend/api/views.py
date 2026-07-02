import re
from datetime import datetime, timedelta

from django.db.models import Count, Q
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from events.clickhouse import ch
from events.models import Event
from projects.models import Project
from analytics.models import DailyActiveUser, EventCount, RetentionCurve, FunnelAnalysis
from analytics.insights import generate_insights


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


LANG_TO_COUNTRY = {
    'en': 'United States', 'en-US': 'United States', 'en-GB': 'United Kingdom',
    'en-AU': 'Australia', 'en-CA': 'Canada', 'en-IN': 'India',
    'es': 'Spain', 'es-MX': 'Mexico', 'es-AR': 'Argentina',
    'fr': 'France', 'fr-CA': 'Canada', 'fr-BE': 'Belgium',
    'de': 'Germany', 'de-AT': 'Austria', 'de-CH': 'Switzerland',
    'pt': 'Portugal', 'pt-BR': 'Brazil',
    'ru': 'Russia', 'zh': 'China', 'zh-CN': 'China',
    'ja': 'Japan', 'ko': 'South Korea', 'ar': 'Saudi Arabia',
    'it': 'Italy', 'nl': 'Netherlands', 'pl': 'Poland',
    'tr': 'Turkey', 'sv': 'Sweden', 'da': 'Denmark',
    'fi': 'Finland', 'no': 'Norway', 'cs': 'Czech Republic',
    'ro': 'Romania', 'hu': 'Hungary', 'th': 'Thailand',
    'vi': 'Vietnam', 'he': 'Israel', 'id': 'Indonesia',
    'ms': 'Malaysia', 'hi': 'India', 'bn': 'Bangladesh',
    'uk': 'Ukraine', 'el': 'Greece',
}


def parse_browser(ua):
    ua_lower = ua.lower()
    if 'firefox' in ua_lower and 'seamonkey' not in ua_lower:
        return 'Firefox'
    if 'opr' in ua_lower or 'opera' in ua_lower:
        return 'Opera'
    if 'edge' in ua_lower or 'edg/' in ua_lower:
        return 'Edge'
    if 'chrome' in ua_lower and 'chromium' not in ua_lower:
        return 'Chrome'
    if 'safari' in ua_lower and 'chrome' not in ua_lower:
        return 'Safari'
    if 'chromium' in ua_lower:
        return 'Chromium'
    return 'Other'


def parse_os(ua):
    ua_lower = ua.lower()
    if 'windows' in ua_lower:
        return 'Windows'
    if 'mac os' in ua_lower or 'macintosh' in ua_lower:
        return 'macOS'
    if 'linux' in ua_lower and 'android' not in ua_lower:
        return 'Linux'
    if 'android' in ua_lower:
        return 'Android'
    if 'ios' in ua_lower or 'iphone' in ua_lower or 'ipad' in ua_lower:
        return 'iOS'
    if 'cros' in ua_lower:
        return 'Chrome OS'
    return 'Other'


def parse_device_type(ua):
    ua_lower = ua.lower()
    if 'mobile' in ua_lower or 'iphone' in ua_lower or 'android' in ua_lower:
        if 'tablet' in ua_lower or 'ipad' in ua_lower:
            return 'Tablet'
        return 'Mobile'
    if 'tablet' in ua_lower or 'ipad' in ua_lower:
        return 'Tablet'
    return 'Desktop'


def _orm_overview(project):
    today = timezone.now().date()
    dau = Event.objects.filter(project=project, timestamp__date=today).values('user_id').distinct().count()
    total_events = Event.objects.filter(project=project).count()
    total_users = Event.objects.filter(project=project).values('user_id').distinct().count()
    return {
        'dau': dau,
        'total_events': total_events,
        'total_users': total_users,
    }


def _orm_event_trends(project, start_date, end_date):
    qs = Event.objects.filter(
        project=project, timestamp__date__gte=start_date, timestamp__date__lte=end_date
    ).values('timestamp__date', 'event_name').annotate(count=Count('id')).order_by('timestamp__date', 'event_name')
    return [{
        'date': str(r['timestamp__date']),
        'event_name': r['event_name'],
        'count': r['count'],
    } for r in qs]


def _orm_retention(project):
    cutoff = timezone.now().date() - timedelta(days=90)
    qs = RetentionCurve.objects.filter(project=project, cohort_date__gte=cutoff).order_by('-cohort_date')
    return [{
        'cohort_date': str(r.cohort_date),
        'period': r.period,
        'retained_users': r.retained_users,
        'total_users': r.total_users,
        'rate': r.rate,
    } for r in qs]


def _orm_funnels(project, start_date, end_date):
    qs = FunnelAnalysis.objects.filter(
        project=project, date__gte=start_date, date__lte=end_date
    ).order_by('date', 'step_order')
    return [{
        'funnel_name': a.funnel.name,
        'date': str(a.date),
        'step_order': a.step_order,
        'step_name': a.step_name,
        'count': a.count,
        'conversion_rate': a.conversion_rate,
    } for a in qs]


def _orm_realtime(project):
    since = timezone.now() - timedelta(minutes=5)
    online = Event.objects.filter(project=project, timestamp__gte=since).values('user_id').distinct().count()
    events_5min = Event.objects.filter(project=project, timestamp__gte=since).count()
    return {
        'online_users': online,
        'events_last_5min': events_5min,
        'users_last_5min': online,
    }


def _orm_top_pages(project, start_date, end_date):
    rows = Event.objects.filter(
        project=project, event_name__in=['$pageview', 'pageview'],
        timestamp__date__gte=start_date, timestamp__date__lte=end_date
    ).values_list('properties', 'user_id', named=True)

    page_map = {}
    for r in rows:
        url = r.properties.get('url', '')
        if not url:
            continue
        if url not in page_map:
            page_map[url] = {'views': 0, 'visitors': set()}
        page_map[url]['views'] += 1
        page_map[url]['visitors'].add(r.user_id)

    result = sorted(
        [{'page': url, 'views': v['views'], 'unique_visitors': len(v['visitors'])} for url, v in page_map.items()],
        key=lambda x: x['views'], reverse=True
    )[:20]

    return result


def _orm_countries(project, start_date):
    rows = Event.objects.filter(
        project=project, timestamp__date__gte=start_date,
        properties__has_key='$language'
    ).values_list('properties', 'user_id', named=True)

    lang_map = {}
    for r in rows:
        lang = r.properties.get('$language', '')
        if not lang:
            continue
        country = LANG_TO_COUNTRY.get(lang, lang.split('-')[0] if '-' in lang else lang)
        if country not in lang_map:
            lang_map[country] = {'country': country, 'users': set(), 'events': 0, 'lang': lang}
        lang_map[country]['events'] += 1
        lang_map[country]['users'].add(r.user_id)

    result = sorted(
        [{**v, 'users': len(v['users'])} for v in lang_map.values()],
        key=lambda x: x['users'], reverse=True
    )
    return result


def _orm_devices(project, start_date):
    browsers = {}
    os_map = {}
    device_types = {}

    ua_rows = Event.objects.filter(
        project=project, timestamp__date__gte=start_date,
        properties__has_key='$user_agent'
    ).values_list('properties', 'user_id', named=True)

    for r in ua_rows:
        ua = r.properties.get('$user_agent', '')
        if not ua:
            continue
        b = parse_browser(ua)
        browsers[b] = browsers.get(b, 0) + 1
        o = parse_os(ua)
        os_map[o] = os_map.get(o, 0) + 1
        d = parse_device_type(ua)
        device_types[d] = device_types.get(d, 0) + 1

    def to_list(d):
        return sorted([{'name': k, 'users': v} for k, v in d.items()], key=lambda x: x['users'], reverse=True)

    return {
        'browsers': to_list(browsers),
        'os': to_list(os_map),
        'device_types': to_list(device_types),
    }


def _orm_sessions(project, start_date):
    session_rows = Event.objects.filter(
        project=project, timestamp__date__gte=start_date,
        properties__has_key='$session_id'
    ).values_list('properties', 'timestamp', 'user_id', named=True)

    sessions = {}
    for r in session_rows:
        sid = r.properties.get('$session_id', '')
        if not sid:
            continue
        if sid not in sessions:
            sessions[sid] = {'min_ts': r.timestamp, 'max_ts': r.timestamp, 'count': 0}
        sessions[sid]['min_ts'] = min(sessions[sid]['min_ts'], r.timestamp)
        sessions[sid]['max_ts'] = max(sessions[sid]['max_ts'], r.timestamp)
        sessions[sid]['count'] += 1

    total = len(sessions)
    total_duration = 0
    bounce = 0
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    sessions_today = 0

    for sid, s in sessions.items():
        dur = (s['max_ts'] - s['min_ts']).total_seconds()
        if dur > 0:
            total_duration += dur
        if s['count'] == 1:
            bounce += 1
        if s['max_ts'] >= today_start:
            sessions_today += 1

    return {
        'total_sessions': total,
        'avg_duration_seconds': round(total_duration / total, 2) if total > 0 else 0,
        'bounce_rate': round(bounce / total * 100, 2) if total > 0 else 0,
        'sessions_today': sessions_today,
    }


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
        return Response(_orm_overview(project))

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
        return Response(_orm_event_trends(project, start_date, end_date))

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
        return Response(_orm_retention(project))

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
        return Response(_orm_funnels(project, start_date, end_date))

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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def realtime(request):
    project = get_project(request)
    if not project:
        return Response({'error': 'No project found'}, status=status.HTTP_404_NOT_FOUND)

    now = timezone.now()
    five_min_ago = now - timedelta(minutes=5)

    result = ch_query('''
        SELECT
            uniqExact(user_id) as online_users,
            count() as events_last_5min,
            uniqExact(user_id) as users_last_5min
        FROM insightflow.events
        WHERE project_id = %(project_id)s
          AND timestamp >= %(since)s
    ''', {'project_id': project.id, 'since': five_min_ago.isoformat()})

    if result is None:
        return Response(_orm_realtime(project))

    row = result.result_rows[0]
    return Response({
        'online_users': row[0],
        'events_last_5min': row[1],
        'users_last_5min': row[2],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def top_pages(request):
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
            JSONExtractString(properties, 'url') as page,
            count() as views,
            uniqExact(user_id) as unique_visitors
        FROM insightflow.events
        WHERE project_id = %(project_id)s
          AND toDate(timestamp) >= %(start)s
          AND toDate(timestamp) <= %(end)s
          AND JSONExtractString(properties, 'url') != ''
        GROUP BY page
        ORDER BY views DESC
        LIMIT 20
    ''', {'project_id': project.id, 'start': start_date.isoformat(), 'end': end_date.isoformat()})

    if result is None:
        return Response(_orm_top_pages(project, start_date, end_date))

    return Response([{
        'page': r[0],
        'views': r[1],
        'unique_visitors': r[2],
    } for r in result.result_rows])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def countries(request):
    project = get_project(request)
    if not project:
        return Response({'error': 'No project found'}, status=status.HTTP_404_NOT_FOUND)

    today = timezone.now().date()
    start_date = today - timedelta(days=30)

    result = ch_query('''
        SELECT
            JSONExtractString(properties, '$language') as lang,
            uniqExact(user_id) as users,
            count() as events
        FROM insightflow.events
        WHERE project_id = %(project_id)s
          AND toDate(timestamp) >= %(start)s
          AND JSONExtractString(properties, '$language') != ''
        GROUP BY lang
        ORDER BY users DESC
        LIMIT 20
    ''', {'project_id': project.id, 'start': start_date.isoformat()})

    if result is None:
        return Response(_orm_countries(project, start_date))

    country_map = {}
    for row in result.result_rows:
        lang = row[0]
        country = LANG_TO_COUNTRY.get(lang, lang.split('-')[0] if '-' in lang else lang)
        if country in country_map:
            country_map[country]['users'] += row[1]
            country_map[country]['events'] += row[2]
        else:
            country_map[country] = {'country': country, 'users': row[1], 'events': row[2], 'lang': lang}

    sorted_countries = sorted(country_map.values(), key=lambda x: x['users'], reverse=True)
    return Response(sorted_countries)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def devices(request):
    project = get_project(request)
    if not project:
        return Response({'error': 'No project found'}, status=status.HTTP_404_NOT_FOUND)

    today = timezone.now().date()
    start_date = today - timedelta(days=30)

    result = ch_query('''
        SELECT
            user_agent,
            uniqExact(user_id) as users,
            count() as events
        FROM insightflow.events
        WHERE project_id = %(project_id)s
          AND toDate(timestamp) >= %(start)s
          AND user_agent != ''
        GROUP BY user_agent
        ORDER BY users DESC
        LIMIT 500
    ''', {'project_id': project.id, 'start': start_date.isoformat()})

    if result is None:
        return Response(_orm_devices(project, start_date))

    browsers = {}
    os_map = {}
    device_types = {}
    for row in result.result_rows:
        ua = row[0]
        users = row[1]

        browser = parse_browser(ua)
        browsers[browser] = browsers.get(browser, 0) + users

        os_name = parse_os(ua)
        os_map[os_name] = os_map.get(os_name, 0) + users

        device = parse_device_type(ua)
        device_types[device] = device_types.get(device, 0) + users

    def to_list(d):
        return sorted([{'name': k, 'users': v} for k, v in d.items()], key=lambda x: x['users'], reverse=True)

    return Response({
        'browsers': to_list(browsers),
        'os': to_list(os_map),
        'device_types': to_list(device_types),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sessions(request):
    project = get_project(request)
    if not project:
        return Response({'error': 'No project found'}, status=status.HTTP_404_NOT_FOUND)

    today = timezone.now().date()
    start_date = today - timedelta(days=30)

    result = ch_query('''
        SELECT
            JSONExtractString(properties, '$session_id') as sid,
            min(timestamp) as session_start,
            max(timestamp) as session_end,
            count() as event_count
        FROM insightflow.events
        WHERE project_id = %(project_id)s
          AND toDate(timestamp) >= %(start)s
          AND JSONExtractString(properties, '$session_id') != ''
        GROUP BY sid
        HAVING event_count > 0
        ORDER BY session_start DESC
        LIMIT 10000
    ''', {'project_id': project.id, 'start': start_date.isoformat()})

    if result is None:
        return Response(_orm_sessions(project, start_date))

    total_duration = 0
    bounce_count = 0
    total_sessions = 0
    sessions_today = 0

    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    for row in result.result_rows:
        sid, ts_min, ts_max, event_count = row
        if sid == '':
            continue
        total_sessions += 1
        duration = (ts_max - ts_min).total_seconds()
        if duration > 0:
            total_duration += duration
        if event_count == 1:
            bounce_count += 1
        if ts_max >= today_start:
            sessions_today += 1

    avg_duration = round(total_duration / total_sessions, 2) if total_sessions > 0 else 0
    bounce_rate = round(bounce_count / total_sessions * 100, 2) if total_sessions > 0 else 0

    return Response({
        'total_sessions': total_sessions,
        'avg_duration_seconds': avg_duration,
        'bounce_rate': bounce_rate,
        'sessions_today': sessions_today,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def insights(request):
    project = get_project(request)
    if not project:
        return Response({'error': 'No project found'}, status=status.HTTP_404_NOT_FOUND)

    data = generate_insights(project)
    return Response(data)
