from django.db import models
from django.conf import settings
from food.models import FoodItem, Category, MealSession

class FoodDemandForecast(models.Model):
    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE, related_name='demand_forecasts')
    forecast_date = models.DateField()
    predicted_quantity = models.FloatField(default=0.0)
    confidence_score = models.FloatField(default=1.0)

    def __str__(self):
        return f"{self.food_item.name} forecast for {self.forecast_date}: {self.predicted_quantity}"

class FoodWastePrediction(models.Model):
    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE, related_name='waste_predictions')
    prediction_date = models.DateField()
    predicted_waste_quantity = models.FloatField(default=0.0) # predicted portions wasted or kg

    def __str__(self):
        return f"{self.food_item.name} waste forecast for {self.prediction_date}: {self.predicted_waste_quantity}"

class StockPrediction(models.Model):
    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE, related_name='stock_predictions')
    prediction_date = models.DateField()
    predicted_days_until_out_of_stock = models.FloatField(default=5.0)
    stock_needed_refill = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.food_item.name} stock refill prediction: {self.stock_needed_refill} portions"

class CustomerBehavior(models.Model):
    BEHAVIOR_SEGMENTS = (
        ('high_value', 'High-Value Customer'),
        ('regular', 'Regular Customer'),
        ('occasional', 'Occasional Customer'),
    )
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='behavior')
    total_orders_count = models.IntegerField(default=0)
    average_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    most_ordered_session = models.ForeignKey(MealSession, on_delete=models.SET_NULL, null=True, blank=True)
    most_ordered_category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    behavior_segment = models.CharField(max_length=20, choices=BEHAVIOR_SEGMENTS, default='occasional')

    def __str__(self):
        return f"Behavior of {self.user.username}: {self.get_behavior_segment_display()}"
