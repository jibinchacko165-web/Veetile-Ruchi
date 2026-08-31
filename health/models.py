from django.db import models
from django.conf import settings
from food.models import FoodItem

class HealthProfile(models.Model):
    DIET_PREF_CHOICES = (
        ('any', 'No Preference'),
        ('veg', 'Vegetarian'),
        ('non_veg', 'Non-Vegetarian'),
        ('vegan', 'Vegan'),
        ('keto', 'Keto-Friendly'),
    )
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='health_profile')
    has_diabetes = models.BooleanField(default=False)
    has_cholesterol = models.BooleanField(default=False)
    has_bp = models.BooleanField(default=False) # High blood pressure
    allergies = models.TextField(blank=True, null=True, help_text="Comma-separated values, e.g. peanuts, dairy")
    dietary_preference = models.CharField(max_length=20, choices=DIET_PREF_CHOICES, default='any')
    daily_calorie_target = models.FloatField(default=2000.0)

    def __str__(self):
        return f"Health Profile: {self.user.username}"

class HealthRecommendation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='health_recommendations')
    recommended_food = models.ForeignKey(FoodItem, on_delete=models.CASCADE)
    reason = models.TextField()
    score = models.FloatField(default=1.0)
    generated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Rec for {self.user.username}: {self.recommended_food.name}"
