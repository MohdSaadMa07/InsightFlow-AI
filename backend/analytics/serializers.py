from rest_framework import serializers

from analytics.models import (
    AnalyticsResult,
    DailyActiveUser,
    EventCount,
    FunnelAnalysis,
    FunnelDefinition,
    RetentionCurve,
)


class DailyActiveUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyActiveUser
        fields = '__all__'


class EventCountSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventCount
        fields = '__all__'


class FunnelDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FunnelDefinition
        fields = '__all__'


class FunnelAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = FunnelAnalysis
        fields = '__all__'


class RetentionCurveSerializer(serializers.ModelSerializer):
    class Meta:
        model = RetentionCurve
        fields = '__all__'


class AnalyticsResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalyticsResult
        fields = '__all__'
