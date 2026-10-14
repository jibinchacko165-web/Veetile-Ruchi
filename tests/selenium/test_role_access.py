from selenium.webdriver.common.by import By
from .base import BaseSeleniumTest

class RoleAccessTest(BaseSeleniumTest):
    def test_customer_cannot_access_staff_or_chef_pages(self):
        self.login('testcustomer', 'testpassword123')
        
        # Try staff
        self.driver.get(self.live_server_url + '/dashboard/staff/')
        self.assertTrue('staff' not in self.driver.current_url or '403' in self.driver.page_source or 'Permission Denied' in self.driver.page_source or 'Login' in self.driver.page_source)
        
        # Try chef
        self.driver.get(self.live_server_url + '/dashboard/chef/')
        self.assertTrue('chef' not in self.driver.current_url or '403' in self.driver.page_source or 'Permission Denied' in self.driver.page_source or 'Login' in self.driver.page_source)

        # Try courier
        self.driver.get(self.live_server_url + '/dashboard/delivery/')
        self.assertTrue('delivery' not in self.driver.current_url or '403' in self.driver.page_source or 'Permission Denied' in self.driver.page_source or 'Login' in self.driver.page_source)
        
    def test_chef_cannot_access_unauthorized_pages(self):
        self.login('testchef', 'testpassword123')
        
        # Try admin
        self.driver.get(self.live_server_url + '/admin-dashboard/')
        self.assertTrue('admin-dashboard' not in self.driver.current_url or '403' in self.driver.page_source or 'Permission Denied' in self.driver.page_source)

    def test_unauthenticated_users_redirected(self):
        self.driver.get(self.live_server_url + '/dashboard/')
        self.assertTrue('login' in self.driver.current_url.lower())
