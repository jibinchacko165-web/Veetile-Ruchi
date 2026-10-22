import json
import zoneinfo
from datetime import datetime, timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.conf import settings

from accounts.models import User, DeliveryBoyProfile, ChefProfile
from food.models import Category, MealSession, FoodItem
from orders.models import Order, OrderItem, Payment, Notification
from delivery.models import DeliveryAssignment, District, HotelBranch
from orders.utils import to_kolkata_datetime, format_kolkata_time, KOLKATA_TZ


class OrderWorkflowAndTimestampsTestCase(TestCase):
    """
    Comprehensive test suite validating:
    1. Localized Asia/Kolkata event timestamps without UTC leakage.
    2. Complete 7-step Order Workflow:
       Order Placed -> Chef Accepted -> Food Prepared -> Staff Assigns Courier ->
       Courier Picks Up -> In Transit -> Delivered.
    3. Chef Dashboard status wording and action buttons.
    4. Staff assignment validations and courier busy/available checks.
    5. Courier role-based authorization and sequential state transition guards.
    """

    def setUp(self):
        self.client = Client()
        self.password = "Secr3tP@ssw0rd!"

        # Create District & Hub
        self.district = District.objects.create(
            name="Kottayam",
            code="kottayam",
            latitude=9.5564,
            longitude=76.7909
        )
        self.branch = HotelBranch.objects.create(
            name="Kanjirappally Central Kitchen",
            district=self.district,
            address="Kanjirappally, Kerala",
            latitude=9.5564,
            longitude=76.7909,
            max_delivery_radius_km=30.0,
            is_central_hub=True,
            is_active=True
        )

        # Users
        self.customer = User.objects.create_user(
            username="customer_anu",
            email="anu@example.com",
            password=self.password,
            role="customer",
            phone="9876543210"
        )
        self.chef_user = User.objects.create_user(
            username="chef_suresh",
            email="suresh@example.com",
            password=self.password,
            role="chef",
            phone="9876543211"
        )
        self.chef_profile = ChefProfile.objects.create(
            user=self.chef_user,
            is_approved=True,
            specialty="Traditional Kerala Cuisine"
        )

        self.staff_user = User.objects.create_user(
            username="staff_rahul",
            email="rahul@example.com",
            password=self.password,
            role="staff",
            phone="9876543212"
        )

        self.courier_user1 = User.objects.create_user(
            username="courier_vipin",
            email="vipin@example.com",
            password=self.password,
            role="delivery_boy",
            phone="9876543213"
        )
        self.courier_profile1 = DeliveryBoyProfile.objects.create(
            user=self.courier_user1,
            vehicle_number="KL-34-A-1234",
            status="available",
            current_latitude=9.5564,
            current_longitude=76.7909
        )

        self.courier_user2 = User.objects.create_user(
            username="courier_shyam",
            email="shyam@example.com",
            password=self.password,
            role="delivery_boy",
            phone="9876543214"
        )
        self.courier_profile2 = DeliveryBoyProfile.objects.create(
            user=self.courier_user2,
            vehicle_number="KL-34-B-5678",
            status="available",
            current_latitude=9.5564,
            current_longitude=76.7909
        )

        # Food item
        self.category, _ = Category.objects.get_or_create(name="Vegetarian", defaults={'description': 'Fresh Vegetarian Dishes'})
        self.session, _ = MealSession.objects.get_or_create(name="Morning Breakfast", defaults={'start_time': "06:00:00", 'end_time': "11:30:00"})
        self.food = FoodItem.objects.create(
            chef=self.chef_user,
            name="Wheat Puttu with Green Gram Curry",
            description="Traditional Kerala breakfast",
            price=90.00,
            category=self.category,
            meal_session=self.session,
            stock_quantity=50,
            is_available=True
        )

    def test_timezone_configuration_and_helpers(self):
        """Verify settings are configured for Asia/Kolkata and to_kolkata_datetime converts properly."""
        self.assertTrue(settings.USE_TZ)
        self.assertEqual(settings.TIME_ZONE, 'Asia/Kolkata')

        # Create known UTC timestamp: 2026-10-22 00:32:00 UTC
        utc_dt = datetime(2026, 10, 22, 0, 32, 0, tzinfo=zoneinfo.ZoneInfo('UTC'))
        kolkata_dt = to_kolkata_datetime(utc_dt)
        self.assertEqual(kolkata_dt.tzinfo.key, 'Asia/Kolkata')
        # +05:30 -> 06:02:00 AM
        self.assertEqual(kolkata_dt.hour, 6)
        self.assertEqual(kolkata_dt.minute, 2)
        formatted = kolkata_dt.strftime("%b %d, %Y • %I:%M %p")
        self.assertEqual(formatted, "Oct 22, 2026 • 06:02 AM")

    def test_complete_order_lifecycle_and_status_transitions(self):
        """
        End-to-end test of the entire 7-step sequence:
        Order Placed (pending) -> Chef Preparing -> Food Prepared -> Staff Assigned ->
        Courier Picked Up -> In Transit -> Delivered.
        """
        # Step 1: Customer places order
        order = Order.objects.create(
            user=self.customer,
            total_amount=90.00,
            branch=self.branch,
            latitude=9.5580,
            longitude=76.7915,
            status='pending'
        )
        OrderItem.objects.create(order=order, food_item=self.food, quantity=1, price=90.00)
        Payment.objects.create(order=order, payment_method='cod', amount=90.00, status='pending')

        self.assertEqual(order.status, 'pending')
        self.assertIsNotNone(order.created_at)
        self.assertIsNone(order.preparing_started_at)
        self.assertIsNone(order.food_prepared_at)
        self.assertIsNone(order.courier_assigned_at)
        self.assertIsNone(order.picked_up_at)
        self.assertIsNone(order.delivered_at)

        # Step 2: Chef accepts order
        self.client.login(username="chef_suresh", password=self.password)
        resp = self.client.post(reverse('chef_order_status_update', args=[order.order_id]), {'status': 'preparing'})
        self.assertEqual(resp.status_code, 302)

        order.refresh_from_db()
        self.assertEqual(order.status, 'preparing')
        self.assertIsNotNone(order.preparing_started_at)
        self.assertIsNone(order.food_prepared_at)

        # Step 3: Chef marks food prepared
        resp = self.client.post(reverse('chef_order_status_update', args=[order.order_id]), {'status': 'ready_pickup'})
        self.assertEqual(resp.status_code, 302)

        order.refresh_from_db()
        self.assertEqual(order.status, 'ready_pickup')
        self.assertIsNotNone(order.food_prepared_at)

        # Verify Chef order queue API status_message for ready_pickup
        resp = self.client.get(reverse('api_chef_orders'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        target_card = next((item for item in data['orders'] if item['order_id'] == order.order_id), None)
        self.assertIsNotNone(target_card)
        self.assertEqual(target_card['status'], 'ready_pickup')
        self.assertEqual(target_card['status_message'], 'Food Prepared — Awaiting Staff Courier Assignment')
        # Timestamp must be localized and formatted clearly
        self.assertIn("•", target_card['created_at'])

        # Step 4: Staff assigns Courier
        self.client.login(username="staff_rahul", password=self.password)
        resp = self.client.post(reverse('staff_assign_delivery', args=[order.order_id]), {
            'delivery_boy_id': self.courier_profile1.id
        })
        self.assertEqual(resp.status_code, 302)

        order.refresh_from_db()
        self.assertEqual(order.status, 'assigned')
        self.assertIsNotNone(order.courier_assigned_at)
        self.assertTrue(hasattr(order, 'delivery_assignment'))
        self.assertEqual(order.delivery_assignment.status, 'assigned')
        self.assertEqual(order.delivery_assignment.delivery_boy, self.courier_profile1)

        self.courier_profile1.refresh_from_db()
        self.assertEqual(self.courier_profile1.status, 'on_delivery')

        # Verify Chef order queue API status_message for assigned
        self.client.login(username="chef_suresh", password=self.password)
        resp = self.client.get(reverse('api_chef_orders'))
        data = resp.json()
        target_card = next((item for item in data['orders'] if item['order_id'] == order.order_id), None)
        self.assertIsNotNone(target_card)
        self.assertEqual(target_card['status'], 'assigned')
        self.assertEqual(target_card['status_message'], 'Courier Assigned — Awaiting Pickup')

        # Step 5: Courier confirms pickup
        self.client.login(username="courier_vipin", password=self.password)
        resp = self.client.post(reverse('pickup_order', args=[order.delivery_assignment.id]))
        self.assertEqual(resp.status_code, 302)

        order.refresh_from_db()
        self.assertEqual(order.status, 'picked_up')
        self.assertIsNotNone(order.picked_up_at)
        order.delivery_assignment.refresh_from_db()
        self.assertEqual(order.delivery_assignment.status, 'picked_up')
        self.assertIsNotNone(order.delivery_assignment.picked_up_at)

        # Step 6: Courier starts delivery (In Transit)
        resp = self.client.post(reverse('start_delivery', args=[order.delivery_assignment.id]))
        self.assertEqual(resp.status_code, 302)

        order.refresh_from_db()
        self.assertEqual(order.status, 'in_transit')
        order.delivery_assignment.refresh_from_db()
        self.assertEqual(order.delivery_assignment.status, 'in_transit')
        self.assertIsNotNone(order.delivery_assignment.out_for_delivery_at)

        # Verify Chef order queue API status_message for in_transit
        self.client.login(username="chef_suresh", password=self.password)
        resp = self.client.get(reverse('api_chef_orders'))
        data = resp.json()
        target_card = next((item for item in data['orders'] if item['order_id'] == order.order_id), None)
        self.assertIsNotNone(target_card)
        self.assertEqual(target_card['status_message'], 'Picked Up — In Transit')

        # Verify customer tracking API reflects all milestone timestamps in local time
        self.client.login(username="customer_anu", password=self.password)
        resp = self.client.get(reverse('api_order_status', args=[order.order_id]))
        self.assertEqual(resp.status_code, 200)
        track_json = resp.json()
        self.assertEqual(track_json['order_status'], 'in_transit')
        ts = track_json['timestamps']
        self.assertIsNotNone(ts['confirmed_time'])
        self.assertIsNotNone(ts['preparing_time'])
        self.assertIsNotNone(ts['prepared_time'])
        self.assertIsNotNone(ts['assigned_time'])
        self.assertIsNotNone(ts['picked_up_time'])
        self.assertIsNotNone(ts['out_for_delivery_time'])
        self.assertIsNone(ts['delivered_time'])

        # Step 7: Courier completes delivery
        self.client.login(username="courier_vipin", password=self.password)
        resp = self.client.post(reverse('complete_delivery', args=[order.delivery_assignment.id]))
        self.assertEqual(resp.status_code, 302)

        order.refresh_from_db()
        self.assertEqual(order.status, 'delivered')
        self.assertIsNotNone(order.delivered_at)

        order.delivery_assignment.refresh_from_db()
        self.assertEqual(order.delivery_assignment.status, 'delivered')
        self.assertFalse(order.delivery_assignment.is_active)
        self.assertIsNotNone(order.delivery_assignment.delivered_at)

        # Courier 1 should automatically be reset to available
        self.courier_profile1.refresh_from_db()
        self.assertEqual(self.courier_profile1.status, 'available')

        # Final customer tracking verification
        self.client.login(username="customer_anu", password=self.password)
        resp = self.client.get(reverse('api_order_status', args=[order.order_id]))
        track_json = resp.json()
        self.assertEqual(track_json['order_status'], 'delivered')
        self.assertIsNotNone(track_json['timestamps']['delivered_time'])

    def test_courier_security_and_unauthorized_access(self):
        """Verify courier B cannot view or update an order assigned to courier A."""
        order = Order.objects.create(
            user=self.customer,
            total_amount=90.00,
            branch=self.branch,
            latitude=9.5580,
            longitude=76.7915,
            status='assigned',
            food_prepared_at=timezone.now(),
            courier_assigned_at=timezone.now()
        )
        OrderItem.objects.create(order=order, food_item=self.food, quantity=1, price=90.00)
        assignment = DeliveryAssignment.objects.create(
            order=order,
            delivery_boy=self.courier_profile1,
            status='assigned',
            is_active=True
        )

        # Log in as unauthorized courier 2
        self.client.login(username="courier_shyam", password=self.password)

        # Try to view courier 1's track page
        resp = self.client.get(reverse('delivery_boy_track', args=[assignment.id]))
        self.assertEqual(resp.status_code, 302) # Redirected with Access restricted error

        # Try to pickup courier 1's order
        resp = self.client.post(reverse('pickup_order', args=[assignment.id]))
        self.assertEqual(resp.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, 'assigned') # Unchanged

        # Try to start delivery of courier 1's order
        resp = self.client.post(reverse('start_delivery', args=[assignment.id]))
        self.assertEqual(resp.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, 'assigned') # Unchanged

        # Try to complete delivery of courier 1's order
        resp = self.client.post(reverse('complete_delivery', args=[assignment.id]))
        self.assertEqual(resp.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, 'assigned') # Unchanged

    def test_invalid_status_jumps_rejected(self):
        """Prevent invalid sequence jumps such as premature delivery or skipping pickup."""
        order = Order.objects.create(
            user=self.customer,
            total_amount=90.00,
            branch=self.branch,
            latitude=9.5580,
            longitude=76.7915,
            status='assigned',
            food_prepared_at=timezone.now(),
            courier_assigned_at=timezone.now()
        )
        OrderItem.objects.create(order=order, food_item=self.food, quantity=1, price=90.00)
        assignment = DeliveryAssignment.objects.create(
            order=order,
            delivery_boy=self.courier_profile1,
            status='assigned',
            is_active=True
        )

        self.client.login(username="courier_vipin", password=self.password)

        # Cannot complete delivery directly from assigned status
        resp = self.client.post(reverse('complete_delivery', args=[assignment.id]))
        self.assertEqual(resp.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, 'assigned') # Order should NOT be marked delivered

        # Pickup order once
        resp = self.client.post(reverse('pickup_order', args=[assignment.id]))
        self.assertEqual(resp.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, 'picked_up')

        # Duplicate pickup attempt
        resp = self.client.post(reverse('pickup_order', args=[assignment.id]))
        self.assertEqual(resp.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, 'picked_up')

    def test_staff_cannot_assign_busy_courier(self):
        """Verify staff cannot assign a courier who is already busy on an active delivery."""
        # Set courier 1 to on_delivery with an existing active assignment
        self.courier_profile1.status = 'on_delivery'
        self.courier_profile1.save()

        order_active = Order.objects.create(
            user=self.customer,
            total_amount=90.00,
            branch=self.branch,
            status='in_transit'
        )
        DeliveryAssignment.objects.create(
            order=order_active,
            delivery_boy=self.courier_profile1,
            status='in_transit',
            is_active=True
        )

        # New prepared order waiting for assignment
        order_new = Order.objects.create(
            user=self.customer,
            total_amount=90.00,
            branch=self.branch,
            status='ready_pickup',
            food_prepared_at=timezone.now()
        )

        self.client.login(username="staff_rahul", password=self.password)
        resp = self.client.post(reverse('staff_assign_delivery', args=[order_new.order_id]), {
            'delivery_boy_id': self.courier_profile1.id
        })
        self.assertEqual(resp.status_code, 302)

        order_new.refresh_from_db()
        # Assignment should be rejected and status remained ready_pickup
        self.assertEqual(order_new.status, 'ready_pickup')
        self.assertFalse(hasattr(order_new, 'delivery_assignment'))
