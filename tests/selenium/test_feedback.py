from decimal import Decimal
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base import BaseSeleniumTest
from orders.models import Order, OrderItem, ChefFeedback
from delivery.models import DeliveryAssignment, DeliveryFeedback

class CustomerDualFeedbackSeleniumTest(BaseSeleniumTest):
    def setUp(self):
        super().setUp()
        # Create a delivered order for testing feedback
        self.delivered_order = Order.objects.create(
            order_id='VR-SEL-FB-01',
            user=self.customer,
            total_amount=Decimal('150.00'),
            status='delivered'
        )
        OrderItem.objects.create(
            order=self.delivered_order,
            food_item=self.food_item,
            quantity=1,
            price=Decimal('150.00')
        )
        self.assignment = DeliveryAssignment.objects.create(
            order=self.delivered_order,
            delivery_boy=self.courier.delivery_boy_profile,
            status='delivered'
        )

    def tearDown(self):
        try:
            ChefFeedback.objects.filter(order=self.delivered_order).delete()
            DeliveryFeedback.objects.filter(order=self.delivered_order).delete()
            self.assignment.delete()
            self.delivered_order.delete()
        except Exception:
            pass
        super().tearDown()

    def test_customer_can_submit_chef_and_food_feedback(self):
        """Customer opens order history and submits Food & Chef feedback via interactive modal."""
        self.login('testcustomer', 'testpassword123')
        self.wait.until(lambda d: '/login/' not in d.current_url)

        self.driver.get(self.live_server_url + '/orders/history/')
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'table')))

        # Find and click Rate Food & Chef button
        chef_rate_btn = self.wait.until(EC.element_to_be_clickable(
            (By.XPATH, f"//button[contains(text(), 'Rate Food & Chef')]")
        ))
        self.driver.execute_script("arguments[0].click();", chef_rate_btn)

        # Modal should become visible
        modal = self.wait.until(EC.visibility_of_element_located((By.ID, 'chefFeedbackModal')))
        self.assertTrue(modal.is_displayed())

        # Fill comments
        comment_input = self.driver.find_element(By.ID, 'chefCommentInput')
        comment_input.clear()
        comment_input.send_keys("The food was freshly made, authentic, and delicious!")

        # Submit form
        submit_btn = self.driver.find_element(By.CSS_SELECTOR, "#chefFeedbackForm button[type='submit']")
        self.driver.execute_script("arguments[0].click();", submit_btn)

        # Wait for redirect back to order history
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'table')))

        # Verify ChefFeedback record exists in database
        self.delivered_order.refresh_from_db()
        fb = ChefFeedback.objects.filter(order=self.delivered_order).first()
        self.assertIsNotNone(fb)
        self.assertEqual(fb.rating, 5)
        self.assertEqual(fb.comment, "The food was freshly made, authentic, and delicious!")
        self.assertEqual(fb.chef, self.chef)

        # Verify page updated to show rated button
        self.wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Food Rated')]")))

    def test_customer_can_submit_courier_feedback(self):
        """Customer opens order history and submits Courier & Delivery feedback via interactive modal."""
        self.login('testcustomer', 'testpassword123')
        self.wait.until(lambda d: '/login/' not in d.current_url)

        self.driver.get(self.live_server_url + '/orders/history/')
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'table')))

        # Find and click Rate Delivery & Courier button
        courier_rate_btn = self.wait.until(EC.element_to_be_clickable(
            (By.XPATH, f"//button[contains(text(), 'Rate Delivery & Courier')]")
        ))
        self.driver.execute_script("arguments[0].click();", courier_rate_btn)

        # Modal should become visible
        modal = self.wait.until(EC.visibility_of_element_located((By.ID, 'courierFeedbackModal')))
        self.assertTrue(modal.is_displayed())

        # Fill comments
        comment_input = self.driver.find_element(By.ID, 'courierCommentInput')
        comment_input.clear()
        comment_input.send_keys("The delivery was fast, on time, and the courier was polite.")

        # Submit form
        submit_btn = self.driver.find_element(By.CSS_SELECTOR, "#courierFeedbackForm button[type='submit']")
        self.driver.execute_script("arguments[0].click();", submit_btn)

        # Wait for redirect back to order history
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'table')))

        # Verify DeliveryFeedback record exists in database
        self.delivered_order.refresh_from_db()
        fb = DeliveryFeedback.objects.filter(order=self.delivered_order).first()
        self.assertIsNotNone(fb)
        self.assertEqual(fb.rating, 5)
        self.assertEqual(fb.comment, "The delivery was fast, on time, and the courier was polite.")
        self.assertEqual(fb.delivery_boy, self.courier.delivery_boy_profile)

        # Verify page updated to show delivery rated button
        self.wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Delivery Rated')]")))

    def test_independent_dual_feedback_isolation(self):
        """Submitting chef feedback does not auto-create courier feedback and vice versa."""
        self.login('testcustomer', 'testpassword123')
        self.wait.until(lambda d: '/login/' not in d.current_url)

        # Submit only chef feedback via POST endpoint
        url_chef = f"/orders/feedback/chef/{self.delivered_order.order_id}/"
        self.driver.get(self.live_server_url + '/orders/history/')
        self.driver.execute_script(f"""
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = '{url_chef}';
            const csrf = document.querySelector('[name=csrfmiddlewaretoken]').value;
            const csrfIn = document.createElement('input');
            csrfIn.name = 'csrfmiddlewaretoken';
            csrfIn.value = csrf;
            form.appendChild(csrfIn);
            const rIn = document.createElement('input');
            rIn.name = 'rating';
            rIn.value = '4';
            form.appendChild(rIn);
            document.body.appendChild(form);
            form.submit();
        """)
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'table')))

        self.assertTrue(ChefFeedback.objects.filter(order=self.delivered_order).exists())
        self.assertFalse(DeliveryFeedback.objects.filter(order=self.delivered_order).exists())
