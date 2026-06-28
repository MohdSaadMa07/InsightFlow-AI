from django.db import models

from projects.models import Project


class EventMapping(models.Model):
    CATEGORIES = [
        ('discovery', 'Discovery'),
        ('purchase_intent', 'Purchase Intent'),
        ('checkout', 'Checkout'),
        ('conversion', 'Conversion'),
        ('engagement', 'Engagement'),
        ('unknown', 'Unknown'),
    ]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='event_mappings'
    )
    event_name = models.CharField(max_length=255)
    category = models.CharField(max_length=50, choices=CATEGORIES, default='unknown')
    is_auto_detected = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['project', 'event_name']
        ordering = ['event_name']

    def __str__(self):
        return f'{self.event_name} → {self.category}'
