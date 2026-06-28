from django.urls import path

from projects import views

urlpatterns = [
    path('projects/', views.project_list, name='project-list'),
    path('projects/<int:project_id>/', views.project_detail, name='project-detail'),
]
