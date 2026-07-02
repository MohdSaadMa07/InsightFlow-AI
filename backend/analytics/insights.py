import json
from datetime import datetime, timedelta, date
from collections import Counter, defaultdict

from django.db.models import Count, Q
from django.utils import timezone

from events.models import Event
from analytics.models import RetentionCurve, FunnelAnalysis
from events.clickhouse import ch


def q_ch(sql, params=None):
    if not ch.available:
        return None
    try:
        return ch.get_client().query(sql, parameters=params or {})
    except Exception:
        return None


def today():
    return timezone.now().date()


def days_ago(n):
    return today() - timedelta(days=n)


def _compare_periods(project, fn_current, fn_previous):
    """Generic helper: run fn_current for recent period, fn_previous for prior period, return comparison."""
    return fn_current(project)


def generate_insights(project):
    """Main entry point — returns list of insight dicts."""
    if not project:
        return []

    insights = []

    insights.extend(_trend_insights(project))
    insights.extend(_funnel_insights(project))
    insights.extend(_anomaly_insights(project))
    insights.extend(_behavior_insights(project))
    insights.extend(_suggestion_insights(project))

    insights.sort(key=lambda x: _severity_order(x.get('severity', 'info')), reverse=True)
    return insights


def _get_domain(url):
    try:
        from urllib.parse import urlparse
        return urlparse(url).hostname.replace('www.', '') or url
    except Exception:
        return url


def _severity_order(s):
    return {'critical': 3, 'warning': 2, 'info': 1}.get(s, 0)


def _make(itype, severity, title, description, **kw):
    """Build a standardised insight dict."""
    return {
        'type': itype,
        'severity': severity,
        'title': title,
        'description': description,
        'timestamp': timezone.now().isoformat(),
        **kw,
    }


# ── Trend insights ──────────────────────────────────────────────

