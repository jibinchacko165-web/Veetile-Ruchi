from django.db import models
from django.conf import settings
from orders.models import Order
from accounts.models import DeliveryBoyProfile

class DeliveryAssignment(models.Model):
    STATUS_CHOICES = (
        ('assigned', 'Assigned'),
        ('picked_up', 'Picked Up'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
    )
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='delivery_assignment')
    delivery_boy = models.ForeignKey(DeliveryBoyProfile, on_delete=models.CASCADE, related_name='assignments')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='assigned')
    
    assigned_at = models.DateTimeField(auto_now_add=True)
    picked_up_at = models.DateTimeField(blank=True, null=True)
    out_for_delivery_at = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    # AI/ML predicted values vs actual
    predicted_delivery_time = models.FloatField(default=30.0) # predicted delivery time in minutes
    actual_delivery_time = models.FloatField(blank=True, null=True) # actual duration in minutes

    def __str__(self):
        return f"Assignment: Order {self.order.order_id} assigned to {self.delivery_boy.user.username}"

class GPSLocationTracking(models.Model):
    delivery_assignment = models.ForeignKey(DeliveryAssignment, on_delete=models.CASCADE, related_name='breadcrumbs')
    latitude = models.FloatField()
    longitude = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Breadcrumb for Order {self.delivery_assignment.order.order_id} at {self.timestamp}"

class DeliveryFeedback(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='delivery_feedback')
    delivery_assignment = models.ForeignKey(DeliveryAssignment, on_delete=models.CASCADE, related_name='feedbacks')
    delivery_boy = models.ForeignKey(DeliveryBoyProfile, on_delete=models.CASCADE, related_name='feedbacks')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='submitted_delivery_feedbacks')
    rating = models.PositiveIntegerField(default=5)
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Feedback for Order #{self.order.order_id} - {self.rating}★ by {self.customer.username}"

class DeliverySetting(models.Model):
    """
    Configurable Delivery Center & Service Area Perimeter settings managed by Admin/Staff.
    """
    name = models.CharField(max_length=120, default='Central Kitchen Hub (Kanjirappally)')
    address = models.CharField(max_length=255, default='Kanjirappally Town, Kottayam, Kerala')
    latitude = models.FloatField(default=9.5564)
    longitude = models.FloatField(default=76.7909)
    max_delivery_radius_km = models.FloatField(default=20.0)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Delivery Service Area Setting'
        verbose_name_plural = 'Delivery Service Area Settings'

    @classmethod
    def get_settings(cls):
        setting = cls.objects.filter(is_active=True).first()
        if not setting:
            setting = cls.objects.first()
        if not setting:
            setting = cls.objects.create(
                name='Central Kitchen Hub (Kanjirappally)',
                address='Kanjirappally Town, Kottayam, Kerala',
                latitude=9.5564,
                longitude=76.7909,
                max_delivery_radius_km=20.0,
                is_active=True
            )
        return setting

    def __str__(self):
        return f"{self.name} (Radius: {self.max_delivery_radius_km} km)"
