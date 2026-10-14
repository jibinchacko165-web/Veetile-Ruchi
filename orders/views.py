from django.db import models, transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.contrib import messages
from django.utils import timezone
from .models import CartItem, Coupon, Order, OrderItem, Payment, Wishlist, Notification
from food.models import FoodItem
from accounts.models import User, DeliveryBoyProfile, ChefProfile, SavedLocation
from accounts.decorators import role_required
from delivery.models import DeliveryAssignment, GPSLocationTracking, District, HotelBranch, DeliverySetting
from ai_models.models import CustomerBehavior
from ai_models.ml_engine import predict_delivery_time, recommend_coupons_kmeans, optimize_delivery_route
from .utils import is_within_delivery_perimeter, KERALA_PRESET_PLACES, get_active_delivery_setting, calculate_distance_km, find_nearest_serving_branch, validate_coordinates

@never_cache
@login_required
def cart_view(request):
    """View shopping cart items and apply AI recommended coupons."""
    cart_items = CartItem.objects.filter(user=request.user)
    subtotal = sum(item.food_item.price * item.quantity for item in cart_items)
    
    # Coupon management
    coupon_code = request.GET.get('coupon_code')
    discount = 0.0
    applied_coupon = None
    
    if coupon_code:
        try:
            coupon = Coupon.objects.get(code=coupon_code, is_active=True, expiry_date__gte=timezone.now().date())
            if subtotal >= coupon.min_purchase_amount:
                discount = float(subtotal) * float(coupon.discount_percentage) / 100.0
                applied_coupon = coupon
                messages.success(request, f"Coupon '{coupon_code}' applied successfully!")
            else:
                messages.warning(request, f"Minimum purchase amount of {coupon.min_purchase_amount} not met for this coupon.")
        except Coupon.DoesNotExist:
            messages.error(request, "Invalid or expired coupon code.")
            
    # AI Smart Coupon Recommendation using K-Means Clustering
    coupons = list(Coupon.objects.filter(is_active=True))
    all_users = User.objects.filter(role='customer')
    customers_data = []
    for u in all_users:
        orders = u.orders.all()
        orders_count = orders.count()
        avg_spend = float(orders.aggregate(models.Avg('total_amount'))['total_amount__avg'] or 0.00)
        customers_data.append({'user_id': u.id, 'orders_count': orders_count, 'avg_spend': avg_spend})
        
    rec_coupons = recommend_coupons_kmeans(customers_data, coupons)
    user_rec = rec_coupons.get(request.user.id, {'segment': 'Regular', 'coupon': None, 'reason': 'Loyal customer discount.'})
    
    context = {
        'cart_items': cart_items,
        'subtotal': subtotal,
        'discount': discount,
        'total': float(subtotal) - discount,
        'applied_coupon': applied_coupon,
        'user_rec': user_rec,
    }
    return render(request, 'orders/cart.html', context)

@login_required
def cart_add(request, food_id):
    food = get_object_or_404(FoodItem, id=food_id)
    if food.stock_quantity <= 0:
        messages.error(request, "Sorry, this item is out of stock.")
        return redirect('food_catalog')
        
    cart_item, created = CartItem.objects.get_or_create(user=request.user, food_item=food)
    if not created:
        if cart_item.quantity < food.stock_quantity:
            cart_item.quantity += 1
            cart_item.save()
            messages.success(request, f"Added another {food.name} to cart.")
        else:
            messages.warning(request, f"Cannot add more. Only {food.stock_quantity} available in stock.")
    else:
        cart_item.quantity = 1
        cart_item.save()
        messages.success(request, f"Added {food.name} to cart.")
        
    return redirect('cart_view')

@login_required
def cart_update_quantity(request, item_id):
    """Increments or decrements cart quantity with stock limits."""
    cart_item = get_object_or_404(CartItem, id=item_id, user=request.user)
    action = request.POST.get('action') or request.GET.get('action', 'increase')
    
    if action == 'increase':
        if cart_item.food_item.stock_quantity > cart_item.quantity:
            cart_item.quantity += 1
            cart_item.save()
            messages.success(request, f"Updated {cart_item.food_item.name} quantity to {cart_item.quantity}.")
        else:
            messages.warning(request, f"Maximum available quantity for {cart_item.food_item.name} is {cart_item.food_item.stock_quantity}.")
    elif action == 'decrease':
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save()
            messages.info(request, f"Updated {cart_item.food_item.name} quantity to {cart_item.quantity}.")
        else:
            cart_item.delete()
            messages.info(request, f"Removed {cart_item.food_item.name} from cart.")
            
    return redirect('cart_view')

@login_required
def cart_remove(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, user=request.user)
    item.delete()
    messages.info(request, "Item removed from cart.")
    return redirect('cart_view')

