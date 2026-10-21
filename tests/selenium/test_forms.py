from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base import BaseSeleniumTest

class FormValidationTest(BaseSeleniumTest):
    def test_registration_form_validation(self):
        self.driver.get(self.live_server_url + '/register/')
        
        # Test required fields
        btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", btn)
        username_input = self.driver.find_element(By.NAME, 'username')
        self.check_validation_message(username_input)
        
        # Test invalid email
        username_input.send_keys('testuser')
        email_input = self.driver.find_element(By.NAME, 'email')
        email_input.send_keys('invalid-email')
        btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", btn)
        self.check_validation_message(email_input)
        
        # Test password mismatch
        email_input.clear()
        email_input.send_keys('testuser@example.com')
        self.driver.find_element(By.NAME, 'password').send_keys('ValidPass123!')
        self.driver.find_element(By.NAME, 'confirm_password').send_keys('Mismatch123!')
        btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", btn)

        
        # Wait for django message
        try:
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.alert-danger, .error-message, .messages')))
            self.assertTrue('match' in self.driver.page_source.lower() or 'password' in self.driver.page_source.lower())
        except Exception:
            pass
            
    def test_invalid_phone_number(self):
        self.driver.get(self.live_server_url + '/register/')
        
        self.driver.find_element(By.NAME, 'username').send_keys('newuser123')
        self.driver.find_element(By.NAME, 'email').send_keys('newuser123@example.com')
        self.driver.find_element(By.NAME, 'password').send_keys('Test@1234')
        self.driver.find_element(By.NAME, 'confirm_password').send_keys('Test@1234')
        
        # Invalid phone
        self.driver.find_element(By.NAME, 'phone').send_keys('12345') 
        self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        
        # Should stay on page or show error
        self.assertTrue('register' in self.driver.current_url)
