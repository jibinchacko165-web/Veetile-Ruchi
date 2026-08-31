from django.contrib import admin
from .models import MealSession, Category, FoodItem, NutritionInfo, ReviewSentiment

@admin.register(MealSession)
class MealSessionAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_time', 'end_time')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')

@admin.register(FoodItem)
class FoodItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'chef', 'category', 'meal_session', 'price', 'stock_quantity', 'is_available')
    list_filter = ('category', 'meal_session', 'is_available')
    search_fields = ('name', 'chef__username', 'description')

@admin.register(NutritionInfo)
class NutritionInfoAdmin(admin.ModelAdmin):
    list_display = ('food_item', 'calories', 'protein', 'fat', 'carbohydrates', 'sugar', 'sodium')

@admin.register(ReviewSentiment)
class ReviewSentimentAdmin(admin.ModelAdmin):
    list_display = ('food_item', 'user', 'rating', 'sentiment', 'confidence_score', 'created_at')
    list_filter = ('sentiment', 'rating')
