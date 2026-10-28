from django.contrib import admin
from .models import CartItem, Coupon, Order, OrderItem, Payment, Wishlist, Notification, ChefFeedback

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('user', 'food_item', 'quantity', 'created_at')

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_percentage', 'min_purchase_amount', 'is_active', 'expiry_date')
    list_filter = ('is_active',)

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'user', 'total_amount', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('order_id', 'user__username', 'delivery_address')
    inlines = [OrderItemInline]

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('order', 'payment_method', 'transaction_id', 'razorpay_order_id', 'amount', 'status', 'created_at')
    list_filter = ('payment_method', 'status')
    search_fields = ('transaction_id', 'razorpay_order_id', 'razorpay_payment_id', 'order__order_id')
    readonly_fields = ('created_at',)

@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('user', 'food_item', 'created_at')

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'notification_type', 'title', 'is_read', 'created_at')
    list_filter = ('is_read', 'notification_type', 'created_at')
    search_fields = ('user__username', 'title', 'message')

@admin.register(ChefFeedback)
class ChefFeedbackAdmin(admin.ModelAdmin):
    list_display = ('order', 'chef', 'customer', 'rating', 'taste_rating', 'freshness_rating', 'packaging_rating', 'is_moderated', 'is_hidden_by_admin', 'created_at')
    list_filter = ('rating', 'is_moderated', 'is_hidden_by_admin', 'created_at')
    search_fields = ('order__order_id', 'chef__username', 'customer__username', 'comment', 'problem_reported')
    list_editable = ('is_moderated', 'is_hidden_by_admin')
    readonly_fields = ('order', 'chef', 'customer', 'branch', 'rating', 'taste_rating', 'freshness_rating', 'packaging_rating', 'comment', 'problem_reported', 'created_at', 'updated_at')


