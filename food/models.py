from django.db import models
from django.conf import settings

class Category(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    image = models.CharField(max_length=255, blank=True, null=True)  # URL or static path

    def __str__(self):
        return self.name

class MealSession(models.Model):
    name = models.CharField(max_length=50, unique=True) # e.g. Breakfast, Lunch, Evening Snack, Dinner
    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        return self.name

    def is_active_now(self, current_time=None):
        if current_time is None:
            from django.utils import timezone
            current_time = timezone.localtime().time()
        
        if self.start_time <= self.end_time:
            return self.start_time <= current_time <= self.end_time
        else:
            # Handles time window crossing midnight e.g. 18:30 to 00:00 or overnight
            return current_time >= self.start_time or current_time <= self.end_time


class FoodItem(models.Model):
    chef = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='foods')
    name = models.CharField(max_length=100)
    malayalam_name = models.CharField(max_length=150, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    malayalam_description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='foods')
    meal_session = models.ForeignKey(MealSession, on_delete=models.SET_NULL, null=True, related_name='foods')
    stock_quantity = models.IntegerField(default=10)
    is_available = models.BooleanField(default=True)
    image = models.CharField(max_length=255, blank=True, null=True) # URL or path

    def __str__(self):
        return self.name

class NutritionInfo(models.Model):
    food_item = models.OneToOneField(FoodItem, on_delete=models.CASCADE, related_name='nutrition')
    calories = models.FloatField(default=0.0)      # kcal
    sugar = models.FloatField(default=0.0)         # grams
    cholesterol = models.FloatField(default=0.0)   # mg
    sodium = models.FloatField(default=0.0)        # mg
    protein = models.FloatField(default=0.0)       # grams
    fat = models.FloatField(default=0.0)           # grams
    carbohydrates = models.FloatField(default=0.0) # grams
    fiber = models.FloatField(default=0.0)         # grams

    def __str__(self):
        return f"Nutrition for {self.food_item.name}"

class ReviewSentiment(models.Model):
    SENTIMENT_CHOICES = (
        ('positive', 'Positive'),
        ('neutral', 'Neutral'),
        ('negative', 'Negative'),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE, related_name='reviews')
    rating = models.IntegerField(default=5)
    review_text = models.TextField()
    sentiment = models.CharField(max_length=15, choices=SENTIMENT_CHOICES, default='neutral')
    confidence_score = models.FloatField(default=1.0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review by {self.user.username} on {self.food_item.name}: {self.sentiment}"
