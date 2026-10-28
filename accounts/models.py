from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    ROLE_CHOICES = (
        ('customer', 'Customer'),
        ('chef', 'Chef'),
        ('staff', 'Staff'),
        ('delivery_boy', 'Delivery Boy'),
        ('admin', 'Administrator'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer', db_index=True)
    phone = models.CharField(max_length=15, blank=True, null=True, db_index=True)
    address = models.TextField(blank=True, null=True, default='')
    latitude = models.FloatField(default=9.462534)
    longitude = models.FloatField(default=76.72185)
    dob = models.DateField(blank=True, null=True, verbose_name="Date of Birth")
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)

    @property
    def is_customer(self):
        return self.role == 'customer'

    @property
    def is_chef(self):
        return self.role == 'chef'

    @property
    def is_delivery_boy(self):
        return self.role == 'delivery_boy'

    @property
    def is_staff_member(self):
        return self.role == 'staff' or self.is_staff

    @property
    def is_admin_user(self):
        return self.role == 'admin' or self.is_superuser

    def clean(self):
        super().clean()
        if self.email:
            from .validators import validate_custom_email
            validate_custom_email(self.email)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    @property
    def has_valid_coordinates(self):
        try:
            return self.latitude is not None and self.longitude is not None and -90.0 <= float(self.latitude) <= 90.0 and -180.0 <= float(self.longitude) <= 180.0
        except (ValueError, TypeError):
            return False

class SavedLocation(models.Model):
    LOCATION_TYPE_CHOICES = (
        ('home', 'Home'),
        ('work', 'Work / Office'),
        ('parents', "Parent's House"),
        ('landmark', 'Nearby Landmark / Junction'),
        ('other', 'Other'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_locations')
    name = models.CharField(max_length=100)
    location_type = models.CharField(max_length=20, choices=LOCATION_TYPE_CHOICES, default='home')
    description = models.TextField(blank=True, null=True, help_text="House name, building, street, or flat number")
    landmark = models.CharField(max_length=150, blank=True, null=True, help_text="Nearby shop, temple, church, hospital, or bus stop")
    district = models.ForeignKey('delivery.District', on_delete=models.SET_NULL, null=True, blank=True, related_name='saved_locations')
    latitude = models.FloatField(default=9.462534)
    longitude = models.FloatField(default=76.72185)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', '-created_at']

    def save(self, *args, **kwargs):
        # If marked as default, unset other default locations for this user
        if self.is_default:
            SavedLocation.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        # If user has no other saved locations, make this default automatically
        elif not SavedLocation.objects.filter(user=self.user).exclude(pk=self.pk).exists():
            self.is_default = True
        super().save(*args, **kwargs)

    def __str__(self):
        default_str = " [Default]" if self.is_default else ""
        return f"{self.name} ({self.get_location_type_display()}){default_str} - {self.user.username}"

    @property
    def has_valid_coordinates(self):
        try:
            return self.latitude is not None and self.longitude is not None and -90.0 <= float(self.latitude) <= 90.0 and -180.0 <= float(self.longitude) <= 180.0
        except (ValueError, TypeError):
            return False

class ChefProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='chef_profile')
    specialty = models.CharField(max_length=100, blank=True, null=True)
    kitchen_name = models.CharField(max_length=150, blank=True, null=True, default='')
    kitchen_address = models.TextField(blank=True, null=True, default='')
    experience_years = models.PositiveIntegerField(default=1)
    bio = models.TextField(blank=True, null=True, default='')
    is_approved = models.BooleanField(default=False, db_index=True)
    rating = models.FloatField(default=5.0)

    def __str__(self):
        status_str = 'Approved' if self.is_approved else 'Pending Approval'
        return f"Chef: {self.user.username} ({status_str})"

class DeliveryBoyProfile(models.Model):
    STATUS_CHOICES = (
        ('available', 'Available'),
        ('on_delivery', 'Busy (currently delivering an order)'),
        ('busy', 'Busy (currently delivering an order)'),
        ('offline', 'Offline'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='delivery_boy_profile')
    vehicle_number = models.CharField(max_length=30, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available', db_index=True)
    rating = models.FloatField(default=5.0)
    current_latitude = models.FloatField(default=9.5564)
    current_longitude = models.FloatField(default=76.7909)

    @property
    def courier_number(self):
        """Returns 'Courier X' for the profile based on user username or phone."""
        USER_MAP = {
            'courier1': 'Courier 1',
            'courier2': 'Courier 2',
            'courier3': 'Courier 3',
            'courier4': 'Courier 4',
            'courier5': 'Courier 5',
            'courier': 'Courier 5',
            'courier6': 'Courier 6',
            'courier7': 'Courier 7',
            'courier8': 'Courier 8',
            'courier9': 'Courier 9',
        }
        PHONE_MAP = {
            '7510672351': 'Courier 1',
            '7510672352': 'Courier 2',
            '7510672353': 'Courier 3',
            '7510672354': 'Courier 4',
            '7510672355': 'Courier 5',
            '7510672356': 'Courier 6',
            '7510672357': 'Courier 7',
            '7510672358': 'Courier 8',
            '7510672359': 'Courier 9',
        }
        if not self.user:
            return "Courier"
        u = self.user.username.lower()
        if u in USER_MAP:
            return USER_MAP[u]
        if self.user.phone in PHONE_MAP:
            return PHONE_MAP[self.user.phone]
        full = self.user.get_full_name().strip()
        if "Courier" in full:
            return full
        for i in range(1, 10):
            if f"courier{i}" in u or f"courier {i}" in full.lower():
                return f"Courier {i}"
        return f"Courier {self.id}"

    @property
    def courier_name(self):
        return self.courier_number

    @property
    def courier_username(self):
        if not self.user:
            return ""
        u = self.user.username.lower()
        if u == 'courier':
            return 'courier5'
        if self.user.phone == '7510672355':
            return 'courier5'
        return self.user.username

    @property
    def realtime_status(self):
        """
        Returns one of the 3 real-time statuses required by prompt:
        - 'Offline'
        - 'Busy (currently delivering an order)'
        - 'Available'
        """
        if self.status == 'offline':
            return 'Offline'
        
        # Check if courier has any active delivery assignment in progress
        has_active = hasattr(self, 'assignments') and self.assignments.filter(
            status__in=['assigned', 'picked_up', 'in_transit'],
            is_active=True
        ).exists()
        if self.status in ['on_delivery', 'busy'] or has_active:
            return 'Busy (currently delivering an order)'
        return 'Available'

    @property
    def realtime_status_display(self):
        return self.realtime_status

    @property
    def is_available(self):
        return self.realtime_status == 'Available'

    @property
    def is_busy(self):
        return self.realtime_status == 'Busy (currently delivering an order)'

    @property
    def is_offline(self):
        return self.realtime_status == 'Offline'

    @property
    def active_assignment(self):
        if hasattr(self, 'assignments'):
            return self.assignments.filter(
                status__in=['assigned', 'picked_up', 'in_transit'],
                is_active=True
            ).select_related('order').first()
        return None

    def __str__(self):
        return f"{self.courier_name} ({self.user.username}): {self.realtime_status}"

class PasswordResetOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_otps')
    otp_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    attempts = models.PositiveIntegerField(default=0)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"OTP for {self.user.email}"


