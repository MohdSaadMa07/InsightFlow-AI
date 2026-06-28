from django.db import models

from projects.models import Project


def category_default_used_in_funnel(category):
    return category in ('discovery', 'purchase_intent', 'checkout', 'conversion')


class EventMapping(models.Model):
    CATEGORIES = [
        ('authentication', 'Authentication'),
        ('discovery', 'Discovery'),
        ('engagement', 'Engagement'),
        ('purchase_intent', 'Purchase Intent'),
        ('checkout', 'Checkout'),
        ('conversion', 'Conversion'),
        ('exit', 'Exit'),
        ('support', 'Support'),
        ('unknown', 'Unknown'),
    ]

    FUNNEL_CATEGORIES = ['discovery', 'purchase_intent', 'checkout', 'conversion']

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='event_mappings'
    )
    event_name = models.CharField(max_length=255)
    category = models.CharField(max_length=50, choices=CATEGORIES, default='unknown')
    used_in_funnel = models.BooleanField(default=False)
    is_auto_detected = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['project', 'event_name']
        ordering = ['event_name']

    def __str__(self):
        return f'{self.event_name} → {self.category}'
