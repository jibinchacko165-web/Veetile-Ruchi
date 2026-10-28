from django.db import models, transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from .models import DeliveryAssignment, GPSLocationTracking, DeliveryFeedback
from orders.models import Order, Notification, Payment
from accounts.models import User, DeliveryBoyProfile
from accounts.decorators import role_required
from ai_models.ml_engine import optimize_delivery_route
from orders.utils import to_kolkata_datetime

@never_cache
@login_required
@role_required('delivery_boy', 'admin', 'staff')
def delivery_boy_dashboard(request):
    """
    Courier Dashboard where couriers view only their assigned delivery tasks.
    """
    all_profiles = DeliveryBoyProfile.objects.select_related('user').all()
    user_profile = getattr(request.user, 'delivery_boy_profile', None)

    req_vehicle = request.GET.get('vehicle_number') or request.POST.get('vehicle_number')
    req_courier_id = request.GET.get('courier_id')
    if req_courier_id:
        profile = all_profiles.filter(id=req_courier_id).first()
    elif req_vehicle:
        profile = all_profiles.filter(vehicle_number__iexact=req_vehicle.strip()).first()
    else:
        profile = user_profile or all_profiles.first()

    other_courier_assignments = DeliveryAssignment.objects.none()

    active_vehicle_number = profile.vehicle_number if profile else ''
    if profile:
        request.session['selected_vehicle_number'] = profile.vehicle_number

    # Base Queryset: strictly filter by the assigned Courier Profile ID
    all_assignments = DeliveryAssignment.objects.filter(
        delivery_boy=profile
    ).select_related('order', 'order__user', 'delivery_boy__user').prefetch_related('order__items__food_item').order_by('-assigned_at')

    # Active tab parameter (Defaults to 'new')
    tab = request.GET.get('tab', 'new')
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # 1. Current / Active Orders for selected vehicle number
    current_assignments = all_assignments.exclude(
        status__in=['delivered', 'cancelled']
    ).exclude(
        order__status__in=['delivered', 'cancelled']
    )

    # 2. New / Pending Deliveries for selected vehicle number
    pending_assignments = all_assignments.exclude(
        status__in=['in_transit', 'delivered', 'cancelled']
    ).exclude(
        order__status__in=['in_transit', 'delivered', 'cancelled']
    )

    # 3. Active Out for Delivery Tasks (In transit) for selected vehicle number
    in_transit_assignments = all_assignments.filter(
        models.Q(status='in_transit') | models.Q(order__status='in_transit')
    ).exclude(
        status__in=['delivered', 'cancelled']
    ).exclude(
        order__status__in=['delivered', 'cancelled']
    )

    # 4. Completed Deliveries for selected vehicle number
    completed_assignments = all_assignments.filter(
        models.Q(status='delivered') | models.Q(order__status='delivered')
    )

    # 5. Today's assignments
    todays_assignments = all_assignments.filter(assigned_at__gte=today_start)

    # Determine assignments list based on tab
    if tab in ['new', 'pending']:
        assignments = pending_assignments
    elif tab in ['current', 'dashboard']:
        assignments = current_assignments
    elif tab in ['active', 'in_transit']:
        assignments = in_transit_assignments
    elif tab in ['completed', 'delivered']:
        assignments = completed_assignments
    elif tab == 'today':
        assignments = todays_assignments
    elif tab in ['total', 'all']:
        assignments = all_assignments
    else:
        assignments = pending_assignments

    # Search filter
    query = request.GET.get('q', '').strip()
    if query:
        food_id_clean = query.upper().replace('FOOD-', '').replace('FOOD', '').replace('#', '').strip()
        q_filter = (
            models.Q(order__order_id__icontains=query) |
            models.Q(order__items__food_item__name__icontains=query) |
            models.Q(order__user__username__icontains=query) |
            models.Q(order__user__first_name__icontains=query)
        )
        if food_id_clean.isdigit():
            q_filter |= models.Q(order__items__food_item__id=int(food_id_clean))
        elif food_id_clean:
            q_filter |= models.Q(order__items__food_item__id__icontains=food_id_clean)

        assignments = assignments.filter(q_filter).distinct()

    feedbacks = DeliveryFeedback.objects.filter(
        delivery_boy=profile,
        is_hidden_by_admin=False
    ).select_related('order', 'customer').order_by('-created_at') if profile else []
    
    total_delivery_reviews = feedbacks.count() if profile else 0
    if total_delivery_reviews > 0:
        agg = feedbacks.aggregate(
            avg_rating=models.Avg('rating'),
            avg_time=models.Avg('timeliness_rating'),
            avg_behavior=models.Avg('behavior_rating'),
            avg_handling=models.Avg('food_handling_rating')
        )
        avg_delivery_rating = round(float(agg['avg_rating'] or 5.0), 1)
        avg_timeliness = round(float(agg['avg_time'] or 5.0), 1)
        avg_behavior = round(float(agg['avg_behavior'] or 5.0), 1)
        avg_handling = round(float(agg['avg_handling'] or 5.0), 1)
        
        star_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for fb in feedbacks:
            r = min(5, max(1, fb.rating))
            star_counts[r] += 1
            
        rating_distribution = [
            {'star': s, 'count': star_counts[s], 'pct': round((star_counts[s] / total_delivery_reviews) * 100, 1)}
            for s in range(5, 0, -1)
        ]
    else:
        avg_delivery_rating = round(float(profile.rating if profile else 5.0), 1)
        avg_timeliness = 5.0
        avg_behavior = 5.0
        avg_handling = 5.0
        rating_distribution = [
            {'star': s, 'count': 0, 'pct': 0.0} for s in range(5, 0, -1)
        ]

    recent_delivery_comments = feedbacks.exclude(comment__isnull=True).exclude(comment__exact='')[:10] if profile else []

    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:20]
    
    total_assigned_count = all_assignments.count()
    current_count = current_assignments.count()
    pending_count = pending_assignments.count()
    active_count = in_transit_assignments.count()
    completed_count = completed_assignments.count()
    todays_count = todays_assignments.count()
    unread_notifications = Notification.objects.filter(user=request.user, is_read=False).select_related('order__branch').order_by('-created_at')
    unread_notif_count = unread_notifications.count()
    
    avg_rating = avg_delivery_rating

    context = {
        'assignments': assignments,
        'all_assignments': all_assignments,
        'other_courier_assignments': other_courier_assignments,
        'all_profiles': all_profiles,
        'active_vehicle_number': active_vehicle_number,
        'feedbacks': feedbacks,
        'total_delivery_reviews': total_delivery_reviews,
        'avg_delivery_rating': avg_delivery_rating,
        'avg_timeliness': avg_timeliness,
        'avg_behavior': avg_behavior,
        'avg_handling': avg_handling,
        'rating_distribution': rating_distribution,
        'recent_delivery_comments': recent_delivery_comments,
        'notifications': notifications,
        'unread_notifications': unread_notifications,
        'profile': profile,
        'tab': tab,
        'total_assigned_count': total_assigned_count,
        'current_count': current_count,
        'pending_count': pending_count,
        'active_count': active_count,
        'completed_count': completed_count,
        'todays_count': todays_count,
        'unread_notif_count': unread_notif_count,
        'avg_rating': round(avg_rating, 1),
        'query': query,
    }
    return render(request, 'delivery/dashboard.html', context)

