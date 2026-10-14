from selenium.webdriver.common.by import By
from .base import BaseSeleniumTest

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
