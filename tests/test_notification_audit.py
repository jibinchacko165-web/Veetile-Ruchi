from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.messages import get_messages
from accounts.models import User

class NotificationRemovalTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='akshai_raj',
            email='akshairaj@test.com',
            password='TestPassword@123',
            first_name='Akshai',
            last_name='Raj',
            role='customer',
            dob='1995-01-01',
            phone='9876543210'
        )

    def test_01_successful_login_has_no_welcome_back_message_or_green_tick(self):
        """Verifies successful login redirects without generating 'Welcome back' or '✓' notification."""
        resp = self.client.post(reverse('login'), {
            'username': 'akshai_raj',
            'password': 'TestPassword@123'
        }, follow=True)
        self.assertEqual(resp.status_code, 200)

        # Confirm user is authenticated
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.id)

        content = resp.content.decode('utf-8')
        # Ensure 'Welcome back' message does not appear in rendered page
        self.assertNotIn("Welcome back", content)
        self.assertNotIn("✓ Welcome back", content)
        # Ensure no green checkmark success banner was rendered in base.html messages
        self.assertNotIn("✓ Welcome back, Akshai Raj!", content)

    def test_02_invalid_login_still_displays_error_feedback(self):
        """Verifies invalid login continues to display the required authentication error message."""
        resp = self.client.post(reverse('login'), {
            'username': 'akshai_raj',
            'password': 'wrongpassword'
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn("Invalid username/email or password.", content)
        self.assertIn("⚠️", content)

    def test_03_registration_validation_errors_preserved(self):
        """Verifies registration validation errors continue to display."""
        resp = self.client.post(reverse('register'), {
            'username': 'short',
            'password': 'mismatch1',
            'confirm_password': 'mismatch2'
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        # Should stay on page and present error feedback
        self.assertTrue("⚠️" in content or "error" in content.lower())

    def test_04_success_messages_render_with_neutral_indicator_not_green_tick(self):
        """Verifies legitimate success messages render with neutral indicator and no green checkmark."""
        self.client.login(username='akshai_raj', password='TestPassword@123')
        # Trigger a legitimate success message (password change)
        resp = self.client.post(reverse('profile'), {
            'action': 'change_password',
            'current_password': 'TestPassword@123',
            'new_password': 'NewPassword@456',
            'confirm_password': 'NewPassword@456'
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        # Verify the success message text is present
        self.assertIn("Your password has been changed successfully!", content)
        # Verify it uses the neutral indicator ℹ️ and not ✓
        self.assertIn("ℹ️", content)
        self.assertNotIn("✓ Your password has been changed successfully!", content)
        self.assertNotIn("var(--success-bg)", content)

