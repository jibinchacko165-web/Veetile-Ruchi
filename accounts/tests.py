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

    def test_rbac_prevents_unauthorized_dashboard_access(self):
        # Log in as Customer
        self.client.login(username='test_customer', password='password123')
        
        # Try to access Chef Dashboard
        response = self.client.get(reverse('chef_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('dashboard_redirect'), response.url)
        
        # Try to access Admin Dashboard
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('dashboard_redirect'), response.url)

        # Try to access Staff Dashboard
        response = self.client.get(reverse('staff_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('dashboard_redirect'), response.url)

    def test_chef_approval_workflow(self):
        # Log in as Staff member and approve the chef
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
