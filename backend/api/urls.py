from django.urls import path

from api import views

urlpatterns = [
    path('dashboard/overview/', views.overview, name='dashboard-overview'),
    path('dashboard/events/', views.event_trends, name='dashboard-events'),
    path('dashboard/funnels/', views.funnels, name='dashboard-funnels'),
    path('dashboard/retention/', views.retention, name='dashboard-retention'),
    path('dashboard/realtime/', views.realtime, name='dashboard-realtime'),
    path('dashboard/pages/', views.top_pages, name='dashboard-pages'),
    path('dashboard/countries/', views.countries, name='dashboard-countries'),
    path('dashboard/devices/', views.devices, name='dashboard-devices'),
    path('dashboard/sessions/', views.sessions, name='dashboard-sessions'),
    path('dashboard/insights/', views.insights, name='dashboard-insights'),
]