def get_assignment_by_id_or_order_id(assignment_id):
    """Safely retrieves DeliveryAssignment by PK or related Order order_id without invalid field lookups."""
    assignment = None
    if isinstance(assignment_id, int) or (isinstance(assignment_id, str) and str(assignment_id).isdigit()):
        assignment = DeliveryAssignment.objects.filter(id=int(assignment_id)).first()
    
    if not assignment:
        assignment = DeliveryAssignment.objects.filter(order__order_id=str(assignment_id)).first()
        
    return assignment


@login_required
def delivery_boy_track(request, assignment_id):
    """Courier GPS navigation & tracking page with device location connection."""
    assignment = get_assignment_by_id_or_order_id(assignment_id)

    if not assignment:
        messages.error(request, "Delivery assignment was not found or has been reassigned.")
        if request.user.role == 'delivery_boy':
            return redirect('delivery_boy_dashboard')
        elif request.user.role == 'staff':
            return redirect('staff_dashboard')
        else:
            return redirect('dashboard_redirect')
            
    # Security Rule: Courier can track ONLY assigned orders (or staff/admin/customer owner)
    if request.user.role == 'delivery_boy' and assignment.delivery_boy.user != request.user:
        messages.error(request, "Access restricted: You are not assigned to this delivery.")
        return redirect('delivery_boy_dashboard')

    if request.user.role not in ['delivery_boy', 'staff', 'admin'] and request.user != assignment.order.user:
        messages.error(request, "Access restricted.")
        return redirect('dashboard_redirect')

    order = assignment.order
    profile = assignment.delivery_boy
        

    from orders.utils import get_active_delivery_setting, validate_coordinates
    delivery_setting = get_active_delivery_setting()
    branch = getattr(order, 'branch', None)
    chef_lat = branch.latitude if branch else delivery_setting.latitude
    chef_lon = branch.longitude if branch else delivery_setting.longitude
    
    from orders.utils import sanitize_customer_coordinates, is_offshore_sea_coordinate
    cust_lat, cust_lon = sanitize_customer_coordinates(order.latitude, order.longitude, fallback_lat=chef_lat, fallback_lon=chef_lon)
    
    # Genuine courier GPS retrieval with freshness validation (max 5 mins = 300s)
    latest_gps = GPSLocationTracking.objects.filter(delivery_assignment=assignment).order_by('-timestamp').first()
    has_courier_gps = False
    is_gps_stale = False
    courier_lat = None
    courier_lon = None
    last_gps_timestamp = None

    if latest_gps and -90.0 <= latest_gps.latitude <= 90.0 and -180.0 <= latest_gps.longitude <= 180.0:
        age_seconds = (timezone.now() - latest_gps.timestamp).total_seconds()
        courier_lat = latest_gps.latitude
        courier_lon = latest_gps.longitude
        from orders.utils import to_kolkata_datetime
        local_gps_dt = to_kolkata_datetime(latest_gps.timestamp)
        formatted_gps_time = local_gps_dt.strftime("%I:%M:%S %p")
        if age_seconds <= 300:
            has_courier_gps = True
            is_gps_stale = False
            last_gps_timestamp = formatted_gps_time
        else:
            has_courier_gps = False
            is_gps_stale = True
            last_gps_timestamp = formatted_gps_time + " (Stale)"
    elif profile and profile.current_latitude and profile.current_longitude:
        if -90.0 <= profile.current_latitude <= 90.0 and -180.0 <= profile.current_longitude <= 180.0 and not is_offshore_sea_coordinate(profile.current_latitude, profile.current_longitude):
            courier_lat = profile.current_latitude
            courier_lon = profile.current_longitude
            # Only consider profile GPS live if courier is on active delivery task
            if assignment.status in ['in_transit', 'picked_up']:
                has_courier_gps = True
                last_gps_timestamp = timezone.localtime().strftime("%I:%M:%S %p")

    # Critical Business Rule: Calculate route and distance from courier GPS when in transit
    if (assignment.status in ['in_transit', 'picked_up']) and courier_lat and courier_lon:
        calc_origin_lat = courier_lat
        calc_origin_lon = courier_lon
    else:
        calc_origin_lat = chef_lat
        calc_origin_lon = chef_lon

    route_res = optimize_delivery_route(calc_origin_lat, calc_origin_lon, cust_lat, cust_lon)
    route_steps = route_res.route
    distance_km = route_res.distance
    is_road_distance = getattr(route_res, 'is_road', True)

    # Calculate Random Forest Regressor AI Delivery Time & ETA Predictions
    items_cnt = order.items.count() if hasattr(order, 'items') else 1
    completed_hist = DeliveryAssignment.objects.filter(status='delivered', actual_delivery_time__isnull=False)
    from ai_models.ml_engine import predict_delivery_time_rf
    pred_delivery_min, ai_eta_min, dist_km = predict_delivery_time_rf(
        calc_origin_lat, calc_origin_lon, cust_lat, cust_lon,
        items_count=items_cnt, historical_assignments=completed_hist,
        road_distance_km=distance_km
    )

    duration_min = getattr(route_res, 'duration_min', None)
    if duration_min is not None and duration_min > 0:
        travel_mins = duration_min
    else:
        travel_mins = max(1.0, round((dist_km / 25.0) * 60.0, 1))

    travel_mins_int = int(round(travel_mins))
    if dist_km <= 0.4 or travel_mins_int <= 1:
        travel_eta_display = "Estimated Arrival: < 2 minutes"
    else:
        travel_eta_display = f"Estimated Arrival: {travel_mins_int} minutes"

    # Calculate AI Delivery Status Condition Prediction
    if dist_km <= 0.5:
        ai_status_pred = "Near Destination 🎯"
    elif pred_delivery_min <= (assignment.predicted_delivery_time or 30.0) + 5.0:
        ai_status_pred = "On Time ⏱️"
    else:
        ai_status_pred = "Slightly Delayed ⚠️"

    context = {
        'assignment': assignment,
        'order': order,
        'profile': profile,
        'chef_lat': chef_lat,
        'chef_lon': chef_lon,
        'cust_lat': cust_lat,
        'cust_lon': cust_lon,
        'courier_lat': courier_lat,
        'courier_lon': courier_lon,
        'has_courier_gps': has_courier_gps,
        'is_gps_stale': is_gps_stale,
        'is_road_distance': is_road_distance,
        'last_gps_timestamp': last_gps_timestamp,
        'route_steps': route_steps,
        'distance_km': dist_km,
        'travel_eta_display': travel_eta_display,
        'travel_mins': travel_mins_int,
        'pred_delivery_min': pred_delivery_min,
        'ai_eta_min': ai_eta_min,
        'ai_status_pred': ai_status_pred,
    }
    return render(request, 'delivery/track.html', context)



