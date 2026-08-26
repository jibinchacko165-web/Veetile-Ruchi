from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_redirect, name='dashboard_redirect'),
    path('profile/', views.profile_view, name='profile'),
    path('chefs/<int:chef_id>/toggle-approval/', views.toggle_chef_approval, name='toggle_chef_approval'),
    path('courier/status/', views.toggle_courier_status_view, name='toggle_courier_status'),
    path('password-reset/', views.password_reset_view, name='password_reset'),
    path('password-reset/cancel/', views.password_reset_cancel_view, name='password_reset_cancel'),
    path('notifications/', views.notifications_view, name='notifications'),
    path('notifications/read/<int:notif_id>/', views.mark_notification_read, name='mark_notification_read'),
]
