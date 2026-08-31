from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
import secrets
import re
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
from .decorators import role_required
from health.models import HealthProfile
from orders.models import Notification

def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        dob = request.POST.get('dob', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        role = request.POST.get('role', 'customer')
        phone = request.POST.get('phone', '').strip()
        
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
            'kitchen_name': request.POST.get('kitchen_name', ''),
            'vehicle_number': request.POST.get('vehicle_number', ''),
            'latitude': latitude,
            'longitude': longitude,
        }

        parsed_dob = None
        if not dob:
            messages.error(request, "Date of Birth is required.")
            return render(request, 'accounts/register.html', {'form_data': form_data})
        else:
            try:
                parts = dob.split('-')
                if len(parts) != 3 or len(parts[0]) != 4:
                    raise ValueError("Year must be a 4-digit number.")
                year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                from datetime import date
                parsed_dob = date(year, month, day)
                today = timezone.now().date()
                if parsed_dob.year < 1900 or parsed_dob > today:
                    messages.error(request, "Please enter a valid Date of Birth (between 1900 and today).")
                    return render(request, 'accounts/register.html', {'form_data': form_data})
            except (ValueError, TypeError):
                messages.error(request, "Invalid Date of Birth format. Please select a valid date in YYYY-MM-DD format (e.g. 2003-10-10).")
                return render(request, 'accounts/register.html', {'form_data': form_data})

        if confirm_password and password != confirm_password:
            messages.error(request, "Passwords do not match. Please enter matching passwords.")
            return render(request, 'accounts/register.html', {'form_data': form_data})

        if len(password) < 6:
            messages.error(request, "Password must be at least 6 characters long.")
            return render(request, 'accounts/register.html', {'form_data': form_data})

        if User.objects.filter(username__iexact=username).exists():
            messages.error(request, "Username already exists. Please choose a different username.")
            return render(request, 'accounts/register.html', {'form_data': form_data})

        if email and User.objects.filter(email__iexact=email).exists():
            messages.error(request, "An account with this email address already exists. Please sign in or use a different email.")
            return render(request, 'accounts/register.html', {'form_data': form_data})

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

        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                dob=parsed_dob,
                password=password,
                role=role,
                phone=clean_phone if clean_phone else phone,
                address='',
                latitude=latitude,
                longitude=longitude
            )
        except Exception as e:
            messages.error(request, f"Registration could not be completed: {str(e)}")
            return render(request, 'accounts/register.html', {'form_data': form_data})

        # Create role-specific profiles
        if role == 'chef':
            specialty = request.POST.get('specialty', 'Kerala Cuisine').strip() or 'Kerala Cuisine'
            kitchen_name = request.POST.get('kitchen_name', f"{username}'s Kitchen").strip() or f"{username}'s Kitchen"
            ChefProfile.objects.create(
                user=user, 
                specialty=specialty, 
                kitchen_name=kitchen_name,
                is_approved=False  # Requires Admin/Staff approval workflow
            )
        elif role == 'delivery_boy':
            vehicle_num = request.POST.get('vehicle_number', 'KL-01-A-1234').strip() or 'KL-01-A-1234'
            DeliveryBoyProfile.objects.create(
                user=user, 
                vehicle_number=vehicle_num, 
                status='available',
                current_latitude=latitude, 
                current_longitude=longitude
            )
        elif role == 'customer':
            HealthProfile.objects.create(user=user)

        request.session['prefill_username'] = username
        messages.success(request, f"Registration successful for '{username}'! Please enter your password to sign in.")
        return redirect(f"{reverse('login')}?username={username}")
        
    return render(request, 'accounts/register.html')

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')

    prefilled_username = request.GET.get('username', '').strip()

    if request.method == 'POST':
        identifier = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if not identifier or not password:
            messages.error(request, "Invalid username/email or password.")
            return render(request, 'accounts/login.html', {'prefilled_username': identifier})

        # 1. Try direct authentication (supports username & backend email matching)
        user = authenticate(request=request, username=identifier, password=password)

        # 2. If username authentication fails, try looking up by email
        if user is None:
            try:
                existing_user = User.objects.filter(email__iexact=identifier).first()
                if existing_user:
                    user = authenticate(
                        request=request,
                        username=existing_user.get_username(),
                        password=password
                    )
            except Exception:
                user = None

        if user is not None:
            if not user.is_active:
                messages.error(request, "This account is inactive. Please contact support.")
                return render(request, 'accounts/login.html', {'prefilled_username': identifier})

            login(request, user)
            messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
            return redirect('dashboard_redirect')
        else:
            messages.error(request, "Invalid username/email or password.")
            return render(request, 'accounts/login.html', {'prefilled_username': identifier})

    return render(request, 'accounts/login.html', {'prefilled_username': prefilled_username})