@login_required
@role_required('delivery_boy', 'admin')
def pickup_order(request, assignment_id):
    """Courier marks food as picked up from kitchen."""
    if request.method != 'POST':
        return redirect('delivery_boy_dashboard')

    assignment = get_assignment_by_id_or_order_id(assignment_id)
    if not assignment:
        messages.error(request, "Delivery assignment not found.")
        return redirect('delivery_boy_dashboard')

    if request.user.role not in ['delivery_boy', 'staff', 'admin']:
        messages.error(request, "Access Denied: You are not authorized.")
        return redirect('delivery_boy_dashboard')

    if request.user.role == 'delivery_boy' and assignment.delivery_boy.user != request.user:
        messages.error(request, "Access Denied: You cannot pick up an order assigned to another courier.")
        return redirect('delivery_boy_dashboard')

    profile = assignment.delivery_boy
    order = assignment.order

    if order.status in ['cancelled', 'delivered']:
        messages.error(request, f"Order #{order.order_id} cannot be picked up (current status: {order.get_status_display()}).")
        return redirect('delivery_boy_dashboard')

    if assignment.status in ['picked_up', 'in_transit'] or order.status in ['picked_up', 'in_transit']:
        messages.warning(request, f"Order #{order.order_id} has already been marked as picked up.")
        return redirect('delivery_boy_dashboard')

    if order.status not in ['assigned', 'ready_pickup'] and assignment.status != 'assigned':
        messages.error(request, f"Order #{order.order_id} is not ready for pickup (current status: {order.get_status_display()}).")
        return redirect('delivery_boy_dashboard')

    with transaction.atomic():
        now = timezone.now()
        assignment.status = 'picked_up'
        assignment.picked_up_at = now
        assignment.save(update_fields=['status', 'picked_up_at'])

        order.status = 'picked_up'
        order.picked_up_at = now
        order.save(update_fields=['status', 'picked_up_at', 'updated_at'])

        # Notify customer
        Notification.objects.create(
            user=order.user,
            order=order,
            title="Food Picked Up",
            message=f"Your order #{order.order_id} has been picked up by {profile.courier_name} and will be out for delivery soon.",
            notification_type='general'
        )

    messages.success(request, f"Food for Order #{order.order_id} picked up successfully! Ready to start delivery.")
    return redirect('delivery_boy_dashboard')


@login_required
@role_required('delivery_boy', 'admin')
def start_delivery(request, assignment_id):
    """Courier starts delivery (Status -> in_transit / Out for Delivery)."""
    if request.method != 'POST':
        return redirect('delivery_boy_dashboard')

    assignment = get_assignment_by_id_or_order_id(assignment_id)
    if not assignment:
        messages.error(request, "Delivery assignment not found.")
        return redirect('delivery_boy_dashboard')

    if request.user.role not in ['delivery_boy', 'staff', 'admin']:
        messages.error(request, "Access Denied: You are not authorized.")
        return redirect('delivery_boy_dashboard')

    if request.user.role == 'delivery_boy' and assignment.delivery_boy.user != request.user:
        messages.error(request, "Access Denied: You cannot start delivery for an order assigned to another courier.")
        return redirect('delivery_boy_dashboard')

    profile = assignment.delivery_boy
    order = assignment.order

    if order.status in ['cancelled', 'delivered']:
        messages.error(request, f"Order #{order.order_id} cannot be delivered (current status: {order.get_status_display()}).")
        return redirect('delivery_boy_dashboard')

    if assignment.status == 'in_transit' or order.status == 'in_transit':
        messages.info(request, f"Order #{order.order_id} is already Out for Delivery.")
        return redirect('delivery_boy_track', assignment_id=assignment.id)



    with transaction.atomic():
        now = timezone.now()
        if not assignment.picked_up_at:
            assignment.picked_up_at = now
        assignment.status = 'in_transit'
        assignment.out_for_delivery_at = now
        assignment.save(update_fields=['status', 'picked_up_at', 'out_for_delivery_at'])

        order.status = 'in_transit'
        if not order.picked_up_at:
            order.picked_up_at = now
        order.save(update_fields=['status', 'picked_up_at', 'updated_at'])

        profile.status = 'on_delivery'
        profile.save(update_fields=['status'])

        # Notify customer
        Notification.objects.create(
            user=order.user,
            order=order,
            title="Out for Delivery",
            message=f"Your order #{order.order_id} is now out for delivery! Track live courier GPS.",
            notification_type='out_for_delivery'
        )

    messages.success(request, f"Delivery started for Order #{order.order_id}! Status is now Out for Delivery.")
    return redirect('delivery_boy_track', assignment_id=assignment.id)


