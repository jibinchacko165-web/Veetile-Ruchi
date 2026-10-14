from django.contrib import admin
from .models import DeliveryAssignment, GPSLocationTracking, DeliveryFeedback, District, HotelBranch, DeliverySetting

@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'latitude', 'longitude', 'is_active', 'branch_count', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')
    ordering = ('name',)

    def branch_count(self, obj):
        return obj.branches.count()
    branch_count.short_description = 'Registered Branches'

@admin.register(HotelBranch)
class HotelBranchAdmin(admin.ModelAdmin):
    list_display = ('name', 'district', 'operating_status', 'is_active', 'is_central_hub', 'effective_radius_display', 'latitude', 'longitude', 'phone')
    list_filter = ('district', 'operating_status', 'is_active', 'is_central_hub')
    search_fields = ('name', 'address', 'district__name', 'phone')
    filter_horizontal = ('available_food_items',)
    readonly_fields = ('created_at', 'updated_at')

    def effective_radius_display(self, obj):
        return f"{obj.effective_radius_km} km (configured: {obj.max_delivery_radius_km} km)"
    effective_radius_display.short_description = 'Delivery Radius'

@admin.register(DeliverySetting)
class DeliverySettingAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'latitude', 'longitude', 'max_delivery_radius_km', 'is_active', 'branch', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'address')

