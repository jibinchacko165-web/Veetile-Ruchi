import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "veetile_ruchi_project.settings")
django.setup()
from django.test import Client, TestCase
from accounts.models import User

class ProfileValidationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='milan_test', email='milan@example.com', password='password123', first_name='Milan', last_name='User')

    def test_invalid_profile_post(self):
        self.client.login(username='milan_test', password='password123')
        # Simulate missing last_name and invalid email
        data = {
            'action': 'edit_profile',
            'first_name': 'J',
            'last_name': '',  # Empty
            'email': 'milan123@gmail', # Invalid
            'phone': '790702465' # Invalid phone
        }
        response = self.client.post('/accounts/profile/', data)
        self.assertEqual(response.status_code, 200) # Should render the form again, not redirect
        
        content = response.content.decode('utf-8')
        self.assertIn('Last Name is required.', content)
        self.assertIn('Enter a valid email address.', content)
        self.assertIn('Please enter a valid 10-digit mobile phone number', content)
        
        # Verify db unchanged
        self.user.refresh_from_db()
        self.assertEqual(self.user.last_name, 'User')
        self.assertEqual(self.user.email, 'milan@example.com')
