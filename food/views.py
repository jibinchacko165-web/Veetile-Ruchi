import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Avg, Sum, Count, F, FloatField
from .models import FoodItem, Category, MealSession, NutritionInfo, ReviewSentiment
from accounts.models import User, ChefProfile, DeliveryBoyProfile
from accounts.decorators import role_required
from orders.models import Wishlist, Order, OrderItem, Coupon, Payment
from delivery.models import DeliveryAssignment, GPSLocationTracking
from health.models import HealthProfile, HealthRecommendation
from ai_models.models import FoodDemandForecast, FoodWastePrediction, StockPrediction, CustomerBehavior
from ai_models.ml_engine import (
    analyze_review_sentiment, 
    recommend_foods_content_based, 
    predict_health_suitability, 
    get_forecasts,
    classify_health_profile_risk,
    recommend_health_and_time_aware_foods
)

def food_catalog(request):
    """Customer dashboard and central food browsing portal with automatic time-based session filtering."""
    if request.user.is_authenticated and request.user.role == 'delivery_boy':
        messages.info(request, "Redirected to your Delivery Portal.")
        return redirect('delivery_boy_dashboard')

    query = request.GET.get('q', '')
    cat_filter = request.GET.get('category', '')
    raw_session = request.GET.get('session', None)
    
    current_time = timezone.localtime().time()
    sessions = list(MealSession.objects.all().order_by('start_time'))
    
    active_session = None
    for s in sessions:
        if s.is_active_now(current_time):
            active_session = s
            break

    # Determine session filter - Default to active meal session if no query parameter supplied
    if raw_session is None or raw_session == '':
        if active_session:
            session_filter = active_session.name
        else:
            session_filter = 'All'
    else:
        session_filter = raw_session

    foods = FoodItem.objects.filter(is_available=True)
    if query:
        foods = foods.filter(Q(name__icontains=query) | Q(description__icontains=query))
    if cat_filter:
        foods = foods.filter(category__name=cat_filter)
    if session_filter and session_filter != 'All':
        foods = foods.filter(meal_session__name__icontains=session_filter)
        
    categories = Category.objects.all()
    
    session_pills = []
    active_session_short_name = ""

    for s in sessions:
        s.is_active = (active_session and s.id == active_session.id)
        name_lower = s.name.lower()
        if 'breakfast' in name_lower:
            icon = '☀️'
            short_name = 'Breakfast'
        elif 'lunch' in name_lower:
            icon = '🍴'
            short_name = 'Lunch'
        elif 'snack' in name_lower:
            icon = '🍪'
            short_name = 'Snacks'
        elif 'dinner' in name_lower:
            icon = '🌙'
            short_name = 'Dinner'
        else:
            icon = '🍽️'
            short_name = s.name

        if s.is_active:
            active_session_short_name = short_name

        is_selected = False
        if session_filter and session_filter != 'All':
            if session_filter.lower() in name_lower or session_filter.lower() == short_name.lower():
                is_selected = True

        session_pills.append({
            'obj': s,
            'name': s.name,
            'short_name': short_name,
            'icon': icon,
            'is_active': s.is_active,
            'is_selected': is_selected
        })
    
    # Wishlist IDs for currently logged in user
    wish_ids = []
    ai_recs = []
    health_risk = 'Low'
    health_recs = []
    health_combined_reason = ""
    target_rec_session = ""
    rec_food_ids = []
    
    if request.user.is_authenticated:
        profile, created = HealthProfile.objects.get_or_create(user=request.user)

        # Allow inline health filter toggling from catalog POST
        if request.method == 'POST' and 'update_health_filters' in request.POST:
            profile.has_diabetes = (request.POST.get('has_diabetes') == 'on')
            profile.has_cholesterol = (request.POST.get('has_cholesterol') == 'on')
            profile.has_bp = (request.POST.get('has_bp') == 'on')
            profile.save()
            messages.success(request, "AI Health Condition filters updated!")
            return redirect('food_catalog')

        wish_ids = list(Wishlist.objects.filter(user=request.user).values_list('food_item_id', flat=True))
        
        # 1. AI Recommendation: Content-Based from Wishlist
        user_wishes = [w.food_item for w in Wishlist.objects.filter(user=request.user)]
        all_avail = list(FoodItem.objects.filter(is_available=True))
        ai_recs = recommend_foods_content_based(all_avail, user_wishes, limit=4)
        
        # 2. AI Health Profile & Meal-Time Aware Recommendations
        health_risk = classify_health_profile_risk(profile.has_diabetes, profile.has_cholesterol, profile.has_bp)
        
        # Target active meal session name (Prioritizes session filter or current active application time)
        if session_filter and session_filter != 'All':
            target_rec_session = session_filter
        elif active_session:
            target_rec_session = active_session.name
        else:
            target_rec_session = 'Morning Breakfast'

        recommended_food_objs, health_combined_reason = recommend_health_and_time_aware_foods(
            all_avail,
            profile,
            active_session_name=target_rec_session,
            limit=4
        )

        for food in recommended_food_objs:
            rec_food_ids.append(food.id)
            # Save to HealthRecommendation model
            HealthRecommendation.objects.get_or_create(
                user=request.user,
                recommended_food=food,
                defaults={'reason': health_combined_reason, 'score': 0.95}
            )
            health_recs.append({
                'food': food,
                'reason': health_combined_reason
            })
        
    context = {
        'foods': foods,
        'categories': categories,
        'sessions': sessions,
        'session_pills': session_pills,
        'active_session': active_session,
        'active_session_short_name': active_session_short_name,
        'current_time': current_time,
        'query': query,
        'cat_filter': cat_filter,
        'session_filter': session_filter,
        'wish_ids': wish_ids,
        'ai_recs': ai_recs,
        'health_risk': health_risk,
        'health_recs': health_recs,
        'health_combined_reason': health_combined_reason,
        'target_rec_session': target_rec_session,
        'rec_food_ids': rec_food_ids,
    }
    return render(request, 'food/catalog.html', context)

