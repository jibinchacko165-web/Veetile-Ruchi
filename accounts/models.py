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
    latitude = models.FloatField(default=10.0)
    longitude = models.FloatField(default=76.0)
    dob = models.DateField(blank=True, null=True, verbose_name="Date of Birth")

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

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

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
        ('on_delivery', 'On Delivery'),
        ('busy', 'On Delivery'),
        ('offline', 'Offline'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='delivery_boy_profile')
    vehicle_number = models.CharField(max_length=30, blank=True, null=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='available', db_index=True)
    rating = models.FloatField(default=5.0)
    current_latitude = models.FloatField(default=10.0)
    current_longitude = models.FloatField(default=76.0)

    def __str__(self):
        return f"Delivery Boy: {self.user.username} ({self.get_status_display()})"

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

