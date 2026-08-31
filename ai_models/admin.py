from django.contrib import admin
from .models import FoodDemandForecast, FoodWastePrediction, StockPrediction, CustomerBehavior

@admin.register(FoodDemandForecast)
class FoodDemandForecastAdmin(admin.ModelAdmin):
    list_display = ('food_item', 'forecast_date', 'predicted_quantity', 'confidence_score')

@admin.register(FoodWastePrediction)
class FoodWastePredictionAdmin(admin.ModelAdmin):
    list_display = ('food_item', 'prediction_date', 'predicted_waste_quantity')

@admin.register(StockPrediction)
class StockPredictionAdmin(admin.ModelAdmin):
    list_display = ('food_item', 'prediction_date', 'predicted_days_until_out_of_stock', 'stock_needed_refill')

@admin.register(CustomerBehavior)
class CustomerBehaviorAdmin(admin.ModelAdmin):
    list_display = ('user', 'total_orders_count', 'average_order_value', 'behavior_segment')
    list_filter = ('behavior_segment',)