def food_detail(request, pk):
    """Displays detailed nutritional properties and customer reviews with AI sentiment analysis."""
    if request.user.is_authenticated and request.user.role == 'delivery_boy':
        messages.info(request, "Menu browsing is restricted for Couriers.")
        return redirect('delivery_boy_dashboard')

    food = get_object_or_404(FoodItem, pk=pk)
    reviews = food.reviews.all().order_by('-created_at')
    
    # Calculate average rating
    avg_rating = reviews.aggregate(Avg('rating'))['rating__avg']
    avg_rating = round(avg_rating, 1) if avg_rating else 5.0
    
    # Suitability indicators
    suitability = {}
    if hasattr(food, 'nutrition'):
        suitability = predict_health_suitability(
            food.nutrition.sugar, 
            food.nutrition.cholesterol, 
            food.nutrition.sodium
        )
        
    if request.method == 'POST' and request.user.is_authenticated:
        rating = int(request.POST.get('rating', 5))
        review_text = request.POST.get('review_text', '')
        
        if not review_text.strip():
            messages.error(request, "Review comment cannot be empty.")
            return redirect('food_detail', pk=pk)
            
        # AI Sentiment prediction
        sentiment, conf = analyze_review_sentiment(review_text)
        
        ReviewSentiment.objects.create(
            user=request.user,
            food_item=food,
            rating=rating,
            review_text=review_text,
            sentiment=sentiment,
            confidence_score=conf
        )
        
        messages.success(request, f"Review submitted. AI classified sentiment: {sentiment.upper()} (Confidence: {int(conf*100)}%)")
        return redirect('food_detail', pk=pk)
        
    context = {
        'food': food,
        'reviews': reviews,
        'avg_rating': avg_rating,
        'suitability': suitability,
    }
    return render(request, 'food/detail.html', context)

@login_required
def wishlist_toggle(request, pk):
    food = get_object_or_404(FoodItem, pk=pk)
    wish, created = Wishlist.objects.get_or_create(user=request.user, food_item=food)
    if not created:
        wish.delete()
        is_favorited = False
        msg = f"Removed '{food.name}' from your wishlist."
        messages.info(request, msg)
    else:
        is_favorited = True
        msg = f"Added '{food.name}' to your wishlist."
        messages.success(request, msg)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        wishlist_count = Wishlist.objects.filter(user=request.user).count()
        return JsonResponse({
            'status': 'success',
            'is_favorited': is_favorited,
            'wishlist_count': wishlist_count,
            'message': msg
        })

    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('food_catalog')