@login_required
def checkout_view(request):
    """Review screen supporting saved delivery location selection and branch-specific perimeter check."""
    cart_items = CartItem.objects.filter(user=request.user)
    if not cart_items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect('food_catalog')
        
    subtotal = sum(item.food_item.price * item.quantity for item in cart_items)
    coupon_id = request.GET.get('coupon_id')
    coupon = None
    discount = 0.0
    
    if coupon_id:
        coupon = get_object_or_404(Coupon, id=coupon_id)
        discount = float(subtotal) * float(coupon.discount_percentage) / 100.0
        
    total = float(subtotal) - discount

    saved_locations = request.user.saved_locations.all() if hasattr(request.user, 'saved_locations') else []
    default_location = None
    for loc in saved_locations:
        if loc.is_default:
            default_location = loc
            break
    if not default_location and saved_locations.exists():
        default_location = saved_locations.first()
    
    delivery_setting = get_active_delivery_setting()
    districts = District.objects.filter(is_active=True).order_by('name')
    branches = HotelBranch.objects.filter(is_active=True).select_related('district').order_by('district__name', 'name')
    
    # Identify requested or nearest serving branch
    requested_branch_id = request.GET.get('branch_id')
    requested_district_code = request.GET.get('district')
    selected_branch = None

    if requested_branch_id:
        selected_branch = branches.filter(id=requested_branch_id).first()
    elif requested_district_code:
        selected_branch = branches.filter(district__code=requested_district_code).first()

    if not selected_branch:
        if default_location:
            selected_branch, _, _ = find_nearest_serving_branch(default_location.latitude, default_location.longitude)
        elif hasattr(request.user, 'latitude') and request.user.latitude:
            selected_branch, _, _ = find_nearest_serving_branch(request.user.latitude, request.user.longitude)

    if not selected_branch:
        selected_branch = branches.filter(is_central_hub=True).first() or branches.first()

    # Determine serving coordinates and max radius
    if selected_branch:
        hub_lat = selected_branch.latitude
        hub_lon = selected_branch.longitude
        hub_name = selected_branch.name
        hub_radius_km = selected_branch.effective_radius_km
    else:
        hub_lat = delivery_setting.latitude
        hub_lon = delivery_setting.longitude
        hub_name = delivery_setting.name
        hub_radius_km = min(delivery_setting.max_delivery_radius_km, 25.0)

    context = {
        'cart_items': cart_items,
        'subtotal': subtotal,
        'discount': discount,
        'total': total,
        'coupon': coupon,
        'saved_locations': saved_locations,
        'default_location': default_location,
        'kerala_preset_places': KERALA_PRESET_PLACES,
        'delivery_setting': delivery_setting,
        'districts': districts,
        'branches': branches,
        'selected_branch': selected_branch,
        'hub_lat': hub_lat,
        'hub_lon': hub_lon,
        'hub_name': hub_name,
        'hub_radius_km': hub_radius_km,
    }
    return render(request, 'orders/checkout.html', context)

