import math

# Default Central Kerala Service Hub (Kanjirappally, Kerala)
DEFAULT_HUB_LAT = 9.5564
DEFAULT_HUB_LON = 76.7909
DEFAULT_MAX_DELIVERY_RADIUS_KM = 20.0

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

def is_within_delivery_perimeter(customer_lat, customer_lon, chef_lat=None, chef_lon=None, max_radius_km=None):
    """
    Verify whether customer coordinates are within acceptable service radius (20 km) from
    the Kanjirappally Delivery Hub.
    Returns: (is_serviceable: bool, distance_km: float, message: str)
    """
    try:
        c_lat = float(customer_lat)
        c_lon = float(customer_lon)
    except (ValueError, TypeError):
        return False, 999.0, "Invalid delivery coordinates provided."

    settings = get_active_delivery_setting()
    origin_lat = float(chef_lat) if chef_lat is not None else settings.latitude
    origin_lon = float(chef_lon) if chef_lon is not None else settings.longitude
    allowed_radius = float(max_radius_km) if max_radius_km is not None else settings.max_delivery_radius_km

    dist = calculate_distance_km(c_lat, c_lon, origin_lat, origin_lon)

    if dist <= allowed_radius:
        return True, dist, f"Location is inside our service area ({dist} km from {settings.name})."
    else:
        return False, dist, "Sorry, delivery is currently available only within 20 km of Kanjirappally."