@never_cache
@login_required
@role_required('chef', 'admin')
def chef_dashboard(request):
    """Chef dashboard view showing incoming orders, chef approval status, and AI predictions."""
    chef_profile = getattr(request.user, 'chef_profile', None)
    is_approved = chef_profile.is_approved if chef_profile else True

    if chef_profile and not chef_profile.is_approved:
        messages.warning(
            request, 
            "Your Chef Profile is currently PENDING APPROVAL from Staff/Admin. "
            "You can view your dashboard and update profile details, but you cannot manage or publish menu items until approved."
        )

    chef_foods = FoodItem.objects.all() if request.user.role == 'admin' else FoodItem.objects.filter(Q(chef=request.user) | Q(chef__isnull=True))
    orders_items = OrderItem.objects.select_related('order', 'food_item', 'food_item__meal_session', 'food_item__category').order_by('-order__created_at')
    
    # Calculate AI forecasting for each food
    forecasts = []
    order_items_all = list(OrderItem.objects.all())
    today_weekday = datetime.datetime.now().weekday()
    
    for food in chef_foods:
        demand, waste, deplete_days = get_forecasts(food, order_items_all, day_of_week=today_weekday)
        
        # Store in DB tables
        FoodDemandForecast.objects.update_or_create(
            food_item=food,
            forecast_date=datetime.date.today(),
            defaults={'predicted_quantity': demand, 'confidence_score': 0.85}
        )
        FoodWastePrediction.objects.update_or_create(
            food_item=food,
            prediction_date=datetime.date.today(),
            defaults={'predicted_waste_quantity': waste}
        )
        
        refill_needed = max(0, int(demand * 1.2) - food.stock_quantity)
        StockPrediction.objects.update_or_create(
            food_item=food,
            prediction_date=datetime.date.today(),
            defaults={'predicted_days_until_out_of_stock': deplete_days, 'stock_needed_refill': refill_needed}
        )
        
        forecasts.append({
            'food': food,
            'demand': demand,
            'waste': waste,
            'deplete_days': deplete_days,
            'refill': refill_needed,
            'out_of_stock_warning': deplete_days < 2.0
        })
        
    context = {
        'chef_profile': chef_profile,
        'is_approved': is_approved,
        'foods': chef_foods,
        'order_items': orders_items,
        'forecasts': forecasts,
    }
    return render(request, 'food/chef_dashboard.html', context)


@login_required
@role_required('chef', 'admin')
def api_chef_orders(request):
    """Real-time API endpoint returning pending/active kitchen orders for the Chef Portal."""
    if request.user.role not in ['chef', 'admin']:
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    order_items = OrderItem.objects.filter(
        order__status__in=['pending', 'preparing', 'ready_pickup']
    ).select_related('order', 'food_item', 'food_item__meal_session', 'food_item__category').order_by('-order__created_at')

    data = []
    for item in order_items:
        data.append({
            'order_id': item.order.order_id,
            'food_id': f"FOOD{item.food_item.id:04d}",
            'food_name': item.food_item.name,
            'quantity': item.quantity,
            'category': item.food_item.category.name if item.food_item.category else 'General',
            'session': item.food_item.meal_session.name if item.food_item.meal_session else 'All Day',
            'status': item.order.status,
            'status_display': item.order.get_status_display(),
            'created_at': item.order.created_at.strftime("%b %d, %Y • %I:%M %p"),
        })

    return JsonResponse({
        'status': 'success',
        'count': len(data),
        'has_pending': any(item['status'] == 'pending' for item in data),
        'orders': data
    })

