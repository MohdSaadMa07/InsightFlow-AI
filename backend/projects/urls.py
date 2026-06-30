from django.urls import path

from projects import views

urlpatterns = [
    path('projects/', views.project_list, name='project-list'),
    path('projects/<int:project_id>/', views.project_detail, name='project-detail'),
    path('projects/<int:project_id>/keys/', views.list_keys, name='project-keys'),
    path('projects/<int:project_id>/regenerate-key/', views.regenerate_key, name='project-regenerate-key'),
]
