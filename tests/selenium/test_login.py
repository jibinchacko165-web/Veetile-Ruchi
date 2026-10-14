from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base import BaseSeleniumTest

class LoginTest(BaseSeleniumTest):
    def test_valid_customer_login(self):
        self.login('testcustomer', 'testpassword123')
        self.wait.until(lambda d: '/login/' not in d.current_url)
        # Usually redirects to food catalog '/'
        self.assertNotIn('/login/', self.driver.current_url)
        
    def test_valid_chef_login(self):
        self.login('testchef', 'testpassword123')
        self.wait.until(lambda d: '/dashboard' in d.current_url or '/chef' in d.current_url)
        self.assertTrue(any(x in self.driver.current_url for x in ['dashboard', 'chef']))

    def test_valid_staff_login(self):
        self.login('teststaff', 'testpassword123')
        self.wait.until(lambda d: '/dashboard' in d.current_url or '/staff' in d.current_url)
        
    def test_valid_courier_login(self):
        self.login('testcourier', 'testpassword123')
        self.wait.until(lambda d: '/delivery' in d.current_url or '/dashboard' in d.current_url)

    def test_invalid_username(self):
        self.login('wronguser', 'testpassword123')
        # Should stay on login page and show error
        self.wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Invalid username/email or password')]")))
        self.assertIn('/login/', self.driver.current_url)
        
    def test_invalid_password(self):
        self.login('testcustomer', 'wrongpassword')
        self.wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Invalid username/email or password')]")))
        self.assertIn('/login/', self.driver.current_url)

    def test_empty_credentials(self):
        self.driver.get(self.live_server_url + '/login/')
        submit_btn = self.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
        submit_btn.click()
        
        username_input = self.driver.find_element(By.NAME, 'username')
        self.check_validation_message(username_input)
