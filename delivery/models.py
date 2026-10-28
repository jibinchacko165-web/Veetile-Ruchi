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
    
    # 1-5 Star Ratings
    rating = models.PositiveIntegerField(default=5, help_text="Overall delivery rating (1-5)")
    timeliness_rating = models.PositiveIntegerField(default=5, help_text="Timeliness rating (1-5)")
    behavior_rating = models.PositiveIntegerField(default=5, help_text="Courier behavior and communication rating (1-5)")
    food_handling_rating = models.PositiveIntegerField(default=5, help_text="Food handling and delivery condition rating (1-5)")
    
    comment = models.TextField(blank=True, null=True, max_length=1000)
    
    # Moderation & Audit History
    is_moderated = models.BooleanField(default=False)
    moderation_notes = models.TextField(blank=True, null=True)
    is_hidden_by_admin = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Delivery Feedback for Order #{self.order.order_id} - {self.rating}★ by {self.customer.username}"

class District(models.Model):
    name = models.CharField(max_length=60, unique=True, db_index=True)
    code = models.SlugField(max_length=40, unique=True, db_index=True)
    latitude = models.FloatField(help_text="Center latitude for map alignment")
    longitude = models.FloatField(help_text="Center longitude for map alignment")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Kerala District'
        verbose_name_plural = 'Kerala Districts'

    def __str__(self):
        return self.name

class HotelBranch(models.Model):
    OPERATING_STATUS_CHOICES = (
        ('open', 'Open for Orders'),
        ('busy', 'Temporarily Busy'),
        ('closed', 'Closed'),
    )

    name = models.CharField(max_length=150, help_text="Hotel or Kitchen Branch Name")
    district = models.ForeignKey(District, on_delete=models.CASCADE, related_name='hotel_branches')
    address = models.CharField(max_length=255)
    latitude = models.FloatField(help_text="Verified branch latitude")
    longitude = models.FloatField(help_text="Verified branch longitude")
    max_delivery_radius_km = models.FloatField(default=30.0, help_text="Configured delivery radius in km (max 30.0 km)")
    is_active = models.BooleanField(default=True, db_index=True)
    is_central_hub = models.BooleanField(default=False, help_text="Indicates primary central kitchen hub")
    phone = models.CharField(max_length=25, blank=True, null=True, default='')
    opening_time = models.TimeField(default='07:00:00')
    closing_time = models.TimeField(default='22:00:00')
    operating_status = models.CharField(max_length=20, choices=OPERATING_STATUS_CHOICES, default='open')
    available_food_items = models.ManyToManyField(
        'food.FoodItem',
        blank=True,
        related_name='serving_branches',
        help_text="Items available at this branch. Leave blank to serve full master catalog."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_central_hub', 'district__name', 'name']
        verbose_name = 'Hotel / Kitchen Branch'
        verbose_name_plural = 'Hotel & Kitchen Branches'

    def __str__(self):
        hub_str = " (Central Hub)" if self.is_central_hub else ""
        return f"{self.name} [{self.district.name}]{hub_str}"

    @property
    def has_valid_coordinates(self):
        try:
            return self.latitude is not None and self.longitude is not None and -90.0 <= float(self.latitude) <= 90.0 and -180.0 <= float(self.longitude) <= 180.0
        except (ValueError, TypeError):
            return False

    @property
    def effective_radius_km(self):
        """Enforces delivery radius ceiling of 30.0 km while respecting stricter configured radius."""
        return min(float(self.max_delivery_radius_km or 30.0), 30.0)

    def calculate_distance(self, lat, lon):
        from orders.utils import calculate_distance_km
        return calculate_distance_km(self.latitude, self.longitude, lat, lon)

    def is_delivery_eligible(self, customer_lat, customer_lon):
        dist = self.calculate_distance(customer_lat, customer_lon)
        return (dist <= self.effective_radius_km), dist

    def is_open_now(self, current_time=None):
        if not self.is_active or self.operating_status != 'open':
            return False
        if current_time is None:
            from django.utils import timezone
            current_time = timezone.localtime().time()
        if self.opening_time <= self.closing_time:
            return self.opening_time <= current_time <= self.closing_time
        return current_time >= self.opening_time or current_time <= self.closing_time

    def get_menu_items(self):
        """Returns food items available from this branch."""
        from food.models import FoodItem
        custom_items = self.available_food_items.filter(is_available=True)
        if custom_items.exists():
            return custom_items
        return FoodItem.objects.filter(is_available=True)


class DeliverySetting(models.Model):
    """
    Configurable Delivery Center & Service Area Perimeter settings managed by Admin/Staff.
    """
    name = models.CharField(max_length=120, default='Central Kitchen Hub (Kanjirappally)')
    address = models.CharField(max_length=255, default='Kanjirappally Town, Kottayam, Kerala')
    latitude = models.FloatField(default=9.5564)
    longitude = models.FloatField(default=76.7909)
    max_delivery_radius_km = models.FloatField(default=30.0)
    is_active = models.BooleanField(default=True)
    branch = models.ForeignKey(HotelBranch, on_delete=models.SET_NULL, null=True, blank=True, related_name='delivery_settings')
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
                max_delivery_radius_km=30.0,
                is_active=True
            )
        return setting

    def __str__(self):
        return f"{self.name} (Radius: {self.max_delivery_radius_km} km)"
