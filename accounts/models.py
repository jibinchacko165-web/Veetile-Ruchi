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
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer')
    phone = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True, default='')
    latitude = models.FloatField(default=10.0)
    longitude = models.FloatField(default=76.0)
    dob = models.DateField(blank=True, null=True, verbose_name="Date of Birth")

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

class ChefProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='chef_profile')
    specialty = models.CharField(max_length=100, blank=True, null=True)
    is_approved = models.BooleanField(default=False)
    rating = models.FloatField(default=5.0)

    def __str__(self):
        return f"Chef: {self.user.username}"

class DeliveryBoyProfile(models.Model):
    STATUS_CHOICES = (
        ('available', 'Available'),
        ('busy', 'Busy'),
        ('offline', 'Offline'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='delivery_boy_profile')
    vehicle_number = models.CharField(max_length=30, blank=True, null=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='available')
    rating = models.FloatField(default=5.0)
    current_latitude = models.FloatField(default=10.0)
    current_longitude = models.FloatField(default=76.0)

    def __str__(self):
        return f"Delivery Boy: {self.user.username} ({self.status})"

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