def logout_view(request):
    """Safely logs out the user without modifying credentials or account state."""
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
    """
    Comprehensive User Profile view supporting:
    1. View Profile (Role-specific stats & details)
    2. Edit Profile (Personal details & Role-specific profile attributes)
    3. Change Password (Current password check & new password validation)
    """
    user = request.user
    active_tab = request.GET.get('tab', 'view')

    chef_profile = getattr(user, 'chef_profile', None)
    courier_profile = getattr(user, 'delivery_boy_profile', None)
    try:
        health_profile = getattr(user, 'health_profile', None)
    except Exception:
        health_profile = None

    if request.method == 'POST':
        action = request.POST.get('action', 'edit_profile')

        if action == 'change_password':
            current_password = request.POST.get('current_password', '')
            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')

            if not user.check_password(current_password):
                messages.error(request, "Incorrect current password. Please try again.")
                return redirect(f"{reverse('profile')}?tab=password")

            if new_password != confirm_password:
                messages.error(request, "New passwords do not match. Please verify.")
                return redirect(f"{reverse('profile')}?tab=password")

            if len(new_password) < 6:
                messages.error(request, "New password must be at least 6 characters long.")
                return redirect(f"{reverse('profile')}?tab=password")

            user.set_password(new_password)
            user.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Your password has been changed successfully!")
            return redirect(f"{reverse('profile')}?tab=view")

        elif action == 'toggle_status' and user.role == 'delivery_boy' and courier_profile:
            new_status = request.POST.get('status', 'available')
            if new_status in ['available', 'offline', 'on_delivery']:
                courier_profile.status = new_status
                courier_profile.save()
                messages.success(request, f"Availability status updated to '{courier_profile.get_status_display()}'.")
            return redirect(f"{reverse('profile')}?tab=view")

        elif action == 'edit_profile':
            email_input = request.POST.get('email', '').strip()
            phone_input = request.POST.get('phone', '').strip()
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            address = request.POST.get('address', '').strip()

            if email_input and User.objects.filter(email__iexact=email_input).exclude(id=user.id).exists():
                messages.error(request, "This email address is already in use by another account.")
                return redirect(f"{reverse('profile')}?tab=edit")

            if phone_input:
                clean_phone = re.sub(r'\D', '', phone_input)
                if not re.match(r'^[6-9]\d{9}$', clean_phone):
                    messages.error(request, "Please enter a valid 10-digit mobile phone number (e.g. 9876543210).")
                    return redirect(f"{reverse('profile')}?tab=edit")
                if User.objects.filter(phone=clean_phone).exclude(id=user.id).exists():
                    messages.error(request, "This phone number is already assigned to another account.")
                    return redirect(f"{reverse('profile')}?tab=edit")
                user.phone = clean_phone

            user.first_name = first_name
            user.last_name = last_name
            if email_input:
                user.email = email_input
            user.address = address

            try:
                user.latitude = float(request.POST.get('latitude', '') or user.latitude)
            except (ValueError, TypeError):
                pass
            try:
                user.longitude = float(request.POST.get('longitude', '') or user.longitude)
            except (ValueError, TypeError):
                pass
            user.save()

            # Update Role Specific Details
            if user.role == 'chef':
                if not chef_profile:
                    chef_profile = ChefProfile.objects.create(user=user)
                chef_profile.specialty = request.POST.get('specialty', chef_profile.specialty or '').strip()
                chef_profile.kitchen_name = request.POST.get('kitchen_name', chef_profile.kitchen_name or '').strip()
                chef_profile.kitchen_address = request.POST.get('kitchen_address', chef_profile.kitchen_address or '').strip()
                chef_profile.bio = request.POST.get('bio', chef_profile.bio or '').strip()
                try:
                    chef_profile.experience_years = int(request.POST.get('experience_years', chef_profile.experience_years))
                except (ValueError, TypeError):
                    pass
                chef_profile.save()

            elif user.role == 'delivery_boy':
                if not courier_profile:
                    courier_profile = DeliveryBoyProfile.objects.create(user=user)
                courier_profile.vehicle_number = request.POST.get('vehicle_number', courier_profile.vehicle_number or '').strip()
                courier_status = request.POST.get('status', courier_profile.status)
                if courier_status in ['available', 'offline', 'on_delivery']:
                    courier_profile.status = courier_status
                courier_profile.current_latitude = user.latitude
                courier_profile.current_longitude = user.longitude
                courier_profile.save()

            elif user.role == 'customer' and health_profile:
                health_profile.has_diabetes = request.POST.get('has_diabetes') == 'on'
                health_profile.has_hypertension = request.POST.get('has_hypertension') == 'on'
                health_profile.dietary_preference = request.POST.get('dietary_preference', health_profile.dietary_preference)
                try:
                    health_profile.caloric_limit = float(request.POST.get('caloric_limit', health_profile.caloric_limit or 2000.0))
                except (ValueError, TypeError):
                    pass
                health_profile.save()

            messages.success(request, "Profile updated successfully.")
            return redirect(f"{reverse('profile')}?tab=view")

    context = {
        'user': user,
        'chef_profile': chef_profile,
        'courier_profile': courier_profile,
        'health_profile': health_profile,
        'active_tab': active_tab,
    }
    return render(request, 'accounts/profile.html', context)

