from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('events.urls')),
    path('api/v1/', include('api.urls')),
    path('api/v1/', include('users.urls')),
    path('api/v1/', include('projects.urls')),
    path('api/v1/', include('semantic.urls')),
    path('', include('dashboard.urls')),
]
