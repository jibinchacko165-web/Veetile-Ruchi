import os
from django.conf import settings
from django.db import models, transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from django.contrib import messages
from django.utils import timezone
from .models import CartItem, Coupon, Order, OrderItem, Payment, Wishlist, Notification, ChefFeedback
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

    # Configure Central Kitchen Hub (Kanjirappally) as the only active kitchen for checkout
    branches = HotelBranch.objects.filter(is_active=True, is_central_hub=True).select_related('district')
    if not branches.exists():
        branches = HotelBranch.objects.filter(is_active=True, name__icontains='Kanjirappally').select_related('district')
    if not branches.exists():
        branches = HotelBranch.objects.filter(is_active=True).select_related('district')[:1]
    if not branches.exists():
        # Safeguard fallback: Ensure Central Kitchen Hub is registered and linked
        kottayam, _ = District.objects.get_or_create(
            name='Kottayam',
            defaults={'code': 'kottayam', 'latitude': 9.5916, 'longitude': 76.5222, 'is_active': True}
        )
        hub, _ = HotelBranch.objects.get_or_create(
            is_central_hub=True,
            defaults={
                'name': delivery_setting.name or 'Central Kitchen Hub (Kanjirappally)',
                'district': kottayam,
                'address': delivery_setting.address or 'Kanjirappally Town, Kottayam, Kerala',
                'latitude': delivery_setting.latitude or 9.5564,
                'longitude': delivery_setting.longitude or 76.7909,
                'max_delivery_radius_km': 30.0,
                'is_active': True,
                'is_central_hub': True,
                'phone': '+91 7510672355',
                'operating_status': 'open',
            }
        )
        branches = HotelBranch.objects.filter(id=hub.id).select_related('district')

    # Selected default is Central Kitchen Hub (Kanjirappally)
    selected_branch = branches.first()

    # Determine serving coordinates and 30 km max radius
    if selected_branch:
        hub_lat = selected_branch.latitude
        hub_lon = selected_branch.longitude
        hub_name = selected_branch.name
        hub_radius_km = min(float(selected_branch.max_delivery_radius_km or 30.0), 30.0)
    else:
        hub_lat = delivery_setting.latitude
        hub_lon = delivery_setting.longitude
        hub_name = delivery_setting.name
        hub_radius_km = min(float(delivery_setting.max_delivery_radius_km or 30.0), 30.0)

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


        # Resolve serving hotel branch - strictly enforce active Central Kitchen Hub (Kanjirappally)
        central_branch = HotelBranch.objects.filter(is_central_hub=True, is_active=True).first()
        if not central_branch:
            central_branch = HotelBranch.objects.filter(name__icontains='Kanjirappally', is_active=True).first()
        if not central_branch:
            central_branch = HotelBranch.objects.filter(is_active=True).first()

        serving_branch = central_branch
        if branch_id:
            try:
                b_id_int = int(branch_id)
            except (ValueError, TypeError):
                messages.error(request, "Invalid kitchen branch selected.")
                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                    return JsonResponse({'success': False, 'message': 'Invalid kitchen branch selected.'}, status=400)
                return redirect('checkout_view')

            requested_branch = HotelBranch.objects.filter(id=b_id_int).first()
            if not requested_branch or not requested_branch.is_active or (central_branch and requested_branch.id != central_branch.id):
                error_msg = "Selected kitchen branch is unavailable. Only Central Kitchen Hub (Kanjirappally) is accepting orders."
                messages.error(request, error_msg)
                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                    return JsonResponse({'success': False, 'message': error_msg}, status=400)
                return redirect('checkout_view')
            serving_branch = requested_branch

        # Enforce Delivery Perimeter Verification (strictly 30 km limit for Central Hub)
        is_serviceable, dist_km, perimeter_msg = is_within_delivery_perimeter(
            latitude, longitude,
            branch_id=serving_branch.id if serving_branch else None,
            max_radius_km=30.0
        )
        if not is_serviceable:
            # Basket remains 100% intact
            messages.error(request, "Sorry, this hotel cannot deliver to your selected location. Please choose a nearer address or another available hotel.")
            messages.error(request, perimeter_msg)
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

            # Create Chef notification(s) for New Incoming Food Order
            chef_recipients = set()
            for oi in order.items.select_related('food_item', 'food_item__chef'):
                if oi.food_item.chef:
                    chef_recipients.add(oi.food_item.chef)
            if not chef_recipients:
                chef_recipients = set(User.objects.filter(role='chef', is_active=True))

            cust_display_name = request.user.get_full_name() or request.user.username
            for chef_user in chef_recipients:
                Notification.objects.create(
                    user=chef_user,
                    order=order,
                    title="New Order Received!",
                    message=f"New Order #{order.order_id} received from {cust_display_name}.",
                    notification_type='new_order'
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

    from .utils import get_active_delivery_setting, validate_coordinates, sanitize_customer_coordinates, is_offshore_sea_coordinate
    delivery_setting = get_active_delivery_setting()
    branch = getattr(order, 'branch', None)
    chef_lat = branch.latitude if branch else delivery_setting.latitude
    chef_lon = branch.longitude if branch else delivery_setting.longitude
    
    cust_lat, cust_lon = sanitize_customer_coordinates(order.latitude, order.longitude, fallback_lat=chef_lat, fallback_lon=chef_lon)
    
    from .utils import calculate_accurate_order_eta, get_courier_gps_status
    gps_info = get_courier_gps_status(order, assignment)

    tracking_data = calculate_accurate_order_eta(
        order=order,
        chef_lat=chef_lat,
        chef_lon=chef_lon,
        cust_lat=cust_lat,
        cust_lon=cust_lon,
        courier_lat=gps_info['courier_lat'],
        courier_lon=gps_info['courier_lon'],
        has_courier_gps=gps_info['has_courier_gps'],
        is_gps_stale=gps_info['is_gps_stale'],
        last_gps_update=gps_info['last_gps_update']
    )

    assigned_courier = assignment.delivery_boy.user if assignment and assignment.delivery_boy else None

    context = {
        'order': order,
        'payment': payment,
        'assignment': assignment,
        'assigned_courier': assigned_courier,
        'chef_lat': chef_lat,
        'chef_lon': chef_lon,
        'cust_lat': cust_lat,
        'cust_lon': cust_lon,
        'courier_lat': tracking_data.get('courier_lat'),
        'courier_lon': tracking_data.get('courier_lon'),
        'has_courier_gps': tracking_data.get('has_courier_gps'),
        'is_gps_stale': tracking_data.get('is_gps_stale'),
        'last_gps_update': tracking_data.get('last_gps_update'),
        'route_steps': tracking_data.get('route_steps', []),
        'distance_km': tracking_data.get('remaining_road_distance_km', 0.0),
        'is_road_distance': tracking_data.get('is_road_distance', True),
        'ai_eta_min': tracking_data.get('ai_eta_min', 35),
        'tracking_data': tracking_data,
        **tracking_data,
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
    
    from .utils import get_active_delivery_setting, validate_coordinates, sanitize_customer_coordinates, is_offshore_sea_coordinate, calculate_accurate_order_eta
    delivery_setting = get_active_delivery_setting()
    branch = getattr(order, 'branch', None)
    chef_lat = branch.latitude if branch else delivery_setting.latitude
    chef_lon = branch.longitude if branch else delivery_setting.longitude
    
    cust_lat, cust_lon = sanitize_customer_coordinates(order.latitude, order.longitude, fallback_lat=chef_lat, fallback_lon=chef_lon)
        
    from .utils import calculate_accurate_order_eta, get_courier_gps_status
    gps_info = get_courier_gps_status(order, assignment)

    tracking_data = calculate_accurate_order_eta(
        order=order,
        chef_lat=chef_lat,
        chef_lon=chef_lon,
        cust_lat=cust_lat,
        cust_lon=cust_lon,
        courier_lat=gps_info['courier_lat'],
        courier_lon=gps_info['courier_lon'],
        has_courier_gps=gps_info['has_courier_gps'],
        is_gps_stale=gps_info['is_gps_stale'],
        last_gps_update=gps_info['last_gps_update']
    )

    payment = getattr(order, 'payment', None)
    payment_method = payment.payment_method if payment else 'cod'
    payment_status = payment.status if payment else 'pending'
    payment_display = payment.display_status if payment else ('Paid Online' if payment_method == 'upi' else 'Cash on Delivery')

    return JsonResponse({
        'status': 'success',
        **tracking_data,
        'customer_name': order.user.get_full_name() or order.user.username,
        'customer_phone': getattr(order.user, 'phone', '') or 'Phone not provided',
        'customer_delivery_notes': order.customer_delivery_notes or order.delivery_address or '',
        'has_courier': courier_user is not None,
        'courier_name': courier_profile.courier_name if courier_profile else None,
        'courier_username': courier_profile.courier_username if courier_profile else None,
        'courier_phone': getattr(courier_user, 'phone', '') if courier_user else None,
        'vehicle_number': courier_profile.vehicle_number if courier_profile else None,
        'distance_km': tracking_data.get('remaining_road_distance_km', 0.0),
        'pred_delivery_min': tracking_data.get('remaining_travel_minutes', 0),
        'payment_method': payment_method,
        'payment_status': payment_status,
        'payment_display_status': payment_display,
    })


@login_required
def cancel_order(request, order_id):
    """
    Allows the customer who placed an order to cancel it while still in 'pending' status
    (before kitchen accepts/prepares or staff assigns courier).
    Restocks ordered items, updates payment/notification state, and provides clear feedback.
    """
    order = get_object_or_404(Order, order_id=order_id)
    if order.user != request.user and not request.user.is_staff and request.user.role != 'admin':
        messages.error(request, "Access denied. You can only cancel your own orders.")
        return redirect('order_history')

    if order.status == 'pending':
        with transaction.atomic():
            order.status = 'cancelled'
            order.save()
            for item in order.items.select_related('food_item'):
                food = item.food_item
                food.stock_quantity += item.quantity
                food.save()
            payment = getattr(order, 'payment', None)
            if payment and payment.status in ['pending', 'unpaid']:
                payment.status = 'cancelled'
                payment.save()
            Notification.objects.create(
                user=order.user,
                order=order,
                title="Order Cancelled",
                message=f"Your order #{order.order_id} has been cancelled successfully. Ordered items have been returned to stock.",
                notification_type='general'
            )
            messages.success(request, f"Order #{order.order_id} has been cancelled successfully.")
    elif order.status == 'cancelled':
        messages.info(request, f"Order #{order.order_id} is already cancelled.")
    else:
        messages.error(request, f"Order #{order.order_id} cannot be cancelled because it is already {order.get_status_display().lower()}.")

    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('order_tracking', order_id=order.order_id)


@never_cache
@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).select_related(
        'payment', 
        'delivery_assignment__delivery_boy__user', 
        'delivery_feedback',
        'chef_feedback'
    ).prefetch_related('items__food_item').order_by('-created_at')
    return render(request, 'orders/history.html', {'orders': orders})


@login_required
def submit_chef_feedback(request, order_id):
    """Customer chef and food quality review submission handler."""
    order = get_object_or_404(Order, order_id=order_id)

    if request.user != order.user:
        messages.error(request, "You can only review food for your own orders.")
        return redirect('order_history')

    if order.status != 'delivered':
        messages.error(request, "Chef and food reviews can only be submitted after the order has been Delivered.")
        return redirect('order_history')

    chef = order.responsible_chef
    if not chef:
        messages.error(request, "No chef or kitchen partner profile is associated with this order.")
        return redirect('order_history')

    if request.method == 'POST':
        try:
            rating = int(request.POST.get('rating', 5))
            rating = max(1, min(5, rating))
        except (ValueError, TypeError):
            rating = 5

        try:
            taste_rating = int(request.POST.get('taste_rating', rating))
            taste_rating = max(1, min(5, taste_rating))
        except (ValueError, TypeError):
            taste_rating = rating

        try:
            freshness_rating = int(request.POST.get('freshness_rating', rating))
            freshness_rating = max(1, min(5, freshness_rating))
        except (ValueError, TypeError):
            freshness_rating = rating

        try:
            packaging_rating = int(request.POST.get('packaging_rating', rating))
            packaging_rating = max(1, min(5, packaging_rating))
        except (ValueError, TypeError):
            packaging_rating = rating

        comment = request.POST.get('comment', '').strip()[:1000]
        problem_reported = request.POST.get('problem_reported', '').strip()[:1000]

        with transaction.atomic():
            feedback, created = ChefFeedback.objects.update_or_create(
                order=order,
                defaults={
                    'chef': chef,
                    'customer': request.user,
                    'branch': order.branch,
                    'rating': rating,
                    'taste_rating': taste_rating,
                    'freshness_rating': freshness_rating,
                    'packaging_rating': packaging_rating,
                    'comment': comment,
                    'problem_reported': problem_reported,
                }
            )

            # Recompute chef average rating from genuine unmoderated reviews
            avg_rating = ChefFeedback.objects.filter(
                chef=chef,
                is_hidden_by_admin=False
            ).aggregate(models.Avg('rating'))['rating__avg']
            if avg_rating is not None and hasattr(chef, 'chef_profile'):
                chef.chef_profile.rating = round(float(avg_rating), 1)
                chef.chef_profile.save(update_fields=['rating'])

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
            return JsonResponse({
                'status': 'success',
                'message': "Thank you! Your food and chef review has been submitted successfully.",
                'rating': rating,
                'taste_rating': taste_rating,
                'freshness_rating': freshness_rating,
                'packaging_rating': packaging_rating,
                'comment': comment,
                'problem_reported': problem_reported
            })

        messages.success(request, "Thank you! Your food and chef review has been recorded successfully.")
        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'order_history'
        return redirect(next_url)

    # GET request - return existing saved feedback if any
    existing = ChefFeedback.objects.filter(order=order).first()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        if existing:
            return JsonResponse({
                'status': 'success',
                'has_feedback': True,
                'rating': existing.rating,
                'taste_rating': existing.taste_rating,
                'freshness_rating': existing.freshness_rating,
                'packaging_rating': existing.packaging_rating,
                'comment': existing.comment,
                'problem_reported': existing.problem_reported,
                'created_at': existing.created_at.strftime("%b %d, %Y • %I:%M %p")
            })
        else:
            chef_name = chef.get_full_name() or chef.username
            if hasattr(chef, 'chef_profile') and chef.chef_profile.kitchen_name:
                chef_name = f"{chef.chef_profile.kitchen_name} ({chef_name})"
            return JsonResponse({
                'status': 'success',
                'has_feedback': False,
                'chef_name': chef_name
            })

    return redirect('order_history')

@never_cache
@login_required
@role_required('staff', 'admin')
def staff_dashboard(request):
    """Staff Console for food order management, chef approvals, delivery tracking, and district-wise branches."""
    active_tab = request.GET.get('tab', 'orders')
    orders = Order.objects.all().order_by('-created_at').select_related('user', 'payment', 'delivery_assignment__delivery_boy__user').prefetch_related('items__food_item')
    # All 9 registered courier boys with unique mobile numbers
    courier_usernames = [f'courier{i}' for i in range(1, 10)]
    all_couriers_qs = DeliveryBoyProfile.objects.filter(user__username__in=courier_usernames).select_related('user').prefetch_related('assignments__order')
    all_couriers = list(all_couriers_qs)
    if len(all_couriers) < 9:
        fallback = list(DeliveryBoyProfile.objects.exclude(user__username='courier').select_related('user').prefetch_related('assignments__order')[:9])
        if len(fallback) > len(all_couriers):
            all_couriers = fallback

    # Sort stably: Courier 1 through Courier 9
    def courier_sort_key(c):
        u = c.user.username.lower() if c.user else ''
        for i in range(1, 10):
            if f"courier{i}" in u:
                return i
        return c.id
    all_couriers.sort(key=courier_sort_key)

    # Automatically synchronize each courier boy's status based on active delivery assignments
    for c in all_couriers:
        active = c.assignments.filter(
            status__in=['assigned', 'picked_up', 'in_transit'],
            is_active=True
        ).exists()
        if active and c.status not in ['on_delivery', 'busy']:
            c.status = 'on_delivery'
            c.save(update_fields=['status'])
        elif not active and c.status in ['on_delivery', 'busy']:
            c.status = 'available'
            c.save(update_fields=['status'])

    available_boys = [c for c in all_couriers if c.realtime_status == 'Available']
    busy_couriers = [c for c in all_couriers if c.realtime_status == 'Busy (currently delivering an order)']
    offline_couriers = [c for c in all_couriers if c.realtime_status == 'Offline']
    delivery_boys = all_couriers
    chefs = ChefProfile.objects.all().select_related('user')
    delivery_setting = get_active_delivery_setting()

    # District & Hotel Branch Management Data
    districts = District.objects.all().annotate(branches_count=models.Count('hotel_branches')).order_by('name')
    district_filter = request.GET.get('district_filter', '').strip()
    
    hotel_branches = HotelBranch.objects.all().select_related('district').prefetch_related('available_food_items').order_by('district__name', 'name')
    if district_filter and district_filter != 'All':
        hotel_branches = hotel_branches.filter(models.Q(district__code=district_filter) | models.Q(district__name__iexact=district_filter))
        
    all_food_items = FoodItem.objects.all().order_by('name')
    cash_collected_orders_count = orders.filter(payment__payment_method='cod', payment__status='cash_collected').count()

    context = {
        'active_tab': active_tab,
        'orders': orders,
        'cash_collected_orders_count': cash_collected_orders_count,
        'delivery_boys': delivery_boys,
        'available_couriers_count': len(available_boys),
        'busy_couriers_count': len(busy_couriers),
        'offline_couriers_count': len(offline_couriers),
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
        now = timezone.now()
        if new_status == 'preparing':
            if not order.preparing_started_at:
                order.preparing_started_at = now
        elif new_status == 'ready_pickup':
            if not order.food_prepared_at:
                order.food_prepared_at = now
            if not order.preparing_started_at:
                order.preparing_started_at = order.created_at or now
        order.save()
        messages.success(request, f"Order #{order.order_id} status updated to {order.get_status_display()}.")
    return redirect('staff_dashboard')

@login_required
@role_required('staff', 'admin')
def staff_confirm_payment(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)
    payment = get_object_or_404(Payment, order=order)
    payment.status = 'success'
    now = timezone.now()
    if payment.payment_method == 'cod' and not payment.cash_collected_by:
        payment.cash_collected_by = request.user
        payment.cash_collected_at = now
        payment.save(update_fields=['status', 'cash_collected_by', 'cash_collected_at'])
    else:
        payment.save(update_fields=['status'])
    messages.success(request, f"Payment for Order #{order.order_id} verified successfully.")
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
                
            if db_profile.realtime_status != 'Available':
                messages.error(request, f"Courier {db_profile.courier_name} is currently {db_profile.realtime_status} and cannot be assigned a new order.")
                return redirect('staff_dashboard')

            active_deliv = DeliveryAssignment.objects.filter(
                delivery_boy=db_profile,
                status__in=['assigned', 'picked_up', 'in_transit'],
                is_active=True
            ).exclude(order=order).exists()
            if active_deliv:
                messages.error(request, f"Courier {db_profile.courier_name} already has an active delivery in progress.")
                return redirect('staff_dashboard')

            # Clean up old assignment if reassignment
            old_profile = None
            if hasattr(order, 'delivery_assignment'):
                old_assignment = order.delivery_assignment
                if old_assignment.delivery_boy != db_profile:
                    old_profile = old_assignment.delivery_boy
                    Notification.objects.filter(user=old_profile.user, order=order).delete()

            now = timezone.now()
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
                assignment.assigned_at = now
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
                    status__in=['assigned', 'picked_up', 'in_transit'],
                    is_active=True
                ).exclude(order=order).exists()
                if not other_busy:
                    old_profile.status = 'available'
                    old_profile.save()

            # Mark new delivery boy as on_delivery
            db_profile.status = 'on_delivery'
            db_profile.save()
            
            # Advance order status to 'assigned' (Courier Assigned stage)
            order.status = 'assigned'
            order.courier_assigned_at = now
            order.picked_up_at = None
            if not order.food_prepared_at:
                order.food_prepared_at = now
            if not order.preparing_started_at:
                order.preparing_started_at = order.created_at or now
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
            radius_km = float(request.POST.get('max_delivery_radius_km', 30.0))
            # Strict 30 km cap
            radius_km = min(max(radius_km, 1.0), 30.0)
        except (ValueError, TypeError):
            radius_km = 30.0

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

@require_GET
def api_reverse_geocode(request):
    """
    Reverse-geocode latitude and longitude into a readable address string.
    Uses local Kerala Landmark presets and coordinate formatting.
    """
    lat_str = request.GET.get('lat')
    lon_str = request.GET.get('lon')
    try:
        lat = float(lat_str)
        lon = float(lon_str)
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'Invalid latitude/longitude parameters.'}, status=400)

    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return JsonResponse({'success': False, 'error': 'Coordinates out of geographical range.'}, status=400)

    from django.core.cache import cache
    cache_key = f"orders_rev_geo_{round(lat, 4)}_{round(lon, 4)}"
    cached = cache.get(cache_key)
    # 1. Resolve via Nearest Kerala Preset Place
    best_place = None
    min_dist = float('inf')
    for p in KERALA_PRESET_PLACES:
        dist = calculate_distance_km(lat, lon, p['lat'], p['lon'])
        if dist < min_dist:
            min_dist = dist
            best_place = p

    if best_place:
        if min_dist < 0.3:
            addr = f"{best_place['name']}, {best_place['desc']} (Landmark: {best_place['landmark']})"
        else:
            addr = f"Near {best_place['name']} (~{min_dist:.1f} km away), {best_place['desc']}"
        return JsonResponse({'success': True, 'address': addr, 'source': 'preset', 'distance_km': min_dist})

    return JsonResponse({'success': True, 'address': f"Location: Lat {lat:.5f}, Lon {lon:.5f}", 'source': 'coordinates'})