@login_required
@role_required('admin', 'staff')
def toggle_chef_approval(request, chef_id):
    """Staff/Admin workflow to approve or revoke a chef's approval status."""
    chef_profile = get_object_or_404(ChefProfile, pk=chef_id)
    chef_profile.is_approved = not chef_profile.is_approved
    chef_profile.save()

    status_str = "Approved" if chef_profile.is_approved else "Revoked Approval for"
    messages.success(request, f"Chef '{chef_profile.user.username}' status updated: {status_str}.")

    # Send Notification to Chef
    Notification.objects.create(
        user=chef_profile.user,
        message=f"Your Chef account status has been updated to: {'APPROVED' if chef_profile.is_approved else 'PENDING APPROVAL'}.",
    )
    
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('admin_dashboard')

@login_required
@role_required('delivery_boy', 'admin')
def toggle_courier_status_view(request):
    """Allows courier to switch availability status (available / offline)."""
    if hasattr(request.user, 'delivery_boy_profile'):
        profile = request.user.delivery_boy_profile
        new_status = request.POST.get('status')
        if new_status in ['available', 'offline', 'on_delivery']:
            profile.status = new_status
            profile.save()
            messages.success(request, f"Your courier availability status is now '{profile.get_status_display()}'.")
    return redirect('delivery_boy_dashboard')

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

            target_username = verified_user.username
            verified_user.set_password(new_password)
            verified_user.save()

            request.session.pop('reset_user_id', None)

            messages.success(request, f"Password for account '{target_username}' updated successfully! Please sign in with your new password.")
            return redirect(f"{reverse('login')}?username={target_username}")

    return render(request, 'accounts/password_reset.html', {'step': step, 'verified_user': verified_user})

def password_reset_cancel_view(request):
    request.session.pop('reset_user_id', None)
    return redirect('password_reset')

def csrf_failure_view(request, reason=""):
    messages.warning(request, "Security token refreshed. Please submit your request again.")
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('food_catalog')
