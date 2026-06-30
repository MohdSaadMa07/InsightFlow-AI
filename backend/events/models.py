from django.db import models

from projects.models import Project


class Event(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='events'
    )
    user_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    event_name = models.CharField(max_length=255, db_index=True)
    properties = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['project', 'event_name']),
            models.Index(fields=['project', 'timestamp']),
            models.Index(fields=['project', 'user_id']),
        ]
        ordering = ['-timestamp']
