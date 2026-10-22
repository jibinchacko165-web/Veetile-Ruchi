import math
import zoneinfo
from django.utils import timezone

KOLKATA_TZ = zoneinfo.ZoneInfo('Asia/Kolkata')

def to_kolkata_datetime(dt):
    """
    Safely converts any datetime (aware or naive UTC) to Asia/Kolkata timezone.
    Never manually adds or subtracts 5 hours and 30 minutes.
    """
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.utc)
    return timezone.localtime(dt, KOLKATA_TZ)

def format_kolkata_time(dt, format_str="%I:%M:%S %p"):
    """Formats datetime in Asia/Kolkata timezone with specified format."""
    local_dt = to_kolkata_datetime(dt)
    return local_dt.strftime(format_str) if local_dt else ""

def format_kolkata_iso(dt):
    """Returns an ISO 8601 string in Asia/Kolkata timezone."""
    local_dt = to_kolkata_datetime(dt)
    return local_dt.isoformat() if local_dt else None

# Default Central Kerala Service Hub (Kanjirappally, Kerala)
DEFAULT_HUB_LAT = 9.5564
DEFAULT_HUB_LON = 76.7909
DEFAULT_MAX_DELIVERY_RADIUS_KM = 30.0

def get_active_delivery_setting():
    """Retrieves the active dynamic DeliverySetting from the database with safe fallback."""
    try:
        from delivery.models import DeliverySetting
        return DeliverySetting.get_settings()
    except Exception:
        class DefaultDeliverySetting:
            name = 'Central Kitchen Hub (Kanjirappally)'
            address = 'Kanjirappally Town, Kottayam, Kerala'
            latitude = DEFAULT_HUB_LAT
            longitude = DEFAULT_HUB_LON
            max_delivery_radius_km = DEFAULT_MAX_DELIVERY_RADIUS_KM
            is_active = True
        return DefaultDeliverySetting()

# Recognizable Kerala place presets around Kanjirappally Service Radius (20 KM)
KERALA_PRESET_PLACES = [
    # ── Kanjirappally Town & Key Hubs ──
    {
        'name': 'Kanjirappally Town (Jubilee Junction)',
        'category': 'Junction / Town Center',
        'type': 'home',
        'lat': 9.5564,
        'lon': 76.7909,
        'landmark': 'Near AKJM School / Jubilee Junction',
        'desc': 'Kanjirappally Town Center'
    },
    {
        'name': 'Kanjirappally General Hospital / Petta',
        'category': 'Hospital / Landmark',
        'type': 'landmark',
        'lat': 9.5540,
        'lon': 76.7930,
        'landmark': 'Near General Hospital Gate / Petta Junction',
        'desc': 'Petta, Kanjirappally'
    },
    {
        'name': 'St. Dominic’s Cathedral & College',
        'category': 'Church / College',
        'type': 'work',
        'lat': 9.5580,
        'lon': 76.7915,
        'landmark': 'Near St. Dominic’s Cathedral Gate',
        'desc': 'Kanjirappally Campus Area'
    },

    # ── Nearby Towns & Suburbs (within 20 km radius) ──
    {
        'name': 'Ponkunnam (Bus Stand / KVMS Hospital)',
        'category': 'Junction / Town',
        'type': 'home',
        'lat': 9.5667,
        'lon': 76.7583,
        'landmark': 'Near Ponkunnam KSRTC Bus Stand',
        'desc': 'Ponkunnam Town, Kottayam'
    },
    {
        'name': 'Chirakkadavu Mahadeva Temple Area',
        'category': 'Temple / Heritage',
        'type': 'landmark',
        'lat': 9.5520,
        'lon': 76.7650,
        'landmark': 'Near Chirakkadavu Temple East Gate',
        'desc': 'Chirakkadavu, Ponkunnam'
    },
    {
        'name': 'Amal Jyothi College of Engineering (Koovappally)',
        'category': 'College / Campus',
        'type': 'work',
        'lat': 9.5284,
        'lon': 76.8228,
        'landmark': 'Near Amal Jyothi Main Express Gate',
        'desc': 'Koovappally, Kanjirappally'
    },
    {
        'name': 'Podimattam (St. Mary’s Church)',
        'category': 'Junction / Residential',
        'type': 'home',
        'lat': 9.5750,
        'lon': 76.8150,
        'landmark': 'Near Podimattam Bus Stop',
        'desc': 'Podimattam, Parathode'
    },
    {
        'name': 'Mundakayam Town (Private Stand)',
        'category': 'Junction / Town',
        'type': 'parents',
        'lat': 9.5843,
        'lon': 76.8833,
        'landmark': 'Near Mundakayam Bus Stand Junction',
        'desc': 'Mundakayam, Kottayam'
    },
    {
        'name': 'Erumely (Private Bus Stand / Temple Gate)',
        'category': 'Pilgrim Hub / Town',
        'type': 'landmark',
        'lat': 9.4833,
        'lon': 76.8500,
        'landmark': 'Near Erumely Vavar Ambalam Junction',
        'desc': 'Erumely Town'
    },
    {
        'name': 'Parathode (St. George High School)',
        'category': 'School / Suburb',
        'type': 'home',
        'lat': 9.5600,
        'lon': 76.8450,
        'landmark': 'Near Parathode Church Gate',
        'desc': 'Parathode, Kanjirappally'
    },
    {
        'name': 'Elikulam Junction',
        'category': 'Junction / Suburb',
        'type': 'parents',
        'lat': 9.6010,
        'lon': 76.7320,
        'landmark': 'Near Elikulam Panchayat Stand',
        'desc': 'Elikulam, Kottayam'
    },
]

