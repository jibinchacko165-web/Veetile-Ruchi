import os
import pytest
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from django.contrib.auth import get_user_model
from decimal import Decimal

User = get_user_model()

def get_chromedriver_path():
    user_cache = os.path.expanduser("~/.cache/selenium/chromedriver/win64")
    if os.path.isdir(user_cache):
        for root, dirs, files in os.walk(user_cache):
            if "chromedriver.exe" in files:
                return os.path.join(root, "chromedriver.exe")
    return None

@pytest.fixture(scope="session")
def driver_options():
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--window-size=1440,900')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    return options

@pytest.fixture(scope="function")
def driver(driver_options):
    local_driver = get_chromedriver_path()
    drv = None
    if local_driver and os.path.exists(local_driver):
        try:
            drv = webdriver.Chrome(service=Service(local_driver), options=driver_options)
        except Exception:
            pass
    if drv is None:
        try:
            drv = webdriver.Chrome(options=driver_options)
        except Exception:
            drv = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=driver_options)
    
    drv.implicitly_wait(10)
    yield drv
    try:
        drv.delete_all_cookies()
    except Exception:
        pass
    try:
        drv.quit()
    except Exception:
        pass

@pytest.fixture(scope="function")
def base_url(live_server):
    env_url = os.environ.get("LIVE_SERVER_URL")
    if env_url:
        return env_url.rstrip("/")
    return live_server.url.rstrip("/")

@pytest.fixture
def auth_helper(driver, base_url):
    def _login(username, password):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        driver.delete_all_cookies()
        driver.get(f"{base_url}/login/")
        wait = WebDriverWait(driver, 10)
        u_in = wait.until(EC.presence_of_element_located((By.NAME, 'username')))
        p_in = driver.find_element(By.NAME, 'password')
        sub = driver.find_element(By.XPATH, "//button[@type='submit']")
        u_in.clear()
        u_in.send_keys(username)
        p_in.clear()
        p_in.send_keys(password)
        sub.click()
    return _login

@pytest.fixture
def test_setup_data(db):
    """Seed synthetic test users and base category/session/food in the isolated test database."""
    from accounts.models import ChefProfile, DeliveryBoyProfile
    from food.models import Category, MealSession, FoodItem

    # Cleanup any stale test users
    test_usernames = ['pytest_customer', 'pytest_chef', 'pytest_courier', 'pytest_staff', 'pytest_admin']
    User.objects.filter(username__in=test_usernames).delete()

    customer = User.objects.create_user(
        username='pytest_customer',
        email='customer_test@example.com',
        password='TestPassword123!',
        first_name='Test',
        last_name='Customer'
    )
    customer.role = 'customer'
    customer.phone = '9876543210'
    customer.address = 'Test Residency, MG Road, Ernakulam'
    customer.save()

    chef_user = User.objects.create_user(
        username='pytest_chef',
        email='chef_test@example.com',
        password='TestPassword123!',
        first_name='Test',
        last_name='Chef'
    )
    chef_user.role = 'chef'
    chef_user.phone = '9876543211'
    chef_user.save()
    chef_profile, _ = ChefProfile.objects.get_or_create(
        user=chef_user,
        defaults={
            'kitchen_name': 'Test Healthy Kitchen',
            'specialty': 'Authentic Kerala Cuisine',
            'experience_years': 6,
            'is_approved': True
        }
    )

    courier_user = User.objects.create_user(
        username='pytest_courier',
        email='courier_test@example.com',
        password='TestPassword123!',
        first_name='Test',
        last_name='Courier'
    )
    courier_user.role = 'delivery_boy'
    courier_user.phone = '9876543212'
    courier_user.save()
    courier_profile, _ = DeliveryBoyProfile.objects.get_or_create(
        user=courier_user,
        defaults={
            'vehicle_number': 'KL-07-TEST-1234',
            'status': 'available'
        }
    )

    staff_user = User.objects.create_user(
        username='pytest_staff',
        email='staff_test@example.com',
        password='TestPassword123!',
        is_staff=True,
        first_name='Test',
        last_name='Staff'
    )
    staff_user.role = 'staff'
    staff_user.save()

    admin_user = User.objects.create_superuser(
        username='pytest_admin',
        email='admin_test@example.com',
        password='TestPassword123!',
        first_name='Test',
        last_name='Admin'
    )
    admin_user.role = 'admin'
    admin_user.save()

    category, _ = Category.objects.get_or_create(
        name='Healthy Kerala Breakfast',
        defaults={'description': 'Nutritious morning foods'}
    )
    meal_session, _ = MealSession.objects.get_or_create(
        name='Morning Breakfast',
        defaults={'start_time': '07:00:00', 'end_time': '11:00:00'}
    )
    food_item, _ = FoodItem.objects.get_or_create(
        name='Pytest Kerala Appam with Stew',
        defaults={
            'category': category,
            'meal_session': meal_session,
            'price': Decimal('120.00'),
            'description': 'Soft fermented rice appam with flavorful vegetable stew',
            'stock_quantity': 25,
            'is_available': True,
            'chef': chef_user
        }
    )

    data = {
        'customer': customer,
        'chef': chef_user,
        'courier': courier_user,
        'staff': staff_user,
        'admin': admin_user,
        'category': category,
        'meal_session': meal_session,
        'food_item': food_item
    }

    yield data

    # Cleanup
    User.objects.filter(username__in=test_usernames).delete()
    FoodItem.objects.filter(name='Pytest Kerala Appam with Stew').delete()
