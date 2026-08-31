from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import HealthProfile, HealthRecommendation
from food.models import FoodItem
from ai_models.ml_engine import plan_meals

@login_required
def health_profile_view(request):
    """Enables customer to manage health details."""
    profile, created = HealthProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        profile.has_diabetes = request.POST.get('has_diabetes') == 'on'
        profile.has_cholesterol = request.POST.get('has_cholesterol') == 'on'
        profile.has_bp = request.POST.get('has_bp') == 'on'
        profile.allergies = request.POST.get('allergies', '')
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