def _trend_insights(project):
    results = []
    now = timezone.now()
    today_d = now.date()
    yesterday_d = today_d - timedelta(days=1)
    this_week = today_d - timedelta(days=7)
    last_week = today_d - timedelta(days=14)

    # DAU trend — ClickHouse primary, ORM fallback
    def get_dau_for_range(project, start, end):
        r = q_ch('''
            SELECT uniqExact(user_id) FROM insightflow.events
            WHERE project_id = %(pid)s AND toDate(timestamp) >= %(start)s AND toDate(timestamp) <= %(end)s
        ''', {'pid': project.id, 'start': start.isoformat(), 'end': end.isoformat()})
        if r:
            return r.result_rows[0][0]
        return Event.objects.filter(project=project, timestamp__date__gte=start, timestamp__date__lte=end).values('user_id').distinct().count()

    def get_metric(project, start, end, metric='events'):
        if metric == 'events':
            r = q_ch('''
                SELECT count() FROM insightflow.events
                WHERE project_id = %(pid)s AND toDate(timestamp) >= %(start)s AND toDate(timestamp) <= %(end)s
            ''', {'pid': project.id, 'start': start.isoformat(), 'end': end.isoformat()})
            if r:
                return r.result_rows[0][0]
            return Event.objects.filter(project=project, timestamp__date__gte=start, timestamp__date__lte=end).count()
        if metric == 'sessions':
            r = q_ch('''
                SELECT uniqExact(JSONExtractString(properties, '$session_id'))
                FROM insightflow.events
                WHERE project_id = %(pid)s AND toDate(timestamp) >= %(start)s AND toDate(timestamp) <= %(end)s
                  AND JSONExtractString(properties, '$session_id') != ''
            ''', {'pid': project.id, 'start': start.isoformat(), 'end': end.isoformat()})
            if r:
                return r.result_rows[0][0]
            return Event.objects.filter(project=project, timestamp__date__gte=start, timestamp__date__lte=end, properties__has_key='$session_id').values('properties__$session_id').distinct().count()
        return 0

    def get_bounce(project, start, end):
        r = q_ch('''
            SELECT avg(bounced) FROM (
                SELECT
                    JSONExtractString(properties, '$session_id') as sid,
                    count() = 1 as bounced
                FROM insightflow.events
                WHERE project_id = %(pid)s AND toDate(timestamp) >= %(start)s AND toDate(timestamp) <= %(end)s
                  AND JSONExtractString(properties, '$session_id') != ''
                GROUP BY sid
            )
        ''', {'pid': project.id, 'start': start.isoformat(), 'end': end.isoformat()})
        if r:
            return round(r.result_rows[0][0] * 100, 1) if r.result_rows[0][0] else 0
        sessions = Event.objects.filter(project=project, timestamp__date__gte=start, timestamp__date__lte=end, properties__has_key='$session_id').values('properties__$session_id', 'properties').annotate(cnt=Count('id'))
        if not sessions:
            return 0
        bounced = sum(1 for s in sessions if s['cnt'] == 1)
        return round(bounced / len(sessions) * 100, 1)

    def get_avg_duration(project, start, end):
        r = q_ch('''
            SELECT avg(dur) FROM (
                SELECT
                    JSONExtractString(properties, '$session_id') as sid,
                    dateDiff('second', min(timestamp), max(timestamp)) as dur
                FROM insightflow.events
                WHERE project_id = %(pid)s AND toDate(timestamp) >= %(start)s AND toDate(timestamp) <= %(end)s
                  AND JSONExtractString(properties, '$session_id') != ''
                GROUP BY sid
                HAVING dur > 0
            )
        ''', {'pid': project.id, 'start': start.isoformat(), 'end': end.isoformat()})
        if r:
            return round(r.result_rows[0][0] or 0, 1)
        return 0

    metrics = [
        ('DAU', lambda p, s, e: get_dau_for_range(p, s, e), 'users'),
        ('Events', lambda p, s, e: get_metric(p, s, e, 'events'), 'events'),
        ('Sessions', lambda p, s, e: get_metric(p, s, e, 'sessions'), 'sessions'),
    ]

    for label, fn, unit in metrics:
        current = fn(project, this_week, today_d)
        previous = fn(project, last_week, this_week - timedelta(days=1))
        if current == 0 and previous == 0:
            continue
        if previous == 0:
            continue
        change = round((current - previous) / previous * 100, 1)
        direction = 'up' if change > 0 else 'down'
        if abs(change) < 5:
            continue
        severity = 'warning' if abs(change) > 30 else ('critical' if abs(change) > 50 else 'info')
        if direction == 'up' and label == 'Bounce Rate':
            severity = 'warning' if abs(change) > 20 else 'info'
        results.append(_make('trend', severity,
            f'{label} {direction} {abs(change)}%',
            f'{label} {"increased" if direction == "up" else "decreased"} by {abs(change)}% this week compared to last week ({current} vs {previous} {unit}).',
            metric=label.lower().replace(' ', '_'),
            change_pct=change,
            direction=direction,
            current_value=current,
            previous_value=previous,
        ))

    # Bounce rate trend
    bounce_current = get_bounce(project, this_week, today_d)
    bounce_prev = get_bounce(project, last_week, this_week - timedelta(days=1))
    if bounce_prev > 0:
        bounce_change = round(bounce_current - bounce_prev, 1)
        if abs(bounce_change) > 2:
            direction = 'up' if bounce_change > 0 else 'down'
            severity = 'warning' if abs(bounce_change) > 5 else 'info'
            results.append(_make('trend', severity,
                f'Bounce Rate {direction} {abs(bounce_change)}pp',
                f'Bounce rate {"increased" if direction == "up" else "decreased"} by {abs(bounce_change)} percentage points ({bounce_current}% vs {bounce_prev}%).',
                metric='bounce_rate', change_pct=bounce_change, direction=direction,
                current_value=bounce_current, previous_value=bounce_prev,
            ))

    # Duration trend
    dur_current = get_avg_duration(project, this_week, today_d)
    dur_prev = get_avg_duration(project, last_week, this_week - timedelta(days=1))
    if dur_prev > 0 and dur_current > 0:
        dur_change = round((dur_current - dur_prev) / dur_prev * 100, 1)
        if abs(dur_change) > 10:
            direction = 'up' if dur_change > 0 else 'down'
            severity = 'info'
            results.append(_make('trend', severity,
                f'Session Duration {direction} {abs(dur_change)}%',
                f'Average session duration {"increased" if direction == "up" else "decreased"} by {abs(dur_change)}% ({dur_current}s vs {dur_prev}s).',
                metric='avg_session_duration', change_pct=dur_change, direction=direction,
                current_value=dur_current, previous_value=dur_prev,
            ))

    return results


