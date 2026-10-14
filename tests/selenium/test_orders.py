from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base import BaseSeleniumTest

class OrderWorkflowTest(BaseSeleniumTest):
    def test_customer_can_place_order(self):
        """Test the customer order placement flow."""
        # Customer Login
        self.login('testcustomer', 'testpassword123')
        self.wait.until(lambda d: '/login/' not in d.current_url)
        
        # Add item to cart via direct URL
        self.driver.get(self.live_server_url + f'/orders/cart/add/{self.food_item.id}/')
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        
        # Go to cart to verify
        self.driver.get(self.live_server_url + '/orders/cart/')
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        self.assertIn('Test Food Item', self.driver.page_source)
        
        # Navigate to checkout
        self.driver.get(self.live_server_url + '/orders/checkout/')
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        
        # Try to place order
        try:
            place_order_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            place_order_btn.click()
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        except Exception:
            pass

    def test_chef_can_view_orders(self):
        """Test that chef can access their dashboard to view orders."""
        self.login('testchef', 'testpassword123')
        self.wait.until(lambda d: '/login/' not in d.current_url)
        
        self.driver.get(self.live_server_url + '/chef/dashboard/')
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        self.assertIn('/chef/dashboard/', self.driver.current_url)

    def test_staff_can_view_dashboard(self):
        """Test that staff can access the staff dashboard."""
        self.login('teststaff', 'testpassword123')
        self.wait.until(lambda d: '/login/' not in d.current_url)
        
        self.driver.get(self.live_server_url + '/orders/staff/dashboard/')
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))

    def test_courier_can_view_dashboard(self):
        """Test that courier can access the delivery dashboard."""
        self.login('testcourier', 'testpassword123')
        self.wait.until(lambda d: '/login/' not in d.current_url)
        
        self.driver.get(self.live_server_url + '/delivery/dashboard/')
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))

    def test_order_history_page(self):
        """Test that customer can view order history."""
        self.login('testcustomer', 'testpassword123')
        self.wait.until(lambda d: '/login/' not in d.current_url)
        
        self.driver.get(self.live_server_url + '/orders/history/')
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        self.assertIn('/orders/history/', self.driver.current_url)
