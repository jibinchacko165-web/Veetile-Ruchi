from django.urls import path
from . import views
from food.views import wishlist_toggle

urlpatterns = [
    path('cart/', views.cart_view, name='cart_view'),
    path('cart/add/<int:food_id>/', views.cart_add, name='cart_add'),
    path('cart/update/<int:item_id>/', views.cart_update_quantity, name='cart_update_quantity'),
    path('cart/remove/<int:item_id>/', views.cart_remove, name='cart_remove'),
    path('checkout/', views.checkout_view, name='checkout_view'),
    path('checkout/place/', views.place_order, name='place_order'),
    path('track/<str:order_id>/', views.order_tracking, name='order_tracking'),
    path('history/', views.order_history, name='order_history'),
    path('wishlist/', views.wishlist_view, name='wishlist_view'),
    path('wishlist/toggle/<int:pk>/', wishlist_toggle, name='orders_wishlist_toggle'),
    path('wishlist/remove/<int:pk>/', wishlist_toggle, name='orders_wishlist_remove'),
    path('wishlist/add/<int:pk>/', wishlist_toggle, name='orders_wishlist_add'),
    path('notifications/', views.notifications_view, name='notifications'),
    path('notifications/mark-read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    path('live-status/<str:order_id>/', views.api_order_status, name='api_order_status'),
    path('api/reverse-geocode/', views.api_reverse_geocode, name='api_reverse_geocode'),
    
    # Staff mappings
    path('staff/dashboard/', views.staff_dashboard, name='staff_dashboard'),
    path('staff/order/<str:order_id>/payment/', views.staff_confirm_payment, name='staff_confirm_payment'),
    path('staff/order/<str:order_id>/status/', views.staff_update_order_status, name='staff_update_order_status'),
    path('staff/order/<str:order_id>/assign/', views.staff_assign_delivery, name='staff_assign_delivery'),
    path('staff/delivery-perimeter/save/', views.staff_save_delivery_perimeter, name='staff_save_delivery_perimeter'),
    path('staff/branch/save/', views.staff_save_hotel_branch, name='staff_save_hotel_branch'),
    path('staff/branch/save/<int:branch_id>/', views.staff_save_hotel_branch, name='staff_save_hotel_branch_edit'),
    path('staff/branch/toggle/<int:branch_id>/', views.staff_toggle_branch_status, name='staff_toggle_branch_status'),
]