# ── Funnel bottleneck insights ──────────────────────────────────

def _funnel_insights(project):
    results = []
    analyses = FunnelAnalysis.objects.filter(project=project).order_by('-date', 'step_order')[:20]
    if not analyses:
        return results

    dates = set(a.date for a in analyses)
    latest_date = max(dates)
    latest = [a for a in analyses if a.date == latest_date]
    latest.sort(key=lambda x: x.step_order)

    if len(latest) < 2:
        return results

    initial = latest[0].count
    if initial == 0:
        return results

    for i, step in enumerate(latest):
        if i == 0:
            continue
        rate = step.count / initial * 100 if initial > 0 else 0
        drop = 100 - rate
        prev_drop = 100 - (latest[i - 1].count / initial * 100) if latest[i - 1].count > 0 else 0
        step_drop = drop - prev_drop
        if step_drop > 20:
            results.append(_make('funnel_bottleneck', 'warning' if step_drop > 30 else 'info',
                f'Drop-off: {step.step_name} ({step_drop:.0f}% loss)',
                f'{step_drop:.0f}% of users drop off at "{step.step_name}" — only {rate:.0f}% make it through. Consider reviewing this step for friction.',
                funnel_step=step.step_name, drop_pct=round(step_drop, 1),
                conversion_rate=round(rate, 1), count=step.count, initial_count=initial,
            ))

    overall_rate = (latest[-1].count / initial * 100) if initial > 0 else 0
    if overall_rate < 10:
        results.append(_make('funnel_bottleneck', 'critical',
            f'Overall funnel conversion: {overall_rate:.1f}%',
            f'Only {overall_rate:.1f}% of users complete the full funnel ({latest[-1].count} of {initial}). Major optimisation opportunity.',
            funnel_step='overall', drop_pct=round(100 - overall_rate, 1),
            conversion_rate=round(overall_rate, 1), count=latest[-1].count, initial_count=initial,
        ))
    elif overall_rate > 50:
        results.append(_make('funnel_bottleneck', 'info',
            f'Strong funnel: {overall_rate:.1f}% conversion',
            f'{overall_rate:.1f}% of users complete the full funnel — well above average. Keep monitoring for regressions.',
            funnel_step='overall', drop_pct=round(100 - overall_rate, 1),
            conversion_rate=round(overall_rate, 1), count=latest[-1].count, initial_count=initial,
        ))

    return results


# ── Anomaly insights ────────────────────────────────────────────

