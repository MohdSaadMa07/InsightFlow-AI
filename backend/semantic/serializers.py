from rest_framework import serializers

from semantic.models import EventMapping


class EventMappingSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventMapping
        fields = ['id', 'event_name', 'category', 'is_auto_detected', 'created_at', 'updated_at']
        read_only_fields = ['id', 'event_name', 'is_auto_detected', 'created_at', 'updated_at']


class EventMappingBulkSerializer(serializers.Serializer):
    mappings = EventMappingSerializer(many=True)


class DetectResultSerializer(serializers.Serializer):
    event_name = serializers.CharField()
    suggested_category = serializers.CharField()
    confidence = serializers.FloatField()
    status = serializers.CharField()