@login_required
@role_required('delivery_boy', 'admin')
def complete_delivery(request, assignment_id):
    """Courier completes delivery (Status -> delivered)."""
    if request.method != 'POST':
        return redirect('delivery_boy_dashboard')

    assignment = get_assignment_by_id_or_order_id(assignment_id)
    if not assignment:
        messages.error(request, "Delivery assignment not found.")
        return redirect('delivery_boy_dashboard')

    if request.user.role not in ['delivery_boy', 'staff', 'admin']:
        messages.error(request, "Access Denied: You are not authorized.")
        return redirect('delivery_boy_dashboard')

    if request.user.role == 'delivery_boy' and assignment.delivery_boy.user != request.user:
        messages.error(request, "Access Denied: You cannot complete a delivery assigned to another courier.")
        return redirect('delivery_boy_dashboard')

    profile = assignment.delivery_boy
    order = assignment.order

    if order.status == 'delivered':
        messages.info(request, f"Order #{order.order_id} is already marked as Delivered.")
        return redirect('delivery_boy_dashboard')

    if order.status in ['pending', 'preparing', 'ready_pickup', 'assigned'] and assignment.status not in ['in_transit', 'picked_up']:
        messages.error(request, f"Cannot mark Order #{order.order_id} as delivered before food has been picked up and dispatched.")
        return redirect('delivery_boy_dashboard')

    with transaction.atomic():
        now = timezone.now()
        assignment.status = 'delivered'
        assignment.delivered_at = now
        assignment.is_active = False
        if assignment.assigned_at:
            duration_delta = now - assignment.assigned_at
            assignment.actual_delivery_time = max(1.0, round(duration_delta.total_seconds() / 60.0, 1))
        assignment.save(update_fields=['status', 'delivered_at', 'is_active', 'actual_delivery_time'])

        order.status = 'delivered'
        order.delivered_at = now
        order.save(update_fields=['status', 'delivered_at', 'updated_at'])

        # Handle Cash on Delivery collection upon delivery completion if requested
        payment = getattr(order, 'payment', None) or Payment.objects.filter(order=order).first()
        collect_cash_param = request.POST.get('collect_cash') or request.POST.get('cash_collected')
        if collect_cash_param == '1' and payment and payment.payment_method == 'cod' and payment.status not in ['cash_collected', 'success']:
            payment.status = 'cash_collected'
            payment.cash_collected_at = now
            payment.cash_collected_by = request.user
            payment.save(update_fields=['status', 'cash_collected_at', 'cash_collected_by'])
            for staff in User.objects.filter(role__in=['staff', 'admin']):
                Notification.objects.create(
                    user=staff,
                    order=order,
                    title=f"Cash Collected for Order #{order.order_id}",
                    message=f"{profile.courier_name} collected cash of ₹{payment.amount} upon delivering Order #{order.order_id}.",
                    notification_type='staff_delivery_alert'
                )

        # Check if courier has other active tasks
        other_active = DeliveryAssignment.objects.filter(
            delivery_boy=profile,
            status__in=['assigned', 'picked_up', 'in_transit'],
            is_active=True
        ).exclude(id=assignment.id).exists()
        if not other_active and profile.status != 'offline':
            profile.status = 'available'
            profile.save(update_fields=['status'])

        # Notify Staff
        for staff in User.objects.filter(role='staff'):
            Notification.objects.create(
                user=staff,
                order=order,
                title=f"Order #{order.order_id} Delivered",
                message=f"Order #{order.order_id} has been successfully delivered by {profile.user.username.title()}.",
                notification_type='staff_delivery_alert'
            )

        # Notify Customer
        Notification.objects.create(
            user=order.user,
            order=order,
            title="Food Delivered!",
            message=f"Your order #{order.order_id} has been delivered. Thank you for choosing Veetile Ruchi!",
            notification_type='order_delivered'
        )

    messages.success(request, f"Order #{order.order_id} marked as Delivered successfully! Delivery completed.")
    next_url = request.POST.get('next')
    if next_url:
        return redirect(next_url)
    referer = request.META.get('HTTP_REFERER', '')
    if 'track' in referer:
        return redirect('delivery_boy_track', assignment_id=assignment.id)
    return redirect('delivery_boy_dashboard')


