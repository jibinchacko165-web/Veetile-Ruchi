import os
import time
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from django.contrib.auth import get_user_model

User = get_user_model()

class BaseSeleniumTest(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        
        # Initialize Chrome driver
        cls.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        cls.driver.implicitly_wait(10)
        cls.wait = WebDriverWait(cls.driver, 10)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()
        super().tearDownClass()

    def setUp(self):
        # Create some base test users
        self.create_test_users()

    def create_test_users(self):
        # Create Customer
        self.customer = User.objects.create_user(
            username='testcustomer',
            email='customer@example.com',
            password='testpassword123',
            role='customer',
            phone='1234567890'
        )
        # Create Chef
        self.chef = User.objects.create_user(
            username='testchef',
            email='chef@example.com',
            password='testpassword123',
            role='chef',
            phone='1234567891'
        )
        from accounts.models import ChefProfile, DeliveryBoyProfile
        from food.models import Category, MealSession, FoodItem
        
        ChefProfile.objects.create(
            user=self.chef,
            specialty='Indian',
            kitchen_name='Test Kitchen',
            is_approved=True
        )
        # Create Staff
        self.staff = User.objects.create_user(
            username='teststaff',
            email='staff@example.com',
            password='testpassword123',
            role='staff',
            phone='1234567892',
            is_staff=True
        )
        # Create Courier
        self.courier = User.objects.create_user(
            username='testcourier',
            email='courier@example.com',
            password='testpassword123',
            role='delivery_boy',
            phone='1234567893'
        )
        from accounts.models import DeliveryBoyProfile
        DeliveryBoyProfile.objects.create(
            user=self.courier,
            vehicle_number='KL-01-AB-1234'
        )
        
        # Create Category
        self.category = Category.objects.create(name='Test Category', description='Test Desc')
        
        # Create Meal Session
        import datetime
        self.meal_session = MealSession.objects.create(
            name='Test Session',
            start_time=datetime.time(0, 0),
            end_time=datetime.time(23, 59)
        )
        
        # Create Food Item
        self.food_item = FoodItem.objects.create(
            chef=self.chef,
            name='Test Food Item',
            price=150.00,
            category=self.category,
            meal_session=self.meal_session,
            stock_quantity=10,
            is_available=True
        )

    def login(self, username, password):
        self.driver.get(self.live_server_url + '/login/')
        username_input = self.wait.until(EC.presence_of_element_located((By.NAME, 'username')))
        password_input = self.driver.find_element(By.NAME, 'password')
        submit_btn = self.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
        
        username_input.send_keys(username)
        password_input.send_keys(password)
        submit_btn.click()

    def logout(self):
        self.driver.get(self.live_server_url + '/logout/')

    def take_screenshot(self, name):
        os.makedirs('tests/selenium/screenshots', exist_ok=True)
        self.driver.save_screenshot(f'tests/selenium/screenshots/{name}.png')

    def check_validation_message(self, element, expected_message=None):
        validation_message = element.get_attribute("validationMessage")
        if expected_message:
            self.assertIn(expected_message, validation_message)
        else:
            self.assertTrue(validation_message)