@login_required
@role_required('chef', 'admin')
def chef_food_manage(request, pk=None):
    """Add/Edit/Delete food items and their nutrition profiles (Approval required)."""
    chef_profile = getattr(request.user, 'chef_profile', None)
    if chef_profile and not chef_profile.is_approved and request.user.role == 'chef':
        messages.error(request, "Your Chef account is pending approval by staff/admin. You cannot add or edit menu items until approved.")
        return redirect('chef_dashboard')
        
    categories = Category.objects.all()
    sessions = MealSession.objects.all()
    
    food = None
    if pk:
        food = get_object_or_404(FoodItem, pk=pk, chef=request.user)
        
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete' and food:
            food.delete()
            messages.success(request, "Food item deleted.")
            return redirect('chef_dashboard')
            
        name = request.POST.get('name')
        description = request.POST.get('description')
        try:
            price = float(request.POST.get('price', '') or 0.0)
        except (ValueError, TypeError):
            price = 0.0
        cat_id = request.POST.get('category')
        sess_id = request.POST.get('session')
        try:
            stock = int(request.POST.get('stock', '') or 10)
        except (ValueError, TypeError):
            stock = 10
            
        image_file = request.FILES.get('image_file')
        if image_file:
            from django.core.files.storage import FileSystemStorage
            from django.conf import settings
            fs = FileSystemStorage(location=settings.MEDIA_ROOT / 'food_photos', base_url='/media/food_photos/')
            filename = fs.save(image_file.name, image_file)
            image = fs.url(filename)
        else:
            image = request.POST.get('image', '')
            if not image and food:
                image = food.image
            elif not image:
                image = '/static/images/food-placeholder.jpg'
                
        is_avail = request.POST.get('is_available') == 'on'
        
        category = Category.objects.get(id=cat_id) if cat_id else None
        session = MealSession.objects.get(id=sess_id) if sess_id else None
        
        if food:
            food.name = name
            food.description = description
            food.price = price
            food.category = category
            food.meal_session = session
            food.stock_quantity = stock
            food.image = image
            food.is_available = is_avail
            food.save()
        else:
            food = FoodItem.objects.create(
                chef=request.user,
                name=name,
                description=description,
                price=price,
                category=category,
                meal_session=session,
                stock_quantity=stock,
                image=image,
                is_available=is_avail
            )
            
        # Update Nutrition Info
        nutrition, _ = NutritionInfo.objects.get_or_create(food_item=food)
        try:
            nutrition.calories = float(request.POST.get('calories', '') or 0.0)
        except (ValueError, TypeError):
            nutrition.calories = 0.0
        try:
            nutrition.sugar = float(request.POST.get('sugar', '') or 0.0)
        except (ValueError, TypeError):
            nutrition.sugar = 0.0
        try:
            nutrition.cholesterol = float(request.POST.get('cholesterol', '') or 0.0)
        except (ValueError, TypeError):
            nutrition.cholesterol = 0.0
        try:
            nutrition.sodium = float(request.POST.get('sodium', '') or 0.0)
        except (ValueError, TypeError):
            nutrition.sodium = 0.0
        try:
            nutrition.protein = float(request.POST.get('protein', '') or 0.0)
        except (ValueError, TypeError):
            nutrition.protein = 0.0
        try:
            nutrition.fat = float(request.POST.get('fat', '') or 0.0)
        except (ValueError, TypeError):
            nutrition.fat = 0.0
        try:
            nutrition.carbohydrates = float(request.POST.get('carbohydrates', '') or 0.0)
        except (ValueError, TypeError):
            nutrition.carbohydrates = 0.0
        try:
            nutrition.fiber = float(request.POST.get('fiber', '') or 0.0)
        except (ValueError, TypeError):
            nutrition.fiber = 0.0
        nutrition.save()
        
        messages.success(request, f"Food '{name}' saved successfully.")
        return redirect('chef_dashboard')
        
    context = {
        'food': food,
        'categories': categories,
        'sessions': sessions,
    }
    return render(request, 'food/food_form.html', context)

@login_required
@role_required('chef', 'admin')
def chef_order_status_update(request, order_id):
    """Allows Chef to update preparation status for their own kitchen order."""
    if request.user.role != 'chef' and request.user.role != 'admin':
        messages.error(request, "Access Denied.")
        return redirect('dashboard_redirect')
        
    order = get_object_or_404(Order, order_id=order_id)

    new_status = request.POST.get('status')
    if new_status in ['preparing', 'ready_pickup']:
        order.status = new_status
        order.save()
        messages.success(request, f"Order status updated to {order.get_status_display()}.")
    return redirect('chef_dashboard')

