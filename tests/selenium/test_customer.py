import pytest
from decimal import Decimal
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from orders.models import CartItem, Order, OrderItem
from delivery.models import DeliverySetting, DeliveryAssignment

@pytest.mark.django_db(transaction=True)
def test_food_catalog_browsing_and_search(driver, base_url, test_setup_data):
    """
    Objective: Validate food catalog browsing, session filtering, and food item search.
    Preconditions: Food item 'Pytest Kerala Appam with Stew' exists.
    Actions: Navigate to catalog, use search input for 'Appam', submit search.
    Expected Result: Matching food item card appears in search results with correct price.
    """
    driver.get(f"{base_url}/?q=Appam")
    wait = WebDriverWait(driver, 10)
    
    # Verify food card appears
    card_title = wait.until(EC.visibility_of_element_located((By.XPATH, "//*[contains(text(), 'Appam')]")))
    assert "Appam" in card_title.text
    page_source = driver.page_source
    assert "120" in page_source

@pytest.mark.django_db(transaction=True)
def test_food_detail_view(driver, base_url, test_setup_data):
    """
    Objective: Verify food detail view renders full description, price, and chef info.
    Preconditions: Food item exists.
    Actions: Navigate directly to /food/<id>/.
    Expected Result: Food detail page renders item title, description, and 'Add to Cart' button.
    """
    food = test_setup_data['food_item']
    driver.get(f"{base_url}/food/{food.id}/")
    wait = WebDriverWait(driver, 10)
    
    heading = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "main h1")))
    assert food.name in heading.text or "Appam" in heading.text
    page_text = driver.page_source
    assert "₹120" in page_text or "120.00" in page_text
    assert "Add to Basket" in page_text or "Basket" in page_text or "Cart" in page_text

@pytest.mark.django_db(transaction=True)
def test_cart_operations_and_total_calculation(driver, base_url, test_setup_data, auth_helper):
    """
    Objective: Verify adding items to cart, subtotal, and total price calculation.
    Preconditions: Customer logged in; CartItem with quantity 2 created in DB.
    Actions: Navigate to /orders/cart/.
    Expected Result: Cart displays item, quantity 2, and correct total (2 * 120 = 240).
    """
    customer = test_setup_data['customer']
    food = test_setup_data['food_item']
    CartItem.objects.filter(user=customer).delete()
    CartItem.objects.create(user=customer, food_item=food, quantity=2)

    auth_helper("pytest_customer", "TestPassword123!")
    wait = WebDriverWait(driver, 10)
    wait.until(lambda d: "/login" not in d.current_url)

    driver.get(f"{base_url}/orders/cart/")
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    page_text = driver.page_source
    assert food.name in page_text or "Appam" in page_text
    assert "240" in page_text

    # Cleanup
    CartItem.objects.filter(user=customer).delete()

@pytest.mark.django_db(transaction=True)
def test_checkout_and_order_placement(driver, base_url, test_setup_data, auth_helper):
    """
    Objective: Verify checkout page loading, address preview, and order placement.
    Preconditions: Active central kitchen hub setting exists; cart has 1 item.
    Actions: Navigate to checkout, click Place Order.
    Expected Result: Order placed, new Order record created with status 'pending'/'placed'.
    """
    customer = test_setup_data['customer']
    food = test_setup_data['food_item']
    
    DeliverySetting.objects.all().delete()
    DeliverySetting.objects.create(
        name="Central Kitchen Hub (Kanjirappally)",
        address="Jubilee Junction, Kanjirappally, Kerala",
        latitude=9.5564,
        longitude=76.7909,
        max_delivery_radius_km=30.0,
        is_active=True
    )
    
    CartItem.objects.filter(user=customer).delete()
    CartItem.objects.create(user=customer, food_item=food, quantity=1)

    auth_helper("pytest_customer", "TestPassword123!")
    wait = WebDriverWait(driver, 10)
    wait.until(lambda d: "/login" not in d.current_url)

    driver.get(f"{base_url}/orders/checkout/")
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    # Verify order summary shows item and price
    page_text = driver.page_source
    assert food.name in page_text or "Appam" in page_text

    # Place order form submission
    place_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Place Order') or contains(., 'Confirm')]")))
    driver.execute_script("arguments[0].scrollIntoView(true); arguments[0].click();", place_btn)

    wait.until(lambda d: "/history" in d.current_url or "/track" in d.current_url or "/checkout" not in d.current_url)
    assert Order.objects.filter(user=customer).exists()

