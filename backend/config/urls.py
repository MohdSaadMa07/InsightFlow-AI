from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),

    # Core API apps
    path('api/v1/', include('events.urls')),
    path('api/v1/', include('api.urls')),
    path('api/v1/', include('users.urls')),
    path('api/v1/', include('projects.urls')),
    path('api/v1/', include('semantic.urls')),

    # Dashboard endpoints (including anomaly data)
    path('api/v1/dashboard/', include('dashboard.urls')),
]