@login_required
@role_required('delivery_boy', 'staff', 'admin')
def courier_collect_cash(request, assignment_id):
    """
    Courier boy marks payment status as 'Cash Collected' for Cash on Delivery (COD) orders.
    Enforces security:
    - Delivery boy can only collect cash for their own assigned delivery (staff/admin can manage any).
    - Can ONLY be performed on Cash on Delivery (COD) orders. Online orders cannot be marked as cash collected.
    - Idempotent and prevents invalid transitions.
    """
    if request.method != 'POST':
        return redirect('delivery_boy_dashboard')

    assignment = get_assignment_by_id_or_order_id(assignment_id)
    if not assignment:
        messages.error(request, "Delivery assignment not found.")
        return redirect('delivery_boy_dashboard')

    # Security: Delivery boy can only collect cash for their own assignment
    if request.user.role == 'delivery_boy' and assignment.delivery_boy.user != request.user:
        messages.error(request, "Access Denied: You cannot update payment for an order assigned to another courier.")
        return redirect('delivery_boy_dashboard')

    order = assignment.order
    payment = getattr(order, 'payment', None) or Payment.objects.filter(order=order).first()

    if not payment:
        messages.error(request, f"No payment record found for Order #{order.order_id}.")
        return redirect('delivery_boy_dashboard')

    # Prevent incorrect payment updates: Online payments cannot be collected as cash
    if payment.payment_method != 'cod':
        messages.error(request, f"Order #{order.order_id} was paid online ({payment.get_payment_method_display()}). Cash collection is not applicable.")
        return redirect('delivery_boy_dashboard')

    # For COD orders, keep COD confirmation disabled until food is handed over to the customer
    if order.status != 'delivered' and assignment.status != 'delivered':
        messages.error(
            request,
            f"Cash collection for Order #{order.order_id} cannot be confirmed before reaching the customer and handing over the food."
        )
        next_url = request.POST.get('next')
        if next_url:
            return redirect(next_url)
        referer = request.META.get('HTTP_REFERER', '')
        if 'track' in referer:
            return redirect('delivery_boy_track', assignment_id=assignment.id)
        return redirect('delivery_boy_dashboard')

    # If already marked as cash collected or verified
    if payment.status in ['cash_collected', 'success']:
        messages.info(request, f"Payment for Order #{order.order_id} is already marked as {payment.display_status}.")
        next_url = request.POST.get('next')
        if next_url:
            return redirect(next_url)
        return redirect('delivery_boy_dashboard')

    with transaction.atomic():
        now = timezone.now()
        payment.status = 'cash_collected'
        payment.cash_collected_at = now
        payment.cash_collected_by = request.user
        payment.save(update_fields=['status', 'cash_collected_at', 'cash_collected_by'])

        courier_name = assignment.delivery_boy.courier_name
        # Notify staff console that cash has been received by courier boy
        for staff in User.objects.filter(role__in=['staff', 'admin']):
            Notification.objects.create(
                user=staff,
                order=order,
                title=f"Cash Collected Successfully for Order #{order.order_id}",
                message=f"Cash Collected Successfully: {courier_name} has collected cash of ₹{payment.amount} for Order #{order.order_id}.",
                notification_type='staff_delivery_alert'
            )

        # Notify customer
        Notification.objects.create(
            user=order.user,
            order=order,
            title="Cash Payment Received",
            message=f"{courier_name} has received your cash payment of ₹{payment.amount} for Order #{order.order_id}. Thank you!",
            notification_type='general'
        )

        # After delivery completion and cash confirmation, ensure courier availability status updates to Available if no other active delivery
        profile = assignment.delivery_boy
        other_active = DeliveryAssignment.objects.filter(
            delivery_boy=profile,
            status__in=['assigned', 'picked_up', 'in_transit'],
            is_active=True
        ).exclude(id=assignment.id).exists()
        if not other_active and profile.status != 'offline':
            profile.status = 'available'
            profile.save(update_fields=['status'])

    messages.success(request, f"Payment for Order #{order.order_id} successfully marked as Cash Collected (₹{payment.amount}).")

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        return JsonResponse({
            'status': 'success',
            'message': f"Payment for Order #{order.order_id} marked as Cash Collected.",
            'amount': float(payment.amount),
            'order_id': order.order_id
        })

    next_url = request.POST.get('next')
    if next_url:
        return redirect(next_url)
    referer = request.META.get('HTTP_REFERER', '')
    if 'track' in referer:
        return redirect('delivery_boy_track', assignment_id=assignment.id)
    return redirect('delivery_boy_dashboard')


@login_required
@role_required('delivery_boy', 'admin')
def delivery_boy_update_status(request, assignment_id):
    """Unified handler for courier status transitions (picked_up, in_transit, delivered, cash_collected)."""
    if request.method != 'POST':
        return redirect('delivery_boy_dashboard')

    new_status = request.POST.get('status')
    if new_status == 'picked_up':
        return pickup_order(request, assignment_id)
    elif new_status == 'in_transit':
        return start_delivery(request, assignment_id)
    elif new_status == 'delivered':
        return complete_delivery(request, assignment_id)
    elif new_status == 'cash_collected':
        return courier_collect_cash(request, assignment_id)

    messages.error(request, "Invalid delivery status update requested.")
    return redirect('delivery_boy_dashboard')



