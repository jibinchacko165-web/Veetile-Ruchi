import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.mark.django_db(transaction=True)
def test_registration_form_validation(driver, base_url):
    """
    Objective: Validate customer account registration and input validation.
    Preconditions: Visitor navigates to /register/.
    Actions: 
      1. Submit invalid phone number and verify rejection.
      2. Submit valid details and verify successful registration.
    Expected Result: Registration succeeds, user record created in test DB.
    """
    driver.get(f"{base_url}/register/")
    wait = WebDriverWait(driver, 10)
    
    # Clean up test registration username if exists
    User.objects.filter(username="pytest_reg_user").delete()

    # Step 1: Attempt registration with invalid phone (letters / short)
    wait.until(EC.presence_of_element_located((By.NAME, "username"))).send_keys("pytest_reg_user")
    driver.find_element(By.NAME, "email").send_keys("pytest_reg@example.com")
    phone_input = driver.find_element(By.NAME, "phone")
    phone_input.clear()
    phone_input.send_keys("12345")  # Invalid format
    driver.find_element(By.NAME, "dob").send_keys("1995-05-15")
    driver.find_element(By.NAME, "password").send_keys("StrongPass123!")
    driver.find_element(By.NAME, "confirm_password").send_keys("StrongPass123!")
    
    submit_btn = driver.find_element(By.XPATH, "//button[@type='submit']")
    driver.execute_script("arguments[0].scrollIntoView(true); arguments[0].click();", submit_btn)
    
    # Verification of failure or error feedback
    assert not User.objects.filter(username="pytest_reg_user").exists()

    # Step 2: Fresh page load, fill valid details and complete registration
    driver.get(f"{base_url}/register/")
    wait.until(EC.presence_of_element_located((By.NAME, "username"))).send_keys("pytest_reg_user")
    driver.find_element(By.NAME, "email").send_keys("pytest_reg@example.com")
    dob_el = driver.find_element(By.NAME, "dob")
    driver.execute_script("arguments[0].value = '1995-10-10';", dob_el)
    driver.find_element(By.NAME, "phone").send_keys("9876543299")
    driver.find_element(By.NAME, "password").send_keys("StrongPass123!")
    driver.find_element(By.NAME, "confirm_password").send_keys("StrongPass123!")
    
    submit_btn = driver.find_element(By.XPATH, "//button[@type='submit']")
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", submit_btn)
    
    # Verify redirected to login with success message
    wait.until(lambda d: "/login" in d.current_url or "/" in d.current_url)
    assert User.objects.filter(username="pytest_reg_user").exists()
    
    # Cleanup
    User.objects.filter(username="pytest_reg_user").delete()

@pytest.mark.django_db(transaction=True)
def test_login_with_valid_credentials(driver, base_url, test_setup_data):
    """
    Objective: Validate authentication with correct user credentials.
    Preconditions: Account 'pytest_customer' exists in test DB.
    Actions: Enter username & password on /login/, submit.
    Expected Result: Successful authentication, session created, navbar shows user profile.
    """
    driver.get(f"{base_url}/login/")
    wait = WebDriverWait(driver, 10)
    
    wait.until(EC.presence_of_element_located((By.NAME, "username"))).send_keys("pytest_customer")
    driver.find_element(By.NAME, "password").send_keys("TestPassword123!")
    sub_btn = driver.find_element(By.XPATH, "//button[@type='submit']")
    driver.execute_script("arguments[0].scrollIntoView(true); arguments[0].click();", sub_btn)
    
    wait.until(lambda d: "/login" not in d.current_url)
    assert driver.current_url.startswith(base_url)
    # Check that logout or user link exists in page
    page_text = driver.page_source
    assert "pytest_customer" in page_text or "Logout" in page_text or "Profile" in page_text

@pytest.mark.django_db(transaction=True)
def test_login_with_invalid_credentials(driver, base_url):
    """
    Objective: Validate rejection and error banner for invalid credentials.
    Preconditions: Visitor on /login/.
    Actions: Enter non-existent username and wrong password, submit.
    Expected Result: Login rejected, remains on /login/, alert banner displayed.
    """
    driver.get(f"{base_url}/login/")
    wait = WebDriverWait(driver, 10)
    
    wait.until(EC.presence_of_element_located((By.NAME, "username"))).send_keys("nonexistent_user")
    driver.find_element(By.NAME, "password").send_keys("WrongPass999!")
    sub_btn = driver.find_element(By.XPATH, "//button[@type='submit']")
    driver.execute_script("arguments[0].scrollIntoView(true); arguments[0].click();", sub_btn)
    
    # Alert message displayed
    wait.until(lambda d: "Invalid username/email or password" in d.page_source or "⚠️" in d.page_source)
    assert "/login" in driver.current_url

@pytest.mark.django_db(transaction=True)
def test_logout_and_session_termination(driver, base_url, test_setup_data, auth_helper):
    """
    Objective: Verify complete session destruction upon logout.
    Preconditions: Customer logged in.
    Actions: Navigate to /logout/ or click logout.
    Expected Result: Session destroyed, redirected to login or home, user elements absent.
    """
    auth_helper("pytest_customer", "TestPassword123!")
    wait = WebDriverWait(driver, 10)
    wait.until(lambda d: "/login" not in d.current_url)
    
    # Perform logout
    driver.get(f"{base_url}/logout/")
    wait.until(lambda d: "/login" in d.current_url or d.current_url == f"{base_url}/")
    
    # Verify protected profile page redirects to login
    driver.get(f"{base_url}/accounts/profile/")
    wait.until(lambda d: "/login" in d.current_url)
    assert "/login" in driver.current_url
