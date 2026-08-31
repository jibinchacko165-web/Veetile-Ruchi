from django.db import models, transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import CartItem, Coupon, Order, OrderItem, Payment, Wishlist, Notification
from food.models import FoodItem
from accounts.models import User, DeliveryBoyProfile, ChefProfile
from accounts.decorators import role_required
from delivery.models import DeliveryAssignment, GPSLocationTracking
from ai_models.models import CustomerBehavior
from ai_models.ml_engine import predict_delivery_time, recommend_coupons_kmeans, optimize_delivery_route

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
    # Gather database user segments
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
        cart_item.quantity += 1
        cart_item.save()
    else:
        cart_item.quantity = 1
        cart_item.save()
        
    messages.success(request, f"Added {food.name} to cart.")
    return redirect('cart_view')

@login_required
def cart_remove(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, user=request.user)
    item.delete()
    messages.info(request, "Item removed from cart.")
    return redirect('cart_view')

@login_required
def checkout_view(request):
    """Review screen capturing GPS coordinates (Latitude/Longitude) for navigation routes."""
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
    
    context = {
        'cart_items': cart_items,
        'subtotal': subtotal,
        'discount': discount,
        'total': total,
        'coupon': coupon,
    }
    return render(request, 'orders/checkout.html', context)

@login_required
def place_order(request):
    """Places order, captures customer GPS location and starts payment transaction."""
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
        
        # Capture customer GPS location coordinates
        try:
            latitude = float(request.POST.get('latitude', '') or getattr(request.user, 'latitude', 9.462534))
        except (ValueError, TypeError):
            latitude = getattr(request.user, 'latitude', 9.462534)
        try:
            longitude = float(request.POST.get('longitude', '') or getattr(request.user, 'longitude', 76.72185))
        except (ValueError, TypeError):
            longitude = getattr(request.user, 'longitude', 76.72185)
        
        # Payment setup
        payment_method = request.POST.get('payment_method', 'cod')
        
        # Create Order
        order = Order.objects.create(
            user=request.user,
            total_amount=total_amount,
            coupon=coupon,
            status='pending',
            latitude=latitude,
            longitude=longitude,
            delivery_address=''
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
        # Recalculate average spend
        user_orders = Order.objects.filter(user=request.user)
        behavior.average_order_value = user_orders.aggregate(models.Avg('total_amount'))['total_amount__avg'] or 0.00
        
        # Guess peak session
        sessions_grouped = user_orders.values('items__food_item__meal_session').annotate(count=models.Count('order_id')).order_by('-count')
        if sessions_grouped and sessions_grouped[0]['items__food_item__meal_session']:
            from food.models import MealSession
            behavior.most_ordered_session = MealSession.objects.filter(id=sessions_grouped[0]['items__food_item__meal_session']).first()
            
        # Guess behavior segment
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
    
    chef_lat, chef_lon = 10.015, 76.325
    cust_lat = order.latitude
    cust_lon = order.longitude
    
    route_steps, distance_km = optimize_delivery_route(chef_lat, chef_lon, cust_lat, cust_lon)
    
    # Calculate Random Forest Regressor AI Predictions
    items_cnt = order.items.count() if hasattr(order, 'items') else 1
    courier_lat = assignment.delivery_boy.current_latitude if assignment else chef_lat
    courier_lon = assignment.delivery_boy.current_longitude if assignment else chef_lon
    from ai_models.ml_engine import predict_delivery_time_rf
    pred_delivery_min, ai_eta_min, dist_km = predict_delivery_time_rf(
        courier_lat, courier_lon, cust_lat, cust_lon, items_count=items_cnt
    )

    assigned_courier = assignment.delivery_boy.user if assignment and assignment.delivery_boy else None

    context = {
        'order': order,
        'payment': payment,
        'assignment': assignment,
        'assigned_courier': assigned_courier,
        'route_steps': route_steps,
        'distance_km': dist_km,
        'pred_delivery_min': pred_delivery_min,
        'ai_eta_min': ai_eta_min,
        'chef_lat': chef_lat,
        'chef_lon': chef_lon,
        'cust_lat': cust_lat,
        'cust_lon': cust_lon,
    }
    return render(request, 'orders/tracking.html', context)

@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).select_related('payment').prefetch_related('items__food_item', 'delivery_assignment__delivery_boy__user', 'delivery_feedback').order_by('-created_at')
    return render(request, 'orders/history.html', {'orders': orders})

