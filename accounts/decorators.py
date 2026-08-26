from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.mixins import AccessMixin

def role_required(*allowed_roles):
    """
    Decorator for views that checks if the user is logged in and has one of the allowed roles.
    Superusers automatically bypass role checks.
    If unauthorized, redirects to user's dashboard redirect page with an explicit warning message.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, "Please log in to access this page.")
                return redirect('login')
            
            if request.user.is_superuser or request.user.role in allowed_roles:
                return view_func(request, *args, **kwargs)
            
            messages.error(request, f"Access denied. Your role ({request.user.get_role_display()}) does not have permission to view that page.")
            return redirect('dashboard_redirect')
        return _wrapped_view
    return decorator


class RoleRequiredMixin(AccessMixin):
    """
    Class-based view mixin that verifies the current user has one of the allowed roles.
    """
    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        if request.user.is_superuser or request.user.role in self.allowed_roles:
            return super().dispatch(request, *args, **kwargs)
        
        messages.error(request, f"Access denied. Your role ({request.user.get_role_display()}) does not have permission to view that page.")
        return redirect('dashboard_redirect')