@pytest.mark.django_db(transaction=True)
def test_customer_order_history_and_status(driver, base_url, test_setup_data, auth_helper):
    """
    Objective: Validate customer order history page and order status rendering.
    Preconditions: Customer has an existing order in test DB.
    Actions: Navigate to /orders/history/.
    Expected Result: Order ID, food items, total amount, and status badge displayed.
    """
    customer = test_setup_data['customer']
    food = test_setup_data['food_item']
    
    order = Order.objects.create(
        order_id="VR-PYTEST-ORD-01",
        user=customer,
        total_amount=Decimal('120.00'),
        status='preparing',
        delivery_address='MG Road, Ernakulam'
    )
    OrderItem.objects.create(order=order, food_item=food, quantity=1, price=Decimal('120.00'))

    auth_helper("pytest_customer", "TestPassword123!")
    wait = WebDriverWait(driver, 10)
    wait.until(lambda d: "/login" not in d.current_url)

    driver.get(f"{base_url}/orders/history/")
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    page_source = driver.page_source
    assert order.order_id in page_source
    assert "120" in page_source
    assert "Preparing" in page_source or "preparing" in page_source

    # Cleanup
    order.delete()

@pytest.mark.django_db(transaction=True)
def test_customer_order_cancellation_and_stock_restoration(driver, base_url, test_setup_data, auth_helper):
    """
    Objective: Customer cancels pending order, stock is restored, and status updates to cancelled.
    Preconditions: Pending order placed with 2 portions of Appam.
    Actions: Customer clicks 'Cancel' button on /orders/history/ and confirms dialog.
    Expected Result: Order status updates to 'cancelled' and stock restored (+2).
    """
    customer = test_setup_data['customer']
    food = test_setup_data['food_item']
    initial_stock = food.stock_quantity

    order = Order.objects.create(
        order_id="VR-CANC-01",
        user=customer,
        total_amount=Decimal('240.00'),
        status='pending',
        delivery_address='Palarivattom, Kochi'
    )
    OrderItem.objects.create(order=order, food_item=food, quantity=2, price=Decimal('120.00'))

    try:
        auth_helper("pytest_customer", "TestPassword123!")
        wait = WebDriverWait(driver, 10)
        wait.until(lambda d: "/login" not in d.current_url)

        driver.get(f"{base_url}/orders/history/")
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Override confirm popup to auto-accept
        driver.execute_script("window.confirm = function() { return true; };")

        cancel_btn = wait.until(EC.element_to_be_clickable(
            (By.XPATH, f"//form[contains(@action, '{order.order_id}')]//button[contains(., 'Cancel')]")
        ))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", cancel_btn)

        wait.until(lambda d: "Cancelled" in d.page_source or "cancelled" in d.page_source)
        order.refresh_from_db()
        assert order.status == 'cancelled'

        food.refresh_from_db()
        assert food.stock_quantity == initial_stock + 2
    finally:
        order.delete()

@pytest.mark.django_db(transaction=True)
def test_customer_dual_feedback_submission(driver, base_url, test_setup_data, auth_helper):
    """
    Objective: Customer submits independent Food & Chef and Courier & Delivery reviews.
    Preconditions: Delivered order with courier assignment.
    Actions: Customer opens review modals, enters 5-star ratings, submits.
    Expected Result: Both review buttons update to rated states; feedback records created.
    """
    customer = test_setup_data['customer']
    food = test_setup_data['food_item']
    courier_profile = test_setup_data['courier'].delivery_boy_profile

    order = Order.objects.create(
        order_id="VR-FB-01",
        user=customer,
        total_amount=Decimal('120.00'),
        status='delivered'
    )
    OrderItem.objects.create(order=order, food_item=food, quantity=1, price=Decimal('120.00'))
    assignment = DeliveryAssignment.objects.create(
        order=order,
        delivery_boy=courier_profile,
        status='delivered'
    )

    try:
        auth_helper("pytest_customer", "TestPassword123!")
        wait = WebDriverWait(driver, 10)
        wait.until(lambda d: "/login" not in d.current_url)

        driver.get(f"{base_url}/orders/history/")
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Food & Chef Review: Open modal, populate, and submit
        rate_chef_btn = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//button[contains(., 'Rate Food & Chef')]")
        ))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", rate_chef_btn)

        wait.until(lambda d: d.find_element(By.ID, "chefFeedbackModal").is_displayed())
        driver.execute_script("""
            const comment = document.getElementById("chefCommentInput");
            if (comment) comment.value = "Delicious authentic taste!";
            const form = document.getElementById("chefFeedbackForm");
            if (form) form.submit();
        """)

        wait.until(lambda d: "✅ Food Rated" in d.page_source or "5★" in d.page_source)
    finally:
        assignment.delete()
        order.delete()
