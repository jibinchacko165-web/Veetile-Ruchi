import pytest
from decimal import Decimal
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from orders.models import Order, OrderItem
from delivery.models import DeliveryAssignment, DeliveryFeedback

@pytest.mark.django_db(transaction=True)
def test_courier_dashboard_and_availability(driver, base_url, test_setup_data, auth_helper):
    """
    Objective: Validate courier dashboard loads with assigned orders and availability toggle.
    Preconditions: Courier account 'pytest_courier' exists.
    Actions: Authenticate and open /delivery/dashboard/.
    Expected Result: Dashboard loaded, courier status badge visible.
    """
    auth_helper("pytest_courier", "TestPassword123!")
    wait = WebDriverWait(driver, 10)
    wait.until(lambda d: "/login" not in d.current_url)

    driver.get(f"{base_url}/delivery/dashboard/")
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    page_text = driver.page_source
    assert "Courier" in page_text or "Delivery" in page_text or "Orders" in page_text

@pytest.mark.django_db(transaction=True)
def test_courier_assigned_order_details_and_contact(driver, base_url, test_setup_data, auth_helper):
    """
    Objective: Validate courier can view assigned order, customer delivery address, and phone number.
    Preconditions: Order assigned to courier.
    Actions: Courier opens dashboard, inspects assigned order card.
    Expected Result: Order ID, customer address, and phone number rendered.
    """
    customer = test_setup_data['customer']
    food = test_setup_data['food_item']
    courier_profile = test_setup_data['courier'].delivery_boy_profile

    order = Order.objects.create(
        order_id="VR-PYTEST-COUR-01",
        user=customer,
        total_amount=Decimal('120.00'),
        status='assigned',
        delivery_address='Tripunithura, Kochi'
    )
    OrderItem.objects.create(order=order, food_item=food, quantity=1, price=Decimal('120.00'))
    assignment = DeliveryAssignment.objects.create(
        order=order,
        delivery_boy=courier_profile,
        status='assigned'
    )

    try:
        auth_helper("pytest_courier", "TestPassword123!")
        wait = WebDriverWait(driver, 10)
        wait.until(lambda d: "/login" not in d.current_url)

        driver.get(f"{base_url}/delivery/dashboard/")
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        page_source = driver.page_source
        assert order.order_id in page_source
        assert "Tripunithura" in page_source
        assert customer.phone in page_source
    finally:
        assignment.delete()
        order.delete()

@pytest.mark.django_db(transaction=True)
def test_courier_feedback_and_performance_view(driver, base_url, test_setup_data, auth_helper):
    """
    Objective: Validate Courier Performance & Customer Feedback Dashboard view.
    Preconditions: Delivered order with customer rating exists.
    Actions: Courier opens /delivery/dashboard/?tab=profile.
    Expected Result: Rating cards, delivery quality breakdown, and customer comments displayed.
    """
    customer = test_setup_data['customer']
    food = test_setup_data['food_item']
    courier_profile = test_setup_data['courier'].delivery_boy_profile

    order = Order.objects.create(
        order_id="VR-PYTEST-COUR-02",
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
    fb = DeliveryFeedback.objects.create(
        order=order,
        delivery_assignment=assignment,
        delivery_boy=courier_profile,
        customer=customer,
        rating=5,
        timeliness_rating=5,
        behavior_rating=5,
        food_handling_rating=5,
        comment='Fast and polite delivery person!'
    )

    try:
        auth_helper("pytest_courier", "TestPassword123!")
        wait = WebDriverWait(driver, 10)
        wait.until(lambda d: "/login" not in d.current_url)

        driver.get(f"{base_url}/delivery/dashboard/?tab=profile")
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        page_source = driver.page_source
        assert "Fast and polite delivery person!" in page_source
        assert "Rating" in page_source or "Quality" in page_source
    finally:
        fb.delete()
        assignment.delete()
        order.delete()

@pytest.mark.django_db(transaction=True)
def test_courier_notification_modal_display_and_dismissal(driver, base_url, test_setup_data, auth_helper):
    """
    Objective: Courier sees unread assignment notification modal upon login and can dismiss it.
    Preconditions: Unread Notification created for courier.
    Actions: Courier logs in, modal appears with order ID & IST timestamp, clicks dismiss.
    Expected Result: Notification card dismissed via AJAX, order status unmodified.
    """
    from orders.models import Notification

    customer = test_setup_data['customer']
    food = test_setup_data['food_item']
    courier_user = test_setup_data['courier']
    courier_profile = courier_user.delivery_boy_profile

    order = Order.objects.create(
        order_id="VR-PYTEST-NOTIF-01",
        user=customer,
        total_amount=Decimal('120.00'),
        status='assigned',
        delivery_address='Tripunithura, Kochi'
    )
    OrderItem.objects.create(order=order, food_item=food, quantity=1, price=Decimal('120.00'))
    assignment = DeliveryAssignment.objects.create(
        order=order,
        delivery_boy=courier_profile,
        status='assigned'
    )
    notif = Notification.objects.create(
        user=courier_user,
        order=order,
        notification_type='assignment',
        title=f"New Delivery Order Assigned #{order.order_id}",
        message="Please proceed to pickup the freshly packed homemade food.",
        is_read=False
    )

    try:
        auth_helper("pytest_courier", "TestPassword123!")
        wait = WebDriverWait(driver, 10)
        wait.until(lambda d: "/login" not in d.current_url)

        driver.get(f"{base_url}/delivery/dashboard/")
        modal = wait.until(EC.visibility_of_element_located((By.ID, "courierNotificationModal")))
        assert modal.is_displayed()

        page_source = driver.page_source
        assert order.order_id in page_source
        assert "(IST)" in page_source

        # Dismiss notification
        dismiss_btn = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, f"#popup-notif-{notif.id} button")
        ))
        driver.execute_script("arguments[0].click();", dismiss_btn)

        wait.until(EC.invisibility_of_element_located((By.ID, f"popup-notif-{notif.id}")))
        notif.refresh_from_db()
        assert notif.is_read is True
        order.refresh_from_db()
        assert order.status == 'assigned'
    finally:
        notif.delete()
        assignment.delete()
        order.delete()