@login_required
def update_profile_gps(request):
    """AJAX endpoint to automatically update logged-in courier's current GPS location."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)
        
    if request.user.role != 'delivery_boy':
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
        
    try:
        import json
        data = json.loads(request.body.decode('utf-8'))
        lat = data.get('latitude')
        lon = data.get('longitude')
    except (ValueError, TypeError, json.JSONDecodeError):
        lat = request.POST.get('latitude')
        lon = request.POST.get('longitude')

    from orders.utils import validate_coordinates
    c_lat, c_lon = validate_coordinates(lat, lon)
    if c_lat is None or c_lon is None:
        return JsonResponse({'status': 'error', 'message': 'Invalid GPS coordinates provided'}, status=400)
        
    profile = getattr(request.user, 'delivery_boy_profile', None)
    if not profile:
        return JsonResponse({'status': 'error', 'message': 'Profile not found'}, status=404)
        
    profile.current_latitude = c_lat
    profile.current_longitude = c_lon
    profile.save(update_fields=['current_latitude', 'current_longitude'])
    
    return JsonResponse({
        'status': 'success',
        'latitude': c_lat,
        'longitude': c_lon,
        'timestamp': timezone.localtime().strftime("%H:%M:%S")
    })


@login_required
def update_courier_gps(request, assignment_id):
    """AJAX endpoint for courier browser to transmit live device GPS location coordinates."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

    if request.user.role != 'delivery_boy':
        return JsonResponse({'status': 'error', 'message': 'Unauthorized: Only delivery couriers can transmit GPS'}, status=403)

    assignment = get_assignment_by_id_or_order_id(assignment_id)
    if not assignment:
        return JsonResponse({'status': 'error', 'message': 'Assignment not found'}, status=404)

    # Security Rule: Verify assigned courier vehicle/user
    if assignment.delivery_boy.user != request.user:
        return JsonResponse({'status': 'error', 'message': 'Access denied: You are not assigned to this order'}, status=403)

    # Stop tracking if order is already completed or cancelled
    if assignment.status in ['delivered', 'cancelled'] or assignment.order.status in ['delivered', 'cancelled']:
        return JsonResponse({
            'status': 'stopped',
            'message': 'Tracking is concluded because this order is delivered or cancelled.'
        }, status=200)

    try:
        import json
        data = json.loads(request.body.decode('utf-8'))
        lat = data.get('latitude')
        lon = data.get('longitude')
        accuracy = data.get('accuracy')
        if accuracy is not None:
            accuracy = float(accuracy)
    except (ValueError, TypeError, json.JSONDecodeError):
        lat = request.POST.get('latitude')
        lon = request.POST.get('longitude')
        accuracy = request.POST.get('accuracy')
        if accuracy is not None:
            try:
                accuracy = float(accuracy)
            except (ValueError, TypeError):
                accuracy = None

    from orders.utils import validate_coordinates
    c_lat, c_lon = validate_coordinates(lat, lon)
    if c_lat is None or c_lon is None:
        return JsonResponse({'status': 'error', 'message': 'Coordinates out of valid geographical bounds'}, status=400)

    # Save GPS Breadcrumb
    GPSLocationTracking.objects.create(
        delivery_assignment=assignment,
        latitude=c_lat,
        longitude=c_lon
    )

    # Update Courier Profile Current Coordinates in DB
    profile = assignment.delivery_boy
    profile.current_latitude = c_lat
    profile.current_longitude = c_lon
    if assignment.status == 'in_transit':
        profile.status = 'on_delivery'
    profile.save(update_fields=['current_latitude', 'current_longitude', 'status'])

    now_str = timezone.localtime().strftime("%I:%M:%S %p")

    # Calculate real-time route, distance & Travel ETA from courier's latest GPS to customer
    from orders.utils import get_active_delivery_setting, sanitize_customer_coordinates
    from ai_models.ml_engine import optimize_delivery_route, predict_delivery_time_rf

    delivery_setting = get_active_delivery_setting()
    branch = getattr(assignment.order, 'branch', None)
    hub_lat = branch.latitude if branch else delivery_setting.latitude
    hub_lon = branch.longitude if branch else delivery_setting.longitude
    cust_lat, cust_lon = sanitize_customer_coordinates(
        assignment.order.latitude, assignment.order.longitude,
        fallback_lat=hub_lat, fallback_lon=hub_lon
    )

    route_res = optimize_delivery_route(c_lat, c_lon, cust_lat, cust_lon)
    route_steps = route_res.route
    distance_km = route_res.distance
    is_road = getattr(route_res, 'is_road', True)
    duration_min = getattr(route_res, 'duration_min', None)

    if duration_min is not None and duration_min > 0:
        travel_mins = duration_min
    else:
        travel_mins = max(1.0, round((distance_km / 25.0) * 60.0, 1))

    travel_mins_int = int(round(travel_mins))
    if distance_km <= 0.4 or travel_mins_int <= 1:
        travel_eta_display = "Estimated Arrival: < 2 minutes"
    else:
        travel_eta_display = f"Estimated Arrival: {travel_mins_int} minutes"

    # AI Delivery Time & Status
    items_cnt = assignment.order.items.count() if hasattr(assignment.order, 'items') else 1
    pred_delivery_min, ai_eta_min, dist_km = predict_delivery_time_rf(
        c_lat, c_lon, cust_lat, cust_lon,
        items_count=items_cnt, road_distance_km=distance_km
    )
    if dist_km <= 0.5:
        ai_status_pred = "Near Destination 🎯"
    elif pred_delivery_min <= (assignment.predicted_delivery_time or 30.0) + 5.0:
        ai_status_pred = "On Time ⏱️"
    else:
        ai_status_pred = "Slightly Delayed ⚠️"

    return JsonResponse({
        'status': 'success',
        'latitude': c_lat,
        'longitude': c_lon,
        'accuracy': accuracy,
        'timestamp': now_str,
        'distance_km': dist_km,
        'is_road_distance': is_road,
        'travel_eta_display': travel_eta_display,
        'travel_mins': travel_mins_int,
        'ai_eta_min': ai_eta_min,
        'ai_status_pred': ai_status_pred,
        'route_steps': route_steps,
    })

@login_required
def get_live_gps_location(request, order_id):
    """API endpoint returning live courier GPS location for customer tracking map."""
    order = get_object_or_404(Order, order_id=order_id)
    
    # Security Rule: Only authorized users (customer owner, staff/admin, assigned courier) can access order location data
    is_owner = (request.user == order.user)
    is_staff = (request.user.role in ['staff', 'admin'])
    is_assigned_courier = (hasattr(order, 'delivery_assignment') and order.delivery_assignment.delivery_boy.user == request.user)
    
    if not (is_owner or is_staff or is_assigned_courier):
        return JsonResponse({'status': 'error', 'message': 'Access denied'}, status=403)

    assignment = getattr(order, 'delivery_assignment', None)

    if not assignment:
        return JsonResponse({
            'status': order.status,
            'gps_active': False,
            'has_courier_gps': False,
            'message': 'No delivery assignment associated with this order'
        })

    # Active GPS tracking allowed ONLY while assigned / in_transit / picked_up
    gps_active = (order.status in ['assigned', 'picked_up', 'in_transit'])

    latest_crumb = GPSLocationTracking.objects.filter(delivery_assignment=assignment).order_by('-timestamp').first()
    courier_lat = None
    courier_lon = None
    has_courier_gps = False
    is_stale = False
    last_update_str = None

    if latest_crumb:
        from orders.utils import validate_coordinates
        c_lat, c_lon = validate_coordinates(latest_crumb.latitude, latest_crumb.longitude)
        if c_lat is not None and c_lon is not None:
            courier_lat = c_lat
            courier_lon = c_lon
            from orders.utils import to_kolkata_datetime
            local_crumb_dt = to_kolkata_datetime(latest_crumb.timestamp)
            formatted_crumb_time = local_crumb_dt.strftime("%I:%M:%S %p")
            age_sec = (timezone.now() - latest_crumb.timestamp).total_seconds()
            if age_sec <= 300: # 5 minutes threshold for live freshness
                has_courier_gps = True
                is_stale = False
                last_update_str = formatted_crumb_time
            else:
                has_courier_gps = False
                is_stale = True
                last_update_str = formatted_crumb_time + " (Signal Stale)"
    elif assignment.delivery_boy.current_latitude and assignment.delivery_boy.current_longitude:
        from orders.utils import validate_coordinates, is_offshore_sea_coordinate
        c_lat, c_lon = validate_coordinates(assignment.delivery_boy.current_latitude, assignment.delivery_boy.current_longitude)
        if c_lat is not None and c_lon is not None and not is_offshore_sea_coordinate(c_lat, c_lon):
            courier_lat = c_lat
            courier_lon = c_lon
            if assignment.status in ['in_transit', 'picked_up']:
                has_courier_gps = True
                is_stale = False
                last_update_str = timezone.localtime().strftime("%I:%M:%S %p")

    # Hotel Base vs Courier GPS separation (Critical Business Rule)
    from orders.utils import get_active_delivery_setting
    delivery_setting = get_active_delivery_setting()
    branch = getattr(order, 'branch', None)
    chef_lat = branch.latitude if branch else delivery_setting.latitude
    chef_lon = branch.longitude if branch else delivery_setting.longitude

    if (order.status in ['in_transit', 'picked_up']) and courier_lat and courier_lon:
        calc_origin_lat = courier_lat
        calc_origin_lon = courier_lon
    else:
        calc_origin_lat = chef_lat
        calc_origin_lon = chef_lon

    from ai_models.ml_engine import predict_delivery_time_rf, optimize_delivery_route
    route_res = optimize_delivery_route(calc_origin_lat, calc_origin_lon, order.latitude, order.longitude)
    route_steps = route_res.route
    dist_km = route_res.distance
    is_road_dist = getattr(route_res, 'is_road', True)

    items_cnt = order.items.count() if hasattr(order, 'items') else 1
    completed_hist = DeliveryAssignment.objects.filter(status='delivered', actual_delivery_time__isnull=False)
    pred_delivery_min, ai_eta_min, dist_km = predict_delivery_time_rf(
        calc_origin_lat, calc_origin_lon, order.latitude, order.longitude,
        items_count=items_cnt, historical_assignments=completed_hist,
        road_distance_km=dist_km
    )

    payment = getattr(order, 'payment', None) or Payment.objects.filter(order=order).first()
    payment_method = payment.payment_method if payment else 'cod'
    payment_status = payment.status if payment else 'pending'
    payment_display = payment.display_status if payment else ('Paid Online' if payment_method == 'upi' else 'Cash on Delivery')

    return JsonResponse({
        'order_id': order.order_id,
        'status': order.status,
        'gps_active': gps_active and has_courier_gps,
        'has_courier_gps': has_courier_gps,
        'is_stale': is_stale,
        'latitude': courier_lat,
        'longitude': courier_lon,
        'distance_km': dist_km,
        'is_road_distance': is_road_dist,
        'route_steps': route_steps,
        'pred_delivery_min': pred_delivery_min,
        'ai_eta_min': ai_eta_min,
        'delivery_boy': {
            'name': assignment.delivery_boy.user.username.title(),
            'phone': assignment.delivery_boy.user.phone or '',
            'vehicle_number': assignment.delivery_boy.vehicle_number or '',
        },
        'vehicle_number': assignment.delivery_boy.vehicle_number,
        'driver_name': assignment.delivery_boy.user.username.title(),
        'driver_phone': assignment.delivery_boy.user.phone or '',
        'updated_at': last_update_str or timezone.localtime().strftime("%I:%M:%S %p"),
        'payment_method': payment_method,
        'payment_status': payment_status,
        'payment_display_status': payment_display,
    })


