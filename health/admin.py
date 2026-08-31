from django.contrib import admin
from .models import HealthProfile, HealthRecommendation

@admin.register(HealthProfile)
class HealthProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'has_diabetes', 'has_cholesterol', 'has_bp', 'dietary_preference', 'daily_calorie_target')
    list_filter = ('has_diabetes', 'has_cholesterol', 'has_bp', 'dietary_preference')

@admin.register(HealthRecommendation)
class HealthRecommendationAdmin(admin.ModelAdmin):
    list_display = ('user', 'recommended_food', 'score', 'generated_at')
