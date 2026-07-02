import json

from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from events.kafka import producer
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

    producer.produce({
        'project_id': api_key.project.id,
        'user_id': data.get('user_id') or '',
        'event_name': data['event'],
        'properties': json.dumps(data.get('properties', {})),
        'timestamp': (data.get('timestamp') or timezone.now()).isoformat(),
        'ip_address': request.META.get('REMOTE_ADDR', ''),
        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
    })

    return Response({'status': 'ok'}, status=status.HTTP_201_CREATED)