@login_required
def submit_delivery_feedback(request, order_id):
    """Customer delivery feedback handler."""
    order = get_object_or_404(Order, order_id=order_id)
    
    if request.user != order.user:
        messages.error(request, "You can only submit delivery feedback for your own orders.")
        return redirect('order_history')

    if order.status != 'delivered':
        messages.error(request, "Delivery feedback can only be submitted after the order status is Delivered.")
        return redirect('order_history')

    if not hasattr(order, 'delivery_assignment') or not order.delivery_assignment or not order.delivery_assignment.delivery_boy:
        messages.error(request, "No delivery courier record associated with this order.")
        return redirect('order_history')

    assignment = order.delivery_assignment
    delivery_boy = assignment.delivery_boy

    if request.method == 'POST':
        try:
            rating = int(request.POST.get('rating', 5))
            rating = max(1, min(5, rating))
        except (ValueError, TypeError):
            rating = 5

        try:
            timeliness_rating = int(request.POST.get('timeliness_rating', rating))
            timeliness_rating = max(1, min(5, timeliness_rating))
        except (ValueError, TypeError):
            timeliness_rating = rating

        try:
            behavior_rating = int(request.POST.get('behavior_rating', rating))
            behavior_rating = max(1, min(5, behavior_rating))
        except (ValueError, TypeError):
            behavior_rating = rating

        try:
            food_handling_rating = int(request.POST.get('food_handling_rating', rating))
            food_handling_rating = max(1, min(5, food_handling_rating))
        except (ValueError, TypeError):
            food_handling_rating = rating

        comment = request.POST.get('comment', '').strip()[:1000]

        with transaction.atomic():
            feedback, created = DeliveryFeedback.objects.update_or_create(
                order=order,
                defaults={
                    'delivery_assignment': assignment,
                    'delivery_boy': delivery_boy,
                    'customer': request.user,
                    'rating': rating,
                    'timeliness_rating': timeliness_rating,
                    'behavior_rating': behavior_rating,
                    'food_handling_rating': food_handling_rating,
                    'comment': comment,
                }
            )

            # Recompute delivery boy average rating from genuine unmoderated reviews
            avg_rating = DeliveryFeedback.objects.filter(
                delivery_boy=delivery_boy,
                is_hidden_by_admin=False
            ).aggregate(models.Avg('rating'))['rating__avg']
            if avg_rating is not None:
                delivery_boy.rating = round(float(avg_rating), 1)
                delivery_boy.save(update_fields=['rating'])

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
            return JsonResponse({
                'status': 'success',
                'message': f"Thank you! Your feedback for {delivery_boy.courier_name} has been submitted successfully.",
                'rating': rating,
                'timeliness_rating': timeliness_rating,
                'behavior_rating': behavior_rating,
                'food_handling_rating': food_handling_rating,
                'comment': comment
            })

        messages.success(request, f"Thank you! Your feedback for {delivery_boy.courier_name} has been submitted successfully.")
        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'order_history'
        return redirect(next_url)

    # GET request - return existing saved feedback if any
    existing = DeliveryFeedback.objects.filter(order=order).first()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        if existing:
            return JsonResponse({
                'status': 'success',
                'has_feedback': True,
                'rating': existing.rating,
                'timeliness_rating': existing.timeliness_rating,
                'behavior_rating': existing.behavior_rating,
                'food_handling_rating': existing.food_handling_rating,
                'comment': existing.comment,
                'created_at': existing.created_at.strftime("%b %d, %Y • %I:%M %p")
            })
        else:
            return JsonResponse({
                'status': 'success',
                'has_feedback': False,
                'courier_name': delivery_boy.courier_name,
                'vehicle_number': delivery_boy.vehicle_number
            })

    return redirect('order_history')


