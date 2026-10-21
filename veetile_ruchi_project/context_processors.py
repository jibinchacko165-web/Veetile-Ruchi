import os
from django.conf import settings

def global_settings(request):
    carto_key = getattr(settings, 'CARTO_API_KEY', os.environ.get('CARTO_API_KEY', '')).strip()
    if carto_key:
        carto_url = 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png?api_key=' + carto_key
        carto_attr = '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions" target="_blank" rel="noopener">CARTO</a>'
    else:
        carto_url = ''
        carto_attr = ''

    # Policy-compliant, high-availability Esri map tiles (authorized for Leaflet, no API key required, no 403 blocks)
    esri_street_url = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}'
    esri_street_attr = 'Tiles &copy; Esri &mdash; Source: Esri, DeLorme, NAVTEQ, USGS, TomTom'

    esri_topo_url = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}'
    esri_topo_attr = 'Tiles &copy; Esri &mdash; Source: Esri, DeLorme, NAVTEQ, TomTom'

    default_primary_url = carto_url if carto_url else getattr(settings, 'MAP_TILE_URL', esri_street_url)
    default_primary_attr = carto_attr if carto_url else getattr(settings, 'MAP_TILE_ATTRIBUTION', esri_street_attr)

    google_maps_key = getattr(settings, 'GOOGLE_MAPS_API_KEY', os.environ.get('GOOGLE_MAPS_API_KEY', '')).strip()

    return {
        'GOOGLE_MAPS_API_KEY': google_maps_key,
        'HAS_GOOGLE_MAPS_KEY': bool(google_maps_key),
        'CARTO_API_KEY': carto_key,
        'MAP_TILE_URL': os.environ.get('MAP_TILE_URL', default_primary_url),
        'MAP_TILE_ATTRIBUTION': os.environ.get('MAP_TILE_ATTRIBUTION', default_primary_attr),
        'MAP_TILE_SUBDOMAINS': os.environ.get('MAP_TILE_SUBDOMAINS', 'abc' if not carto_url else 'abcd'),
        'MAP_TILE_FALLBACK_URL': os.environ.get(
            'MAP_TILE_FALLBACK_URL',
            getattr(settings, 'MAP_TILE_FALLBACK_URL', esri_topo_url)
        ),
        'MAP_TILE_FALLBACK_ATTRIBUTION': os.environ.get(
            'MAP_TILE_FALLBACK_ATTRIBUTION',
            getattr(settings, 'MAP_TILE_FALLBACK_ATTRIBUTION', esri_topo_attr)
        ),
    }

