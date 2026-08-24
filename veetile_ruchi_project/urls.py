"""
URL configuration for veetile_ruchi_project project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from food import views as food_views
from accounts import views as account_views

# Custom Admin Site Header
admin.site.site_header = "Veetile-Ruchi – Django DB Administration"
admin.site.site_title = "VR DB Admin"
admin.site.index_title = "Database Model Administration"

urlpatterns = [
    # ───── Django Built-in DB Admin (Explicitly at /admin/) ─────
    path('admin/', admin.site.urls),

    # ───── Custom Veetile-Ruchi Admin Dashboard Routes ─────
    path('dashboard/', food_views.admin_dashboard, name='dashboard'),
    path('dashboard/<str:section>/', food_views.admin_dashboard, name='dashboard_section'),
    path('admin-dashboard/', food_views.admin_dashboard, name='admin_dashboard'),
    path('admin-dashboard/<str:section>/', food_views.admin_dashboard, name='admin_dashboard_section'),

    # ───── Direct Top-Level Auth Routes ─────
    path('login/', account_views.login_view, name='login_direct'),
    path('register/', account_views.register_view, name='register_direct'),
    path('logout/', account_views.logout_view, name='logout_direct'),

    # ───── Application URL Includes ─────
    path('accounts/', include('accounts.urls')),
    path('delivery/', include('delivery.urls')),
    path('orders/', include('orders.urls')),
    path('health/', include('health.urls')),
    path('ai/', include('ai_models.urls')),
    path('', include('food.urls')),  # Homepage & Catalog
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