@never_cache
@login_required
@role_required('admin')
def admin_dashboard(request, section='overview'):
    """Comprehensive Admin control center detailing global business statistics, ML sentiments, data tables, etc."""
    today = timezone.localtime().date()
    seven_days_ago = today - datetime.timedelta(days=7)
    thirty_days_ago = today - datetime.timedelta(days=30)
    
    # 1. Customers stats
    total_customers = User.objects.filter(role='customer').count()
    active_customers = User.objects.filter(role='customer', is_active=True).count()
    inactive_customers = User.objects.filter(role='customer', is_active=False).count()
    
    # 2. Team members stats
    total_chefs = User.objects.filter(role='chef').count()
    total_staff = User.objects.filter(role='staff').count()
    total_delivery_boys = User.objects.filter(role='delivery_boy').count()
    active_delivery_boys = DeliveryBoyProfile.objects.filter(status='available').count()
    busy_delivery_boys = DeliveryBoyProfile.objects.filter(status__in=['on_delivery', 'busy']).count()
    inactive_delivery_boys = DeliveryBoyProfile.objects.filter(status='offline').count()
    
    # 3. Food & Categories stats
    total_foods = FoodItem.objects.count()
    available_foods = FoodItem.objects.filter(is_available=True, stock_quantity__gt=0).count()
    out_of_stock_foods = FoodItem.objects.filter(Q(stock_quantity__lte=0) | Q(is_available=False)).count()
    total_categories = Category.objects.count()
    
    popular_cat_obj = Category.objects.annotate(order_count=Count('foods__orderitem')).order_by('-order_count').first()
    popular_category = popular_cat_obj.name if popular_cat_obj else "Kerala Delicacies"
    
    # 4. Orders stats
    total_orders = Order.objects.count()
    today_orders = Order.objects.filter(created_at__date=today).count()
    pending_orders = Order.objects.filter(status='pending').count()
    processing_orders = Order.objects.filter(status__in=['preparing', 'ready_pickup', 'assigned']).count()
    in_transit_orders = Order.objects.filter(status='in_transit').count()
    completed_orders = Order.objects.filter(status='delivered').count()
    cancelled_orders = Order.objects.filter(status='cancelled').count()
    
    # 5. Revenue & Food Sales Analytics
    valid_orders_qs = Order.objects.exclude(status='cancelled').exclude(payment__status='failed')

    def make_day_range(target_date):
        start_dt = timezone.make_aware(datetime.datetime.combine(target_date, datetime.time.min))
        end_dt = timezone.make_aware(datetime.datetime.combine(target_date, datetime.time.max))
        return start_dt, end_dt

    start_today, end_today = make_day_range(today)
    start_7days, _ = make_day_range(seven_days_ago)
    first_of_this_month = today.replace(day=1)
    start_month, _ = make_day_range(first_of_this_month)

    total_revenue = float(valid_orders_qs.aggregate(total=Sum('total_amount'))['total'] or 0.00)
    today_revenue = float(valid_orders_qs.filter(created_at__range=(start_today, end_today)).aggregate(total=Sum('total_amount'))['total'] or 0.00)
    monthly_revenue = float(valid_orders_qs.filter(created_at__gte=start_month).aggregate(total=Sum('total_amount'))['total'] or 0.00)
    weekly_revenue = float(valid_orders_qs.filter(created_at__gte=start_7days).aggregate(total=Sum('total_amount'))['total'] or 0.00)

    # Date-based filtering for Food Sales Analytics & Selected Period Revenue
    period = request.GET.get('period', 'all').strip()
    selected_date_str = request.GET.get('date', '').strip()
    selected_month_str = request.GET.get('month', '').strip()
    start_date_str = request.GET.get('start_date', '').strip()
    end_date_str = request.GET.get('end_date', '').strip()

    filtered_orders_qs = valid_orders_qs
    date_filter_label = "All Time"

    if selected_date_str:
        try:
            sel_date = datetime.datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            s_dt, e_dt = make_day_range(sel_date)
            filtered_orders_qs = valid_orders_qs.filter(created_at__range=(s_dt, e_dt))
            date_filter_label = sel_date.strftime('%B %d, %Y')
            period = 'single_date'
        except ValueError:
            pass
    elif selected_month_str:
        try:
            parts = selected_month_str.split('-')
            year, month = int(parts[0]), int(parts[1])
            filtered_orders_qs = valid_orders_qs.filter(created_at__year=year, created_at__month=month)
            date_filter_label = datetime.date(year, month, 1).strftime('%B %Y')
            period = 'single_month'
        except ValueError:
            pass
    elif period == 'today':
        filtered_orders_qs = valid_orders_qs.filter(created_at__range=(start_today, end_today))
        date_filter_label = f"Today ({today.strftime('%b %d, %Y')})"
    elif period == 'yesterday':
        yesterday = today - datetime.timedelta(days=1)
        s_dt, e_dt = make_day_range(yesterday)
        filtered_orders_qs = valid_orders_qs.filter(created_at__range=(s_dt, e_dt))
        date_filter_label = f"Yesterday ({yesterday.strftime('%b %d, %Y')})"
    elif period == 'last_7_days':
        filtered_orders_qs = valid_orders_qs.filter(created_at__gte=start_7days)
        date_filter_label = "Last 7 Days"
    elif period == 'this_month':
        filtered_orders_qs = valid_orders_qs.filter(created_at__gte=start_month)
        date_filter_label = today.strftime('%B %Y')
    elif period == 'previous_month':
        last_month_end = first_of_this_month - datetime.timedelta(days=1)
        first_of_last_month = last_month_end.replace(day=1)
        s_dt, _ = make_day_range(first_of_last_month)
        _, e_dt = make_day_range(last_month_end)
        filtered_orders_qs = valid_orders_qs.filter(created_at__range=(s_dt, e_dt))
        date_filter_label = first_of_last_month.strftime('%B %Y')
    elif period == 'custom' and start_date_str and end_date_str:
        try:
            s_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            e_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            s_dt, _ = make_day_range(s_date)
            _, e_dt = make_day_range(e_date)
            filtered_orders_qs = valid_orders_qs.filter(created_at__range=(s_dt, e_dt))
            date_filter_label = f"{s_date.strftime('%b %d, %Y')} to {e_date.strftime('%b %d, %Y')}"
        except ValueError:
            pass

    # Summary Metrics for Selected Filter Period
    filtered_orders_count = filtered_orders_qs.count()
    filtered_items_sold = OrderItem.objects.filter(order__in=filtered_orders_qs).aggregate(total=Sum('quantity'))['total'] or 0
    filtered_revenue = float(filtered_orders_qs.aggregate(total=Sum('total_amount'))['total'] or 0.00)

    # Food Sales Analytics Queryset for Selected Filter Period
    food_sales_qs = FoodItem.objects.annotate(
        total_qty_sold=Sum('orderitem__quantity', filter=Q(orderitem__order__in=filtered_orders_qs)),
        orders_cnt=Count('orderitem__order', filter=Q(orderitem__order__in=filtered_orders_qs), distinct=True),
        food_revenue=Sum(F('orderitem__quantity') * F('orderitem__price'), filter=Q(orderitem__order__in=filtered_orders_qs), output_field=FloatField())
    ).order_by('-total_qty_sold')

    food_sales_analysis = []
    top_selling_foods = []
    
    total_rev_pct_base = filtered_revenue if filtered_revenue > 0 else 1.0
    rank = 1
    
    for food in food_sales_qs:
        qty = food.total_qty_sold or 0
        rev = float(food.food_revenue or 0.0)
        ord_cnt = food.orders_cnt or 0
        
        food_code = f"FOOD{food.id:04d}"
        pct = round((rev / total_rev_pct_base) * 100, 1) if filtered_revenue > 0 else 0.0
        
        badge_icon = "🥇" if rank == 1 else ("🥈" if rank == 2 else ("🥉" if rank == 3 else f"#{rank}"))
        
        item_data = {
            'rank': rank,
            'badge_icon': badge_icon,
            'id': food.id,
            'food_code': food_code,
            'name': food.name,
            'category': food.category.name if food.category else 'N/A',
            'qty_sold': qty,
            'orders_count': ord_cnt,
            'revenue': rev,
            'percentage': pct,
        }
        
        if qty > 0:
            food_sales_analysis.append(item_data)
            if len(top_selling_foods) < 5:
                top_selling_foods.append(item_data)
            rank += 1

    most_purchased_food = top_selling_foods[0] if top_selling_foods else None

    # 6. Active Deliveries & Tracking
    active_deliveries = DeliveryAssignment.objects.filter(status__in=['assigned', 'picked_up', 'in_transit']).count()
    waiting_deliveries = Order.objects.filter(status='ready_pickup').count()
    out_for_delivery = DeliveryAssignment.objects.filter(status='in_transit').count()
    completed_deliveries = DeliveryAssignment.objects.filter(status='delivered').count()
    active_delivery_assignments = DeliveryAssignment.objects.filter(
        status__in=['assigned', 'picked_up', 'in_transit']
    ).select_related('order', 'order__user', 'delivery_boy', 'delivery_boy__user').order_by('-assigned_at')[:10]
    
    # 7. AI Alerts & Predictions
    low_stock_items = FoodItem.objects.filter(stock_quantity__lte=3, is_available=True)[:5]
    high_demand_items = FoodDemandForecast.objects.all().order_by('-predicted_quantity')[:5]
    waste_predictions = FoodWastePrediction.objects.all().order_by('-predicted_waste_quantity')[:5]
    negative_reviews = ReviewSentiment.objects.filter(sentiment='negative').order_by('-created_at')[:5]
    
    sentiments = ReviewSentiment.objects.values('sentiment').annotate(count=Count('id'))
    sentiment_data = {'positive': 0, 'neutral': 0, 'negative': 0}
    for s in sentiments:
        sentiment_data[s['sentiment']] = s['count']
        
    diab_count = HealthProfile.objects.filter(has_diabetes=True).count()
    chol_count = HealthProfile.objects.filter(has_cholesterol=True).count()
    bp_count = HealthProfile.objects.filter(has_bp=True).count()
    
    recent_orders = Order.objects.all().order_by('-created_at')[:10]
    
    # Chart series data for past 7 days
    chart_days = []
    chart_revenue = []
    chart_orders = []
    for i in range(6, -1, -1):
        day_date = today - datetime.timedelta(days=i)
        day_str = day_date.strftime('%a %d')
        chart_days.append(day_str)
        rev = float(valid_orders_qs.filter(created_at__date=day_date).aggregate(Sum('total_amount'))['total_amount__sum'] or 0.00)
        ords = valid_orders_qs.filter(created_at__date=day_date).count()
        chart_revenue.append(rev)
        chart_orders.append(ords)
        
    # Category sales breakdown for charts
    cat_sales = Category.objects.annotate(total_sales=Sum('foods__orderitem__quantity', filter=Q(foods__orderitem__order__in=valid_orders_qs))).values('name', 'total_sales')
    cat_labels = [c['name'] for c in cat_sales if c['total_sales']]
    cat_data = [int(c['total_sales']) for c in cat_sales if c['total_sales']]
    if not cat_labels:
        cat_labels = ['Vegetarian', 'Non-Vegetarian', 'Traditional Snacks', 'Desserts & Drinks']
        cat_data = [42, 68, 35, 24]

    # --- Business Analytics ---
    most_ordered_foods = food_sales_analysis[:10]
        
    popular_categories_stats_qs = Category.objects.annotate(
        qty_sold=Sum('foods__orderitem__quantity', filter=Q(foods__orderitem__order__in=valid_orders_qs)),
        orders_count=Count('foods__orderitem__order', filter=Q(foods__orderitem__order__in=valid_orders_qs), distinct=True),
        revenue_gen=Sum(F('foods__orderitem__quantity') * F('foods__orderitem__price'), filter=Q(foods__orderitem__order__in=valid_orders_qs), output_field=FloatField())
    ).filter(qty_sold__gt=0).order_by('-qty_sold')
    
    popular_categories_stats = []
    total_sales_revenue = filtered_revenue if filtered_revenue > 0 else 1.0
    for c_obj in popular_categories_stats_qs:
        popular_categories_stats.append({
            'name': c_obj.name,
            'orders_count': c_obj.orders_count,
            'qty_sold': c_obj.qty_sold,
            'revenue': float(c_obj.revenue_gen or 0.0),
            'percentage': round((float(c_obj.revenue_gen or 0.0) / total_sales_revenue) * 100, 1) if total_sales_revenue > 0 else 0
        })

    total_orders_all = valid_orders_qs.count() or 1
    meal_session_stats = []
    highest_session_orders = None
    highest_session_deliveries = None
    max_o_count = -1
    max_d_count = -1
    
    sessions = MealSession.objects.all()
    for sess in sessions:
        sess_items = OrderItem.objects.filter(food_item__meal_session=sess, order__in=valid_orders_qs)
        sess_orders_count = sess_items.values('order').distinct().count()
        sess_qty = sess_items.aggregate(Sum('quantity'))['quantity__sum'] or 0
        sess_rev = sess_items.aggregate(rev=Sum(F('quantity') * F('price'), output_field=FloatField()))['rev'] or 0.0
        sess_deliv_count = DeliveryAssignment.objects.filter(
            status='delivered', 
            order__items__food_item__meal_session=sess,
            order__in=valid_orders_qs
        ).distinct().count()
        
        meal_session_stats.append({
            'name': sess.name,
            'orders_count': sess_orders_count,
            'qty_sold': sess_qty,
            'revenue': float(sess_rev),
            'deliveries': sess_deliv_count,
            'percentage': round((sess_orders_count / total_orders_all) * 100, 1)
        })
        
        if sess_orders_count > max_o_count:
            max_o_count = sess_orders_count
            highest_session_orders = sess.name
        if sess_deliv_count > max_d_count:
            max_d_count = sess_deliv_count
            highest_session_deliveries = sess.name

    # --- Section Data Routing for Custom Dashboard ---
    table_data = []
    table_type = section

    if section == 'users':
        table_data = User.objects.filter(role='customer').order_by('-date_joined')
    elif section == 'chef-profiles':
        table_data = ChefProfile.objects.select_related('user').all()
    elif section == 'staff':
        table_data = User.objects.filter(role='staff').order_by('-date_joined')
    elif section == 'delivery-boys':
        table_data = DeliveryBoyProfile.objects.select_related('user').all()
    elif section == 'food':
        table_data = FoodItem.objects.select_related('category', 'chef').all()
    elif section == 'categories':
        table_data = Category.objects.annotate(food_count=Count('foods')).all()
    elif section == 'meal-sessions':
        table_data = MealSession.objects.all()
    elif section == 'nutrition':
        table_data = NutritionInfo.objects.select_related('food_item').all()
    elif section == 'health-recommendations':
        table_data = HealthRecommendation.objects.select_related('user', 'recommended_food').all()
    elif section == 'orders':
        table_data = Order.objects.select_related('user').all().order_by('-created_at')
    elif section == 'payments':
        table_data = Payment.objects.select_related('order', 'order__user').all().order_by('-created_at')
    elif section == 'delivery':
        table_data = DeliveryAssignment.objects.select_related('order', 'delivery_boy', 'delivery_boy__user').all().order_by('-assigned_at')
    elif section == 'customer-behaviors':
        table_data = CustomerBehavior.objects.select_related('user').all()
    elif section == 'food-demand':
        table_data = FoodDemandForecast.objects.select_related('food_item').all().order_by('-predicted_quantity')
    elif section == 'food-waste':
        table_data = FoodWastePrediction.objects.select_related('food_item').all().order_by('-predicted_waste_quantity')
    elif section == 'stock-predictions':
        table_data = StockPrediction.objects.select_related('food_item').all().order_by('predicted_days_until_out_of_stock')
    elif section == 'review-sentiments':
        table_data = ReviewSentiment.objects.select_related('food_item').all().order_by('-created_at')
    elif section == 'groups':
        table_data = User.objects.values('role').annotate(count=Count('id')).order_by('-count')

    context = {
        'active_section': section,
        'table_data': table_data,
        'table_type': table_type,
        
        'customers_count': total_customers,
        'active_customers': active_customers,
        'inactive_customers': inactive_customers,
        'chefs_count': total_chefs,
        'total_staff': total_staff,
        'delivery_boys_count': total_delivery_boys,
        'active_delivery_boys': active_delivery_boys,
        'busy_delivery_boys': busy_delivery_boys,
        'inactive_delivery_boys': inactive_delivery_boys,
        'total_foods': total_foods,
        'available_foods': available_foods,
        'out_of_stock_foods': out_of_stock_foods,
        'total_categories': total_categories,
        'popular_category': popular_category,
        'orders_count': total_orders,
        'today_orders': today_orders,
        'pending_orders': pending_orders,
        'processing_orders': processing_orders,
        'in_transit_orders': in_transit_orders,
        'completed_orders': completed_orders,
        'cancelled_orders': cancelled_orders,
        'total_revenue': total_revenue,
        'today_revenue': today_revenue,
        'weekly_revenue': weekly_revenue,
        'monthly_revenue': monthly_revenue,
        'active_deliveries': active_deliveries,
        'waiting_deliveries': waiting_deliveries,
        'out_for_delivery': out_for_delivery,
        'completed_deliveries': completed_deliveries,
        'active_delivery_assignments': active_delivery_assignments,
        'low_stock_items': low_stock_items,
        'high_demand_items': high_demand_items,
        'waste_predictions': waste_predictions,
        'negative_reviews': negative_reviews,
        'sentiment_data': sentiment_data,
        'diab_count': diab_count,
        'chol_count': chol_count,
        'bp_count': bp_count,
        'recent_orders': recent_orders,
        'chart_days': chart_days,
        'chart_revenue': chart_revenue,
        'chart_orders': chart_orders,
        'cat_labels': cat_labels,
        'cat_data': cat_data,
        
        # New Business Analytics Context
        'period': period,
        'selected_date_str': selected_date_str,
        'selected_month_str': selected_month_str,
        'start_date_str': start_date_str,
        'end_date_str': end_date_str,
        'date_filter_label': date_filter_label,
        'filtered_orders_count': filtered_orders_count,
        'filtered_items_sold': filtered_items_sold,
        'filtered_revenue': filtered_revenue,
        'food_sales_analysis': food_sales_analysis,
        'top_selling_foods': top_selling_foods,
        'most_purchased_food': most_purchased_food,
        'most_ordered_foods': most_ordered_foods,
        'popular_categories_stats': popular_categories_stats,
        'meal_session_stats': meal_session_stats,
        'highest_session_orders': highest_session_orders,
        'highest_session_deliveries': highest_session_deliveries,
    }
    return render(request, 'food/admin_dashboard.html', context)
