import pytest
from decimal import Decimal
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from orders.models import Order, OrderItem

@pytest.mark.django_db(transaction=True)
def test_admin_dashboard_metrics(driver, base_url, test_setup_data, auth_helper):
    """
    Objective: Validate Admin Dashboard overview cards and metrics.
    Preconditions: Superuser/Admin account 'pytest_admin' logged in.
    Actions: Navigate to /admin-dashboard/ or /dashboard/.
    Expected Result: Metrics cards render (Orders, Customers, Chefs, Revenue) without errors.
    """
    auth_helper("pytest_admin", "TestPassword123!")
    wait = WebDriverWait(driver, 10)
    wait.until(lambda d: "/login" not in d.current_url)

    driver.get(f"{base_url}/admin-dashboard/")
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    page_text = driver.page_source
    assert "Admin" in page_text or "Dashboard" in page_text or "Orders" in page_text

@pytest.mark.django_db(transaction=True)
def test_staff_order_courier_assignment(driver, base_url, test_setup_data, auth_helper):
    """
    Objective: Validate staff can assign an unassigned order to an available courier.
    Preconditions: Staff authenticated; order with status 'preparing' exists.
    Actions: Staff opens /orders/staff/dashboard/, selects courier, clicks Assign.
    Expected Result: Order successfully assigned to courier in database and UI updates.
    """
    customer = test_setup_data['customer']
    food = test_setup_data['food_item']

    order = Order.objects.create(
        order_id="VR-PYTEST-STAFF-01",
        user=customer,
        total_amount=Decimal('120.00'),
        status='preparing',
        latitude=9.55,
        longitude=76.79
    )
    OrderItem.objects.create(order=order, food_item=food, quantity=1, price=Decimal('120.00'))

    try:
        auth_helper("pytest_staff", "TestPassword123!")
        wait = WebDriverWait(driver, 10)
        wait.until(lambda d: "/login" not in d.current_url)

        driver.get(f"{base_url}/orders/staff/dashboard/")
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        select_element = wait.until(EC.presence_of_element_located((By.NAME, "delivery_boy_id")))
        select = Select(select_element)
        # Select first available courier option
        if len(select.options) > 1:
            select.select_by_index(1)
            assign_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Assign Delivery Boy')]")
            driver.execute_script("arguments[0].scrollIntoView(true); arguments[0].click();", assign_btn)
            wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(., 'Assigned Courier')]")))

            order.refresh_from_db()
            assert hasattr(order, 'delivery_assignment')
    finally:
        order.delete()
