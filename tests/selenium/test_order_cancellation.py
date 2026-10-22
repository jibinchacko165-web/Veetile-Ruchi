from decimal import Decimal
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base import BaseSeleniumTest
from orders.models import Order, OrderItem

class OrderCancellationSeleniumTest(BaseSeleniumTest):
    def setUp(self):
        super().setUp()
        self.pending_order = Order.objects.create(
            order_id='VR-SEL-CNC-01',
            user=self.customer,
            total_amount=Decimal('150.00'),
            status='pending'
        )
        OrderItem.objects.create(
            order=self.pending_order,
            food_item=self.food_item,
            quantity=2,
            price=Decimal('75.00')
        )
        self.initial_stock = self.food_item.stock_quantity

    def tearDown(self):
        try:
            self.pending_order.delete()
        except Exception:
            pass
        super().tearDown()

    def test_customer_can_cancel_pending_order_from_order_history(self):
        """Customer can click Cancel button in order history, order status becomes cancelled and stock is restored."""
        self.login('testcustomer', 'testpassword123')
        self.wait.until(lambda d: '/login/' not in d.current_url)

        self.driver.get(self.live_server_url + '/orders/history/')
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'table')))

        # Verify cancel button is present for pending order
        cancel_btn = self.wait.until(EC.element_to_be_clickable(
            (By.XPATH, f"//form[contains(@action, '{self.pending_order.order_id}')]//button[contains(text(), 'Cancel')]")
        ))
        self.assertTrue(cancel_btn.is_displayed())

        # Bypass window.confirm or submit form directly to cancel
        self.driver.execute_script("""
            window.confirm = function() { return true; };
        """)
        self.driver.execute_script("arguments[0].click();", cancel_btn)

        # Wait for reload
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'table')))

        # Verify database state
        self.pending_order.refresh_from_db()
        self.assertEqual(self.pending_order.status, 'cancelled')

        self.food_item.refresh_from_db()
        self.assertEqual(self.food_item.stock_quantity, self.initial_stock + 2)

        # Verify badge shows Cancelled and Cancel button is no longer visible
        page_source = self.driver.page_source
        self.assertIn('Cancelled', page_source)
        remaining_cancel_btns = self.driver.find_elements(
            By.XPATH, f"//form[contains(@action, '{self.pending_order.order_id}')]//button[contains(text(), 'Cancel')]"
        )
        self.assertEqual(len(remaining_cancel_btns), 0)