@login_required
def place_order(request):
    """Places order with strict 25 km Delivery Perimeter validation per serving hotel branch."""
    if request.method == 'POST':
        cart_items = CartItem.objects.filter(user=request.user)
        if not cart_items.exists():
            messages.error(request, "Your cart is empty.")
            return redirect('food_catalog')
            
        subtotal = sum(item.food_item.price * item.quantity for item in cart_items)
        coupon_id = request.POST.get('coupon_id')
        coupon = Coupon.objects.filter(id=coupon_id).first() if coupon_id else None
        
        discount = 0.0
        if coupon:
            discount = float(subtotal) * float(coupon.discount_percentage) / 100.0
            
        total_amount = float(subtotal) - discount
        
        # ───── LOCATION SELECTION & BRANCH RESOLUTION ─────
        saved_loc_id = request.POST.get('saved_location_id')
        delivery_address = request.POST.get('delivery_address', '').strip()
        customer_delivery_notes = request.POST.get('customer_delivery_notes', '').strip()
        branch_id = request.POST.get('branch_id')
        
        if saved_loc_id:
            saved_loc = SavedLocation.objects.filter(id=saved_loc_id, user=request.user).first()
            if saved_loc:
                latitude = saved_loc.latitude
                longitude = saved_loc.longitude
                loc_desc = (saved_loc.description or '').strip()
                loc_name = (saved_loc.name or '').strip()
                clean_n = loc_name.split("(")[0].strip() if loc_name else ''
                if clean_n and loc_desc and clean_n.lower() in loc_desc.lower():
                    import re
                    base_addr = re.sub(re.escape(clean_n), loc_name, loc_desc, count=1, flags=re.IGNORECASE)
                elif loc_name and loc_desc:
                    base_addr = f"{loc_name}, {loc_desc}"
                else:
                    base_addr = loc_name or loc_desc or "Kanjirappally"
                
                if saved_loc.landmark and saved_loc.landmark.strip() and saved_loc.landmark.strip().upper() != 'N/A':
                    delivery_address = f"{base_addr} • Landmark: {saved_loc.landmark.strip()}"
                else:
                    delivery_address = base_addr
            else:
                try:
                    latitude = float(request.POST.get('latitude', 9.5564))
                    longitude = float(request.POST.get('longitude', 76.7909))
                except (ValueError, TypeError):
                    latitude = 9.5564
                    longitude = 76.7909
        else:
            try:
                latitude = float(request.POST.get('latitude', '') or getattr(request.user, 'latitude', 9.5564))
            except (ValueError, TypeError):
                latitude = getattr(request.user, 'latitude', 9.5564)
            try:
                longitude = float(request.POST.get('longitude', '') or getattr(request.user, 'longitude', 76.7909))
            except (ValueError, TypeError):
                longitude = getattr(request.user, 'longitude', 76.7909)

        v_lat, v_lon = validate_coordinates(latitude, longitude)
        if v_lat is None or v_lon is None:
            messages.error(request, "Invalid delivery coordinates provided. Please select a valid location on the map.")
            return redirect('checkout_view')
        latitude, longitude = v_lat, v_lon


        # Resolve serving hotel branch (Default to Central Kitchen Hub in Kanjirappally if not specified)
        serving_branch = None
        if branch_id:
            serving_branch = HotelBranch.objects.filter(id=branch_id, is_active=True).first()
        if not serving_branch:
            serving_branch = HotelBranch.objects.filter(is_central_hub=True, is_active=True).first()
            if not serving_branch:
                serving_branch, _, _ = find_nearest_serving_branch(latitude, longitude)

        # Enforce Delivery Perimeter Verification (30 km limit for Central Hub)
        is_serviceable, dist_km, perimeter_msg = is_within_delivery_perimeter(
            latitude, longitude, branch_id=serving_branch.id if serving_branch else None
        )
        if not is_serviceable:
            # Basket remains 100% intact
            messages.error(request, "Sorry, this hotel cannot deliver to your selected location. Please choose a nearer address or another available hotel.")
            messages.error(request, "Sorry, delivery is currently available only within 30 km of Kanjirappally.")
            return redirect('checkout_view')
        
        # Payment setup
        payment_method = request.POST.get('payment_method', 'cod')
        
        with transaction.atomic():
            # Create Order linked to serving branch
            order = Order.objects.create(
                user=request.user,
                total_amount=total_amount,
                coupon=coupon,
                status='pending',
                latitude=latitude,
                longitude=longitude,
                delivery_address=delivery_address,
                customer_delivery_notes=customer_delivery_notes,
                branch=serving_branch
            )
            
            # Create Order Items & Decrement Stock
            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    food_item=item.food_item,
                    quantity=item.quantity,
                    price=item.food_item.price
                )
                food = item.food_item
                food.stock_quantity = max(0, food.stock_quantity - item.quantity)
                food.save()
                
            # Create Payment record
            upi_ref = request.POST.get('upi_ref', '').strip()
            if payment_method == 'upi' and upi_ref:
                tx_id = f"UPI-{upi_ref}"
            else:
                tx_id = f"TXN-{timezone.now().strftime('%Y%m%d%H%M%S')}-{order.order_id.split('-')[-1]}"
                
            pay_status = 'pending'
            if payment_method == 'upi':
                pay_status = 'success' # Simulate successful instant UPI
                
            Payment.objects.create(
                order=order,
                payment_method=payment_method,
                transaction_id=tx_id,
                status=pay_status,
                amount=total_amount
            )
            
            # AI Behavioral tracking updates
            behavior, _ = CustomerBehavior.objects.get_or_create(user=request.user)
            behavior.total_orders_count += 1
            user_orders = Order.objects.filter(user=request.user)
            behavior.average_order_value = user_orders.aggregate(models.Avg('total_amount'))['total_amount__avg'] or 0.00
            
            sessions_grouped = user_orders.values('items__food_item__meal_session').annotate(count=models.Count('order_id')).order_by('-count')
            if sessions_grouped and sessions_grouped[0]['items__food_item__meal_session']:
                from food.models import MealSession
                behavior.most_ordered_session = MealSession.objects.filter(id=sessions_grouped[0]['items__food_item__meal_session']).first()
                
            if behavior.total_orders_count >= 5:
                behavior.behavior_segment = 'high_value'
            elif behavior.total_orders_count >= 2:
                behavior.behavior_segment = 'regular'
            else:
                behavior.behavior_segment = 'occasional'
            behavior.save()
            
            # Clear Cart
            cart_items.delete()
            
            # Create Customer notification for Order Confirmed
            Notification.objects.create(
                user=request.user,
                order=order,
                title="Order Confirmed",
                message=f"Order Confirmed – #{order.order_id} has been received.",
                notification_type='order_confirmed'
            )
            
        messages.success(request, f"Order placed successfully! Order ID: {order.order_id}")
        return redirect('order_tracking', order_id=order.order_id)
        
    return redirect('cart_view')

