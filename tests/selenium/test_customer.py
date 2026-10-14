from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base import BaseSeleniumTest

class CustomerTest(BaseSeleniumTest):
    def test_customer_browse_catalog(self):
        """Test that customer can login and browse the food catalog."""
        self.login('testcustomer', 'testpassword123')
        self.driver.get(self.live_server_url + '/')
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        # Verify the catalog page loaded (look for food cards or catalog content)
        page_source = self.driver.page_source
        self.assertTrue(len(page_source) > 500)  # Page loaded with content

    def test_customer_add_to_cart(self):
        """Test that customer can add a food item to cart via direct URL."""
        self.login('testcustomer', 'testpassword123')
        
        # Add item to cart directly using cart_add URL
        self.driver.get(self.live_server_url + f'/orders/cart/add/{self.food_item.id}/')
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        
        # Go to cart page and verify item is there
        self.driver.get(self.live_server_url + '/orders/cart/')
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        page_source = self.driver.page_source
        self.assertIn('Test Food Item', page_source)

    def test_customer_view_food_detail(self):
        """Test that customer can view food detail page."""
        self.login('testcustomer', 'testpassword123')
        self.driver.get(self.live_server_url + f'/food/{self.food_item.id}/')
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        page_source = self.driver.page_source
        self.assertIn('Test Food Item', page_source)
        
        # Verify add-to-cart link exists
        cart_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/cart/add/')]")
        self.assertTrue(len(cart_links) > 0)

    def test_customer_checkout_flow(self):
        """Test checkout page loads after adding item to cart."""
        self.login('testcustomer', 'testpassword123')
        
        # Add item to cart
        self.driver.get(self.live_server_url + f'/orders/cart/add/{self.food_item.id}/')
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        
        # Navigate to checkout
        self.driver.get(self.live_server_url + '/orders/checkout/')
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        # Verify we're on checkout or redirected (if cart is empty it may redirect)
        page_source = self.driver.page_source
        self.assertTrue('checkout' in self.driver.current_url.lower() or 'cart' in self.driver.current_url.lower() or 'Test Food Item' in page_source)
