from celery import shared_task


@shared_task
def process_event(event_id):
    from events.models import Event
    from analytics.models import DailyActiveUser, EventCount

    try:
        event = Event.objects.select_related('project').get(id=event_id)
    except Event.DoesNotExist:
        return

    date = event.timestamp.date()
    project = event.project

    DailyActiveUser.objects.update_or_create(
        project=project,
        date=date,
        defaults={'count': Event.objects.filter(
            project=project,
            timestamp__date=date
        ).values('user_id').distinct().count()}
    )

    EventCount.objects.update_or_create(
        project=project,
        event_name=event.event_name,
        date=date,
        defaults={'count': Event.objects.filter(
            project=project,
            event_name=event.event_name,
            timestamp__date=date
        ).count()}
    )
