import os
from django.conf import settings

def global_settings(request):
    carto_key = os.environ.get('CARTO_API_KEY', '').strip()
    if carto_key:
        carto_url = 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png?api_key=' + carto_key
        carto_attr = '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions" target="_blank" rel="noopener">CARTO</a>'
    else:
        carto_url = ''
        carto_attr = ''

    return {
        'GOOGLE_MAPS_API_KEY': os.environ.get('GOOGLE_MAPS_API_KEY', ''),
        'CARTO_API_KEY': carto_key,
        'MAP_TILE_URL': os.environ.get(
            'MAP_TILE_URL',
            carto_url if carto_url else 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}'
        ),
        'MAP_TILE_ATTRIBUTION': os.environ.get(
            'MAP_TILE_ATTRIBUTION',
            carto_attr if carto_url else 'Tiles &copy; Esri &mdash; Source: Esri, DeLorme, NAVTEQ, USGS, TomTom'
        ),
        'MAP_TILE_SUBDOMAINS': os.environ.get('MAP_TILE_SUBDOMAINS', 'abc' if not carto_url else 'abcd'),
        'MAP_TILE_FALLBACK_URL': os.environ.get(
            'MAP_TILE_FALLBACK_URL',
            'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}'
        ),
        'MAP_TILE_FALLBACK_ATTRIBUTION': os.environ.get(
            'MAP_TILE_FALLBACK_ATTRIBUTION',
            'Tiles &copy; Esri &mdash; Source: Esri, DeLorme, NAVTEQ, TomTom'
        ),
    }

