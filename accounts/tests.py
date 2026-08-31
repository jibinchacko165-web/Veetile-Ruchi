from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User, ChefProfile, DeliveryBoyProfile
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
            'password': 'password123',
            'confirm_password': 'password123',
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
            'new_password': 'newpassword456',
            'confirm_password': 'newpassword456'
        })
        self.assertRedirects(response, reverse('profile') + '?tab=view')
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.check_password('newpassword456'))

