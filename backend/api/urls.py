from django.urls import path

from api import views

urlpatterns = [
    path('dashboard/overview/', views.overview, name='dashboard-overview'),
    path('dashboard/events/', views.event_trends, name='dashboard-events'),
    path('dashboard/funnels/', views.funnels, name='dashboard-funnels'),
    path('dashboard/retention/', views.retention, name='dashboard-retention'),
]