@login_required
def order_tracking(request, order_id):
    """Customer-facing order delivery tracking screen by entering Order ID."""
    order = get_object_or_404(Order, order_id=order_id)
    
    # Location Privacy Security: Only authorized users (owner, staff/admin, or assigned courier) can access customer GPS & tracking info
    is_owner = (request.user == order.user)
    is_staff = (request.user.role in ['staff', 'admin'])
    is_assigned_courier = (hasattr(order, 'delivery_assignment') and order.delivery_assignment.delivery_boy.user == request.user)
    
    if not (is_owner or is_staff or is_assigned_courier):
        messages.error(request, "Access Denied: You are not authorized to view tracking info for this order.")
        return redirect('dashboard_redirect')

    payment = getattr(order, 'payment', None)
    assignment = getattr(order, 'delivery_assignment', None)

    from .utils import get_active_delivery_setting, validate_coordinates
    delivery_setting = get_active_delivery_setting()
    branch = getattr(order, 'branch', None)
    chef_lat = branch.latitude if branch else delivery_setting.latitude
    chef_lon = branch.longitude if branch else delivery_setting.longitude
    
    cust_lat, cust_lon = validate_coordinates(order.latitude, order.longitude)
    if cust_lat is None:
        cust_lat, cust_lon = chef_lat, chef_lon
    
    # Genuine courier GPS retrieval with freshness check (5 mins)
    courier_lat = None
    courier_lon = None
    has_courier_gps = False
    is_gps_stale = False
    last_gps_update = None
    courier_profile = getattr(assignment, 'delivery_boy', None) if assignment else None

    if assignment:
        from delivery.models import GPSLocationTracking
        latest_crumb = GPSLocationTracking.objects.filter(delivery_assignment=assignment).order_by('-timestamp').first()
        if latest_crumb:
            c_lat, c_lon = validate_coordinates(latest_crumb.latitude, latest_crumb.longitude)
            if c_lat is not None and c_lon is not None:
                courier_lat = c_lat
                courier_lon = c_lon
                age_sec = (timezone.now() - latest_crumb.timestamp).total_seconds()
                if age_sec <= 300:
                    has_courier_gps = True
                    is_gps_stale = False
                    last_gps_update = latest_crumb.timestamp.strftime("%I:%M:%S %p")
                else:
                    has_courier_gps = False
                    is_gps_stale = True
                    last_gps_update = latest_crumb.timestamp.strftime("%I:%M:%S %p") + " (Signal Stale)"
        elif courier_profile and courier_profile.current_latitude and courier_profile.current_longitude:
            c_lat, c_lon = validate_coordinates(courier_profile.current_latitude, courier_profile.current_longitude)
            if c_lat is not None and c_lon is not None and not (c_lat == 10.0 and c_lon == 76.0):
                courier_lat = c_lat
                courier_lon = c_lon
                if assignment.status in ['in_transit', 'picked_up']:
                    has_courier_gps = True
                    is_gps_stale = False
                    last_gps_update = timezone.localtime().strftime("%I:%M:%S %p")

    # Critical Business Rule: Separate hotel base from actual courier GPS
    if (order.status in ['in_transit', 'picked_up']) and courier_lat and courier_lon:
        calc_origin_lat = courier_lat
        calc_origin_lon = courier_lon
    else:
        calc_origin_lat = chef_lat
        calc_origin_lon = chef_lon

    from ai_models.ml_engine import predict_delivery_time_rf, optimize_delivery_route
    route_res = optimize_delivery_route(calc_origin_lat, calc_origin_lon, cust_lat, cust_lon)
    route_steps = route_res.route
    distance_km = route_res.distance
    is_road_distance = getattr(route_res, 'is_road', True)

    # Calculate Random Forest Regressor AI Predictions
    items_cnt = order.items.count() if hasattr(order, 'items') else 1
    pred_delivery_min, ai_eta_min, dist_km = predict_delivery_time_rf(
        calc_origin_lat, calc_origin_lon, cust_lat, cust_lon, 
        items_count=items_cnt, road_distance_km=distance_km
    )

    if dist_km <= 0.5:
        ai_status_pred = "Near Destination 🎯"
    elif assignment and pred_delivery_min <= (assignment.predicted_delivery_time or 30.0) + 5.0:
        ai_status_pred = "On Time ⏱️"
    else:
        ai_status_pred = "Slightly Delayed ⚠️"

    assigned_courier = assignment.delivery_boy.user if assignment and assignment.delivery_boy else None

    context = {
        'order': order,
        'payment': payment,
        'assignment': assignment,
        'assigned_courier': assigned_courier,
        'route_steps': route_steps,
        'distance_km': dist_km,
        'is_road_distance': is_road_distance,
        'pred_delivery_min': pred_delivery_min,
        'ai_eta_min': ai_eta_min,
        'ai_status_pred': ai_status_pred,
        'chef_lat': chef_lat,
        'chef_lon': chef_lon,
        'cust_lat': cust_lat,
        'cust_lon': cust_lon,
        'courier_lat': courier_lat,
        'courier_lon': courier_lon,
        'has_courier_gps': has_courier_gps,
        'is_gps_stale': is_gps_stale,
        'last_gps_update': last_gps_update,
    }
    return render(request, 'orders/tracking.html', context)

