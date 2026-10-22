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
        ('pending', 'Order Confirmed'),
        ('preparing', 'Food Preparing'),
        ('ready_pickup', 'Food Prepared'),
        ('assigned', 'Courier Assigned'),
        ('picked_up', 'Food Picked Up'),
        ('in_transit', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    )
    # Custom Alphanumeric Order ID as Primary Key
    order_id = models.CharField(max_length=20, primary_key=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    branch = models.ForeignKey('delivery.HotelBranch', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    
    # GPS Location Capture at time of order
    latitude = models.FloatField(default=9.5564)
    longitude = models.FloatField(default=76.7909)
    delivery_address = models.TextField(blank=True, null=True, default='')
    customer_delivery_notes = models.TextField(blank=True, null=True, default='')
    internal_kitchen_notes = models.TextField(blank=True, null=True, default='')
    
    # Lifecycle Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    preparing_started_at = models.DateTimeField(null=True, blank=True)
    food_prepared_at = models.DateTimeField(null=True, blank=True)
    courier_assigned_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        is_new = not bool(self.order_id)
        old_status = None
        if not is_new:
            try:
                old_status = Order.objects.get(pk=self.pk).status
            except Order.DoesNotExist:
                pass

        if old_status and old_status != self.status:
            from django.utils import timezone
            now_ts = timezone.now()
            if self.status == 'preparing' and not self.preparing_started_at:
                self.preparing_started_at = now_ts
            elif self.status == 'ready_pickup' and not self.food_prepared_at:
                self.food_prepared_at = now_ts
            elif self.status == 'assigned' and not self.courier_assigned_at:
                self.courier_assigned_at = now_ts
            elif self.status == 'picked_up' and not self.picked_up_at:
                self.picked_up_at = now_ts

        if not self.order_id:
            # Generate a unique Order ID: VR-YYYYMMDD-XXXX where XXXX is random letters/numbers
            from django.utils import timezone
            now_ts = timezone.now()
            date_str = now_ts.strftime('%Y%m%d')
            random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            self.order_id = f"VR-{date_str}-{random_str}"
        super().save(*args, **kwargs)
        
        if old_status and old_status != self.status:
            self._send_status_email()

    def _send_status_email(self):
        from django.core.mail import send_mail
        from django.conf import settings
        
        subject = ''
        message = ''
        if self.status == 'preparing':
            subject = f"Order #{self.order_id} - Food Preparation Started"
            message = f"Hello {self.user.username},\n\nYour order #{self.order_id} has been accepted and is now being prepared by the kitchen!"
        elif self.status == 'ready_pickup':
            subject = f"Order #{self.order_id} - Food Prepared"
            message = f"Hello {self.user.username},\n\nYour food for order #{self.order_id} has been freshly prepared and is awaiting courier assignment."
        elif self.status == 'assigned':
            subject = f"Order #{self.order_id} - Courier Assigned"
            message = f"Hello {self.user.username},\n\nYour order #{self.order_id} has been assigned to a courier and is awaiting pickup from the kitchen."
        elif self.status == 'picked_up':
            subject = f"Order #{self.order_id} - Food Picked Up"
            message = f"Hello {self.user.username},\n\nYour order #{self.order_id} has been collected by the courier from the kitchen."
        elif self.status == 'in_transit':
            subject = f"Order #{self.order_id} - Order Dispatched"
            message = f"Hello {self.user.username},\n\nGood news! Your order #{self.order_id} has been dispatched and is out for delivery."
        elif self.status == 'delivered':
            subject = f"Order #{self.order_id} - Order Delivered"
            message = f"Hello {self.user.username},\n\nYour order #{self.order_id} has been successfully delivered. Enjoy your meal!"
        elif self.status == 'cancelled':
            subject = f"Order #{self.order_id} - Order Cancelled"
            message = f"Hello {self.user.username},\n\nUnfortunately, your order #{self.order_id} has been cancelled."
            
        if subject and message and self.user.email:
            try:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@veetileruchi.com'),
                    recipient_list=[self.user.email],
                    fail_silently=True,
                )
            except Exception:
                pass


    @property
    def formatted_delivery_address(self):
        if not self.delivery_address:
            return "Kanjirappally Service Area"
        addr = str(self.delivery_address).strip()
        
        landmark = ""
        if " | Landmark: " in addr:
            main_part, landmark = addr.split(" | Landmark: ", 1)
            addr = main_part.strip()
            landmark = landmark.strip()
        elif " • Landmark: " in addr:
            main_part, landmark = addr.split(" • Landmark: ", 1)
            addr = main_part.strip()
            landmark = landmark.strip()
        elif " (Landmark: " in addr:
            parts = addr.split(" (Landmark: ", 1)
            addr = parts[0].strip()
            landmark = parts[1].rstrip(")").strip()
            
        if ":" in addr:
            parts = addr.split(":", 1)
            name_part = parts[0].strip()
            desc_part = parts[1].strip()
            
            if desc_part and desc_part != name_part:
                clean_n = name_part.split("(")[0].strip()
                if clean_n and clean_n.lower() in desc_part.lower():
                    import re
                    addr = re.sub(re.escape(clean_n), name_part, desc_part, count=1, flags=re.IGNORECASE)
                else:
                    addr = f"{name_part}, {desc_part}"
            else:
                addr = name_part or desc_part

        if landmark and landmark.upper() != "N/A":
            addr = f"{addr} • Landmark: {landmark}"
            
        return addr

    @property
    def responsible_chef(self):
        """Returns the chef responsible for preparing this order's food items."""
        first_item = self.items.select_related('food_item__chef').first()
        if first_item and first_item.food_item and first_item.food_item.chef:
            return first_item.food_item.chef
        from accounts.models import User
        return User.objects.filter(role='chef').first()

    @property
    def assigned_courier(self):
        """Returns the assigned DeliveryBoyProfile for this order if present."""
        if hasattr(self, 'delivery_assignment') and self.delivery_assignment:
            return self.delivery_assignment.delivery_boy
        return None

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


class ChefFeedback(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='chef_feedback')
    chef = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_chef_feedbacks')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='submitted_chef_feedbacks')
    branch = models.ForeignKey('delivery.HotelBranch', on_delete=models.SET_NULL, null=True, blank=True, related_name='chef_feedbacks')
    
    # 1-5 Star Ratings
    rating = models.PositiveIntegerField(default=5, help_text="Overall food/chef rating (1-5)")
    taste_rating = models.PositiveIntegerField(default=5, help_text="Food taste and quality rating (1-5)")
    freshness_rating = models.PositiveIntegerField(default=5, help_text="Freshness and preparation rating (1-5)")
    packaging_rating = models.PositiveIntegerField(default=5, help_text="Packaging and presentation rating (1-5)")
    
    comment = models.TextField(blank=True, null=True, max_length=1000)
    problem_reported = models.TextField(blank=True, null=True, max_length=1000, help_text="Optional food-quality or service-problem report")
    
    # Moderation & Audit History
    is_moderated = models.BooleanField(default=False)
    moderation_notes = models.TextField(blank=True, null=True)
    is_hidden_by_admin = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Chef Feedback for Order #{self.order.order_id} - {self.rating}★ by {self.customer.username}"
