import string
import random
from django.db import models
from django.conf import settings
from food.models import FoodItem

class Wishlist(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wishlist')
    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE, related_name='wished_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'food_item')

    def __str__(self):
        return f"{self.user.username} - {self.food_item.name} Wish"

class CartItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cart')
    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE, related_name='in_carts')
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.food_item.name} x{self.quantity}"

class Coupon(models.Model):
    code = models.CharField(max_length=20, unique=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    min_purchase_amount = models.DecimalField(max_digits=8, decimal_places=2, default=100.00)
    is_active = models.BooleanField(default=True)
    expiry_date = models.DateField()

    def __str__(self):
        return f"{self.code} ({self.discount_percentage}% off)"

class Order(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('preparing', 'Preparing'),
        ('ready_pickup', 'Ready for Pickup'),
        ('assigned', 'Assigned'),
        ('picked_up', 'Picked Up'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    )
    # Custom Alphanumeric Order ID as Primary Key
    order_id = models.CharField(max_length=20, primary_key=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # GPS Location Capture at time of order
    latitude = models.FloatField(default=9.462534)
    longitude = models.FloatField(default=76.72185)
    delivery_address = models.TextField(blank=True, null=True, default='')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.order_id:
            # Generate a unique Order ID: VR-YYYYMMDD-XXXX where XXXX is random letters/numbers
            from django.utils.timezone import now
            date_str = now().strftime('%Y%m%d')
            random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            self.order_id = f"VR-{date_str}-{random_str}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order {self.order_id} ({self.status})"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=8, decimal_places=2)

    def __str__(self):
        return f"{self.food_item.name} x {self.quantity} for Order {self.order.order_id}"

class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = (
        ('cod', 'Cash On Delivery'),
        ('upi', 'UPI Payment'),
    )
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    )
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment')
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES, default='cod')
    transaction_id = models.CharField(max_length=50, blank=True, null=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment of {self.amount} for Order {self.order.order_id} - {self.status}"

class Notification(models.Model):
    TYPE_CHOICES = (
        ('order_confirmed', 'Order Confirmed'),
        ('order_preparing', 'Order Preparing'),
        ('order_ready', 'Order Ready'),
        ('out_for_delivery', 'Out for Delivery'),
        ('order_delivered', 'Order Delivered'),
        ('staff_delivery_alert', 'Staff Delivery Alert'),
        ('general', 'General'),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    title = models.CharField(max_length=100)
    message = models.TextField()
    notification_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default='general')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.notification_type}] {self.title} → {self.user.username}"
