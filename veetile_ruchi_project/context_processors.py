import os
from django.conf import settings

def global_settings(request):
    osm_url = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
    osm_attr = '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors'

    osm_fallback_url = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
    osm_fallback_attr = '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors'

    primary_url = os.environ.get('MAP_TILE_URL', getattr(settings, 'MAP_TILE_URL', osm_url))
    primary_attr = os.environ.get('MAP_TILE_ATTRIBUTION', getattr(settings, 'MAP_TILE_ATTRIBUTION', osm_attr))
    subdomains = os.environ.get('MAP_TILE_SUBDOMAINS', getattr(settings, 'MAP_TILE_SUBDOMAINS', 'abc'))

    fallback_url = os.environ.get('MAP_TILE_FALLBACK_URL', getattr(settings, 'MAP_TILE_FALLBACK_URL', osm_fallback_url))
    fallback_attr = os.environ.get('MAP_TILE_FALLBACK_ATTRIBUTION', getattr(settings, 'MAP_TILE_FALLBACK_ATTRIBUTION', osm_fallback_attr))

    return {
        'MAP_TILE_URL': primary_url,
        'MAP_TILE_ATTRIBUTION': primary_attr,
        'MAP_TILE_SUBDOMAINS': subdomains,
        'MAP_TILE_FALLBACK_URL': fallback_url,
        'MAP_TILE_FALLBACK_ATTRIBUTION': fallback_attr,
    }



