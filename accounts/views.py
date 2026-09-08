from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
import secrets
import re
import os
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.contrib import messages
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings
from django.db.models import Q
from .models import User, ChefProfile, DeliveryBoyProfile, PasswordResetOTP, SavedLocation
from .decorators import role_required
from health.models import HealthProfile
from orders.models import Notification
from orders.utils import KERALA_PRESET_PLACES

def validate_strong_password(password):
    """
    Validates password against strong criteria:
    - Min 8 chars
    - 1 uppercase [A-Z]
    - 1 lowercase [a-z]
    - 1 number [0-9]
    - 1 special character (@, #, $, %, etc.)
    """
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter (A-Z)."
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter (a-z)."
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number (0-9)."
    if not re.search(r'[!@#$%^&*(),.?":{}|<>_~+=\-\[\]\\/]', password):
        return False, "Password must contain at least one special character (e.g. @, #, $, %, etc.)."
    return True, ""

def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        dob = request.POST.get('dob', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        role = request.POST.get('role', 'customer')
        phone = request.POST.get('phone', '').strip()

        form_data = {
            'username': username,
            'email': email,
            'dob': dob,
            'role': role,
            'phone': phone,
            'specialty': request.POST.get('specialty', ''),
            'kitchen_name': request.POST.get('kitchen_name', ''),
            'vehicle_number': request.POST.get('vehicle_number', ''),
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

        is_valid_pwd, pwd_err = validate_strong_password(password)
        if not is_valid_pwd:
            messages.error(request, pwd_err)
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
            # Create user cleanly without requiring address or GPS during signup
            user = User.objects.create_user(
                username=username,
                email=email,
                dob=parsed_dob,
                password=password,
                role=role,
                phone=clean_phone if clean_phone else phone,
                address='',
                latitude=9.462534,
                longitude=76.72185
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
                current_latitude=9.462534, 
                current_longitude=76.72185
            )
        elif role == 'customer':
            HealthProfile.objects.create(user=user)

        request.session['prefill_username'] = username
        messages.success(request, f"Registration successful for '{username}'! Please sign in with your password.")
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

        # 2. If username authentication fails, try looking up by email, phone, or case-insensitive username
        if user is None:
            try:
                from django.db.models import Q
                existing_user = User.objects.filter(
                    Q(username__iexact=identifier) | Q(email__iexact=identifier) | Q(phone=identifier)
                ).first()
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

@never_cache
def logout_view(request):
    """Safely logs out the user and flushes session data."""
    logout(request)
    if hasattr(request, 'session'):
        request.session.flush()
    messages.info(request, "You have been logged out.")
    response = redirect('login')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

@never_cache
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

@never_cache
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

        # ───── PROFILE PICTURE UPLOAD ─────
        if action == 'upload_profile_picture':
            pic = request.FILES.get('profile_picture')
            if not pic:
                messages.error(request, "Please select an image file to upload.")
                return redirect(f"{reverse('profile')}?tab=view")
            
            ext = os.path.splitext(pic.name)[1].lower()
            if ext not in ['.jpg', '.jpeg', '.png', '.webp']:
                messages.error(request, "Invalid file format. Please upload a JPG, PNG, or WEBP image.")
                return redirect(f"{reverse('profile')}?tab=view")

            if pic.size > 5 * 1024 * 1024:
                messages.error(request, "Image size exceeds maximum limit of 5MB.")
                return redirect(f"{reverse('profile')}?tab=view")

            user.profile_picture = pic
            user.save()
            messages.success(request, "Profile picture updated successfully!")
            return redirect(f"{reverse('profile')}?tab=view")

        # ───── SAVED LOCATIONS: ADD ─────
        elif action == 'add_saved_location':
            loc_name = request.POST.get('name', '').strip() or 'My Location'
            loc_type = request.POST.get('location_type', 'home')
            description = request.POST.get('description', '').strip()
            landmark = request.POST.get('landmark', '').strip()
            try:
                lat = float(request.POST.get('latitude', 9.462534))
                lon = float(request.POST.get('longitude', 76.72185))
            except (ValueError, TypeError):
                lat = 9.462534
                lon = 76.72185
            is_default = request.POST.get('is_default') == 'on'

            SavedLocation.objects.create(
                user=user,
                name=loc_name,
                location_type=loc_type,
                description=description,
                landmark=landmark,
                latitude=lat,
                longitude=lon,
                is_default=is_default
            )
            messages.success(request, f"Saved location '{loc_name}' added successfully!")
            return redirect(f"{reverse('profile')}?tab=locations")

        # ───── SAVED LOCATIONS: DELETE ─────
        elif action == 'delete_saved_location':
            loc_id = request.POST.get('location_id')
            SavedLocation.objects.filter(id=loc_id, user=user).delete()
            messages.success(request, "Saved location removed successfully.")
            return redirect(f"{reverse('profile')}?tab=locations")

        # ───── SAVED LOCATIONS: SET DEFAULT ─────
        elif action == 'set_default_saved_location':
            loc_id = request.POST.get('location_id')
            loc = get_object_or_404(SavedLocation, id=loc_id, user=user)
            loc.is_default = True
            loc.save()
            messages.success(request, f"'{loc.name}' is now your default delivery location.")
            return redirect(f"{reverse('profile')}?tab=locations")

        elif action == 'change_password':
            current_password = request.POST.get('current_password', '')
            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')

            if not user.check_password(current_password):
                messages.error(request, "Incorrect current password. Please try again.")
                return redirect(f"{reverse('profile')}?tab=password")

            if new_password != confirm_password:
                messages.error(request, "New passwords do not match. Please verify.")
                return redirect(f"{reverse('profile')}?tab=password")

            is_valid_pwd, pwd_err = validate_strong_password(new_password)
            if not is_valid_pwd:
                messages.error(request, pwd_err)
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
                health_profile.has_bp = (request.POST.get('has_bp') == 'on' or request.POST.get('has_hypertension') == 'on')
                health_profile.has_cholesterol = request.POST.get('has_cholesterol') == 'on'
                health_profile.dietary_preference = request.POST.get('dietary_preference', health_profile.dietary_preference)
                cal_val = request.POST.get('daily_calorie_target') or request.POST.get('caloric_limit')
                if cal_val:
                    try:
                        health_profile.daily_calorie_target = float(cal_val)
                    except (ValueError, TypeError):
                        pass
                health_profile.save()

            messages.success(request, "Profile updated successfully.")
            return redirect(f"{reverse('profile')}?tab=view")

    saved_locations = user.saved_locations.all() if hasattr(user, 'saved_locations') else []

    context = {
        'user': user,
        'chef_profile': chef_profile,
        'courier_profile': courier_profile,
        'health_profile': health_profile,
        'saved_locations': saved_locations,
        'kerala_preset_places': KERALA_PRESET_PLACES,
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
    """
    Comprehensive Password Reset workflow supporting:
    1. Forgot Password -> Enter Email/Username -> Generate & Dispatch 6-digit OTP
    2. OTP Verification -> Verify OTP with expiry check & brute-force prevention
    3. Password Reset -> Set strong new password using Django password hashing
    4. Backward-compatible Date of Birth verification support
    """
    step = 'request'
    verified_user = None
    pending_user = None

    reset_user_id = request.session.get('reset_user_id')
    if reset_user_id:
        try:
            verified_user = User.objects.get(pk=reset_user_id)
            step = 'reset'
        except User.DoesNotExist:
            request.session.pop('reset_user_id', None)
            reset_user_id = None

    if not verified_user:
        otp_pending_id = request.session.get('otp_pending_user_id')
        if otp_pending_id:
            try:
                pending_user = User.objects.get(pk=otp_pending_id)
                step = 'otp_verify'
            except User.DoesNotExist:
                request.session.pop('otp_pending_user_id', None)
                pending_user = None

    if request.method == 'POST':
        action = request.POST.get('action', '').strip()

        # ───── STEP 1: REQUEST OTP (Forgot Password) ─────
        if action == 'request_otp' or (not action and 'identifier' in request.POST) or (not action and 'email' in request.POST and 'dob' not in request.POST and 'otp' not in request.POST and 'new_password' not in request.POST):
            identifier = (request.POST.get('identifier') or request.POST.get('email') or request.POST.get('username') or '').strip()

            if not identifier:
                messages.error(request, "Please enter your registered email address or username.")
                return render(request, 'accounts/password_reset.html', {'step': 'request', 'identifier': identifier})

            user = User.objects.filter(Q(email__iexact=identifier) | Q(username__iexact=identifier)).first()
            if not user:
                messages.error(request, "No account found with this email address or username. Please check your credentials and try again.")
                return render(request, 'accounts/password_reset.html', {'step': 'request', 'identifier': identifier})

            # Generate 6-digit numeric OTP
            otp_code = f"{secrets.randbelow(900000) + 100000}"

            # Invalidate any older OTPs for this user
            PasswordResetOTP.objects.filter(user=user).delete()

            # Store OTP with 10-minute expiry
            PasswordResetOTP.objects.create(
                user=user,
                otp_hash=make_password(otp_code),
                expires_at=timezone.now() + timedelta(minutes=10),
                attempts=0
            )

            # Send OTP email
            try:
                send_mail(
                    subject="Veetile-Ruchi — Password Reset OTP",
                    message=(
                        f"Hello {user.username},\n\n"
                        f"Your 6-digit OTP for resetting your Veetile-Ruchi password is: {otp_code}\n\n"
                        f"This code is valid for 10 minutes. If you did not request this, please ignore this email.\n\n"
                        f"Best regards,\nVeetile-Ruchi Team"
                    ),
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@veetileruchi.com'),
                    recipient_list=[user.email] if user.email else [],
                    fail_silently=True
                )
            except Exception:
                pass

            request.session['otp_pending_user_id'] = user.id
            request.session['otp_target_email'] = user.email or user.username
            messages.success(request, f"A 6-digit OTP has been sent to '{user.email or user.username}'. Please enter it below to verify.")
            return render(request, 'accounts/password_reset.html', {
                'step': 'otp_verify',
                'pending_user': user,
                'otp_code_dev': otp_code if settings.DEBUG else None
            })

        # ───── STEP 2: VERIFY OTP ─────
        elif action == 'verify_otp' or (not action and 'otp' in request.POST):
            pending_user_id = request.session.get('otp_pending_user_id')
            user = User.objects.filter(pk=pending_user_id).first() if pending_user_id else None

            if not user:
                messages.error(request, "Session expired or verification required. Please request a new OTP.")
                return render(request, 'accounts/password_reset.html', {'step': 'request'})

            entered_otp = request.POST.get('otp', '').strip()
            if not entered_otp:
                messages.error(request, "Please enter the 6-digit OTP sent to your email.")
                return render(request, 'accounts/password_reset.html', {'step': 'otp_verify', 'pending_user': user})

            otp_record = PasswordResetOTP.objects.filter(user=user).order_by('-created_at').first()
            if not otp_record:
                messages.error(request, "No active OTP found. Please request a new OTP.")
                return render(request, 'accounts/password_reset.html', {'step': 'request'})

            if otp_record.is_expired():
                otp_record.delete()
                request.session.pop('otp_pending_user_id', None)
                messages.error(request, "OTP has expired. Please request a new OTP.")
                return render(request, 'accounts/password_reset.html', {'step': 'request'})

            if otp_record.attempts >= 5:
                otp_record.delete()
                request.session.pop('otp_pending_user_id', None)
                messages.error(request, "Maximum OTP verification attempts exceeded. Please request a new OTP.")
                return render(request, 'accounts/password_reset.html', {'step': 'request'})

            if check_password(entered_otp, otp_record.otp_hash) or entered_otp == otp_record.otp_hash:
                # OTP is valid!
                otp_record.delete()
                request.session.pop('otp_pending_user_id', None)
                request.session['reset_user_id'] = user.id
                messages.success(request, f"OTP verified successfully for account '{user.username}'! Please enter your new password below.")
                return render(request, 'accounts/password_reset.html', {'step': 'reset', 'verified_user': user})
            else:
                otp_record.attempts += 1
                otp_record.save()
                remaining = max(0, 5 - otp_record.attempts)
                messages.error(request, f"Invalid OTP entered. Please try again. ({remaining} attempt(s) remaining)")
                return render(request, 'accounts/password_reset.html', {'step': 'otp_verify', 'pending_user': user})

        # ───── STEP 1B: VERIFY DATE OF BIRTH (Backward Compatibility) ─────
        elif action == 'verify' or 'dob' in request.POST:
            email = request.POST.get('email', '').strip()
            dob_str = request.POST.get('dob', '').strip()

            if not email or not dob_str:
                messages.error(request, "Please enter both your registered email address and Date of Birth.")
                return render(request, 'accounts/password_reset.html', {'step': 'request', 'email': email, 'dob': dob_str})

            user = User.objects.filter(email__iexact=email, dob=dob_str).first()
            if user:
                request.session['reset_user_id'] = user.id
                messages.success(request, f"Identity verified for account '{user.username}'! Please enter your new password below.")
                return render(request, 'accounts/password_reset.html', {'step': 'reset', 'verified_user': user, 'reset_user_id': user.id})
            else:
                request.session.pop('reset_user_id', None)
                messages.error(request, "Invalid Email Address or Date of Birth. Verification failed. Please check your details and try again.")
                return render(request, 'accounts/password_reset.html', {'step': 'request', 'email': email, 'dob': dob_str})

        # ───── STEP 3: SET NEW PASSWORD ─────
        elif action == 'reset' or ('new_password' in request.POST and 'confirm_password' in request.POST):
            if not verified_user:
                messages.error(request, "Session expired or verification required. Please verify your details first.")
                return render(request, 'accounts/password_reset.html', {'step': 'request'})

            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')

            if not new_password or not confirm_password:
                messages.error(request, "Please enter both new password fields.")
                return render(request, 'accounts/password_reset.html', {'step': 'reset', 'verified_user': verified_user})

            if new_password != confirm_password:
                messages.error(request, "Passwords do not match. Please re-enter matching passwords.")
                return render(request, 'accounts/password_reset.html', {'step': 'reset', 'verified_user': verified_user})

            is_valid_pwd, pwd_err = validate_strong_password(new_password)
            if not is_valid_pwd:
                messages.error(request, pwd_err)
                return render(request, 'accounts/password_reset.html', {'step': 'reset', 'verified_user': verified_user})

            target_username = verified_user.username
            verified_user.set_password(new_password)
            verified_user.save()

            request.session.pop('reset_user_id', None)
            request.session.pop('otp_pending_user_id', None)

            messages.success(request, f"Password for account '{target_username}' updated successfully! Please sign in with your new password.")
            return redirect(f"{reverse('login')}?username={target_username}")

    context = {
        'step': step,
        'verified_user': verified_user,
        'pending_user': pending_user,
        'reset_user_id': reset_user_id,
    }
    return render(request, 'accounts/password_reset.html', context)

def password_reset_cancel_view(request):
    request.session.pop('reset_user_id', None)
    request.session.pop('otp_pending_user_id', None)
    return redirect('password_reset')

def csrf_failure_view(request, reason=""):
    messages.warning(request, "Security token refreshed. Please submit your request again.")
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('food_catalog')
