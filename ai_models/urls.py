from django.urls import path
from . import views

urlpatterns = [
    path('analytics/', views.ai_analytics_dashboard, name='ai_analytics_dashboard'),
]
