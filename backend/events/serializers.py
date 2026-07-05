from rest_framework import serializers

from events.models import Event

REVENUE_TYPES = ['one_time', 'subscription', 'upgrade', 'refund']
BILLING_PERIODS = ['monthly', 'yearly']


class EventSerializer(serializers.Serializer):
    api_key = serializers.CharField(write_only=True)
    event = serializers.CharField(max_length=255)
    user_id = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    properties = serializers.JSONField(default=dict, required=False)
    timestamp = serializers.DateTimeField(required=False)

    def validate_properties(self, value):
        if not isinstance(value, dict):
            return value
        revenue = value.get('$revenue')
        rev_type = value.get('$revenue_type')
        billing = value.get('$billing_period')

        if revenue is not None:
            try:
                value['$revenue'] = float(revenue)
            except (TypeError, ValueError):
                raise serializers.ValidationError('$revenue must be a number')

        if rev_type is not None and rev_type not in REVENUE_TYPES:
            raise serializers.ValidationError(f'$revenue_type must be one of {REVENUE_TYPES}')

        if rev_type == 'subscription':
            if billing is not None and billing not in BILLING_PERIODS:
                raise serializers.ValidationError(f'$billing_period must be one of {BILLING_PERIODS}')
        elif billing is not None:
            raise serializers.ValidationError('$billing_period is only valid with $revenue_type=subscription')

        return value


class EventReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = '__all__'
