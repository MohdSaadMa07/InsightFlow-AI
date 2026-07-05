from django.db import models


class AnomalyIncident(models.Model):
    """Persists anomaly incidents for the incident log view."""

    STATUS_CHOICES = [
        ('open', 'Open'),
        ('investigating', 'Investigating'),
        ('resolved', 'Resolved'),
    ]

    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    project_id = models.IntegerField(db_index=True)
    window_start = models.DateField()
    severity = models.CharField(max_length=16, choices=SEVERITY_CHOICES, default='low')
    score = models.FloatField()
    threshold = models.FloatField(default=0.0)
    description = models.TextField(blank=True, default='')
    top_features = models.JSONField(default=list)
    recommendations = models.JSONField(default=list)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-window_start']
        indexes = [
            models.Index(fields=['project_id', 'window_start']),
            models.Index(fields=['project_id', 'status']),
        ]

    def __str__(self):
        return f"Incident [{self.severity}] project={self.project_id} date={self.window_start}"