@login_required
def api_order_status(request, order_id):
    """Real-time order status API endpoint for live customer tracking page without page refresh."""
    from django.http import JsonResponse
    order = get_object_or_404(Order, order_id=order_id)
    
    is_owner = (request.user == order.user)
    is_staff = (request.user.role in ['staff', 'admin'])
    is_assigned_courier = (hasattr(order, 'delivery_assignment') and order.delivery_assignment.delivery_boy.user == request.user)
    
    if not (is_owner or is_staff or is_assigned_courier):
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
        
    assignment = getattr(order, 'delivery_assignment', None)
    courier_profile = assignment.delivery_boy if assignment else None
    courier_user = courier_profile.user if courier_profile else None
    
    from .utils import get_active_delivery_setting, validate_coordinates
    delivery_setting = get_active_delivery_setting()
    branch = getattr(order, 'branch', None)
    chef_lat = branch.latitude if branch else delivery_setting.latitude
    chef_lon = branch.longitude if branch else delivery_setting.longitude
    
    cust_lat, cust_lon = validate_coordinates(order.latitude, order.longitude)
    if cust_lat is None:
        cust_lat, cust_lon = chef_lat, chef_lon
        
    # Genuine courier GPS retrieval from breadcrumbs or validated profile
    courier_lat = None
    courier_lon = None
    has_courier_gps = False
    is_gps_stale = False
    last_gps_update = None

    if assignment:
        from delivery.models import GPSLocationTracking
        latest_crumb = GPSLocationTracking.objects.filter(delivery_assignment=assignment).order_by('-timestamp').first()
        if latest_crumb:
            c_lat, c_lon = validate_coordinates(latest_crumb.latitude, latest_crumb.longitude)
            if c_lat is not None and c_lon is not None:
                courier_lat = c_lat
                courier_lon = c_lon
                age_sec = (timezone.now() - latest_crumb.timestamp).total_seconds()
                if age_sec <= 300: # 5 minutes threshold
                    has_courier_gps = True
                    is_gps_stale = False
                    last_gps_update = latest_crumb.timestamp.strftime("%I:%M:%S %p")
                else:
                    has_courier_gps = False
                    is_gps_stale = True
                    last_gps_update = latest_crumb.timestamp.strftime("%I:%M:%S %p") + " (Signal Stale)"
        elif courier_profile and courier_profile.current_latitude and courier_profile.current_longitude:
            c_lat, c_lon = validate_coordinates(courier_profile.current_latitude, courier_profile.current_longitude)
            if c_lat is not None and c_lon is not None and not (c_lat == 10.0 and c_lon == 76.0):
                courier_lat = c_lat
                courier_lon = c_lon
                if assignment.status in ['in_transit', 'picked_up']:
                    has_courier_gps = True
                    is_gps_stale = False
                    last_gps_update = timezone.localtime().strftime("%I:%M:%S %p")

    # Hotel Base vs Courier GPS separation
    if (order.status in ['in_transit', 'picked_up']) and courier_lat and courier_lon:
        calc_origin_lat = courier_lat
        calc_origin_lon = courier_lon
    else:
        calc_origin_lat = chef_lat
        calc_origin_lon = chef_lon

    items_cnt = order.items.count() if hasattr(order, 'items') else 1
    from ai_models.ml_engine import predict_delivery_time_rf, optimize_delivery_route
    route_res = optimize_delivery_route(calc_origin_lat, calc_origin_lon, cust_lat, cust_lon)
    route_steps = route_res.route
    distance_km = route_res.distance
    is_road_distance = getattr(route_res, 'is_road', True)

    pred_delivery_min, ai_eta_min, dist_km = predict_delivery_time_rf(
        calc_origin_lat, calc_origin_lon, cust_lat, cust_lon, items_count=items_cnt, road_distance_km=distance_km
    )
    
    status_display_map = {
        'pending': 'Order Placed (Pending Kitchen Confirmation)',
        'preparing': 'Food Being Prepared in Kitchen',
        'ready_pickup': 'Ready for Pickup',
        'assigned': 'Courier Assigned & Ready for Pickup',
        'picked_up': 'Picked Up by Courier',
        'in_transit': 'Out for Delivery',
        'delivered': 'Delivered',
        'cancelled': 'Cancelled',
    }
    
    return JsonResponse({
        'status': 'success',
        'order_id': order.order_id,
        'order_status': order.status,
        'status_display': status_display_map.get(order.status, order.get_status_display()),
        'customer_name': order.user.get_full_name() or order.user.username,
        'customer_phone': getattr(order.user, 'phone', '') or 'Phone not provided',
        'customer_delivery_notes': order.customer_delivery_notes or order.delivery_address or '',
        'has_courier': courier_user is not None,
        'has_courier_gps': has_courier_gps,
        'is_gps_stale': is_gps_stale,
        'courier_name': (courier_user.get_full_name() or courier_user.username) if courier_user else None,
        'courier_phone': getattr(courier_user, 'phone', '') if courier_user else None,
        'vehicle_number': courier_profile.vehicle_number if courier_profile else None,
        'ai_eta_min': ai_eta_min,
        'pred_delivery_min': pred_delivery_min,
        'distance_km': dist_km,
        'is_road_distance': is_road_distance,
        'route_steps': route_steps,
        'courier_lat': courier_lat,
        'courier_lon': courier_lon,
        'last_gps_update': last_gps_update,
        'chef_lat': chef_lat,
        'chef_lon': chef_lon,
        'cust_lat': cust_lat,
        'cust_lon': cust_lon,
    })


