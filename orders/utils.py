import math

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

def is_within_delivery_perimeter(customer_lat, customer_lon, branch_id=None, chef_lat=None, chef_lon=None, max_radius_km=None):
    """
    Verify whether customer coordinates are within acceptable service radius (exactly 30 km) from
    the Central Kitchen Hub (Kanjirappally) or selected branch.
    Returns: (is_serviceable: bool, distance_km: float, message: str)
    """
    try:
        c_lat = float(customer_lat)
        c_lon = float(customer_lon)
    except (ValueError, TypeError):
        return False, 999.0, "Invalid delivery coordinates provided. Please select your location on the map."

    if not (-90.0 <= c_lat <= 90.0 and -180.0 <= c_lon <= 180.0):
        return False, 999.0, "Coordinates out of valid geographical range."

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

    dist = calculate_distance_km(c_lat, c_lon, origin_lat, origin_lon)

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
    if 70 <= lat <= 80 and 8 <= lon <= 13:
        lat, lon = lon, lat
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None, None
    return round(lat, 6), round(lon, 6)

def is_valid_coordinate(lat, lon):
    """Returns True if latitude and longitude are valid geographical coordinates."""
    c_lat, c_lon = validate_coordinates(lat, lon)
    return c_lat is not None and c_lon is not None

