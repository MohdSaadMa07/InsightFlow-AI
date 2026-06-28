from datetime import timedelta

from celery import shared_task
from django.db.models import Count
from django.utils import timezone

from analytics.models import DailyActiveUser, EventCount, RetentionCurve
from events.models import Event
from projects.models import Project


@shared_task
def compute_dau():

    today = timezone.now().date()
    for project in Project.objects.all():
        count = Event.objects.filter(
            project=project,
            timestamp__date=today
        ).values('user_id').distinct().count()

        DailyActiveUser.objects.update_or_create(
            project=project, date=today,
            defaults={'count': count}
        )


@shared_task
def compute_event_counts():
    today = timezone.now().date()
    for project in Project.objects.all():
        counts = Event.objects.filter(
            project=project, timestamp__date=today
        ).values('event_name').annotate(count=Count('id'))

        for entry in counts:
            EventCount.objects.update_or_create(
                project=project,
                event_name=entry['event_name'],
                date=today,
                defaults={'count': entry['count']}
            )


@shared_task
def compute_retention():
    today = timezone.now().date()
    for project in Project.objects.all():
        for period_days, label in [(1, 'D1'), (7, 'D7'), (30, 'D30')]:
            cohort_date = today - timedelta(days=period_days)
            cutoff = today - timedelta(days=period_days)

            total = Event.objects.filter(
                project=project,
                timestamp__date=cutoff
            ).values('user_id').distinct().count()

            retained = Event.objects.filter(
                project=project,
                timestamp__date=today
            ).values('user_id').distinct().count()

            if total > 0 and retained > 0:
                RetentionCurve.objects.update_or_create(
                    project=project,
                    cohort_date=cohort_date,
                    period=label,
                    defaults={
                        'total_users': total,
                        'retained_users': retained,
                        'rate': round(retained / total, 4),
                    }
                )
