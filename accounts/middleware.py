class NoCacheMiddleware:
    """
    Middleware that attaches strict HTTP cache control headers to dynamic responses.
    This prevents browsers from caching protected dashboard and profile pages,
    ensuring that pressing the browser 'Back' button post-logout triggers a fresh request
    which gets blocked by Django authentication checks.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Apply anti-caching headers for authenticated sessions and protected responses
        is_static_or_media = request.path.startswith('/static/') or request.path.startswith('/media/')
        if not is_static_or_media:
            if (hasattr(request, 'user') and request.user.is_authenticated) or 'no-cache' in response.headers.get('Cache-Control', ''):
                response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
                response['Pragma'] = 'no-cache'
                response['Expires'] = '0'
            
        return response
