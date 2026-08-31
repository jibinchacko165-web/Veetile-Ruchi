from django.urls import path
from . import views

urlpatterns = [
    path('profile/', views.health_profile_view, name='health_profile'),
    path('meal-planner/', views.meal_planner_view, name='meal_planner'),
]
