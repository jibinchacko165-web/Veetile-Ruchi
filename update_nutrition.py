import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'veetile_ruchi_project.settings')
django.setup()

from food.models import FoodItem, NutritionInfo

nutrition_mapping = {
    'puttu': (300, 6.0, 65.0, 1.5, 4.0, 2.0, 0, 10),
    'kadala': (250, 10.0, 30.0, 12.0, 8.0, 2.0, 0, 450),
    'appam': (120, 2.0, 25.0, 1.0, 1.5, 2.0, 0, 150),
    'stew': (200, 5.0, 15.0, 14.0, 3.0, 2.0, 0, 400),
    'idli': (120, 4.0, 24.0, 0.5, 2.0, 0.0, 0, 120),
    'dosa': (160, 4.0, 28.0, 3.0, 1.5, 0.5, 0, 150),
    'sambar': (150, 6.0, 20.0, 5.0, 6.0, 2.0, 0, 600),
    'chutney': (70, 2.0, 5.0, 5.0, 2.0, 0.5, 0, 300),
    'biriyani': (450, 18.0, 50.0, 20.0, 4.0, 1.0, 50, 800),
    'chicken biriyani': (550, 25.0, 55.0, 22.0, 4.0, 1.0, 80, 850),
    'beef': (350, 25.0, 10.0, 22.0, 2.0, 0.5, 90, 600),
    'fish': (250, 20.0, 5.0, 15.0, 1.0, 0.5, 60, 500),
    'meals': (600, 15.0, 90.0, 15.0, 10.0, 5.0, 5, 900),
    'porotta': (220, 5.0, 35.0, 8.0, 2.0, 1.0, 5, 300),
    'chapathi': (100, 3.0, 18.0, 2.0, 3.0, 0.0, 0, 150),
    'chicken curry': (280, 20.0, 12.0, 18.0, 3.0, 1.5, 70, 550),
    'egg': (140, 12.0, 2.0, 10.0, 0.0, 0.0, 370, 200),
    'payasam': (350, 5.0, 60.0, 10.0, 2.0, 40.0, 10, 50),
    'tea': (60, 2.0, 10.0, 1.5, 0.0, 8.0, 5, 20),
    'coffee': (70, 2.0, 12.0, 1.5, 0.0, 10.0, 5, 20),
    'vada': (150, 4.0, 15.0, 8.0, 2.0, 0.0, 0, 250),
    'pazhampori': (200, 2.0, 35.0, 6.0, 2.5, 15.0, 0, 50),
    'default_veg': (250, 6.0, 35.0, 8.0, 4.0, 3.0, 0, 400),
    'default_nonveg': (380, 22.0, 15.0, 20.0, 2.0, 1.0, 75, 600)
}

foods = FoodItem.objects.all()
updated_count = 0

for food in foods:
    name_lower = food.name.lower()
    desc_lower = food.description.lower()
    
    is_non_veg = any(word in name_lower or word in desc_lower for word in ['chicken', 'beef', 'mutton', 'fish', 'prawn', 'meat', 'egg', 'pork'])
    
    matched = False
    # Sort keys by length descending to match more specific items first (e.g., 'chicken biriyani' before 'biriyani')
    for key in sorted(nutrition_mapping.keys(), key=len, reverse=True):
        if key in name_lower and not key.startswith('default_'):
            cal, pro, carb, fat, fib, sug, chol, sod = nutrition_mapping[key]
            matched = True
            break
            
    if not matched:
        if is_non_veg:
            cal, pro, carb, fat, fib, sug, chol, sod = nutrition_mapping['default_nonveg']
        else:
            cal, pro, carb, fat, fib, sug, chol, sod = nutrition_mapping['default_veg']
            
    try:
        nutrition = food.nutrition
    except NutritionInfo.DoesNotExist:
        nutrition = NutritionInfo(food_item=food)
        
    nutrition.calories = cal
    nutrition.protein = pro
    nutrition.carbohydrates = carb
    nutrition.fat = fat
    nutrition.fiber = fib
    nutrition.sugar = sug
    nutrition.cholesterol = chol
    nutrition.sodium = sod
    
    nutrition.save()
    updated_count += 1

print(f"Successfully updated nutritional information for {updated_count} food items.")
