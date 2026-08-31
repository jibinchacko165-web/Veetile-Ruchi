from django.urls import path
from . import views

urlpatterns = [
    path('', views.food_catalog, name='food_catalog'),
    path('food/<int:pk>/', views.food_detail, name='food_detail'),
    path('food/<int:pk>/wishlist/', views.wishlist_toggle, name='wishlist_toggle'),
    path('chef/dashboard/', views.chef_dashboard, name='chef_dashboard'),
    path('chef/food/add/', views.chef_food_manage, name='chef_food_add'),
    path('chef/food/<int:pk>/edit/', views.chef_food_manage, name='chef_food_edit'),
    path('chef/order/<str:order_id>/status/', views.chef_order_status_update, name='chef_order_status_update'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
]
