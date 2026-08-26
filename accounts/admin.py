from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, ChefProfile, DeliveryBoyProfile

@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'role', 'phone', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Custom Profile Info', {'fields': ('role', 'phone', 'address', 'latitude', 'longitude')}),
    )

@admin.register(ChefProfile)
class ChefProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'kitchen_name', 'specialty', 'is_approved', 'rating')
    list_filter = ('is_approved',)
    search_fields = ('user__username', 'kitchen_name', 'specialty')

@admin.register(DeliveryBoyProfile)
class DeliveryBoyProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'vehicle_number', 'status', 'current_latitude', 'current_longitude')
    list_filter = ('status',)
