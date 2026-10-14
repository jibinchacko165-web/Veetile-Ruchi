from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.contrib import messages
from .models import HealthProfile, HealthRecommendation
from food.models import FoodItem
from ai_models.ml_engine import plan_meals

@never_cache
@login_required
def health_profile_view(request):
    """Enables customer to manage health details."""
    profile, created = HealthProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        profile.diabetes_conscious = request.POST.get('diabetes_conscious') == 'on'
        profile.cholesterol_conscious = request.POST.get('cholesterol_conscious') == 'on'
        profile.sugar_conscious = request.POST.get('sugar_conscious') == 'on'
        profile.lower_saturated_fat = request.POST.get('lower_saturated_fat') == 'on'
        profile.calorie_awareness = request.POST.get('calorie_awareness') == 'on'
        profile.enable_recommendations = request.POST.get('enable_recommendations') == 'on'
        
        profile.allergies = request.POST.get('allergies', '')
        profile.dislikes = request.POST.get('dislikes', '')
        profile.dietary_preference = request.POST.get('dietary_preference', 'any')
        
        try:
            profile.daily_calorie_target = float(request.POST.get('daily_calorie_target', '') or 2000.0)
        except (ValueError, TypeError):
            profile.daily_calorie_target = 2000.0
            
        profile.save()
        
        # Clear old recommendations to trigger regeneration
        HealthRecommendation.objects.filter(user=request.user).delete()
        
        messages.success(request, "Health Profile updated. Recommended menu will update on the catalog.")
        return redirect('health_profile')
        
    return render(request, 'health/profile.html', {'profile': profile})

@never_cache
@login_required
def meal_planner_view(request):
    """Retrieves menu options and builds a daily recommended breakfast/lunch/snack/dinner plan using KNN."""
    profile = getattr(request.user, 'health_profile', None)
    all_foods = FoodItem.objects.filter(is_available=True)
    
    if not all_foods.exists():
        messages.warning(request, "No foods available to formulate a meal plan.")
        return redirect('food_catalog')
        
    plan, target_calories = plan_meals(all_foods, profile)
    
    context = {
        'plan': plan,
        'target_calories': target_calories,
        'profile': profile,
    }
    return render(request, 'health/meal_planner.html', context)
