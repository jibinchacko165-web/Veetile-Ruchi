from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
import secrets
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings
from django.db.models import Q
from .models import User, ChefProfile, DeliveryBoyProfile
from health.models import HealthProfile
from orders.models import Notification

def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        dob = request.POST.get('dob')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        role = request.POST.get('role', 'customer')
        phone = request.POST.get('phone', '')
        try:
            latitude = float(request.POST.get('latitude', '') or 10.0)
        except (ValueError, TypeError):
            latitude = 10.0
        try:
            longitude = float(request.POST.get('longitude', '') or 76.0)
        except (ValueError, TypeError):
            longitude = 76.0

        form_data = {
            'username': username,
            'email': email,
            'dob': dob,
            'role': role,
            'phone': phone,
            'specialty': request.POST.get('specialty', ''),
            'vehicle_number': request.POST.get('vehicle_number', ''),
            'latitude': latitude,
            'longitude': longitude,
        }

        if not dob:
            messages.error(request, "Date of Birth is required.")
            return render(request, 'accounts/register.html', {'form_data': form_data})

        if confirm_password and password != confirm_password:
            messages.error(request, "Passwords do not match. Please enter matching passwords.")
            return render(request, 'accounts/register.html', {'form_data': form_data})

        if len(password) < 6:
            messages.error(request, "Password must be at least 6 characters long.")
            return render(request, 'accounts/register.html', {'form_data': form_data})

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists. Please choose a different username.")
            return render(request, 'accounts/register.html', {'form_data': form_data})

        import re
        clean_phone = re.sub(r'\D', '', phone)
        if role == 'delivery_boy' and not clean_phone:
            messages.error(request, "Phone number is required for Delivery Personnel registration.")
            return render(request, 'accounts/register.html', {'form_data': form_data})

        if clean_phone:
            if not re.match(r'^[6-9]\d{9}$', clean_phone):
                messages.error(request, "Please enter a valid 10-digit mobile phone number (e.g. 9876543210).")
                return render(request, 'accounts/register.html', {'form_data': form_data})

            if User.objects.filter(phone=clean_phone).exists():
                messages.error(request, "This phone number is already assigned to another Courier / user account.")
                return render(request, 'accounts/register.html', {'form_data': form_data})

        user = User.objects.create_user(
            username=username,
            email=email,
            dob=dob,
            password=password,
            role=role,
            phone=clean_phone if clean_phone else phone,
            address='',
            latitude=latitude,
            longitude=longitude
        )

        # Create role-specific profiles
        if role == 'chef':
            ChefProfile.objects.create(user=user, specialty=request.POST.get('specialty', 'All Rounder'), is_approved=True)
        elif role == 'delivery_boy':
            DeliveryBoyProfile.objects.create(
                user=user, 
                vehicle_number=request.POST.get('vehicle_number', 'KL-01-A-1234'), 
                current_latitude=latitude, 
                current_longitude=longitude
            )
        elif role == 'customer':
            # Create default empty health profile
            HealthProfile.objects.create(user=user)

        # Do not automatically log in user upon registration
        request.session['prefill_username'] = username
        messages.success(request, f"Registration successful for '{username}'! Please enter your password to sign in.")
        return redirect(f"{reverse('login')}?username={username}")
        
    return render(request, 'accounts/register.html')

