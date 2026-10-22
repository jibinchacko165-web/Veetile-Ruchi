import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

@pytest.mark.django_db(transaction=True)
def test_unauthenticated_user_access_restrictions(driver, base_url):
    """
    Objective: Verify unauthenticated guest users cannot access private portals.
    Preconditions: Visitor is not logged in.
    Actions: Directly navigate to /accounts/profile/, /orders/history/, /chef/dashboard/.
    Expected Result: Redirection to /login/ with 'next' parameter preserved.
    """
    driver.delete_all_cookies()
    wait = WebDriverWait(driver, 10)

    for protected_url in ['/accounts/profile/', '/orders/history/', '/chef/dashboard/', '/delivery/dashboard/']:
        driver.get(f"{base_url}{protected_url}")
        wait.until(lambda d: "/login" in d.current_url)
        assert "/login" in driver.current_url

@pytest.mark.django_db(transaction=True)
def test_customer_blocked_from_chef_and_courier_portals(driver, base_url, test_setup_data, auth_helper):
    """
    Objective: Verify customer cannot access Chef or Courier dashboards.
    Preconditions: Authenticated as 'pytest_customer'.
    Actions: Customer navigates to /chef/dashboard/ and /delivery/dashboard/.
    Expected Result: Access denied (redirected away, 403 Forbidden, or permission error).
    """
    auth_helper("pytest_customer", "TestPassword123!")
    wait = WebDriverWait(driver, 10)
    wait.until(lambda d: "/login" not in d.current_url)

    # Customer accessing chef dashboard
    driver.get(f"{base_url}/chef/dashboard/")
    page_text = driver.page_source
    assert "403" in page_text or "Permission" in page_text or "/chef" not in driver.current_url or "Forbidden" in page_text

    # Customer accessing courier dashboard
    driver.get(f"{base_url}/delivery/dashboard/")
    page_text = driver.page_source
    assert "403" in page_text or "Permission" in page_text or "/delivery/dashboard" not in driver.current_url or "Forbidden" in page_text

@pytest.mark.django_db(transaction=True)
def test_courier_blocked_from_chef_portal(driver, base_url, test_setup_data, auth_helper):
    """
    Objective: Verify courier cannot access Chef kitchen management dashboard.
    Preconditions: Authenticated as 'pytest_courier'.
    Actions: Courier navigates to /chef/dashboard/.
    Expected Result: Access denied.
    """
    auth_helper("pytest_courier", "TestPassword123!")
    wait = WebDriverWait(driver, 10)
    wait.until(lambda d: "/login" not in d.current_url)

    driver.get(f"{base_url}/chef/dashboard/")
    page_text = driver.page_source
    assert "403" in page_text or "Permission" in page_text or "/chef" not in driver.current_url or "Forbidden" in page_text
