from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base import BaseSeleniumTest

class LogoutSessionTest(BaseSeleniumTest):
    def test_customer_logout_and_session(self):
        self.login('testcustomer', 'testpassword123')
        self.wait.until(lambda d: '/login/' not in d.current_url)
        
        # Navigate to a protected page (profile) to verify authenticated access
        self.driver.get(self.live_server_url + '/accounts/profile/')
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        
        self.logout()
        self.wait.until(EC.url_contains('/login/'))
        
        # Try accessing the protected profile page after logout
        self.driver.get(self.live_server_url + '/accounts/profile/')
        # Should be redirected to login since session is cleared
        self.wait.until(EC.url_contains('/login'))
        self.assertIn('/login', self.driver.current_url)
        
    def test_chef_logout_and_session(self):
        self.login('testchef', 'testpassword123')
        self.wait.until(lambda d: '/login/' not in d.current_url)
        
        self.logout()
        self.wait.until(EC.url_contains('/login/'))
        
        # Try accessing chef dashboard after logout
        self.driver.get(self.live_server_url + '/chef/dashboard/')
        self.wait.until(EC.url_contains('/login'))
        self.assertIn('/login', self.driver.current_url)

    def test_staff_logout_and_session(self):
        self.login('teststaff', 'testpassword123')
        self.wait.until(lambda d: '/login/' not in d.current_url)
        
        self.logout()
        self.wait.until(EC.url_contains('/login/'))
        
        # Try accessing staff dashboard after logout
        self.driver.get(self.live_server_url + '/orders/staff/dashboard/')
        self.wait.until(EC.url_contains('/login'))
        self.assertIn('/login', self.driver.current_url)

    def test_courier_logout_and_session(self):
        self.login('testcourier', 'testpassword123')
        self.wait.until(lambda d: '/login/' not in d.current_url)
        
        self.logout()
        self.wait.until(EC.url_contains('/login/'))
        
        # Try accessing delivery dashboard after logout
        self.driver.get(self.live_server_url + '/delivery/dashboard/')
        self.wait.until(EC.url_contains('/login'))
        self.assertIn('/login', self.driver.current_url)
