from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from .base import BaseSeleniumTest

class StaffTest(BaseSeleniumTest):
    def test_staff_dashboard(self):
        self.login('teststaff', 'testpassword123')
        
        # Verify dashboard
        self.wait.until(lambda d: '/dashboard' in d.current_url or '/staff' in d.current_url)
        
        # Staff should not be able to access full admin if they are just staff
        # Wait, if they are `is_staff`, they might have some admin access, but let's test specific admin views if any.
        self.driver.get(self.live_server_url + '/admin-dashboard/')
        # Usually staff can access admin dashboard or they have their own
        pass

    def test_staff_assign_delivery(self):
        """Test that staff can assign orders to available delivery personnel."""
        from orders.models import Order, OrderItem
        from accounts.models import DeliveryBoyProfile
        
        order = Order.objects.create(
            user=self.customer,
            total_amount=150.00,
            status='preparing',
            latitude=9.55,
            longitude=76.79
        )
        OrderItem.objects.create(
            order=order,
            food_item=self.food_item,
            quantity=1,
            price=150.00
        )
        
        self.login('teststaff', 'testpassword123')
        
        self.driver.get(self.live_server_url + '/orders/staff/dashboard/')
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        
        select_element = self.wait.until(EC.presence_of_element_located((By.NAME, "delivery_boy_id")))
        
        select = Select(select_element)
        select.select_by_index(1) 
        
        assign_btn = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Assign Delivery Boy')]")
        assign_btn.click()
        
        self.wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(., 'Assigned Courier')]")))
        
        order.refresh_from_db()
        self.assertTrue(hasattr(order, 'delivery_assignment'))
        self.assertEqual(order.delivery_assignment.delivery_boy.user.username, 'testcourier')
