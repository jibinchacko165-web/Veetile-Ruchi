from django.urls import path
from . import views

urlpatterns = [
    path('cart/', views.cart_view, name='cart_view'),
    path('cart/add/<int:food_id>/', views.cart_add, name='cart_add'),
    path('cart/remove/<int:item_id>/', views.cart_remove, name='cart_remove'),
    path('checkout/', views.checkout_view, name='checkout_view'),
    path('checkout/place/', views.place_order, name='place_order'),
    path('track/<str:order_id>/', views.order_tracking, name='order_tracking'),
    path('history/', views.order_history, name='order_history'),
    path('wishlist/', views.wishlist_view, name='wishlist_view'),
    path('notifications/', views.notifications_view, name='notifications'),
    path('notifications/mark-read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    
    # Staff mappings
    path('staff/dashboard/', views.staff_dashboard, name='staff_dashboard'),
    path('staff/order/<str:order_id>/payment/', views.staff_confirm_payment, name='staff_confirm_payment'),
    path('staff/order/<str:order_id>/status/', views.staff_update_order_status, name='staff_update_order_status'),
    path('staff/order/<str:order_id>/assign/', views.staff_assign_delivery, name='staff_assign_delivery'),
]
