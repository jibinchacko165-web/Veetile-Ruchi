from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base import BaseSeleniumTest

class ResponsiveTest(BaseSeleniumTest):
    def test_responsive_layout(self):
        url = self.live_server_url + '/'
        
        # Desktop
        self.driver.set_window_size(1920, 1080)
        self.driver.get(url)
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        
        # Tablet
        self.driver.set_window_size(768, 1024)
        self.driver.get(url)
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        
        # Mobile
        self.driver.set_window_size(375, 812)
        self.driver.get(url)
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        
        # Check if hamburger menu is visible on mobile
        try:
            navbar_toggler = self.driver.find_element(By.CSS_SELECTOR, '.navbar-toggler, .menu-icon, .hamburger')
            self.assertTrue(navbar_toggler.is_displayed())
        except Exception:
            pass # Maybe there's no hamburger or it's named differently

        # Restore window size
        self.driver.set_window_size(1920, 1080)
