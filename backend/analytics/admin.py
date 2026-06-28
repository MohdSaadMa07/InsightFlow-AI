from django.contrib import admin

from analytics.models import (
    AnalyticsResult,
    DailyActiveUser,
    EventCount,
    FunnelAnalysis,
    FunnelDefinition,
    RetentionCurve,
)

admin.site.register(DailyActiveUser)
admin.site.register(EventCount)
admin.site.register(FunnelDefinition)
admin.site.register(FunnelAnalysis)
admin.site.register(RetentionCurve)
admin.site.register(AnalyticsResult)
