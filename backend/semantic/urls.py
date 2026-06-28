from django.urls import path

from semantic import views

urlpatterns = [
    path('semantic/detect/', views.detect, name='semantic-detect'),
    path('semantic/mappings/', views.list_mappings, name='semantic-list'),
    path('semantic/mappings/<int:mapping_id>/', views.update_mapping, name='semantic-update'),
    path('semantic/compute-funnel/', views.compute_funnel, name='semantic-compute-funnel'),
]
