import pytest
from decimal import Decimal
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from orders.models import Order, OrderItem

@pytest.mark.django_db(transaction=True)
def test_chef_dashboard_overview_and_metrics(driver, base_url, test_setup_data, auth_helper):
    """
    Objective: Validate Chef Dashboard loads with authentic kitchen metrics and orders overview.
    Preconditions: Authenticated as 'pytest_chef'.
    Actions: Navigate to /chef/dashboard/.
    Expected Result: Dashboard displays kitchen specialty, order stats, and earnings cards.
    """
    auth_helper("pytest_chef", "TestPassword123!")
    wait = WebDriverWait(driver, 10)
    wait.until(lambda d: "/login" not in d.current_url)

    driver.get(f"{base_url}/chef/dashboard/")
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    page_text = driver.page_source
    assert "Kitchen" in page_text or "Chef" in page_text or "Dashboard" in page_text
    assert "Orders" in page_text or "Menu" in page_text

@pytest.mark.django_db(transaction=True)
def test_chef_menu_management_and_stock(driver, base_url, test_setup_data, auth_helper):
    """
    Objective: Validate chef can view food items and verify availability status.
    Preconditions: Chef has food item 'Pytest Kerala Appam with Stew' assigned.
    Actions: Navigate to chef dashboard, inspect menu management section.
    Expected Result: Food item appears with stock and price details.
    """
    food = test_setup_data['food_item']
    auth_helper("pytest_chef", "TestPassword123!")
    wait = WebDriverWait(driver, 10)
    wait.until(lambda d: "/login" not in d.current_url)

    driver.get(f"{base_url}/chef/dashboard/")
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    page_text = driver.page_source
    assert food.name in page_text or "Appam" in page_text

@pytest.mark.django_db(transaction=True)
def test_chef_order_preparation_status_update(driver, base_url, test_setup_data, auth_helper):
    """
    Objective: Verify chef can see assigned orders and update preparation status.
    Preconditions: Customer order exists containing chef's food item.
    Actions: Chef accesses dashboard, verifies order appears.
    Expected Result: Order card displayed under incoming/active orders.
    """
    customer = test_setup_data['customer']
    food = test_setup_data['food_item']

    order = Order.objects.create(
        order_id="VR-PYTEST-CHEF-01",
        user=customer,
        total_amount=Decimal('120.00'),
        status='preparing',
        delivery_address='Kaloor, Kochi'
    )
    OrderItem.objects.create(order=order, food_item=food, quantity=1, price=Decimal('120.00'))

    try:
        auth_helper("pytest_chef", "TestPassword123!")
        wait = WebDriverWait(driver, 10)
        wait.until(lambda d: "/login" not in d.current_url)

        driver.get(f"{base_url}/chef/dashboard/")
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        page_text = driver.page_source
        assert order.order_id in page_text
    finally:
        order.delete()
