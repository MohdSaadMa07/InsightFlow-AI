from rest_framework import serializers

from events.models import Event


class EventSerializer(serializers.Serializer):
    api_key = serializers.CharField(write_only=True)
    event = serializers.CharField(max_length=255)
    user_id = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    properties = serializers.JSONField(default=dict, required=False)
    timestamp = serializers.DateTimeField(required=False)


class EventReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = '__all__'
