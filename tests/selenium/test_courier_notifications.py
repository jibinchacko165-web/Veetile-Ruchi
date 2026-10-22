from decimal import Decimal
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base import BaseSeleniumTest
from orders.models import Order, OrderItem, Notification
from delivery.models import DeliveryAssignment

class CourierNotificationsSeleniumTest(BaseSeleniumTest):
    def setUp(self):
        super().setUp()
        self.order = Order.objects.create(
            order_id='VR-SEL-NOTIF-01',
            user=self.customer,
            total_amount=Decimal('150.00'),
            status='assigned'
        )
        OrderItem.objects.create(
            order=self.order,
            food_item=self.food_item,
            quantity=1,
            price=Decimal('150.00')
        )
        self.assignment = DeliveryAssignment.objects.create(
            order=self.order,
            delivery_boy=self.courier.delivery_boy_profile,
            status='assigned'
        )
        self.notif = Notification.objects.create(
            user=self.courier,
            order=self.order,
            title='New Delivery Assigned',
            message=f'Order #{self.order.order_id} assigned for pickup.',
            notification_type='assignment',
            is_read=False
        )

    def tearDown(self):
        try:
            self.notif.delete()
            self.assignment.delete()
            self.order.delete()
        except Exception:
            pass
        super().tearDown()

    def test_courier_notification_modal_display_and_dismissal(self):
        """Courier logs in, sees unread notification modal with IST timestamp, dismisses it, and order status is unchanged."""
        self.login('testcourier', 'testpassword123')
        self.wait.until(lambda d: '/login/' not in d.current_url)

        self.driver.get(self.live_server_url + '/delivery/dashboard/')

        # Notification modal should automatically display
        modal = self.wait.until(EC.visibility_of_element_located((By.ID, 'courierNotificationModal')))
        self.assertTrue(modal.is_displayed())

        # Verify Order ID and IST timestamp appear in the modal
        page_source = self.driver.page_source
        self.assertIn(self.order.order_id, page_source)
        self.assertIn('(IST)', page_source)

        # Click Dismiss button inside the notification card
        dismiss_btn = self.wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, f"#popup-notif-{self.notif.id} button")
        ))
        self.driver.execute_script("arguments[0].click();", dismiss_btn)

        # Wait for notification card to be dismissed/hidden
        self.wait.until(EC.invisibility_of_element_located((By.ID, f"popup-notif-{self.notif.id}")))

        # Check DB: notification is marked read
        self.notif.refresh_from_db()
        self.assertTrue(self.notif.is_read)

        # Order status MUST remain assigned (not mutated by notification dismissal)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'assigned')

        # Reloading page should not re-open modal with this dismissed notification
        self.driver.get(self.live_server_url + '/delivery/dashboard/')
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        modal_now = self.driver.find_element(By.ID, 'courierNotificationModal')
        self.assertFalse(modal_now.is_displayed())
