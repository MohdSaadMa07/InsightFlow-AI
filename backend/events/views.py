from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from events.models import Event
from events.serializers import EventSerializer
from projects.models import APIKey


@api_view(['POST'])
def track_event(request):
    serializer = EventSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    try:
        api_key = APIKey.objects.select_related('project').get(
            key=data['api_key'], is_active=True
        )
    except APIKey.DoesNotExist:
        return Response(
            {'error': 'Invalid or inactive API key'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    event = Event.objects.create(
        project=api_key.project,
        event_name=data['event'],
        user_id=data.get('user_id') or None,
        properties=data.get('properties', {}),
        timestamp=data.get('timestamp', timezone.now()),
    )

    from events.tasks import process_event
    process_event.delay(event.id)

    return Response(
        {'status': 'ok', 'event_id': event.id},
        status=status.HTTP_201_CREATED
    )
