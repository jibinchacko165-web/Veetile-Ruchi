from django.contrib import admin
from .models import DeliveryAssignment, GPSLocationTracking, DeliveryFeedback

@admin.register(DeliveryAssignment)
class DeliveryAssignmentAdmin(admin.ModelAdmin):
    list_display = ('order', 'delivery_boy', 'status', 'is_active', 'assigned_at', 'picked_up_at', 'out_for_delivery_at', 'delivered_at', 'predicted_delivery_time', 'actual_delivery_time')
    list_filter = ('status', 'is_active', 'assigned_at')
    search_fields = ('order__order_id', 'delivery_boy__user__username', 'delivery_boy__vehicle_number')

@admin.register(GPSLocationTracking)
class GPSLocationTrackingAdmin(admin.ModelAdmin):
    list_display = ('delivery_assignment', 'latitude', 'longitude', 'timestamp')
    search_fields = ('delivery_assignment__order__order_id',)

@admin.register(DeliveryFeedback)
class DeliveryFeedbackAdmin(admin.ModelAdmin):
    list_display = ('order', 'delivery_boy', 'customer', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('order__order_id', 'delivery_boy__user__username', 'customer__username')

