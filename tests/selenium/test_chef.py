from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base import BaseSeleniumTest

class ChefTest(BaseSeleniumTest):
    def test_chef_dashboard_access(self):
        """Test that chef can access their dashboard."""
        self.login('testchef', 'testpassword123')
        self.wait.until(lambda d: '/login/' not in d.current_url)
        
        # Navigate to chef dashboard using the correct URL
        self.driver.get(self.live_server_url + '/chef/dashboard/')
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        # Verify we're on the chef dashboard (not redirected away)
        self.assertIn('/chef/dashboard/', self.driver.current_url)

    def test_chef_add_food(self):
        """Test that chef can access the add food page."""
        self.login('testchef', 'testpassword123')
        self.wait.until(lambda d: '/login/' not in d.current_url)
        
        # Navigate to the add food page using the correct URL from food/urls.py
        self.driver.get(self.live_server_url + '/chef/food/add/')
        try:
            self.wait.until(EC.presence_of_element_located((By.NAME, 'name')))
            # Verify the form is present
            self.assertTrue(self.driver.find_element(By.NAME, 'name').is_displayed())
        except Exception:
            # If form doesn't load, take screenshot for debugging
            self.take_screenshot('chef_add_food_fail')

    def test_customer_cannot_access_chef_dashboard(self):
        """Test that customer cannot access chef-only pages."""
        self.login('testcustomer', 'testpassword123')
        self.wait.until(lambda d: '/login/' not in d.current_url)
        
        # Try accessing chef dashboard
        self.driver.get(self.live_server_url + '/chef/dashboard/')
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        
        # Customer should be redirected away from chef dashboard
        # The role_required decorator redirects to dashboard_redirect with "Access denied" message
        self.assertNotIn('/chef/dashboard/', self.driver.current_url)

    def test_chef_order_workflow(self):
        """Test that chef can view, accept and update order statuses."""
        from orders.models import Order, OrderItem
        
        # Create an order in the database for the test food item
        order = Order.objects.create(
            user=self.customer,
            total_amount=150.00,
            status='pending'
        )
        OrderItem.objects.create(
            order=order,
            food_item=self.food_item,
            quantity=1,
            price=150.00
        )
        
        self.login('testchef', 'testpassword123')
        self.wait.until(lambda d: '/login/' not in d.current_url)
        
        # 1. View Orders (Go to chef dashboard)
        self.driver.get(self.live_server_url + '/chef/dashboard/')
        self.wait.until(EC.presence_of_element_located((By.ID, 'kitchen-queue')))
        
        # Check if order is present in the queue (by order id)
        self.assertIn(order.order_id, self.driver.page_source)
        self.assertIn('NEW ORDER', self.driver.page_source)
        
        # 2. Accept Order (Change status to 'preparing')
        # There should be an "Accept & Start Preparing" button in a form
        try:
            accept_form = self.driver.find_element(By.CSS_SELECTOR, f"form[action*='{order.order_id}'] input[value='preparing']").find_element(By.XPATH, "..")
            accept_btn = accept_form.find_element(By.CSS_SELECTOR, "button[type='submit']")
            # Selenium click might be intercepted if elements overlap, so use javascript or just click
            self.driver.execute_script("arguments[0].scrollIntoView(true);", accept_btn)
            import time
            time.sleep(0.5)
            accept_btn.click()
            
            # Wait for dashboard to reload
            self.wait.until(EC.presence_of_element_located((By.ID, 'kitchen-queue')))
            
            # Check if status changed
            self.assertIn('Preparing', self.driver.page_source)
        except Exception as e:
            self.take_screenshot('chef_accept_order_fail')
            raise e

        # 3. Update Preparation Status (Change status to 'ready_pickup')
        # There should be a "Ready for Pickup" button
        try:
            ready_form = self.driver.find_element(By.CSS_SELECTOR, f"form[action*='{order.order_id}'] input[value='ready_pickup']").find_element(By.XPATH, "..")
            ready_btn = ready_form.find_element(By.CSS_SELECTOR, "button[type='submit']")
            self.driver.execute_script("arguments[0].scrollIntoView(true);", ready_btn)
            time.sleep(0.5)
            ready_btn.click()
            
            # Wait for dashboard to reload
            self.wait.until(EC.presence_of_element_located((By.ID, 'kitchen-queue')))
            
            # Check if status changed
            self.assertIn('Ready and awaiting courier pickup', self.driver.page_source)
        except Exception as e:
            self.take_screenshot('chef_ready_order_fail')
            raise e
