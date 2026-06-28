from rest_framework import serializers

from projects.models import Project


class ProjectSerializer(serializers.ModelSerializer):
    api_key = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = ['id', 'name', 'api_key', 'created_at', 'updated_at']
        read_only_fields = ['id', 'api_key', 'created_at', 'updated_at']

    def get_api_key(self, obj):
        key = obj.api_keys.filter(is_active=True).first()
        return key.key if key else None
