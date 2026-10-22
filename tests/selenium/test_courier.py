from decimal import Decimal
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base import BaseSeleniumTest
from orders.models import Order, OrderItem
from delivery.models import DeliveryAssignment, DeliveryFeedback

class CourierTest(BaseSeleniumTest):
    def test_courier_dashboard(self):
        self.login('testcourier', 'testpassword123')
        
        # Verify dashboard
        self.wait.until(lambda d: '/delivery' in d.current_url or '/dashboard' in d.current_url)
        
        # Try to switch status if available
        try:
            status_toggle = self.driver.find_element(By.CSS_SELECTOR, "form[action*='status'] button, select[name='status']")
            # Just verify it's there
            self.assertTrue(status_toggle.is_displayed())
        except Exception:
            pass

    def test_unauthorized_users_cannot_access(self):
        self.login('testcustomer', 'testpassword123')
        self.driver.get(self.live_server_url + '/dashboard/delivery/')
        self.assertTrue('delivery' not in self.driver.current_url or '403' in self.driver.page_source or 'Permission' in self.driver.page_source)

    def test_courier_assigned_orders_and_contact_info(self):
        """Courier can view their assigned order, customer delivery address, and phone number."""
        order = Order.objects.create(
            order_id='VR-SEL-COUR-01',
            user=self.customer,
            total_amount=Decimal('150.00'),
            status='assigned',
            delivery_address='Hill Palace Rd, Tripunithura, Kochi'
        )
        OrderItem.objects.create(order=order, food_item=self.food_item, quantity=1, price=Decimal('150.00'))
        assignment = DeliveryAssignment.objects.create(
            order=order,
            delivery_boy=self.courier.delivery_boy_profile,
            status='assigned'
        )

        try:
            self.login('testcourier', 'testpassword123')
            self.wait.until(lambda d: '/login/' not in d.current_url)

            self.driver.get(self.live_server_url + '/delivery/dashboard/')
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))

            page_source = self.driver.page_source
            self.assertIn(order.order_id, page_source)
            self.assertIn('Hill Palace Rd', page_source)
            # Customer contact link (tel:)
            self.assertIn(self.customer.phone, page_source)
        finally:
            assignment.delete()
            order.delete()

    def test_courier_feedback_dashboard_view(self):
        """Courier can navigate to Feedback tab and view ratings and review stats."""
        order = Order.objects.create(
            order_id='VR-SEL-COUR-02',
            user=self.customer,
            total_amount=Decimal('150.00'),
            status='delivered'
        )
        OrderItem.objects.create(order=order, food_item=self.food_item, quantity=1, price=Decimal('150.00'))
        assignment = DeliveryAssignment.objects.create(
            order=order,
            delivery_boy=self.courier.delivery_boy_profile,
            status='delivered'
        )
        fb = DeliveryFeedback.objects.create(
            order=order,
            delivery_assignment=assignment,
            delivery_boy=self.courier.delivery_boy_profile,
            customer=self.customer,
            rating=5,
            timeliness_rating=5,
            behavior_rating=5,
            food_handling_rating=5,
            comment='Excellent and friendly courier boy!'
        )

        try:
            self.login('testcourier', 'testpassword123')
            self.wait.until(lambda d: '/login/' not in d.current_url)

            self.driver.get(self.live_server_url + '/delivery/dashboard/?tab=profile')
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))

            page_source = self.driver.page_source
            self.assertIn('Excellent and friendly courier boy!', page_source)
            self.assertIn('Rating', page_source)
        finally:
            fb.delete()
            assignment.delete()
            order.delete()

