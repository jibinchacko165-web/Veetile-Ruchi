from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from accounts.models import User, ChefProfile, DeliveryBoyProfile, PasswordResetOTP
from health.models import HealthProfile

class AccountsModuleTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Create test users for each role
        self.customer = User.objects.create_user(
            username='test_customer',
            email='customer@test.com',
            password='password123',
            role='customer',
            dob='1995-05-15',
            phone='9876543210'
        )
        HealthProfile.objects.create(user=self.customer)

        self.chef_user = User.objects.create_user(
            username='test_chef',
            email='chef@test.com',
            password='password123',
            role='chef',
            dob='1988-07-20',
            phone='9876543211'
        )
        self.chef_profile = ChefProfile.objects.create(
            user=self.chef_user,
            specialty='Malabar Cuisine',
            kitchen_name="Test Kitchen",
            is_approved=False
        )

        self.courier_user = User.objects.create_user(
            username='test_courier',
            email='courier@test.com',
            password='password123',
            role='delivery_boy',
            dob='1996-08-12',
            phone='9876543212'
        )
        self.courier_profile = DeliveryBoyProfile.objects.create(
            user=self.courier_user,
            vehicle_number='KL-07-AB-1234',
            status='available'
        )

        self.staff_user = User.objects.create_user(
            username='test_staff',
            email='staff@test.com',
            password='password123',
            role='staff',
            dob='1992-03-10'
        )

        self.admin_user = User.objects.create_user(
            username='test_admin',
            email='admin@test.com',
            password='password123',
            role='admin',
            is_staff=True,
            is_superuser=True,
            dob='1990-01-01'
        )

    # =========================================================================
    # 10 EXPLICIT AUTHENTICATION FLOW TESTS REQUIRED BY SPECIFICATION
    # =========================================================================

    def test_01_register_login_logout_relogin_same_credentials(self):
        """TEST 1: Register new user -> Login -> Logout -> Login again with SAME credentials -> SUCCESS"""
        reg_resp = self.client.post(reverse('register'), {
            'username': 'unique_fresh_user',
            'email': 'fresh_user@test.com',
            'password': 'FreshPassword@123',
            'confirm_password': 'FreshPassword@123',
            'role': 'customer',
            'dob': '1998-04-12',
            'phone': '9876500001',
        })
        self.assertEqual(reg_resp.status_code, 302)

        # 1. First Login
        log1 = self.client.post(reverse('login'), {
            'username': 'unique_fresh_user',
            'password': 'FreshPassword@123'
        })
        self.assertEqual(log1.status_code, 302)
        fresh_user = User.objects.get(username='unique_fresh_user')
        self.assertEqual(int(self.client.session['_auth_user_id']), fresh_user.id)

        # 2. Logout
        logout_resp = self.client.get(reverse('logout'))
        self.assertEqual(logout_resp.status_code, 302)
        self.assertNotIn('_auth_user_id', self.client.session)

        # 3. Second Login with SAME credentials
        log2 = self.client.post(reverse('login'), {
            'username': 'unique_fresh_user',
            'password': 'FreshPassword@123'
        })
        self.assertEqual(log2.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), fresh_user.id)

    def test_02_consecutive_five_login_logout_cycles(self):
        """TEST 2: Login -> Logout -> Login again 5 times -> SUCCESS every time"""
        for cycle in range(1, 6):
            login_resp = self.client.post(reverse('login'), {
                'username': 'test_customer',
                'password': 'password123'
            })
            self.assertEqual(login_resp.status_code, 302, f"Failed at login iteration {cycle}")
            self.assertEqual(int(self.client.session['_auth_user_id']), self.customer.id)

            logout_resp = self.client.get(reverse('logout'))
            self.assertEqual(logout_resp.status_code, 302, f"Failed at logout iteration {cycle}")
            self.assertNotIn('_auth_user_id', self.client.session)

    def test_03_login_using_username_and_case_insensitivity(self):
        """TEST 3: Login using username (exact and mixed case / whitespace) -> SUCCESS"""
        # Exact username
        resp1 = self.client.post(reverse('login'), {'username': 'test_customer', 'password': 'password123'})
        self.assertEqual(resp1.status_code, 302)
        self.client.get(reverse('logout'))

        # Mixed-case & whitespace trimmed username
        resp2 = self.client.post(reverse('login'), {'username': '  Test_Customer  ', 'password': 'password123'})
        self.assertEqual(resp2.status_code, 302)
        self.client.get(reverse('logout'))

    def test_04_login_using_registered_email(self):
        """TEST 4: Login using registered email (exact, mixed case, trimmed) -> SUCCESS"""
        # Exact email
        resp1 = self.client.post(reverse('login'), {'username': 'customer@test.com', 'password': 'password123'})
        self.assertEqual(resp1.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.customer.id)
        self.client.get(reverse('logout'))

        # Mixed-case & padded email
        resp2 = self.client.post(reverse('login'), {'username': '  Customer@Test.COM  ', 'password': 'password123'})
        self.assertEqual(resp2.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.customer.id)
        self.client.get(reverse('logout'))

    def test_05_wrong_password_shows_error(self):
        """TEST 5: Wrong password -> Show 'Invalid username/email or password.'"""
        response = self.client.post(reverse('login'), {
            'username': 'test_customer',
            'password': 'incorrect_password'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid username/email or password.')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_06_unknown_username_email_shows_error(self):
        """TEST 6: Unknown username/email -> Show 'Invalid username/email or password.'"""
        response = self.client.post(reverse('login'), {
            'username': 'non_existent_account_12345',
            'password': 'password123'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid username/email or password.')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_07_login_close_browser_reopen_and_login(self):
        """TEST 7: Login -> Close browser (new client instance) -> Open browser -> Login again -> SUCCESS"""
        # Browser session 1
        browser1 = Client()
        r1 = browser1.post(reverse('login'), {'username': 'test_chef', 'password': 'password123'})
        self.assertEqual(r1.status_code, 302)
        self.assertEqual(int(browser1.session['_auth_user_id']), self.chef_user.id)

        # "Browser closed and reopened" = completely new Client instance without shared cookies/session
        browser2 = Client()
        self.assertNotIn('_auth_user_id', browser2.session)
        r2 = browser2.post(reverse('login'), {'username': 'test_chef', 'password': 'password123'})
        self.assertEqual(r2.status_code, 302)
        self.assertEqual(int(browser2.session['_auth_user_id']), self.chef_user.id)

    def test_08_forgot_password_reset_and_login_with_new_password(self):
        """TEST 8: Forgot password -> Reset password -> Logout -> Login using new password -> SUCCESS"""
        # Step 1: Verify identity (Email + DOB)
        verify_resp = self.client.post(reverse('password_reset'), {
            'action': 'verify',
            'email': 'customer@test.com',
            'dob': '1995-05-15'
        })
        self.assertEqual(verify_resp.status_code, 200)
        self.assertEqual(self.client.session.get('reset_user_id'), self.customer.id)

        # Step 2: Set new password
        reset_resp = self.client.post(reverse('password_reset'), {
            'action': 'reset',
            'new_password': 'BrandNewPassword@999',
            'confirm_password': 'BrandNewPassword@999'
        })
        self.assertEqual(reset_resp.status_code, 302)
        self.assertNotIn('reset_user_id', self.client.session)

        # Step 3: Login with new password
        login_resp = self.client.post(reverse('login'), {
            'username': 'test_customer',
            'password': 'BrandNewPassword@999'
        })
        self.assertEqual(login_resp.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.customer.id)

    def test_09_old_password_fails_after_reset(self):
        """TEST 9: Old password after password reset -> MUST FAIL"""
        # Change password
        self.customer.set_password('BrandNewPassword@999')
        self.customer.save()

        # Attempt login with old password
        old_pwd_resp = self.client.post(reverse('login'), {
            'username': 'test_customer',
            'password': 'password123'
        })
        self.assertEqual(old_pwd_resp.status_code, 200)
        self.assertContains(old_pwd_resp, 'Invalid username/email or password.')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_10_logout_and_protected_dashboard_access_blocked(self):
        """TEST 10: Logout -> Protected dashboard must NOT be accessible without authentication"""
        # Login first
        self.client.login(username='test_chef', password='password123')
        
        # Verify access
        dash = self.client.get(reverse('chef_dashboard'))
        self.assertEqual(dash.status_code, 200)

        # Logout
        self.client.get(reverse('logout'))

        # Attempt to access protected dashboard
        protected_resp = self.client.get(reverse('chef_dashboard'))
        self.assertEqual(protected_resp.status_code, 302)
        self.assertIn(reverse('login'), protected_resp.url)

    # =========================================================================
    # ROLE & PROFILE WORKFLOW TESTS
    # =========================================================================

    def test_registration_creates_role_profiles(self):
        response = self.client.post(reverse('register'), {
            'username': 'new_chef',
            'email': 'newchef@test.com',
            'password': 'StrongPassword@123',
            'confirm_password': 'StrongPassword@123',
            'role': 'chef',
            'dob': '1990-01-01',
            'phone': '9876543299',
            'specialty': 'Seafood',
            'kitchen_name': "New Seafood Kitchen"
        })
        self.assertEqual(response.status_code, 302)
        new_user = User.objects.get(username='new_chef')
        self.assertEqual(new_user.role, 'chef')
        self.assertTrue(hasattr(new_user, 'chef_profile'))
        self.assertFalse(new_user.chef_profile.is_approved)

    def test_registration_strong_password_rules(self):
        """Verify that weak passwords failing criteria are rejected with friendly error messages."""
        weak_passwords = [
            ('short', 'Password must be at least 8 characters long.'),
            ('nouppercase123@', 'Password must contain at least one uppercase letter (A-Z).'),
            ('NOLOWERCASE123@', 'Password must contain at least one lowercase letter (a-z).'),
            ('NoNumberSpecial@', 'Password must contain at least one number (0-9).'),
            ('NoSpecialChar123', 'Password must contain at least one special character'),
        ]
        for pwd, expected_err in weak_passwords:
            resp = self.client.post(reverse('register'), {
                'username': f'test_user_{pwd[:4]}',
                'email': f'{pwd[:4]}@test.com',
                'password': pwd,
                'confirm_password': pwd,
                'role': 'customer',
                'dob': '1995-01-01',
                'phone': '9876543210'
            })
            self.assertEqual(resp.status_code, 200)
            self.assertContains(resp, expected_err)

    def test_customer_registration_does_not_require_address(self):
        """Customer registration must succeed without address or GPS parameters."""
        resp = self.client.post(reverse('register'), {
            'username': 'clean_customer',
            'email': 'cleancustomer@test.com',
            'password': 'StrongPass@123',
            'confirm_password': 'StrongPass@123',
            'role': 'customer',
            'dob': '1998-05-15',
            'phone': '9876599999'
        })
        self.assertEqual(resp.status_code, 302)
        user = User.objects.get(username='clean_customer')
        self.assertEqual(user.address, '')

    def test_saved_locations_crud_and_default_handling(self):
        """Verify SavedLocation model and profile views for Add, Set Default, and Delete."""
        from accounts.models import SavedLocation
        self.client.login(username='test_customer', password='password123')

        # 1. Add Saved Location
        resp1 = self.client.post(reverse('profile'), {
            'action': 'add_saved_location',
            'name': 'My Kakkanad Office',
            'location_type': 'work',
            'description': 'InfoPark Phase 2, Floor 4',
            'landmark': 'Near InfoPark Express Gate',
            'latitude': 10.0159,
            'longitude': 76.3419,
            'is_default': 'on'
        })
        self.assertEqual(resp1.status_code, 302)
        loc1 = SavedLocation.objects.filter(user=self.customer, name='My Kakkanad Office').first()
        self.assertIsNotNone(loc1)
        self.assertTrue(loc1.is_default)

        # 2. Add Second Saved Location as Default -> should unset first
        resp2 = self.client.post(reverse('profile'), {
            'action': 'add_saved_location',
            'name': 'My Home',
            'location_type': 'home',
            'description': 'River View Villa No 12',
            'landmark': 'Near Aluva Temple',
            'latitude': 10.1076,
            'longitude': 76.3516,
            'is_default': 'on'
        })
        self.assertEqual(resp2.status_code, 302)
        loc2 = SavedLocation.objects.filter(user=self.customer, name='My Home').first()
        self.assertIsNotNone(loc2)
        self.assertTrue(loc2.is_default)

        loc1.refresh_from_db()
        self.assertFalse(loc1.is_default)

        # 3. Delete Saved Location
        resp3 = self.client.post(reverse('profile'), {
            'action': 'delete_saved_location',
            'location_id': loc1.id
        })
        self.assertEqual(resp3.status_code, 302)
        self.assertFalse(SavedLocation.objects.filter(id=loc1.id).exists())

    def test_login_and_role_redirect(self):
        login_success = self.client.login(username='test_chef', password='password123')
        self.assertTrue(login_success)
        response = self.client.get(reverse('dashboard_redirect'))
        self.assertRedirects(response, reverse('chef_dashboard'))

    def test_all_five_roles_repeated_login_logout(self):
        roles_users = [
            ('test_customer', 'customer@test.com', 'password123', reverse('food_catalog')),
            ('test_chef', 'chef@test.com', 'password123', reverse('chef_dashboard')),
            ('test_courier', 'courier@test.com', 'password123', reverse('delivery_boy_dashboard')),
            ('test_staff', 'staff@test.com', 'password123', reverse('staff_dashboard')),
            ('test_admin', 'admin@test.com', 'password123', reverse('admin_dashboard')),
        ]

        for username, email, pwd, expected_dashboard in roles_users:
            for iteration in range(3):
                # Login with username
                resp = self.client.post(reverse('login'), {'username': username, 'password': pwd})
                self.assertEqual(resp.status_code, 302)
                
                # Check redirect
                dash_resp = self.client.get(reverse('dashboard_redirect'))
                self.assertRedirects(dash_resp, expected_dashboard)

                # Logout
                logout_resp = self.client.get(reverse('logout'))
                self.assertEqual(logout_resp.status_code, 302)

                # Login with email
                resp_email = self.client.post(reverse('login'), {'username': email, 'password': pwd})
                self.assertEqual(resp_email.status_code, 302)

                # Logout again
                self.client.get(reverse('logout'))

    def test_rbac_prevents_unauthorized_dashboard_access(self):
        self.client.login(username='test_customer', password='password123')
        
        response = self.client.get(reverse('chef_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('dashboard_redirect'), response.url)
        
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('dashboard_redirect'), response.url)

        response = self.client.get(reverse('staff_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('dashboard_redirect'), response.url)

    def test_chef_approval_workflow(self):
        self.client.login(username='test_staff', password='password123')
        response = self.client.post(reverse('toggle_chef_approval', args=[self.chef_profile.id]))
        self.assertEqual(response.status_code, 302)
        
        self.chef_profile.refresh_from_db()
        self.assertTrue(self.chef_profile.is_approved)

    def test_courier_status_management(self):
        self.client.login(username='test_courier', password='password123')
        response = self.client.post(reverse('toggle_courier_status'), {'status': 'offline'})
        self.assertEqual(response.status_code, 302)
        
        self.courier_profile.refresh_from_db()
        self.assertEqual(self.courier_profile.status, 'offline')

    def test_change_password(self):
        self.client.login(username='test_customer', password='password123')
        response = self.client.post(reverse('profile'), {
            'action': 'change_password',
            'current_password': 'password123',
            'new_password': 'BrandNewPassword@456',
            'confirm_password': 'BrandNewPassword@456'
        })
        self.assertRedirects(response, reverse('profile') + '?tab=view')
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.check_password('BrandNewPassword@456'))

    def test_otp_forgot_password_and_reset_workflow(self):
        """Test full OTP flow: request OTP -> verify OTP -> reset password -> login with new password"""
        # 1. Request OTP using email
        req_resp = self.client.post(reverse('password_reset'), {
            'action': 'request_otp',
            'identifier': 'customer@test.com'
        })
        self.assertEqual(req_resp.status_code, 200)
        self.assertEqual(self.client.session.get('otp_pending_user_id'), self.customer.id)

        otp_record = PasswordResetOTP.objects.filter(user=self.customer).first()
        self.assertIsNotNone(otp_record)
        self.assertFalse(otp_record.is_expired())

        # For test verification, manually set known OTP hash
        from django.contrib.auth.hashers import make_password
        otp_record.otp_hash = make_password('654321')
        otp_record.save()

        # 2. Verify OTP
        verify_resp = self.client.post(reverse('password_reset'), {
            'action': 'verify_otp',
            'otp': '654321'
        })
        self.assertEqual(verify_resp.status_code, 200)
        self.assertEqual(self.client.session.get('reset_user_id'), self.customer.id)
        self.assertNotIn('otp_pending_user_id', self.client.session)

        # 3. Reset password
        reset_resp = self.client.post(reverse('password_reset'), {
            'action': 'reset',
            'new_password': 'BrandNewCustomerPass@789',
            'confirm_password': 'BrandNewCustomerPass@789'
        })
        self.assertEqual(reset_resp.status_code, 302)
        self.assertNotIn('reset_user_id', self.client.session)

        # 4. Login using new password
        login_resp = self.client.post(reverse('login'), {
            'username': 'test_customer',
            'password': 'BrandNewCustomerPass@789'
        })
        self.assertEqual(login_resp.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.customer.id)

    def test_invalid_and_expired_otp_handling(self):
        """Test error cases: invalid OTP incrementing attempts & expired OTP rejection"""
        from django.contrib.auth.hashers import make_password

        # Create active OTP
        otp_record = PasswordResetOTP.objects.create(
            user=self.customer,
            otp_hash=make_password('112233'),
            expires_at=timezone.now() + timedelta(minutes=10),
            attempts=0
        )

        session = self.client.session
        session['otp_pending_user_id'] = self.customer.id
        session.save()

        # Invalid OTP attempt
        bad_resp = self.client.post(reverse('password_reset'), {
            'action': 'verify_otp',
            'otp': '999999'
        })
        self.assertEqual(bad_resp.status_code, 200)
        otp_record.refresh_from_db()
        self.assertEqual(otp_record.attempts, 1)

        # Expired OTP
        otp_record.expires_at = timezone.now() - timedelta(minutes=5)
        otp_record.save()

        exp_resp = self.client.post(reverse('password_reset'), {
            'action': 'verify_otp',
            'otp': '112233'
        })
        self.assertEqual(exp_resp.status_code, 200)
        self.assertFalse(PasswordResetOTP.objects.filter(id=otp_record.id).exists())


class DjangoSessionFrameworkTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.customer = User.objects.create_user(username='sess_customer', password='Password@123', role='customer')
        self.chef = User.objects.create_user(username='sess_chef', password='Password@123', role='chef')
        ChefProfile.objects.create(user=self.chef, is_approved=True)
        self.staff = User.objects.create_user(username='sess_staff', password='Password@123', role='staff')
        self.courier = User.objects.create_user(username='sess_courier', password='Password@123', role='delivery_boy')
        DeliveryBoyProfile.objects.create(user=self.courier, vehicle_number='KL-01-SESS')
        self.admin = User.objects.create_user(username='sess_admin', password='Password@123', role='admin', is_staff=True, is_superuser=True)

    def test_database_session_created_and_stored_in_db(self):
        from django.contrib.sessions.models import Session
        login_resp = self.client.post(reverse('login'), {'username': 'sess_customer', 'password': 'Password@123'})
        self.assertEqual(login_resp.status_code, 302)
        session_key = self.client.session.session_key
        self.assertTrue(session_key)
        self.assertTrue(Session.objects.filter(session_key=session_key).exists())

    def test_session_persists_across_multiple_page_requests(self):
        self.client.post(reverse('login'), {'username': 'sess_customer', 'password': 'Password@123'})
        r1 = self.client.get(reverse('food_catalog'))
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.customer.id)
        r2 = self.client.get(reverse('profile'))
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.customer.id)

    def test_logout_completely_flushes_session(self):
        from django.contrib.sessions.models import Session
        self.client.post(reverse('login'), {'username': 'sess_customer', 'password': 'Password@123'})
        old_session_key = self.client.session.session_key
        self.client.get(reverse('logout'))
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertFalse(Session.objects.filter(session_key=old_session_key).exists())

    def test_all_five_roles_session_creation_and_dashboard_isolation(self):
        role_targets = [
            (self.customer, 'sess_customer', reverse('food_catalog')),
            (self.chef, 'sess_chef', reverse('chef_dashboard')),
            (self.staff, 'sess_staff', reverse('staff_dashboard')),
            (self.courier, 'sess_courier', reverse('delivery_boy_dashboard')),
            (self.admin, 'sess_admin', reverse('admin_dashboard')),
        ]
        for user_obj, username, expected_url in role_targets:
            res = self.client.post(reverse('login'), {'username': username, 'password': 'Password@123'})
            self.assertEqual(res.status_code, 302)
            self.assertEqual(int(self.client.session['_auth_user_id']), user_obj.id)
            redir = self.client.get(reverse('dashboard_redirect'))
            self.assertRedirects(redir, expected_url)
            self.client.get(reverse('logout'))

    def test_no_cache_middleware_headers(self):
        """Verify NoCacheMiddleware attaches anti-caching headers to protected view responses."""
        self.client.post(reverse('login'), {'username': 'sess_customer', 'password': 'Password@123'})
        response = self.client.get(reverse('food_catalog'))
        self.assertIn('no-cache', response.headers.get('Cache-Control', ''))
        self.assertIn('no-store', response.headers.get('Cache-Control', ''))
        self.assertIn('must-revalidate', response.headers.get('Cache-Control', ''))
        self.assertEqual(response.headers.get('Pragma'), 'no-cache')
        self.assertEqual(response.headers.get('Expires'), '0')

    def test_logout_response_headers_and_session_flush(self):
        """Verify logout flushes session and sets strict anti-caching headers on redirect response."""
        self.client.post(reverse('login'), {'username': 'sess_customer', 'password': 'Password@123'})
        logout_res = self.client.get(reverse('logout'))
        self.assertEqual(logout_res.status_code, 302)
        self.assertIn('no-store', logout_res.headers.get('Cache-Control', ''))
        self.assertNotIn('_auth_user_id', self.client.session)