def _anomaly_insights(project):
    results = []
    today_d = today()
    thirty_days = [today_d - timedelta(days=i) for i in range(30)]

    # Daily event counts for last 30 days
    daily_counts = []
    for d in reversed(thirty_days):
        r = q_ch('''
            SELECT count() FROM insightflow.events
            WHERE project_id = %(pid)s AND toDate(timestamp) = %(d)s
        ''', {'pid': project.id, 'd': d.isoformat()})
        if r:
            daily_counts.append(r.result_rows[0][0] if r.result_rows[0][0] else 0)
        else:
            daily_counts.append(Event.objects.filter(project=project, timestamp__date=d).count())

    if not daily_counts:
        return results

    import statistics
    try:
        mean = statistics.mean(daily_counts)
        stdev = statistics.stdev(daily_counts) if len(daily_counts) > 1 else 0
    except statistics.StatisticsError:
        return results

    today_count = daily_counts[-1]
    if stdev > 0 and abs(today_count - mean) > 2.5 * stdev:
        direction = 'up' if today_count > mean else 'down'
        severity = 'critical' if abs(today_count - mean) > 3.5 * stdev else 'warning'
        results.append(_make('anomaly', severity,
            f'Unusual {"spike" if direction == "up" else "drop"} in events today',
            f'Today\'s event count ({today_count}) is {"{:.1f}".format(abs(today_count - mean) / stdev)} std devs from the 30-day mean ({mean:.0f}). {"Investigate the cause." if direction == "down" else "Something is driving traffic — investigate what changed."}',
            metric='events', current_value=today_count, mean_value=round(mean, 1),
            std_dev=round(stdev, 1), z_score=round((today_count - mean) / stdev, 2) if stdev > 0 else 0,
            direction=direction,
        ))

    return results


# ── Behaviour insights ──────────────────────────────────────────

def _behavior_insights(project):
    results = []
    month_ago = days_ago(30)

    # Top event names
    r = q_ch('''
        SELECT event_name, count() as cnt
        FROM insightflow.events
        WHERE project_id = %(pid)s AND toDate(timestamp) >= %(start)s
        GROUP BY event_name ORDER BY cnt DESC LIMIT 5
    ''', {'pid': project.id, 'start': month_ago.isoformat()})
    if r and r.result_rows:
        top = [{'name': row[0], 'count': row[1]} for row in r.result_rows]
    else:
        rows = Event.objects.filter(project=project, timestamp__date__gte=month_ago).values('event_name').annotate(cnt=Count('id')).order_by('-cnt')[:5]
        top = [{'name': r['event_name'], 'count': r['cnt']} for r in rows]

    if top:
        total = sum(t['count'] for t in top)
        results.append(_make('behavior', 'info',
            f'Top event: {top[0]["name"]}',
            f'"{top[0]["name"]}" is the most frequent event ({top[0]["count"]} times, {round(top[0]["count"] / total * 100, 1)}% of top 5 events).',
            top_events=top,
        ))

    # Device mix
    r = q_ch('''
        SELECT user_agent, uniqExact(user_id) as users
        FROM insightflow.events
        WHERE project_id = %(pid)s AND toDate(timestamp) >= %(start)s AND user_agent != ''
        GROUP BY user_agent ORDER BY users DESC LIMIT 100
    ''', {'pid': project.id, 'start': month_ago.isoformat()})
    def _parse_browser(ua):
        l = ua.lower()
        if 'firefox' in l and 'seamonkey' not in l: return 'Firefox'
        if 'opr' in l or 'opera' in l: return 'Opera'
        if 'edge' in l or 'edg/' in l: return 'Edge'
        if 'chrome' in l and 'chromium' not in l: return 'Chrome'
        if 'safari' in l and 'chrome' not in l: return 'Safari'
        if 'chromium' in l: return 'Chromium'
        return 'Other'
    def _parse_os(ua):
        l = ua.lower()
        if 'windows' in l: return 'Windows'
        if 'mac os' in l or 'macintosh' in l: return 'macOS'
        if 'linux' in l and 'android' not in l: return 'Linux'
        if 'android' in l: return 'Android'
        if 'ios' in l or 'iphone' in l or 'ipad' in l: return 'iOS'
        if 'cros' in l: return 'Chrome OS'
        return 'Other'
    def _parse_device(ua):
        l = ua.lower()
        if 'mobile' in l or 'iphone' in l or 'android' in l:
            if 'tablet' in l or 'ipad' in l: return 'Tablet'
            return 'Mobile'
        if 'tablet' in l or 'ipad' in l: return 'Tablet'
        return 'Desktop'

    if r and r.result_rows:
        device_counts = Counter()
        browser_counts = Counter()
        os_counts = Counter()
        for row in r.result_rows:
            ua = row[0]
            cnt = row[1]
            device_counts[_parse_device(ua)] += cnt
            browser_counts[_parse_browser(ua)] += cnt
            os_counts[_parse_os(ua)] += cnt
        if device_counts:
            top_device = device_counts.most_common(1)[0]
            results.append(_make('behavior', 'info',
                f'Primary device: {top_device[0]}',
                f'{top_device[0]} accounts for {round(top_device[1] / sum(device_counts.values()) * 100, 1)}% of users. Ensure your UX is optimised for this platform.',
                device_type=top_device[0], device_pct=round(top_device[1] / sum(device_counts.values()) * 100, 1),
            ))
        if browser_counts:
            top_browser = browser_counts.most_common(1)[0]
            results.append(_make('behavior', 'info',
                f'Leading browser: {top_browser[0]}',
                f'{top_browser[0]} is used by {round(top_browser[1] / sum(browser_counts.values()) * 100, 1)}% of users.',
                browser=top_browser[0], browser_pct=round(top_browser[1] / sum(browser_counts.values()) * 100, 1),
            ))

    return results


