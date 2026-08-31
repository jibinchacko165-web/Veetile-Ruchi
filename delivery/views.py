from django.db import models, transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from .models import DeliveryAssignment, GPSLocationTracking, DeliveryFeedback
from orders.models import Order, Notification
from accounts.models import User, DeliveryBoyProfile
from accounts.decorators import role_required
from ai_models.ml_engine import optimize_delivery_route

@login_required
@role_required('delivery_boy', 'admin')
def delivery_boy_dashboard(request):
    """Professional Courier Dashboard showing assigned deliveries, stats, tabs, and notifications."""
    profile, _ = DeliveryBoyProfile.objects.get_or_create(user=request.user)
    
    # Base Queryset: strictly filter by the currently logged-in courier profile ONLY
    all_assignments = DeliveryAssignment.objects.filter(
        delivery_boy=profile
    ).select_related('order', 'order__user', 'delivery_boy__user').prefetch_related('order__items__food_item').order_by('-assigned_at')
    
    # Active tab parameter
    tab = request.GET.get('tab', 'current')
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # 1. Current / Active Orders (ALL active assigned orders for logged-in courier NOT delivered or cancelled)
    current_assignments = all_assignments.exclude(
        status__in=['delivered', 'cancelled']
    ).exclude(
        order__status__in=['delivered', 'cancelled']
    )

    # 2. New / Pending Deliveries (Assigned or Picked up, waiting for transit or delivery completion)
    pending_assignments = all_assignments.filter(
        status__in=['assigned', 'picked_up']
    ).exclude(order__status__in=['in_transit', 'delivered', 'cancelled'])

    # 3. Active Out for Delivery Tasks (In transit)
    in_transit_assignments = all_assignments.filter(
        status='in_transit'
    ).exclude(order__status__in=['delivered', 'cancelled'])

    # 4. Completed Deliveries ONLY
    completed_assignments = all_assignments.filter(
        models.Q(status='delivered') | models.Q(order__status='delivered')
    )

    # 5. Today's assignments
    todays_assignments = all_assignments.filter(assigned_at__gte=today_start)

    # Determine assignments list based on tab
    if tab in ['current', 'dashboard']:
        assignments = current_assignments
    elif tab in ['new', 'pending']:
        assignments = pending_assignments
    elif tab in ['active', 'in_transit']:
        assignments = in_transit_assignments
    elif tab in ['completed', 'delivered']:
        assignments = completed_assignments
    elif tab == 'today':
        assignments = todays_assignments
    elif tab in ['total', 'all']:
        assignments = all_assignments
    else:
        assignments = current_assignments

    # Food ID / Order ID search filter
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

    feedbacks = DeliveryFeedback.objects.filter(delivery_boy=profile).select_related('order', 'customer').order_by('-created_at')
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:20]
    
    total_assigned_count = all_assignments.count()
    current_count = current_assignments.count()
    pending_count = pending_assignments.count()
    active_count = in_transit_assignments.count()
    completed_count = completed_assignments.count()
    todays_count = todays_assignments.count()
    unread_notifications = Notification.objects.filter(user=request.user, is_read=False).select_related('order').order_by('-created_at')
    unread_notif_count = unread_notifications.count()
    
    avg_rating = profile.rating or 5.0

    context = {
        'assignments': assignments,
        'all_assignments': all_assignments,
        'feedbacks': feedbacks,
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
            
    # Security Rule: Courier can track ONLY their own assigned orders
    if request.user.role == 'delivery_boy' and assignment.delivery_boy.user != request.user:
        messages.error(request, "Access Denied: This order is not assigned to you.")
        return redirect('delivery_boy_dashboard')

    if request.user.role != 'delivery_boy' and request.user.role != 'staff' and request.user != assignment.order.user:
        messages.error(request, "Access restricted.")
        return redirect('dashboard_redirect')

    order = assignment.order
    profile = assignment.delivery_boy
        
    chef_lat, chef_lon = 9.462534, 76.72185
    cust_lat = order.latitude
    cust_lon = order.longitude
    
    route_steps, distance_km = optimize_delivery_route(chef_lat, chef_lon, cust_lat, cust_lon)
    
    # Get latest courier GPS location if available
    latest_gps = GPSLocationTracking.objects.filter(delivery_assignment=assignment).order_by('-timestamp').first()
    courier_lat = latest_gps.latitude if latest_gps else profile.current_latitude
    courier_lon = latest_gps.longitude if latest_gps else profile.current_longitude

    # Calculate Random Forest Regressor AI Delivery Time & ETA Predictions
    items_cnt = order.items.count() if hasattr(order, 'items') else 1
    completed_hist = DeliveryAssignment.objects.filter(status='delivered', actual_delivery_time__isnull=False)
    from ai_models.ml_engine import predict_delivery_time_rf
    pred_delivery_min, ai_eta_min, dist_km = predict_delivery_time_rf(
        courier_lat, courier_lon, cust_lat, cust_lon,
        items_count=items_cnt, historical_assignments=completed_hist
    )

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
        'route_steps': route_steps,
        'distance_km': dist_km,
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

    profile = getattr(request.user, 'delivery_boy_profile', None)
    if not profile or assignment.delivery_boy != profile:
        messages.error(request, "Access Denied: You are not assigned to this order.")
        return redirect('delivery_boy_dashboard')

    order = assignment.order
    if order.status in ['cancelled', 'delivered']:
        messages.error(request, f"Order #{order.order_id} cannot be picked up (current status: {order.get_status_display()}).")
        return redirect('delivery_boy_dashboard')

    with transaction.atomic():
        assignment.status = 'picked_up'
        assignment.picked_up_at = timezone.now()
        assignment.save(update_fields=['status', 'picked_up_at'])

        order.status = 'picked_up'
        order.save(update_fields=['status'])

        # Notify customer
        Notification.objects.create(
            user=order.user,
            order=order,
            title="Food Picked Up",
            message=f"Your order #{order.order_id} has been picked up by courier {profile.user.username.title()} and will be out for delivery soon.",
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

    profile = getattr(request.user, 'delivery_boy_profile', None)
    if not profile or assignment.delivery_boy != profile:
        messages.error(request, "Access Denied: You are not assigned to this order.")
        return redirect('delivery_boy_dashboard')

    order = assignment.order
    if order.status in ['cancelled', 'delivered']:
        messages.error(request, f"Order #{order.order_id} cannot be delivered (current status: {order.get_status_display()}).")
        return redirect('delivery_boy_dashboard')

    with transaction.atomic():
        now = timezone.now()
        if not assignment.picked_up_at:
            assignment.picked_up_at = now
        assignment.status = 'in_transit'
        assignment.out_for_delivery_at = now
        assignment.save(update_fields=['status', 'picked_up_at', 'out_for_delivery_at'])

        order.status = 'in_transit'
        order.save(update_fields=['status'])

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

    profile = getattr(request.user, 'delivery_boy_profile', None)
    if not profile or assignment.delivery_boy != profile:
        messages.error(request, "Access Denied: You are not assigned to this order.")
        return redirect('delivery_boy_dashboard')

    order = assignment.order
    if order.status == 'delivered':
        messages.info(request, f"Order #{order.order_id} is already marked as Delivered.")
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
        order.save(update_fields=['status'])

        # Check if courier has other active tasks
        other_active = DeliveryAssignment.objects.filter(
            delivery_boy=profile,
            status__in=['assigned', 'picked_up', 'in_transit']
        ).exclude(id=assignment.id).exists()
        if not other_active:
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
    return redirect('delivery_boy_dashboard')


@login_required
@role_required('delivery_boy', 'admin')
def delivery_boy_update_status(request, assignment_id):
    """Unified handler for courier status transitions (picked_up, in_transit, delivered)."""
    if request.method != 'POST':
        return redirect('delivery_boy_dashboard')

    new_status = request.POST.get('status')
    if new_status == 'picked_up':
        return pickup_order(request, assignment_id)
    elif new_status == 'in_transit':
        return start_delivery(request, assignment_id)
    elif new_status == 'delivered':
        return complete_delivery(request, assignment_id)

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
        data = json.loads(request.body.decode('utf-8'))
        lat = float(data.get('latitude'))
        lon = float(data.get('longitude'))
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({'status': 'error', 'message': 'Invalid coordinates'}, status=400)
        
    profile = getattr(request.user, 'delivery_boy_profile', None)
    if not profile:
        return JsonResponse({'status': 'error', 'message': 'Profile not found'}, status=404)
        
    profile.current_latitude = lat
    profile.current_longitude = lon
    profile.save()
    
    return JsonResponse({
        'status': 'success',
        'latitude': lat,
        'longitude': lon,
        'timestamp': timezone.now().strftime("%H:%M:%S")
    })


@login_required
def update_courier_gps(request, assignment_id):
    """AJAX endpoint for courier browser to transmit live device GPS location coordinates."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

    if request.user.role != 'delivery_boy':
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    assignment = get_assignment_by_id_or_order_id(assignment_id)
    if not assignment:
        return JsonResponse({'status': 'error', 'message': 'Assignment not found'}, status=404)

    # Security Rule: Verify assigned courier
    if assignment.delivery_boy != request.user.delivery_boy_profile:
        return JsonResponse({'status': 'error', 'message': 'Access denied to this assignment'}, status=403)

    try:
        data = json.loads(request.body.decode('utf-8'))
        lat = float(data.get('latitude'))
        lon = float(data.get('longitude'))
    except (ValueError, TypeError, json.JSONDecodeError):
        lat = request.POST.get('latitude')
        lon = request.POST.get('longitude')
        try:
            lat = float(lat)
            lon = float(lon)
        except (ValueError, TypeError):
            return JsonResponse({'status': 'error', 'message': 'Invalid GPS coordinates'}, status=400)

    # Save GPS Breadcrumb
    GPSLocationTracking.objects.create(
        delivery_assignment=assignment,
        latitude=lat,
        longitude=lon
    )

    # Update Courier Profile Current Coordinates in DB
    profile = request.user.delivery_boy_profile
    profile.current_latitude = lat
    profile.current_longitude = lon
    profile.save()

    return JsonResponse({
        'status': 'success',
        'latitude': lat,
        'longitude': lon,
        'timestamp': timezone.now().strftime("%H:%M:%S")
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
            'message': 'No delivery assignment associated with this order'
        })

    # Active GPS tracking allowed ONLY while in_transit
    gps_active = (order.status == 'in_transit')

    latest_crumb = GPSLocationTracking.objects.filter(delivery_assignment=assignment).order_by('-timestamp').first()
    courier_lat = latest_crumb.latitude if latest_crumb else assignment.delivery_boy.current_latitude
    courier_lon = latest_crumb.longitude if latest_crumb else assignment.delivery_boy.current_longitude

    # Calculate live Random Forest AI ETA & predicted duration
    items_cnt = order.items.count() if hasattr(order, 'items') else 1
    completed_hist = DeliveryAssignment.objects.filter(status='delivered', actual_delivery_time__isnull=False)
    from ai_models.ml_engine import predict_delivery_time_rf
    pred_delivery_min, ai_eta_min, dist_km = predict_delivery_time_rf(
        courier_lat, courier_lon, order.latitude, order.longitude,
        items_count=items_cnt, historical_assignments=completed_hist
    )

    return JsonResponse({
        'order_id': order.order_id,
        'status': order.status,
        'gps_active': gps_active,
        'latitude': courier_lat,
        'longitude': courier_lon,
        'distance_km': dist_km,
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
        'updated_at': timezone.now().strftime("%H:%M:%S")
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
        return redirect('order_tracking', order_id=order_id)

    if not hasattr(order, 'delivery_assignment'):
        messages.error(request, "No delivery record associated with this order.")
        return redirect('order_history')

    assignment = order.delivery_assignment
    delivery_boy = assignment.delivery_boy

    if DeliveryFeedback.objects.filter(order=order).exists():
        messages.warning(request, "Feedback has already been submitted for this delivered order.")
        return redirect('order_tracking', order_id=order_id)

    if request.method == 'POST':
        try:
            rating = int(request.POST.get('rating', 5))
            rating = max(1, min(5, rating))
        except (ValueError, TypeError):
            rating = 5

        comment = request.POST.get('comment', '').strip()

        DeliveryFeedback.objects.create(
            order=order,
            delivery_assignment=assignment,
            delivery_boy=delivery_boy,
            customer=request.user,
            rating=rating,
            comment=comment
        )

        avg_rating = DeliveryFeedback.objects.filter(delivery_boy=delivery_boy).aggregate(models.Avg('rating'))['rating__avg']
        if avg_rating:
            delivery_boy.rating = round(float(avg_rating), 1)
            delivery_boy.save()

        messages.success(request, f"Thank you! Your feedback for delivery boy {delivery_boy.user.username.title()} has been submitted successfully.")
        return redirect('order_tracking', order_id=order_id)

    return redirect('order_tracking', order_id=order_id)


@login_required
def get_courier_notifications(request):
    """API endpoint for real-time notification polling and entrance popup modal in Courier Portal."""
    if request.user.role != 'delivery_boy':
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
        
    notifications = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).select_related('order__user').prefetch_related('order__items__food_item').order_by('-created_at')[:10]
    
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
        
        if notif.order:
            lat = notif.order.latitude
            lon = notif.order.longitude
            delivery_address = f"Lat {lat}, Lon {lon}"
            order_date = notif.order.created_at.strftime("%b %d, %Y, %I:%M %p")
            
            first_item = notif.order.items.first()
            if first_item:
                food_id = f"FOOD{first_item.food_item.id:04d}"
                food_name = first_item.food_item.name
                quantity = first_item.quantity
                
            if hasattr(notif.order, 'delivery_assignment'):
                assignment_id = notif.order.delivery_assignment.id
                st = notif.order.delivery_assignment.status
                if st == 'assigned':
                    status_display = "Assigned / Pending Delivery"
                elif st == 'in_transit':
                    status_display = "Out for Delivery"
                elif st == 'delivered':
                    status_display = "Delivered"
                else:
                    status_display = notif.order.delivery_assignment.get_status_display()
                
        track_url = f"/orders/notifications/mark-read/{notif.id}/" if notif.id else '#'
        profile = getattr(request.user, 'delivery_boy_profile', None)
        origin_str = f"origin={profile.current_latitude},{profile.current_longitude}&" if (profile and profile.current_latitude and profile.current_longitude) else ""
        nav_url = f"https://www.google.com/maps/dir/?api=1&{origin_str}destination={lat},{lon}" if lat and lon else '#'
            
        data.append({
            'id': notif.id,
            'title': notif.title,
            'message': notif.message,
            'order_id': notif.order.order_id if notif.order else '',
            'food_id': food_id,
            'food_name': food_name,
            'quantity': quantity,
            'latitude': lat,
            'longitude': lon,
            'delivery_address': delivery_address,
            'order_date': order_date,
            'status': status_display,
            'assignment_id': assignment_id,
            'track_url': track_url,
            'nav_url': nav_url,
            'created_at': notif.created_at.strftime("%I:%M %p"),
        })
        
    return JsonResponse({
        'status': 'success',
        'unread_count': len(data),
        'notifications': data
    })

