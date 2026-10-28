import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "veetile_ruchi_project.settings")
django.setup()
from django.test import Client, TestCase
from accounts.models import User
from accounts.forms import UserEditProfileForm
from accounts.validators import validate_email_address

class ProfileValidationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='milan_test',
            email='milan@example.com',
            password='password123',
            first_name='Milan',
            last_name='User',
            dob='1995-01-01'
        )

    def test_invalid_profile_post(self):
        self.client.login(username='milan_test', password='password123')
        # Simulate missing last_name and invalid email
        data = {
            'action': 'edit_profile',
            'first_name': 'J',
            'last_name': '',  # Empty
            'email': 'milan123@gmail',  # Invalid (no domain extension)
            'phone': '790702465'  # Invalid phone
        }
        response = self.client.post('/accounts/profile/', data)
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')
        self.assertIn('Last Name is required.', content)
        self.assertIn('Enter a valid email address.', content)
        self.assertIn('Please enter a valid 10-digit mobile phone number', content)

        # Verify db unchanged
        self.user.refresh_from_db()
        self.assertEqual(self.user.last_name, 'User')
        self.assertEqual(self.user.email, 'milan@example.com')

    def test_invalid_email_domain_rejected_in_profile_edit(self):
        """Reject incomplete domain like rajakshail2@gmail.co in profile edit."""
        self.client.login(username='milan_test', password='password123')
        data = {
            'action': 'edit_profile',
            'first_name': 'Milan',
            'last_name': 'User',
            'email': 'rajakshail2@gmail.co',  # Incomplete / invalid extension
            'phone': '9876543210'
        }
        response = self.client.post('/accounts/profile/', data)
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')
        self.assertIn('Enter a valid email address.', content)
        self.assertIn('valid domain extension', content)

        # Database must NOT be updated with invalid email
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'milan@example.com')

    def test_invalid_email_rejected_in_registration(self):
        """Reject incomplete/invalid email rajakshail2@gmail.co in user registration."""
        reg_data = {
            'username': 'rajakshail_test',
            'email': 'rajakshail2@gmail.co',  # Invalid email
            'dob': '1998-05-15',
            'password': 'StrongPass@123',
            'confirm_password': 'StrongPass@123',
            'role': 'customer',
            'phone': '9876543210'
        }
        response = self.client.post('/accounts/register/', reg_data)
        # Should stay on registration page (HTTP 200), not redirect (HTTP 302)
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')
        self.assertIn('Enter a valid email address.', content)

        # Verify user was NOT created in database
        self.assertFalse(User.objects.filter(username='rajakshail_test').exists())
        self.assertFalse(User.objects.filter(email='rajakshail2@gmail.co').exists())

    def test_valid_email_accepted_in_registration(self):
        """Accept valid email address with valid domain extension (.com)."""
        reg_data = {
            'username': 'valid_user_email_test',
            'email': 'rajakshail2@gmail.com',  # Valid email
            'dob': '1998-05-15',
            'password': 'StrongPass@123',
            'confirm_password': 'StrongPass@123',
            'role': 'customer',
            'phone': '9876543219'
        }
        response = self.client.post('/accounts/register/', reg_data)
        self.assertEqual(response.status_code, 302)

        # Verify user was created in database with the valid email
        user = User.objects.filter(username='valid_user_email_test').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.email, 'rajakshail2@gmail.com')

    def test_validator_various_invalid_emails(self):
        """Test unit validation of various invalid / incomplete email addresses."""
        invalid_emails = [
            'rajakshail2@gmail.co',
            'user@gmail',
            'user@domain.c',
            'user@domain.con',
            'user@.com',
            'plainaddress',
            '@gmail.com',
            'user@domain..com',
        ]
        for em in invalid_emails:
            is_valid, err_msg = validate_email_address(em)
            self.assertFalse(is_valid, f"Expected {em} to be invalid, but passed.")
            self.assertTrue(len(err_msg) > 0)
            self.assertIn('Enter a valid email address.', err_msg)

    def test_validator_various_valid_emails(self):
        """Test unit validation of various valid email addresses with different valid extensions."""
        valid_emails = [
            'rajakshail2@gmail.com',
            'user@kerala.gov.in',
            'admin@community.org',
            'info@techservice.net',
            'student@university.edu',
            'founder@startup.io',
            'jibinpchacko2027@mca.ajce.in',
        ]
        for em in valid_emails:
            is_valid, err_msg = validate_email_address(em)
            self.assertTrue(is_valid, f"Expected {em} to be valid, but failed with: {err_msg}")