def calculate_distance_km(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees) using Haversine formula.
    """
    try:
        lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
    except (ValueError, TypeError):
        return 999.0

    # Convert decimal degrees to radians
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    r = 6371.0 # Radius of earth in kilometers
    return round(c * r, 2)

def get_all_districts():
    """Returns all 14 active Kerala districts."""
    from delivery.models import District
    return District.objects.filter(is_active=True).order_by('name')

def get_active_hotel_branches(district_code=None):
    """Returns active hotel branches, optionally filtered by district."""
    from delivery.models import HotelBranch
    qs = HotelBranch.objects.filter(is_active=True).select_related('district')
    if district_code:
        qs = qs.filter(district__code=district_code)
    return qs

def find_nearest_serving_branch(customer_lat, customer_lon):
    """
    Finds the nearest active branch to customer coordinates.
    Returns: (branch, distance_km, is_within_radius)
    """
    try:
        c_lat, c_lon = float(customer_lat), float(customer_lon)
    except (ValueError, TypeError):
        return None, 999.0, False

    branches = get_active_hotel_branches()
    if not branches.exists():
        setting = get_active_delivery_setting()
        dist = calculate_distance_km(c_lat, c_lon, setting.latitude, setting.longitude)
        return None, dist, (dist <= float(setting.max_delivery_radius_km or 30.0))

    best_branch = None
    min_dist = float('inf')

    for branch in branches:
        dist = branch.calculate_distance(c_lat, c_lon)
        if dist < min_dist:
            min_dist = dist
            best_branch = branch

    if best_branch:
        is_eligible = min_dist <= float(best_branch.effective_radius_km or 30.0)
        return best_branch, min_dist, is_eligible
    return None, 999.0, False

def is_offshore_sea_coordinate(lat, lon):
    """
    Detects if coordinates are offshore in the Arabian Sea west of Kerala
    (e.g. the legacy (10.0, 76.0) default or coordinates with longitude west of the coastline).
    """
    try:
        lat, lon = float(lat), float(lon)
    except (ValueError, TypeError):
        return True
    
    # Check swapped coordinates first
    if 70.0 <= lat <= 80.0 and 8.0 <= lon <= 13.0:
        lat, lon = lon, lat

    # Legacy default (10.0, 76.0) is ~25 km into the Arabian Sea west of Kochi
    if round(lat, 2) == 10.0 and round(lon, 2) == 76.0:
        return True
    if round(lat, 4) == 9.5564 and round(lon, 2) == 76.0:
        return True

    # Kerala coastal boundary approximation (west of coastline is sea)
    if 8.0 <= lat <= 9.0 and lon < 76.4:
        return True
    if 9.0 < lat <= 10.0 and lon < 76.15:
        return True
    if 10.0 < lat <= 11.0 and lon < 75.85:
        return True
    if 11.0 < lat <= 12.0 and lon < 75.35:
        return True
    if 12.0 < lat <= 13.0 and lon < 74.9:
        return True
    return False

def is_within_delivery_perimeter(customer_lat, customer_lon, branch_id=None, chef_lat=None, chef_lon=None, max_radius_km=None):
    """
    Verify whether customer coordinates are within acceptable service radius (exactly 30 km) from
    the Central Kitchen Hub (Kanjirappally) or selected branch.
    Returns: (is_serviceable: bool, distance_km: float, message: str)
    """
    v_lat, v_lon = validate_coordinates(customer_lat, customer_lon)
    if v_lat is None or v_lon is None:
        return False, 999.0, "Invalid delivery coordinates provided. Please select your location on the map."

    if is_offshore_sea_coordinate(v_lat, v_lon):
        return False, 999.0, "Selected coordinates fall in the sea or offshore area. Please select a valid land address within Kerala."

    from delivery.models import HotelBranch
    branch = None
    if branch_id:
        branch = HotelBranch.objects.filter(id=branch_id, is_active=True).first()

    settings = get_active_delivery_setting()

    if branch:
        origin_lat = branch.latitude
        origin_lon = branch.longitude
        allowed_radius = float(max_radius_km) if max_radius_km is not None else float(branch.max_delivery_radius_km or 30.0)
        hub_name = branch.name
    else:
        origin_lat = float(chef_lat) if chef_lat is not None else settings.latitude
        origin_lon = float(chef_lon) if chef_lon is not None else settings.longitude
        allowed_radius = float(max_radius_km) if max_radius_km is not None else float(settings.max_delivery_radius_km or 30.0)
        hub_name = settings.name

    dist = calculate_distance_km(v_lat, v_lon, origin_lat, origin_lon)

    radius_str = f"{int(allowed_radius)}" if float(allowed_radius).is_integer() else f"{allowed_radius}"
    hub_display = "Kanjirappally" if "Kanjirappally" in hub_name else hub_name

    if dist <= allowed_radius:
        return True, dist, f"Location is inside our service area ({dist} km from {hub_name})."
    else:
        return False, dist, f"Sorry, delivery is currently available only within {radius_str} km of {hub_display}. Sorry, this hotel cannot deliver to your selected location. Please choose a nearer address or another available hotel."

def validate_coordinates(lat, lon):
    try:
        lat, lon = float(lat), float(lon)
    except (ValueError, TypeError):
        return None, None
    if math.isnan(lat) or math.isnan(lon) or math.isinf(lat) or math.isinf(lon):
        return None, None
    # If lat/lon are reversed (e.g. lat=76, lon=9 instead of lat=9, lon=76)
    if 70.0 <= lat <= 80.0 and 8.0 <= lon <= 13.0:
        lat, lon = lon, lat
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None, None
    return round(lat, 6), round(lon, 6)

def is_valid_coordinate(lat, lon):
    """Returns True if latitude and longitude are valid geographical coordinates."""
    c_lat, c_lon = validate_coordinates(lat, lon)
    return c_lat is not None and c_lon is not None

def sanitize_customer_coordinates(lat, lon, fallback_lat=DEFAULT_HUB_LAT, fallback_lon=DEFAULT_HUB_LON):
    """
    Safely sanitizes and validates customer destination coordinates.
    Reverses accidentally swapped coordinates, catches offshore sea positions,
    and safely returns verified coordinates on land.
    """
    c_lat, c_lon = validate_coordinates(lat, lon)
    if c_lat is None or c_lon is None:
        return fallback_lat, fallback_lon
    if is_offshore_sea_coordinate(c_lat, c_lon):
        return fallback_lat, fallback_lon
    return c_lat, c_lon

def get_courier_gps_status(order, assignment):
    """
    Retrieves genuine courier GPS coordinates and timestamp in Asia/Kolkata timezone.
    Strictly adheres to:
    - Never uses page refresh time as GPS timestamp.
    - Preserves historical GPS timestamp for delivered orders.
    - Identifies stale updates (> 5 mins) during active transit.
    - Returns 'No GPS update available' when no records exist.
    """
    courier_lat = None
    courier_lon = None
    has_courier_gps = False
    is_gps_stale = False
    if order.status == 'delivered':
        last_gps_update = "Delivered"
    elif order.status in ['in_transit', 'picked_up']:
        last_gps_update = "Waiting for courier GPS location"
    elif order.status == 'ready_pickup':
        last_gps_update = "Waiting for courier assignment"
    elif order.status == 'assigned':
        last_gps_update = "Waiting for food pickup"
    else:
        last_gps_update = "Waiting for kitchen preparation"
    last_gps_iso = None

    if not assignment:
        return {
            'courier_lat': None,
            'courier_lon': None,
            'has_courier_gps': False,
            'is_gps_stale': False,
            'last_gps_update': last_gps_update,
            'last_gps_iso': None,
        }

    from delivery.models import GPSLocationTracking
    courier_profile = getattr(assignment, 'delivery_boy', None)
    latest_crumb = GPSLocationTracking.objects.filter(delivery_assignment=assignment).order_by('-timestamp').first()

    if latest_crumb:
        c_lat, c_lon = validate_coordinates(latest_crumb.latitude, latest_crumb.longitude)
        if c_lat is not None and c_lon is not None:
            local_crumb_dt = to_kolkata_datetime(latest_crumb.timestamp)
            crumb_time_str = local_crumb_dt.strftime("%I:%M:%S %p")
            last_gps_iso = local_crumb_dt.isoformat()

            if order.status == 'delivered':
                # Preserve the final genuine GPS fix recorded during the delivery
                courier_lat = c_lat
                courier_lon = c_lon
                has_courier_gps = False
                is_gps_stale = False
                last_gps_update = crumb_time_str
            else:
                age_sec = (timezone.now() - latest_crumb.timestamp).total_seconds()
                courier_lat = c_lat
                courier_lon = c_lon
                if age_sec <= 300:  # 5 min freshness window
                    has_courier_gps = True
                    is_gps_stale = False
                    last_gps_update = crumb_time_str
                else:
                    has_courier_gps = False
                    is_gps_stale = True
                    last_gps_update = f"{crumb_time_str} (Signal Stale)"
    elif courier_profile and courier_profile.current_latitude and courier_profile.current_longitude:
        c_lat, c_lon = validate_coordinates(courier_profile.current_latitude, courier_profile.current_longitude)
        if c_lat is not None and c_lon is not None and not is_offshore_sea_coordinate(c_lat, c_lon):
            if order.status in ['in_transit', 'picked_up']:
                courier_lat = c_lat
                courier_lon = c_lon
                has_courier_gps = True
                is_gps_stale = False
                last_gps_update = "No GPS update available"

    return {
        'courier_lat': courier_lat,
        'courier_lon': courier_lon,
        'has_courier_gps': has_courier_gps,
        'is_gps_stale': is_gps_stale,
        'last_gps_update': last_gps_update,
        'last_gps_iso': last_gps_iso,
    }

def calculate_accurate_order_eta(order, chef_lat, chef_lon, cust_lat, cust_lon,
                                 courier_lat=None, courier_lon=None,
                                 has_courier_gps=False, is_gps_stale=False,
                                 last_gps_update=None):
    """
    Calculates accurate, transparent delivery tracking information and arrival ETA
    for customer order tracking in the Asia/Kolkata timezone.
    
    Adheres strictly to business rules:
    - Never fabricates GPS coordinates or live positions.
    - Accurately tracks all 7 lifecycle stages:
      1. Order Confirmed (pending)
      2. Food Preparing (preparing)
      3. Food Prepared (ready_pickup)
      4. Courier Assigned (assigned)
      5. Food Picked Up (picked_up)
      6. Out for Delivery (in_transit)
      7. Delivered (delivered)
    - Returns formatted milestone timestamps without predicting future stages.
    - Handles delivered state cleanly without displaying active GPS tracking errors.
    """
    import datetime
    from django.utils import timezone
    from ai_models.ml_engine import optimize_delivery_route, predict_delivery_time_rf

    now_local = to_kolkata_datetime(timezone.now())
    assignment = getattr(order, 'delivery_assignment', None)
    courier_profile = assignment.delivery_boy if assignment else None
    courier_user = courier_profile.user if courier_profile else None
    
    # 7 Lifecycle Stages: 0 to 6
    stage_index_map = {
        'pending': 0,
        'preparing': 1,
        'ready_pickup': 2,
        'assigned': 3,
        'picked_up': 4,
        'in_transit': 5,
        'delivered': 6,
        'cancelled': -1,
    }
    stage_index = stage_index_map.get(order.status, 0)

    def _format_time(dt):
        if not dt:
            return None
        return format_kolkata_time(dt, "%I:%M %p")

    # Milestone timestamps (only for completed/current stages)
    confirmed_time = _format_time(order.created_at) if order.created_at else None

    preparing_time = None
    if order.status in ['preparing', 'ready_pickup', 'assigned', 'picked_up', 'in_transit', 'delivered']:
        prep_dt = getattr(order, 'preparing_started_at', None) or order.created_at
        preparing_time = _format_time(prep_dt)

    prepared_time = None
    if order.status in ['ready_pickup', 'assigned', 'picked_up', 'in_transit', 'delivered']:
        prep_done_dt = getattr(order, 'food_prepared_at', None)
        prepared_time = _format_time(prep_done_dt)

    assigned_time = None
    if order.status in ['assigned', 'picked_up', 'in_transit', 'delivered']:
        assigned_dt = getattr(order, 'courier_assigned_at', None) or (getattr(assignment, 'assigned_at', None) if assignment else None)
        assigned_time = _format_time(assigned_dt)

    picked_up_time = None
    if order.status in ['picked_up', 'in_transit', 'delivered']:
        pickup_dt = getattr(order, 'picked_up_at', None) or (getattr(assignment, 'picked_up_at', None) if assignment else None)
        picked_up_time = _format_time(pickup_dt)

    out_for_delivery_time = None
    if order.status in ['in_transit', 'delivered']:
        transit_dt = getattr(assignment, 'out_for_delivery_at', None) if assignment else None
        out_for_delivery_time = _format_time(transit_dt)

    delivered_time = None
    if order.status == 'delivered':
        deliv_dt = getattr(order, 'delivered_at', None) or (getattr(assignment, 'delivered_at', None) if assignment else None)
        delivered_time = _format_time(deliv_dt)

    timestamps = {
        'confirmed_time': confirmed_time,
        'preparing_time': preparing_time,
        'prepared_time': prepared_time,
        'assigned_time': assigned_time,
        'picked_up_time': picked_up_time,
        'out_for_delivery_time': out_for_delivery_time,
        'delivered_time': delivered_time,
    }
    
    # ── CASE 1: DELIVERED ──
    if order.status == 'delivered':
        delivered_raw = None
        if assignment and assignment.delivered_at:
            delivered_raw = assignment.delivered_at
        elif getattr(order, 'delivered_at', None):
            delivered_raw = order.delivered_at

        if delivered_raw:
            delivered_dt = to_kolkata_datetime(delivered_raw)
            delivered_time_str = delivered_dt.strftime("%I:%M %p")
            expected_arrival_time = f"Delivered at {delivered_time_str}"
            status_display = f"Order delivered successfully at {delivered_time_str}"
            delivery_comp_msg = f"Order completed and delivered at {delivered_time_str}"
            delivered_iso = delivered_dt.isoformat()
        else:
            delivered_time_str = None
            delivered_iso = None
            expected_arrival_time = "Delivered"
            status_display = "Order delivered successfully"
            delivery_comp_msg = "Order delivery completed"

        # Determine last GPS update display:
        # If genuine GPS broadcast crumb occurred, preserve its timestamp;
        # otherwise display the completed delivery time.
        if last_gps_update and last_gps_update not in ["No GPS update available", "Waiting for courier GPS location", "Delivered"]:
            display_gps_update = last_gps_update
            display_gps_msg = f"Final GPS broadcast at {last_gps_update}"
        elif delivered_time_str:
            display_gps_update = f"Delivered at {delivered_time_str}"
            display_gps_msg = f"Order completed and delivered at {delivered_time_str}"
        else:
            display_gps_update = "Delivered"
            display_gps_msg = "Order completed • Verified delivery handover"

        return {
            'order_id': order.order_id,
            'order_status': 'delivered',
            'status_label': 'Delivered ✅',
            'status_display': status_display,
            'status_badge_class': 'badge-success',
            'stage_index': 6,
            'expected_arrival_time': expected_arrival_time,
            'expected_arrival_timestamp': delivered_iso,
            'delivered_timestamp': delivered_iso,
            'remaining_travel_time': "Delivered",
            'remaining_travel_minutes': 0,
            'remaining_road_distance_km': 0.0,
            'road_distance_display': "Completed",
            'is_road_distance': False,
            'prep_time_minutes': 0,
            'prep_status_display': "Preparation Completed",
            'eta_status_type': 'delivered',
            'eta_message': "Your meal has been delivered. Enjoy your hot food from Veetile Ruchi!",
            'has_courier': courier_user is not None,
            'has_courier_gps': False,
            'is_gps_stale': False,
            'courier_name': (courier_user.get_full_name() or courier_user.username).title() if courier_user else None,
            'courier_phone': getattr(courier_user, 'phone', None) if courier_user else None,
            'courier_username': courier_user.username if courier_user else None,
            'vehicle_number': courier_profile.vehicle_number if courier_profile else None,
            'last_gps_update': display_gps_update,
            'gps_status_badge': "✅ Order Completed",
            'gps_status_msg': display_gps_msg,
            'route_steps': [],
            'chef_lat': chef_lat,
            'chef_lon': chef_lon,
            'cust_lat': cust_lat,
            'cust_lon': cust_lon,
            'courier_lat': None,
            'courier_lon': None,
            'ai_eta_min': 0,
            'show_map': False,
            'is_live_tracking_active': False,
            'server_timestamp': format_kolkata_iso(now_local),
            'last_updated_time': format_kolkata_time(now_local, "%I:%M:%S %p"),
            'timestamps': timestamps,
        }

    # ── CASE 2: CANCELLED ──
    if order.status == 'cancelled':
        return {
            'order_id': order.order_id,
            'order_status': 'cancelled',
            'status_label': 'Cancelled ❌',
            'status_display': 'Order Cancelled',
            'status_badge_class': 'badge-danger',
            'stage_index': -1,
            'expected_arrival_time': "Order Cancelled",
            'expected_arrival_timestamp': None,
            'remaining_travel_time': "Cancelled",
            'remaining_travel_minutes': 0,
            'remaining_road_distance_km': 0.0,
            'road_distance_display': "Cancelled",
            'is_road_distance': False,
            'prep_time_minutes': 0,
            'prep_status_display': "Cancelled",
            'eta_status_type': 'cancelled',
            'eta_message': "This order has been cancelled.",
            'has_courier': courier_user is not None,
            'has_courier_gps': False,
            'is_gps_stale': False,
            'courier_name': None,
            'courier_phone': None,
            'courier_username': None,
            'vehicle_number': None,
            'last_gps_update': "Order Cancelled",
            'gps_status_badge': "❌ Order Cancelled",
            'gps_status_msg': "Order was cancelled.",
            'route_steps': [],
            'chef_lat': chef_lat,
            'chef_lon': chef_lon,
            'cust_lat': cust_lat,
            'cust_lon': cust_lon,
            'courier_lat': None,
            'courier_lon': None,
            'ai_eta_min': 0,
            'show_map': False,
            'is_live_tracking_active': False,
            'server_timestamp': format_kolkata_iso(now_local),
            'last_updated_time': format_kolkata_time(now_local, "%I:%M:%S %p"),
            'timestamps': timestamps,
        }

    # ── CASE 3: IN TRANSIT / PICKED UP (With Courier) ──
    if order.status in ['in_transit', 'picked_up']:
        courier_display_name = (courier_user.get_full_name() or courier_user.username).title() if courier_user else "Courier"
        
        # Determine routing origin
        if has_courier_gps and courier_lat and courier_lon:
            origin_lat = courier_lat
            origin_lon = courier_lon
            is_courier_origin = True
        else:
            origin_lat = chef_lat
            origin_lon = chef_lon
            is_courier_origin = False

        route_res = optimize_delivery_route(origin_lat, origin_lon, cust_lat, cust_lon)
        route_steps = route_res.route
        road_dist_km = route_res.distance
        is_road = getattr(route_res, 'is_road', True)
        
        # Calculate road travel time
        raw_travel_min = getattr(route_res, 'duration_min', None)
        if raw_travel_min is not None and raw_travel_min > 0:
            travel_mins = raw_travel_min
        else:
            travel_mins = max(1.0, round((road_dist_km / 25.0) * 60.0, 1))

        if order.status == 'picked_up':
            stage_idx = 4
            prep_status_display = "Picked Up by Courier"
            status_label = "Food Picked Up 📦"
            status_display = f"Courier {courier_display_name} has picked up your food from the kitchen"
            remaining_travel_time = f"~{int(round(travel_mins))} mins road travel"
            road_distance_display = f"{road_dist_km} km (Kitchen to Delivery Location)"
            eta_status_type = 'picked_up'
            eta_message = "Food picked up from kitchen. Preparing to start transit to your address."
        else:
            stage_idx = 5
            prep_status_display = "Picked Up by Courier"
            # Check if arriving soon (within 600m or under 2.5 minutes)
            if road_dist_km <= 0.6 or travel_mins <= 2.5:
                status_label = "Arriving Soon 🎯"
                status_display = f"Delivery partner {courier_display_name} is approaching your address"
                remaining_travel_time = "Arriving in < 2 mins"
            else:
                status_label = "Out for Delivery 🛵"
                status_display = f"Courier {courier_display_name} is on the way to your delivery destination"
                remaining_travel_time = f"Approximately {int(round(travel_mins))} minutes"

            if is_courier_origin:
                road_distance_display = f"{road_dist_km} km remaining" if is_road else f"{road_dist_km} km (Direct estimate)"
                eta_status_type = 'live_gps'
                eta_message = "Live road travel ETA calculated from courier's GPS location."
            else:
                road_distance_display = f"{road_dist_km} km (From Kitchen)"
                eta_status_type = 'courier_transit_no_gps'
                eta_message = "Courier dispatched • Waiting for live courier GPS broadcast."

        arrival_dt = now_local + datetime.timedelta(minutes=travel_mins)
        expected_arrival_time = f"Expected by {arrival_dt.strftime('%I:%M %p')}"

        # GPS status badge & message
        effective_gps_update = last_gps_update or "No GPS update available"
        if has_courier_gps and not is_gps_stale:
            gps_status_badge = "🟢 Live GPS Active"
            gps_status_msg = f"Live GPS • Updated at {effective_gps_update}"
        elif is_gps_stale:
            gps_status_badge = "🟡 GPS Delayed"
            gps_status_msg = f"Location update delayed • Last seen at {effective_gps_update}"
        else:
            effective_gps_update = "Waiting for courier GPS location"
            if order.status == 'picked_up':
                gps_status_badge = "📦 Food Picked Up"
                gps_status_msg = "Food picked up • Waiting for courier GPS location"
            else:
                gps_status_badge = "⌛ Waiting for GPS"
                gps_status_msg = "Courier out for delivery • Waiting for courier GPS location"

        # Supplementary AI Model Baseline
        items_cnt = order.items.count() if hasattr(order, 'items') else 1
        _, ai_eta_min, _ = predict_delivery_time_rf(origin_lat, origin_lon, cust_lat, cust_lon, items_count=items_cnt, road_distance_km=road_dist_km)

        return {
            'order_id': order.order_id,
            'order_status': order.status,
            'status_label': status_label,
            'status_display': status_display,
            'status_badge_class': 'badge-warning',
            'stage_index': stage_idx,
            'expected_arrival_time': expected_arrival_time,
            'expected_arrival_timestamp': format_kolkata_iso(arrival_dt),
            'remaining_travel_time': remaining_travel_time,
            'remaining_travel_minutes': int(round(travel_mins)),
            'remaining_road_distance_km': road_dist_km,
            'road_distance_display': road_distance_display,
            'is_road_distance': is_road,
            'prep_time_minutes': 0,
            'prep_status_display': prep_status_display,
            'eta_status_type': eta_status_type,
            'eta_message': eta_message,
            'has_courier': courier_user is not None,
            'has_courier_gps': has_courier_gps,
            'is_gps_stale': is_gps_stale,
            'courier_name': (courier_user.get_full_name() or courier_user.username).title() if courier_user else None,
            'courier_phone': getattr(courier_user, 'phone', None) if courier_user else None,
            'courier_username': courier_user.username if courier_user else None,
            'vehicle_number': courier_profile.vehicle_number if courier_profile else None,
            'last_gps_update': effective_gps_update,
            'gps_status_badge': gps_status_badge,
            'gps_status_msg': gps_status_msg,
            'route_steps': route_steps,
            'chef_lat': chef_lat,
            'chef_lon': chef_lon,
            'cust_lat': cust_lat,
            'cust_lon': cust_lon,
            'courier_lat': courier_lat if has_courier_gps else None,
            'courier_lon': courier_lon if has_courier_gps else None,
            'ai_eta_min': ai_eta_min,
            'show_map': True,
            'is_live_tracking_active': True,
            'server_timestamp': format_kolkata_iso(now_local),
            'last_updated_time': format_kolkata_time(now_local, "%I:%M:%S %p"),
            'timestamps': timestamps,
        }

    # ── CASE 4: BEFORE PICKUP (Kitchen Preparation & Courier Assignment Stage) ──
    # [pending, preparing, ready_pickup, assigned]
    origin_lat = chef_lat
    origin_lon = chef_lon
    
    route_res = optimize_delivery_route(origin_lat, origin_lon, cust_lat, cust_lon)
    route_steps = route_res.route
    road_dist_km = route_res.distance
    is_road = getattr(route_res, 'is_road', True)
    
    raw_travel_min = getattr(route_res, 'duration_min', None)
    if raw_travel_min is not None and raw_travel_min > 0:
        travel_mins = raw_travel_min
    else:
        travel_mins = max(1.0, round((road_dist_km / 25.0) * 60.0, 1))

    items_cnt = order.items.count() if hasattr(order, 'items') else 1

    if order.status == 'pending':
        prep_time_minutes = 15.0
        status_label = "Order Confirmed 📋"
        status_display = "Order Confirmed • Central kitchen queuing for preparation"
        prep_status_display = "Order Confirmed"
        status_badge_class = 'badge-green'
        pickup_buffer = 4.0
        gps_status_badge = "📋 Order Placed"
        gps_status_msg = "Order received • Central kitchen preparing to start order"
        effective_gps_update = "Waiting for kitchen preparation"
    elif order.status == 'preparing':
        prep_base = getattr(order, 'preparing_started_at', None) or order.created_at
        elapsed_prep_mins = (timezone.now() - prep_base).total_seconds() / 60.0 if prep_base else 0.0
        standard_prep = 15.0 + max(0, items_cnt - 1) * 2.0
        prep_time_minutes = max(3.0, round(standard_prep - elapsed_prep_mins, 1))
        status_label = "Food Preparing 🍳"
        status_display = "Chef is preparing your food with fresh ingredients"
        prep_status_display = f"In Kitchen (~{int(round(prep_time_minutes))} mins)"
        status_badge_class = 'badge-green'
        pickup_buffer = 4.0
        gps_status_badge = "🍳 Kitchen Stage"
        gps_status_msg = "Order being prepared • Courier will be assigned after preparation"
        effective_gps_update = "Waiting for food preparation"
    elif order.status == 'ready_pickup':
        prep_time_minutes = 0.0
        status_label = "Food Prepared 🍲"
        status_display = "Food prepared — waiting for courier assignment"
        prep_status_display = "Food Prepared"
        status_badge_class = 'badge-green'
        pickup_buffer = 4.0
        gps_status_badge = "🍲 Food Prepared"
        gps_status_msg = "Food prepared — waiting for courier assignment"
        effective_gps_update = "Waiting for courier assignment"
    elif order.status == 'assigned':
        prep_time_minutes = 0.0
        c_name = (courier_user.get_full_name() or courier_user.username).title() if courier_user else "Partner"
        status_label = "Courier Assigned 🛵"
        status_display = f"Courier {c_name} assigned • Heading to kitchen for pickup"
        prep_status_display = "Food Prepared"
        status_badge_class = 'badge-green'
        pickup_buffer = 4.0
        gps_status_badge = "🛵 Courier Assigned"
        gps_status_msg = f"Delivery partner {c_name} assigned • Heading to kitchen"
        effective_gps_update = "Waiting for food pickup"
    else:
        prep_time_minutes = 10.0
        status_label = "Order Confirmed 📋"
        status_display = order.get_status_display()
        prep_status_display = "Kitchen Processing"
        status_badge_class = 'badge-green'
        pickup_buffer = 4.0
        gps_status_badge = "📋 Order Placed"
        gps_status_msg = "Processing order"
        effective_gps_update = "Processing"

    total_remaining_mins = prep_time_minutes + travel_mins + pickup_buffer
    arrival_dt = now_local + datetime.timedelta(minutes=total_remaining_mins)
    expected_arrival_time = f"Expected by {arrival_dt.strftime('%I:%M %p')}"
    remaining_travel_time = f"~{int(round(travel_mins))} mins transit estimate"
    road_distance_display = f"{road_dist_km} km (Straight-line distance)"
    eta_message = "Estimated arrival calculated from straight-line distance and kitchen workflow."

    # Supplementary AI prediction
    _, ai_eta_min, _ = predict_delivery_time_rf(origin_lat, origin_lon, cust_lat, cust_lon, items_count=items_cnt, road_distance_km=road_dist_km)

    return {
        'order_id': order.order_id,
        'order_status': order.status,
        'status_label': status_label,
        'status_display': status_display,
        'status_badge_class': status_badge_class,
        'stage_index': stage_index,
        'expected_arrival_time': expected_arrival_time,
        'expected_arrival_timestamp': format_kolkata_iso(arrival_dt),
        'remaining_travel_time': remaining_travel_time,
        'remaining_travel_minutes': int(round(travel_mins)),
        'remaining_road_distance_km': road_dist_km,
        'road_distance_display': road_distance_display,
        'is_road_distance': is_road,
        'prep_time_minutes': int(round(prep_time_minutes)),
        'prep_status_display': prep_status_display,
        'eta_status_type': 'kitchen_prep',
        'eta_message': eta_message,
        'has_courier': courier_user is not None,
        'has_courier_gps': False,
        'is_gps_stale': False,
        'courier_name': (courier_user.get_full_name() or courier_user.username).title() if courier_user else None,
        'courier_phone': getattr(courier_user, 'phone', None) if courier_user else None,
        'courier_username': courier_user.username if courier_user else None,
        'vehicle_number': courier_profile.vehicle_number if courier_profile else None,
        'last_gps_update': effective_gps_update,
        'gps_status_badge': gps_status_badge,
        'gps_status_msg': gps_status_msg,
        'route_steps': route_steps,
        'chef_lat': chef_lat,
        'chef_lon': chef_lon,
        'cust_lat': cust_lat,
        'cust_lon': cust_lon,
        'courier_lat': None,
        'courier_lon': None,
        'ai_eta_min': ai_eta_min,
        'show_map': True,
        'is_live_tracking_active': True,
        'server_timestamp': format_kolkata_iso(now_local),
        'last_updated_time': format_kolkata_time(now_local, "%I:%M:%S %p"),
        'timestamps': timestamps,
    }