@login_required
@role_required('staff', 'admin')
def staff_dashboard(request):
    """Staff Console for food order management, chef approvals, and delivery tracking."""
    active_tab = request.GET.get('tab', 'orders')
    orders = Order.objects.all().order_by('-created_at').select_related('user', 'payment').prefetch_related('items__food_item', 'delivery_assignment__delivery_boy__user')
    available_boys = DeliveryBoyProfile.objects.filter(status='available').select_related('user')
    all_couriers = DeliveryBoyProfile.objects.all().select_related('user')
    chefs = ChefProfile.objects.all().select_related('user')
    
    # If no available delivery boys, show all couriers so staff can still assign
    delivery_boys = available_boys if available_boys.exists() else all_couriers
        
    context = {
        'active_tab': active_tab,
        'orders': orders,
        'delivery_boys': delivery_boys,
        'all_couriers': all_couriers,
        'chefs': chefs,
        'assignments': DeliveryAssignment.objects.all().order_by('-assigned_at').select_related('order__user', 'delivery_boy__user').prefetch_related('order__items__food_item'),
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
    
    # Validation
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

    db_profile = get_object_or_404(DeliveryBoyProfile, id=db_id)
    if not db_profile.user.is_active:
        messages.error(request, "The selected delivery boy account is inactive.")
        return redirect('staff_dashboard')

    # 1. AI Delivery Time Prediction
    chef_lat, chef_lon = 10.015, 76.325
    cust_lat, cust_lon = order.latitude, order.longitude
    pred_minutes = predict_delivery_time(chef_lat, chef_lon, cust_lat, cust_lon)

    with transaction.atomic():
        # 2. Assignment creation / update with re-assignment cleanup
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
        
        # Update order status: Set status to assigned (Never set to delivered on courier assignment)
        order.status = 'assigned'
        order.save()
        
        # Create Customer notification for Courier Assignment
        Notification.objects.create(
            user=order.user,
            order=order,
            title="Courier Assigned",
            message=f"Your order #{order.order_id} has been assigned to Courier {db_profile.user.username.title()} (Phone: {db_profile.user.phone or 'N/A'}, Vehicle #{db_profile.vehicle_number}).",
            notification_type='general'
        )
        
        # Build detailed food items list with quantities and food IDs
        first_item = order.items.first()
        food_id_str = f"FOOD{first_item.food_item.id:04d}" if first_item else "FOOD0000"
        items_list = [f"{item.food_item.name} (x{item.quantity})" for item in order.items.all()]
        items_str = ", ".join(items_list) if items_list else "Food Item"

        courier_msg = (
            f"Order ID: #{order.order_id}\n"
            f"Food ID: {food_id_str}\n"
            f"Food: {items_str}\n"
            f"Delivery Location: Lat {order.latitude}, Lon {order.longitude}\n"
            f"Status: Assigned / Ready for Pickup"
        )
        
        # Create Delivery Boy notification strictly ONCE per courier assignment
        Notification.objects.filter(user=db_profile.user, order=order).delete()
        Notification.objects.create(
            user=db_profile.user,
            order=order,
            title="New Delivery Assigned",
            message=courier_msg,
            notification_type='general'
        )

    messages.success(request, f"Order #{order.order_id} successfully assigned to Courier {db_profile.user.username.title()}.")
    return redirect('staff_dashboard')


@login_required
def wishlist_view(request):
    """Displays customer's saved favorite food items."""
    wishes = Wishlist.objects.filter(user=request.user).select_related('food_item', 'food_item__category')
    return render(request, 'orders/wishlist.html', {
        'wishes': wishes,
        'wishlist_items': wishes,
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
