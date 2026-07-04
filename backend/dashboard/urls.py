from django.urls import path

from dashboard import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('churn/', views.churn_dashboard, name='churn_dashboard'),
    path('churn/data/', views.churn_data, name='churn_data'),
    path('churn/explain/<str:user_id>/', views.churn_explain, name='churn_explain'),
]
