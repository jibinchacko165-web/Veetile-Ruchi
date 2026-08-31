from django.db.models import Sum
from .models import CartItem, Wishlist, Notification

def nav_counts(request):
    """Provides real-time cart item count, wishlist count, and notifications for top navigation bar."""
    if hasattr(request, 'user') and request.user.is_authenticated:
        cart_count = CartItem.objects.filter(user=request.user).aggregate(Sum('quantity'))['quantity__sum'] or 0
        wishlist_count = Wishlist.objects.filter(user=request.user).count()
        unread_notifications = Notification.objects.filter(user=request.user, is_read=False).order_by('-created_at')[:5]
        unread_notif_count = Notification.objects.filter(user=request.user, is_read=False).count()
        
        return {
            'cart_count': cart_count,
            'wishlist_count': wishlist_count,
            'unread_notifications': unread_notifications,
            'unread_notif_count': unread_notif_count,
        }
    return {
        'cart_count': 0,
        'wishlist_count': 0,
        'unread_notifications': [],
        'unread_notif_count': 0,
    }
