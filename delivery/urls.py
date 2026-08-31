from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.delivery_boy_dashboard, name='delivery_boy_dashboard'),
    path('track/<int:assignment_id>/', views.delivery_boy_track, name='delivery_boy_track'),
    path('update/<int:assignment_id>/', views.delivery_boy_update_status, name='delivery_boy_update_status'),
    path('pickup/<int:assignment_id>/', views.pickup_order, name='pickup_order'),
    path('start/<int:assignment_id>/', views.start_delivery, name='start_delivery'),
    path('complete/<int:assignment_id>/', views.complete_delivery, name='complete_delivery'),
    path('update-gps/<int:assignment_id>/', views.update_courier_gps, name='update_courier_gps'),
    path('api/update-profile-gps/', views.update_profile_gps, name='update_profile_gps'),
    path('api/live-gps/<str:order_id>/', views.get_live_gps_location, name='get_live_gps_location'),
    path('api/notifications/', views.get_courier_notifications, name='get_courier_notifications'),
    path('feedback/<str:order_id>/', views.submit_delivery_feedback, name='submit_delivery_feedback'),
]