@login_required
@role_required('delivery_boy')
def dismiss_courier_notification(request, notif_id):
    """Marks a courier notification as read/dismissed without altering order status."""
    notif = get_object_or_404(Notification, id=notif_id, user=request.user)
    notif.is_read = True
    notif.save(update_fields=['is_read'])
    # Mark any redundant notifications for the same order as read to avoid repeated alerts
    if notif.order:
        Notification.objects.filter(user=request.user, order=notif.order, is_read=False).update(is_read=True)
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        return JsonResponse({'status': 'success', 'message': 'Notification dismissed'})
    messages.info(request, "Notification dismissed.")
    return redirect('delivery_boy_dashboard')


@login_required
@role_required('delivery_boy')
def dismiss_delivery_notifications(request, order_id):
    """Marks all notifications for this delivery/order as read for the logged-in courier."""
    updated = Notification.objects.filter(
        user=request.user,
        order__order_id=order_id,
        is_read=False
    ).update(is_read=True)
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        return JsonResponse({'status': 'success', 'updated': updated})
    return redirect('delivery_boy_dashboard')


@login_required
def get_courier_notifications(request):
    """API endpoint for real-time notification polling and entrance popup modal in Courier Portal."""
    if request.user.role != 'delivery_boy':
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    # Strictly load notifications for the authenticated courier only
    notifications = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).select_related('order__branch', 'order__user').prefetch_related('order__items__food_item').order_by('-created_at')[:10]
    
    data = []
    for notif in notifications:
        assignment_id = None
        food_id = "FOOD0000"
        food_name = "Food Item"
        quantity = 1
        lat = 0.0
        lon = 0.0
        delivery_address = "GPS Destination"
        order_date = ""
        status_display = "Assigned / Pending Delivery"
        pickup_location = "Central Kitchen Hub (Kanjirappally)"
        
        if notif.order:
            lat = notif.order.latitude
            lon = notif.order.longitude
            delivery_address = notif.order.formatted_delivery_address or notif.order.delivery_address or f"Lat {lat}, Lon {lon}"
            order_dt = to_kolkata_datetime(notif.order.created_at)
            order_date = order_dt.strftime("%b %d, %Y • %I:%M %p") if order_dt else ""
            if notif.order.branch:
                pickup_location = f"{notif.order.branch.name} ({notif.order.branch.address})"
            
            items_list = list(notif.order.items.select_related('food_item'))
            items_summary = ", ".join(f"{it.food_item.name} x{it.quantity}" for it in items_list) if items_list else "Food Items"
            first_item = items_list[0] if items_list else None
            if first_item:
                food_id = f"FOOD{first_item.food_item.id:04d}"
                food_name = first_item.food_item.name
                quantity = first_item.quantity

            customer_name = notif.order.customer_name
            customer_phone = notif.order.customer_phone
                
            if hasattr(notif.order, 'delivery_assignment'):
                assignment_id = notif.order.delivery_assignment.id
                st = notif.order.delivery_assignment.status
                if st == 'assigned':
                    status_display = "Assigned — Awaiting Pickup"
                elif st == 'picked_up':
                    status_display = "Food Picked Up"
                elif st == 'in_transit':
                    status_display = "Out for Delivery"
                elif st == 'delivered':
                    status_display = "Delivered"
                else:
                    status_display = notif.order.delivery_assignment.get_status_display()
        else:
            customer_name = "Customer"
            customer_phone = ""
            items_summary = ""
                
        track_url = f"/orders/notifications/mark-read/{notif.id}/" if notif.id else '#'
        dismiss_url = f"/delivery/notifications/dismiss/{notif.id}/" if notif.id else '#'
        nav_url = f"/delivery/track/{assignment_id}/" if assignment_id else '#'
            
        notif_dt = to_kolkata_datetime(notif.created_at)
        data.append({
            'id': notif.id,
            'title': notif.title,
            'message': notif.message,
            'order_id': notif.order.order_id if notif.order else '',
            'food_id': food_id,
            'food_name': food_name,
            'quantity': quantity,
            'items_summary': items_summary,
            'customer_name': customer_name,
            'customer_phone': customer_phone,
            'latitude': lat,
            'longitude': lon,
            'delivery_address': delivery_address,
            'pickup_location': pickup_location,
            'order_date': order_date,
            'status': status_display,
            'assignment_id': assignment_id,
            'track_url': track_url,
            'dismiss_url': dismiss_url,
            'nav_url': nav_url,
            'created_at': notif_dt.strftime("%b %d, %Y • %I:%M %p") if notif_dt else "",
        })
        
    return JsonResponse({
        'status': 'success',
        'unread_count': len(data),
        'notifications': data
    })


@login_required
@role_required('staff', 'admin')
def api_list_couriers(request):
    """API endpoint returning dynamic courier fleet details from database for Staff/Admin."""
    if request.user.role not in ['staff', 'admin']:
        return JsonResponse({'status': 'error', 'message': 'Access restricted to Staff and Admin'}, status=403)
        
    couriers = DeliveryBoyProfile.objects.select_related('user').all().order_by('user__username')
    data = []
    for c in couriers:
        active_assignment = c.assignments.filter(status__in=['assigned', 'picked_up', 'in_transit']).first()
        assigned_order_id = active_assignment.order.order_id if active_assignment else None
        
        data.append({
            'id': c.id,
            'user_id': c.user.id,
            'courier_id': f"COURIER-{c.user.phone or c.id}",
            'courier_number': c.courier_number,
            'courier_name': c.courier_name,
            'username': c.courier_username,
            'name': c.courier_name,
            'phone': c.user.phone or 'Phone not provided',
            'is_active': c.user.is_active,
            'status': c.status,
            'status_display': c.get_status_display(),
            'vehicle_number': c.vehicle_number or 'N/A',
            'rating': c.rating,
            'assigned_order_id': assigned_order_id,
            'active_deliveries_count': c.assignments.filter(status__in=['assigned', 'picked_up', 'in_transit']).count()
        })
    return JsonResponse({'status': 'success', 'couriers': data, 'total_count': len(data)})


