from django.db import models

from projects.models import Project


class DailyActiveUser(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='daily_active_users'
    )
    date = models.DateField(db_index=True)
    count = models.IntegerField(default=0)

    class Meta:
        unique_together = ['project', 'date']
        ordering = ['-date']


class EventCount(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='event_counts'
    )
    event_name = models.CharField(max_length=255)
    date = models.DateField(db_index=True)
    count = models.IntegerField(default=0)

    class Meta:
        unique_together = ['project', 'event_name', 'date']
        ordering = ['-date']


class FunnelDefinition(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='funnel_definitions'
    )
    name = models.CharField(max_length=255)
    steps = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class FunnelAnalysis(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='funnel_analyses'
    )
    funnel = models.ForeignKey(
        FunnelDefinition, on_delete=models.CASCADE, related_name='analyses'
    )
    date = models.DateField()
    step_order = models.IntegerField()
    step_name = models.CharField(max_length=255)
    count = models.IntegerField(default=0)
    conversion_rate = models.FloatField(default=0.0)

    class Meta:
        ordering = ['date', 'step_order']


class RetentionCurve(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='retention_curves'
    )
    cohort_date = models.DateField()
    period = models.CharField(max_length=10)
    retained_users = models.IntegerField(default=0)
    total_users = models.IntegerField(default=0)
    rate = models.FloatField(default=0.0)

    class Meta:
        unique_together = ['project', 'cohort_date', 'period']
        ordering = ['cohort_date']


class AnalyticsResult(models.Model):
    METRIC_CHOICES = [
        ('dau', 'Daily Active Users'),
        ('wau', 'Weekly Active Users'),
        ('mau', 'Monthly Active Users'),
        ('retention', 'Retention'),
        ('funnel', 'Funnel'),
        ('cohort', 'Cohort'),
        ('trend', 'Event Trend'),
    ]
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='analytics_results'
    )
    metric_type = models.CharField(max_length=50, choices=METRIC_CHOICES, db_index=True)
    data = models.JSONField(default=dict)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['project', 'metric_type']),
        ]
        ordering = ['-created_at']
