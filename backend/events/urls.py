from django.urls import path

from events import views

urlpatterns = [
    path('track/', views.track_event, name='track-event'),
]