@never_cache
@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).select_related('payment', 'delivery_assignment__delivery_boy__user', 'delivery_feedback').prefetch_related('items__food_item').order_by('-created_at')
    return render(request, 'orders/history.html', {'orders': orders})

@never_cache
@login_required
@role_required('staff', 'admin')
def staff_dashboard(request):
    """Staff Console for food order management, chef approvals, delivery tracking, and district-wise branches."""
    active_tab = request.GET.get('tab', 'orders')
    orders = Order.objects.all().order_by('-created_at').select_related('user', 'payment', 'delivery_assignment__delivery_boy__user').prefetch_related('items__food_item')
    available_boys = DeliveryBoyProfile.objects.filter(status='available').select_related('user')
    all_couriers = DeliveryBoyProfile.objects.all().select_related('user')
    chefs = ChefProfile.objects.all().select_related('user')
    
    delivery_boys = all_couriers
    delivery_setting = get_active_delivery_setting()

    # District & Hotel Branch Management Data
    districts = District.objects.all().annotate(branches_count=models.Count('hotel_branches')).order_by('name')
    district_filter = request.GET.get('district_filter', '').strip()
    
    hotel_branches = HotelBranch.objects.all().select_related('district').prefetch_related('available_food_items').order_by('district__name', 'name')
    if district_filter and district_filter != 'All':
        hotel_branches = hotel_branches.filter(models.Q(district__code=district_filter) | models.Q(district__name__iexact=district_filter))
        
    all_food_items = FoodItem.objects.all().order_by('name')

    context = {
        'active_tab': active_tab,
        'orders': orders,
        'delivery_boys': delivery_boys,
        'available_couriers_count': available_boys.count(),
        'all_couriers': all_couriers,
        'chefs': chefs,
        'assignments': DeliveryAssignment.objects.all().order_by('-assigned_at').select_related('order__user', 'delivery_boy__user').prefetch_related('order__items__food_item'),
        'delivery_setting': delivery_setting,
        'kerala_preset_places': KERALA_PRESET_PLACES,
        'districts': districts,
        'hotel_branches': hotel_branches,
        'district_filter': district_filter,
        'all_food_items': all_food_items,
    }
    return render(request, 'orders/staff_dashboard.html', context)

@login_required
@role_required('staff', 'admin')
def staff_update_order_status(request, order_id):
    """Allows staff to update order preparation status e.g. to ready_pickup (Food Ready)."""
    order = get_object_or_404(Order, order_id=order_id)
    new_status = request.POST.get('status')
    if new_status in ['pending', 'preparing', 'ready_pickup', 'cancelled']:
        order.status = new_status
        order.save()
        messages.success(request, f"Order #{order.order_id} status updated to {order.get_status_display()}.")
    return redirect('staff_dashboard')

@login_required
@role_required('staff', 'admin')
def staff_confirm_payment(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)
    payment = get_object_or_404(Payment, order=order)
    payment.status = 'success'
    payment.save()
    messages.success(request, f"Payment for Order {order.order_id} verified.")
    return redirect('staff_dashboard')