def login_view(request):
    prefilled_username = request.GET.get('username', '').strip() or request.session.pop('prefill_username', '')

    if request.method == 'POST':
        identifier = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        user = authenticate(username=identifier, password=password)
        if user is None and identifier:
            user_obj = User.objects.filter(Q(username__iexact=identifier) | Q(email__iexact=identifier)).first()
            if user_obj:
                user = authenticate(username=user_obj.username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect('dashboard_redirect')
        else:
            messages.error(request, "Invalid username/email or password.")
            return render(request, 'accounts/login.html', {'prefilled_username': identifier})
            
    return render(request, 'accounts/login.html', {'prefilled_username': prefilled_username})

def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('login')

@login_required
def dashboard_redirect(request):
    """Redirects the user to their respective dashboard depending on their role."""
    role = request.user.role
    if role == 'customer':
        return redirect('food_catalog')
    elif role == 'chef':
        return redirect('chef_dashboard')
    elif role == 'staff':
        return redirect('staff_dashboard')
    elif role == 'delivery_boy':
        return redirect('delivery_boy_dashboard')
    elif role == 'admin':
        return redirect('admin_dashboard')
    return redirect('food_catalog')

@login_required
def profile_view(request):
    if request.method == 'POST':
        try:
            phone_input = request.POST.get('phone', '').strip()
            if phone_input:
                import re
                clean_phone = re.sub(r'\D', '', phone_input)
                if not re.match(r'^[6-9]\d{9}$', clean_phone):
                    messages.error(request, "Please enter a valid 10-digit mobile phone number (e.g. 9876543210).")
                    return redirect('profile')
                if User.objects.filter(phone=clean_phone).exclude(id=request.user.id).exists():
                    messages.error(request, "This phone number is already assigned to another Courier / user account.")
                    return redirect('profile')
                request.user.phone = clean_phone

            try:
                request.user.latitude = float(request.POST.get('latitude', '') or request.user.latitude)
            except (ValueError, TypeError):
                pass
            try:
                request.user.longitude = float(request.POST.get('longitude', '') or request.user.longitude)
            except (ValueError, TypeError):
                pass
            request.user.save()
            
            # update coordinates in delivery boy profile if applicable
            if request.user.role == 'delivery_boy' and hasattr(request.user, 'delivery_boy_profile'):
                profile = request.user.delivery_boy_profile
                profile.current_latitude = request.user.latitude
                profile.current_longitude = request.user.longitude
                profile.save()
            messages.success(request, "Profile updated successfully.")
        except Exception as e:
            messages.error(request, f"Error updating profile: {str(e)}")
        return redirect('profile')
        
    return render(request, 'accounts/profile.html')

@login_required
def notifications_view(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'accounts/notifications.html', {'notifications': notifications})

@login_required
def mark_notification_read(request, notif_id):
    try:
        notif = Notification.objects.get(id=notif_id, user=request.user)
        notif.is_read = True
        notif.save()
        if notif.order:
            return redirect('order_tracking', order_id=notif.order.order_id)
    except Notification.DoesNotExist:
        pass
    return redirect('notifications')

def password_reset_view(request):
    """
    Forgot Password recovery view using Email Address and Date of Birth (DOB) verification.
    Step 1: User enters Registered Email Address and Date of Birth.
    Step 2: If credentials match a registered user, user enters and confirms a new password.
    """
    step = 'verify'
    verified_user = None

    reset_user_id = request.session.get('reset_user_id')
    if reset_user_id:
        try:
            verified_user = User.objects.get(pk=reset_user_id)
            step = 'reset'
        except User.DoesNotExist:
            request.session.pop('reset_user_id', None)
            reset_user_id = None

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'verify' or 'dob' in request.POST:
            email = request.POST.get('email', '').strip()
            dob_str = request.POST.get('dob', '').strip()

            if not email or not dob_str:
                messages.error(request, "Please enter both your registered email address and Date of Birth.")
                return render(request, 'accounts/password_reset.html', {'step': 'verify', 'email': email, 'dob': dob_str})

            # Verify registered user using email and DOB
            user = User.objects.filter(email__iexact=email, dob=dob_str).first()
            
            if user:
                request.session['reset_user_id'] = user.id
                messages.success(request, f"Identity verified for account '{user.username}'! Please enter your new password below.")
                return render(request, 'accounts/password_reset.html', {'step': 'reset', 'verified_user': user})
            else:
                request.session.pop('reset_user_id', None)
                messages.error(request, "Invalid Email Address or Date of Birth. Verification failed. Please check your details and try again.")
                return render(request, 'accounts/password_reset.html', {'step': 'verify', 'email': email, 'dob': dob_str})

        elif action == 'reset' or ('new_password' in request.POST and 'confirm_password' in request.POST):
            if not verified_user:
                messages.error(request, "Session expired or verification required. Please verify your details first.")
                return render(request, 'accounts/password_reset.html', {'step': 'verify'})

            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')

            if not new_password or not confirm_password:
                messages.error(request, "Please enter both new password fields.")
                return render(request, 'accounts/password_reset.html', {'step': 'reset', 'verified_user': verified_user})

            if new_password != confirm_password:
                messages.error(request, "Passwords do not match. Please re-enter matching passwords.")
                return render(request, 'accounts/password_reset.html', {'step': 'reset', 'verified_user': verified_user})

            if len(new_password) < 6:
                messages.error(request, "Password must be at least 6 characters long.")
                return render(request, 'accounts/password_reset.html', {'step': 'reset', 'verified_user': verified_user})

            # Securely update user password
            target_username = verified_user.username
            verified_user.set_password(new_password)
            verified_user.save()

            # Clear recovery session key
            request.session.pop('reset_user_id', None)

            messages.success(request, f"Password for account '{target_username}' updated successfully! Please sign in with your new password.")
            return redirect(f"{reverse('login')}?username={target_username}")

    return render(request, 'accounts/password_reset.html', {'step': step, 'verified_user': verified_user})


def password_reset_cancel_view(request):
    """Clears reset session state and returns to verification step."""
    request.session.pop('reset_user_id', None)
    return redirect('password_reset')


def csrf_failure_view(request, reason=""):
    """Custom CSRF failure handler to refresh token and redirect safely without 403 error page."""
    messages.warning(request, "Security token refreshed. Please submit your request again.")
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('food_catalog')