# ── Suggestion insights ─────────────────────────────────────────

def _suggestion_insights(project):
    results = []
    today_d = today()
    month_ago = days_ago(30)

    if not Event.objects.filter(project=project, timestamp__date__gte=month_ago).exists():
        return results

    # Sessions with only one pageview — identify content with highest bounce
    r = q_ch('''
        SELECT
            JSONExtractString(properties, 'url') as page,
            count() as views,
            uniqExact(JSONExtractString(properties, '$session_id')) as sessions
        FROM insightflow.events
        WHERE project_id = %(pid)s
          AND toDate(timestamp) >= %(start)s
          AND event_name IN ('$pageview', 'pageview')
          AND JSONExtractString(properties, 'url') != ''
        GROUP BY page
        ORDER BY views DESC
        LIMIT 20
    ''', {'pid': project.id, 'start': month_ago.isoformat()})
    if r and r.result_rows:
        for row in r.result_rows[:5]:
            page, views, sessions_count = row[0], row[1], row[2]
            if sessions_count > 0 and views / sessions_count < 1.5:
                domain = _get_domain(page)
                short_path = page.split('/')[-1] if page.split('/')[-1] else page
                results.append(_make('suggestion', 'info',
                    f'High bounce: {domain}/{short_path}',
                    f'Page "{domain}/{short_path}" has {views} views across {sessions_count} sessions ({round(views / sessions_count, 1)} views/session). Consider adding clearer CTAs or richer content.',
                    page=page, views=views, sessions=sessions_count, views_per_session=round(views / sessions_count, 1),
                ))

    # No sessions tracked
    has_sessions = Event.objects.filter(project=project, properties__has_key='$session_id', timestamp__date__gte=month_ago).exists()
    if not has_sessions:
        results.append(_make('suggestion', 'info',
            'Enable session tracking',
            'Add the InsightFlow SDK to your site to enable session tracking, user journeys, and bounce rate analytics.',
            action='add_sdk',
        ))

    # Low retention
    retention = RetentionCurve.objects.filter(project=project).order_by('-cohort_date')[:5]
    if retention:
        d1 = [r for r in retention if r.period == 'D1']
        if d1:
            avg_d1 = sum(r.rate for r in d1) / len(d1)
            if avg_d1 < 0.1:
                results.append(_make('suggestion', 'warning',
                    'Low Day-1 retention',
                    f'Only {round(avg_d1 * 100, 1)}% of users return after Day 1. Consider an onboarding email series, in-app nudges, or a rewards programme.',
                    retention_period='D1', retention_rate=round(avg_d1 * 100, 1),
                ))

    # No event mappings
    from semantic.models import EventMapping
    if not EventMapping.objects.filter(project=project).exists():
        results.append(_make('suggestion', 'info',
            'Run semantic detection',
            'Go to Semantic Mapping to auto-categorise your events. This enables funnel analysis and richer insights.',
            action='run_detection',
        ))

    return results