@login_required
@role_required('staff', 'admin')
def staff_assign_delivery(request, order_id):
    """Links Order ID with assigned Delivery Boy using atomic transaction and status validation."""
    if request.method != 'POST':
        return redirect('staff_dashboard')

    order = get_object_or_404(Order, order_id=order_id)
    
    if order.status == 'cancelled':
        messages.error(request, f"Order #{order.order_id} is cancelled and cannot be assigned.")
        return redirect('staff_dashboard')
        
    if order.status == 'delivered':
        messages.error(request, f"Order #{order.order_id} is already delivered and cannot be reassigned.")
        return redirect('staff_dashboard')

    db_id = request.POST.get('delivery_boy_id')
    if not db_id:
        messages.error(request, "Please select a delivery boy to assign.")
        return redirect('staff_dashboard')

    # AI Delivery Time Prediction
    chef_lat, chef_lon = 10.015, 76.325
    cust_lat, cust_lon = order.latitude, order.longitude
    pred_minutes = predict_delivery_time(chef_lat, chef_lon, cust_lat, cust_lon)

    try:
        with transaction.atomic():
            # Lock the order to prevent concurrent assignments to the same order
            order = Order.objects.select_for_update().get(order_id=order_id)
            if hasattr(order, 'delivery_assignment') and order.delivery_assignment.is_active:
                if order.delivery_assignment.delivery_boy.id == int(db_id):
                    messages.error(request, f"Order #{order.order_id} is already assigned to this courier.")
                    return redirect('staff_dashboard')

            # Lock the delivery boy profile to check eligibility
            db_profile = DeliveryBoyProfile.objects.select_for_update().get(id=db_id)
            if not db_profile.user.is_active:
                messages.error(request, "The selected delivery boy account is inactive.")
                return redirect('staff_dashboard')
                
            if db_profile.status != 'available':
                messages.error(request, f"Courier {db_profile.courier_name} is currently not available for assignment.")
                return redirect('staff_dashboard')

            # Clean up old assignment if reassignment
            old_profile = None
            if hasattr(order, 'delivery_assignment'):
                old_assignment = order.delivery_assignment
                if old_assignment.delivery_boy != db_profile:
                    old_profile = old_assignment.delivery_boy
                    Notification.objects.filter(user=old_profile.user, order=order).delete()

            assignment, created = DeliveryAssignment.objects.get_or_create(
                order=order,
                defaults={
                    'delivery_boy': db_profile,
                    'status': 'assigned',
                    'is_active': True,
                    'predicted_delivery_time': pred_minutes
                }
            )
            if not created:
                assignment.delivery_boy = db_profile
                assignment.status = 'assigned'
                assignment.is_active = True
                assignment.picked_up_at = None
                assignment.out_for_delivery_at = None
                assignment.delivered_at = None
                assignment.predicted_delivery_time = pred_minutes
                assignment.save()

            # Reset old courier profile to available if no other active deliveries remain
            if old_profile:
                other_busy = DeliveryAssignment.objects.filter(
                    delivery_boy=old_profile,
                    status__in=['assigned', 'picked_up', 'in_transit']
                ).exclude(order=order).exists()
                if not other_busy:
                    old_profile.status = 'available'
                    old_profile.save()

            # Mark new delivery boy as on_delivery
            db_profile.status = 'on_delivery'
            db_profile.save()
            
            # If status is pending or preparing, keep it or move to ready_pickup?
            # User requirement: "Do not force a courier to be marked On Delivery before the project's actual assignment or dispatch stage if the current business logic distinguishes these states." 
            # We already mark courier as on_delivery because that's our status enum. Wait, "On Delivery" for the courier means they have an active assignment.
            order.status = 'ready_pickup'
            order.save()
            
            Notification.objects.create(
                user=order.user,
                order=order,
                title="Courier Assigned",
                message=f"Your order #{order.order_id} has been assigned to Courier {db_profile.user.username.title()} (Phone: {db_profile.user.phone or 'N/A'}, Vehicle #{db_profile.vehicle_number}).",
                notification_type='general'
            )
            
            courier_msg = (
                f"Order ID: #{order.order_id}\n"
                f"Delivery Location: Lat {order.latitude}, Lon {order.longitude}\n"
                f"Status: Assigned / Ready for Pickup"
            )
            
            Notification.objects.filter(user=db_profile.user, order=order).delete()
            Notification.objects.create(
                user=db_profile.user,
                order=order,
                title="New Delivery Assigned",
                message=courier_msg,
                notification_type='general'
            )
    except Exception as e:
        messages.error(request, f"An error occurred during assignment: {str(e)}")
        return redirect('staff_dashboard')

    messages.success(request, f"Order #{order.order_id} successfully assigned to Courier {db_profile.user.username.title()}.")
    return redirect('staff_dashboard')

@login_required
@role_required('staff', 'admin')
def staff_save_delivery_perimeter(request):
    """Saves Delivery Center and Perimeter Service Area configuration."""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip() or 'Central Kitchen Hub (Kanjirappally)'
        address = request.POST.get('address', '').strip() or 'Kanjirappally Town, Kottayam, Kerala'
        try:
            latitude = float(request.POST.get('latitude', 9.5564))
            longitude = float(request.POST.get('longitude', 76.7909))
            if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
                raise ValueError("Coordinates out of range")
        except (ValueError, TypeError):
            latitude = 9.5564
            longitude = 76.7909

        try:
            radius_km = float(request.POST.get('max_delivery_radius_km', 20.0))
            if radius_km <= 0 or radius_km > 100:
                radius_km = 20.0
        except (ValueError, TypeError):
            radius_km = 20.0

        try:
            from delivery.models import DeliverySetting
            setting = DeliverySetting.get_settings()
            setting.name = name
            setting.address = address
            setting.latitude = latitude
            setting.longitude = longitude
            setting.max_delivery_radius_km = radius_km
            setting.save()

            messages.success(
                request, 
                f"Delivery Center '{name}' and Service Perimeter ({radius_km} km radius) updated successfully!"
            )
        except Exception as e:
            messages.error(request, f"Failed to save delivery center settings: {str(e)}")

    return redirect(f"{reverse('staff_dashboard')}?tab=perimeter")

@login_required
def wishlist_view(request):
    """Displays customer's saved favorite food items."""
    wishes = Wishlist.objects.filter(user=request.user).select_related('food_item', 'food_item__category')
    wishlist_count = wishes.values('food_item_id').distinct().count()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json' or 'application/json' in request.headers.get('accept', ''):
        items_data = [{
            'id': w.food_item.id,
            'name': w.food_item.name,
            'price': float(w.food_item.price),
            'image': w.food_item.image,
            'category': w.food_item.category.name if w.food_item.category else '',
            'stock': w.food_item.stock_quantity,
        } for w in wishes]
        return JsonResponse({
            'status': 'success',
            'wishlist_count': wishlist_count,
            'items': items_data
        })
    return render(request, 'orders/wishlist.html', {
        'wishes': wishes,
        'wishlist_items': wishes,
        'wishlist_count': wishlist_count,
    })


@login_required
def notifications_view(request):
    """View to list all notifications for logged-in user."""
    notifs = Notification.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'orders/notifications.html', {'notifications': notifs})


@login_required
def mark_notification_read(request, notification_id):
    """Marks notification read and redirects courier directly to delivery track page or customer to order tracking."""
    notif = get_object_or_404(Notification, id=notification_id, user=request.user)
    notif.is_read = True
    notif.save()
    if request.user.role == 'delivery_boy' and notif.order and hasattr(notif.order, 'delivery_assignment'):
        return redirect('delivery_boy_track', assignment_id=notif.order.delivery_assignment.id)
    elif notif.order:
        return redirect('order_tracking', order_id=notif.order.order_id)
    return redirect('notifications')

@login_required
@role_required('staff', 'admin')
def staff_save_hotel_branch(request, branch_id=None):
    """Create or update a Hotel Branch across all 14 Kerala districts."""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        district_id = request.POST.get('district_id')
        address = request.POST.get('address', '').strip()
        phone = request.POST.get('phone', '').strip()
        opening_time = request.POST.get('opening_time') or '07:00:00'
        closing_time = request.POST.get('closing_time') or '22:00:00'
        operating_status = request.POST.get('operating_status', 'open')
        is_active = request.POST.get('is_active') in ['on', 'true', '1']
        is_central_hub = request.POST.get('is_central_hub') in ['on', 'true', '1']
        food_item_ids = request.POST.getlist('food_items')

        if not name or not address:
            messages.error(request, "Branch name and physical address are required.")
            return redirect(f"{reverse('staff_dashboard')}?tab=branches")

        district = District.objects.filter(id=district_id).first()
        if not district:
            messages.error(request, "Please select a valid Kerala district.")
            return redirect(f"{reverse('staff_dashboard')}?tab=branches")

        try:
            latitude = float(request.POST.get('latitude', 0.0))
            longitude = float(request.POST.get('longitude', 0.0))
            if not (8.0 <= latitude <= 13.0 and 74.0 <= longitude <= 78.0):
                messages.error(request, f"Coordinates ({latitude}, {longitude}) are outside Kerala bounds (Lat: 8.0-13.0, Lon: 74.0-78.0).")
                return redirect(f"{reverse('staff_dashboard')}?tab=branches")
        except (ValueError, TypeError):
            messages.error(request, "Invalid coordinates provided.")
            return redirect(f"{reverse('staff_dashboard')}?tab=branches")

        try:
            radius_km = float(request.POST.get('max_delivery_radius_km', 25.0))
            # Strict 25 km cap
            radius_km = min(max(radius_km, 1.0), 25.0)
        except (ValueError, TypeError):
            radius_km = 25.0

        if branch_id:
            branch = get_object_or_404(HotelBranch, id=branch_id)
        else:
            branch = HotelBranch()

        branch.name = name
        branch.district = district
        branch.address = address
        branch.latitude = latitude
        branch.longitude = longitude
        branch.max_delivery_radius_km = radius_km
        branch.phone = phone
        branch.opening_time = opening_time
        branch.closing_time = closing_time
        branch.operating_status = operating_status
        branch.is_active = is_active
        if is_central_hub:
            HotelBranch.objects.filter(is_central_hub=True).exclude(id=branch.id).update(is_central_hub=False)
            branch.is_central_hub = True
        else:
            branch.is_central_hub = False
        branch.save()

        if food_item_ids:
            branch.available_food_items.set(food_item_ids)
        else:
            branch.available_food_items.clear()

        messages.success(request, f"Hotel Branch '{name}' ({district.name} District) saved with {radius_km} km max radius.")
        return redirect(f"{reverse('staff_dashboard')}?tab=branches")

    return redirect('staff_dashboard')

@login_required
@role_required('staff', 'admin')
def staff_toggle_branch_status(request, branch_id):
    """Toggle activation of a hotel branch."""
    branch = get_object_or_404(HotelBranch, id=branch_id)
    branch.is_active = not branch.is_active
    branch.save()
    status_str = "Activated" if branch.is_active else "Deactivated"
    messages.success(request, f"Branch '{branch.name}' {status_str}.")
    return redirect(f"{reverse('staff_dashboard')}?tab=branches")

