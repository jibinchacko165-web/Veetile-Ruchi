import json
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import User, DeliveryBoyProfile, ChefProfile
from food.models import Category, MealSession, FoodItem
from orders.models import Order, OrderItem, Payment, Notification
from delivery.models import DeliveryAssignment, District, HotelBranch


class CodPaymentWorkflowTestCase(TestCase):
    """
    Comprehensive test suite validating:
    1. Online Payment: Customer and staff pages clearly display "Paid Online".
    2. Cash on Delivery (COD): Staff page displays "Cash on Delivery" reminder.
    3. Courier Cash Collection: Courier can update payment status to "Cash Collected".
    4. Staff Confirmation: Staff page clearly displays that cash has been received by courier boy.
    5. Cross-role synchronization and invalid transition protection.
    """

    def setUp(self):
        self.client = Client()
        self.password = "Secr3tP@ssw0rd!"

        self.district = District.objects.create(
            name="Kottayam",
            code="kottayam",
            latitude=9.5564,
            longitude=76.7909
        )
        self.branch = HotelBranch.objects.create(
            name="Central Kitchen",
            district=self.district,
            address="Kanjirappally, Kerala",
            latitude=9.5564,
            longitude=76.7909,
            max_delivery_radius_km=30.0,
            is_central_hub=True,
            is_active=True
        )

        self.customer = User.objects.create_user(
            username="customer_user",
            email="cust@example.com",
            password=self.password,
            role="customer",
            first_name="Anu",
            last_name="Mathew",
            phone="9876543210"
        )

        self.chef_user = User.objects.create_user(
            username="chef_user",
            email="chef@example.com",
            password=self.password,
            role="chef",
            phone="9876543211"
        )
        self.chef_profile = ChefProfile.objects.create(
            user=self.chef_user,
            is_approved=True,
            specialty="Kerala Sadhya"
        )

        self.staff_user = User.objects.create_user(
            username="staff_user",
            email="staff@example.com",
            password=self.password,
            role="staff",
            phone="9876543212"
        )

        self.courier_user1 = User.objects.create_user(
            username="courier_boy1",
            email="courier1@example.com",
            password=self.password,
            role="delivery_boy",
            phone="9876543213"
        )
        self.courier_profile1 = DeliveryBoyProfile.objects.create(
            user=self.courier_user1,
            vehicle_number="KL-05-AB-1234",
            status="available",
            current_latitude=9.5564,
            current_longitude=76.7909
        )

        self.courier_user2 = User.objects.create_user(
            username="courier_boy2",
            email="courier2@example.com",
            password=self.password,
            role="delivery_boy",
            phone="9876543214"
        )
        self.courier_profile2 = DeliveryBoyProfile.objects.create(
            user=self.courier_user2,
            vehicle_number="KL-05-CD-5678",
            status="available",
            current_latitude=9.5564,
            current_longitude=76.7909
        )

        self.category, _ = Category.objects.get_or_create(name="Specials", defaults={'description': 'Specials'})
        self.session, _ = MealSession.objects.get_or_create(name="Lunch", defaults={'start_time': "12:00:00", 'end_time': "15:00:00"})
        self.food = FoodItem.objects.create(
            chef=self.chef_user,
            name="Fish Curry Meals",
            price=150.00,
            category=self.category,
            meal_session=self.session,
            stock_quantity=30,
            is_available=True
        )

    def test_online_payment_display_on_customer_and_staff_pages(self):
        """
        Requirement 1: Online Payment
        If customer pays online, customer page and staff page must clearly display 'Paid Online'
        as the payment status.
        """
        # Create an online payment order
        order = Order.objects.create(
            user=self.customer,
            total_amount=150.00,
            branch=self.branch,
            latitude=9.5580,
            longitude=76.7915,
            delivery_address="Green Villa, Pala Road",
            status='preparing'
        )
        Payment.objects.create(
            order=order,
            payment_method='upi',
            transaction_id='UPI-TEST123456',
            status='success',
            amount=150.00
        )

        # 1. Customer Tracking Page must display 'Paid Online'
        self.client.login(username="customer_user", password=self.password)
        resp = self.client.get(reverse('order_tracking', args=[order.order_id]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn("Paid Online", content)

        # 2. Staff Dashboard must display 'Paid Online'
        self.client.login(username="staff_user", password=self.password)
        resp = self.client.get(reverse('staff_dashboard'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn("Paid Online", content)

        # 3. API order status returns 'Paid Online'
        resp = self.client.get(reverse('api_order_status', args=[order.order_id]))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get('payment_display_status'), "Paid Online")
        self.assertEqual(data.get('payment_method'), "upi")

    def test_cod_staff_reminder_and_customer_display(self):
        """
        Requirement 2: Cash on Delivery (COD)
        If customer selects COD, staff page must display a 'Cash on Delivery' reminder
        so staff can identify orders that require cash collection.
        """
        order = Order.objects.create(
            user=self.customer,
            total_amount=300.00,
            branch=self.branch,
            latitude=9.5580,
            longitude=76.7915,
            delivery_address="Riverside Apt 4B, Kanjirappally",
            status='preparing'
        )
        Payment.objects.create(
            order=order,
            payment_method='cod',
            status='pending',
            amount=300.00
        )

        # 1. Staff page must display 'Cash on Delivery Reminder'
        self.client.login(username="staff_user", password=self.password)
        resp = self.client.get(reverse('staff_dashboard'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn("Cash on Delivery Reminder", content)
        self.assertIn("Cash on Delivery", content)
        self.assertIn("300", content)

        # 2. Customer Tracking page displays 'Cash on Delivery'
        self.client.login(username="customer_user", password=self.password)
        resp = self.client.get(reverse('order_tracking', args=[order.order_id]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn("Cash on Delivery", content)

    def test_courier_cash_collection_and_staff_confirmation(self):
        """
        Requirements 3 & 4:
        - Courier Cash Collection: Option for courier boy to update payment status to 'Cash Collected'.
        - Disabled until food handover to customer.
        - Staff Confirmation: Once marked, staff page clearly displays that cash has been received
          by the courier boy.
        """
        order = Order.objects.create(
            user=self.customer,
            total_amount=450.00,
            branch=self.branch,
            latitude=9.5580,
            longitude=76.7915,
            delivery_address="Near Church, Kanjirappally",
            status='in_transit'
        )
        payment = Payment.objects.create(
            order=order,
            payment_method='cod',
            status='pending',
            amount=450.00
        )
        assignment = DeliveryAssignment.objects.create(
            order=order,
            delivery_boy=self.courier_profile1,
            status='in_transit',
            is_active=True
        )

        # Courier 1 logs in and views dashboard active tab
        self.client.login(username="courier_boy1", password=self.password)
        resp = self.client.get(reverse('delivery_boy_dashboard') + '?tab=active')
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        # Before food handover, COD confirmation button must be disabled
        self.assertIn("Disabled until handover", content)

        # Attempt to confirm cash collection before food handover is rejected
        resp = self.client.post(reverse('courier_collect_cash', args=[assignment.id]))
        self.assertEqual(resp.status_code, 302)
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'pending') # Still pending

        # Courier reaches customer and marks delivery completed (hands over food)
        resp = self.client.post(reverse('complete_delivery', args=[assignment.id]))
        self.assertEqual(resp.status_code, 302)
        order.refresh_from_db()
        assignment.refresh_from_db()
        self.assertEqual(order.status, 'delivered')

        # After food handover, COD button is unlocked and courier confirms cash received
        resp = self.client.post(reverse('courier_collect_cash', args=[assignment.id]))
        self.assertEqual(resp.status_code, 302)

        # Verify Payment model state
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'cash_collected')
        self.assertIsNotNone(payment.cash_collected_at)
        self.assertEqual(payment.cash_collected_by, self.courier_user1)
        self.assertEqual(payment.display_status, "Cash Collected")

        # After delivery completion, courier availability status automatically updates to Available
        self.courier_profile1.refresh_from_db()
        self.assertEqual(self.courier_profile1.realtime_status, 'Available')

        # Verify courier dashboard active tab now displays Cash Collected
        resp = self.client.get(reverse('delivery_boy_dashboard') + '?tab=active')
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn("Cash Collected", content)

        # Verify customer page updates to 'Cash Collected'
        self.client.login(username="customer_user", password=self.password)
        resp = self.client.get(reverse('order_tracking', args=[order.order_id]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn("Cash Collected", content)

        # Staff page: Requirement 4: Clearly displays that cash has been received by courier boy
        self.client.login(username="staff_user", password=self.password)
        resp = self.client.get(reverse('staff_dashboard'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn("Cash Collected", content)
        self.assertIn("Cash Received by Courier", content)
        self.assertIn("Courier_Boy1", content) # Displays courier who received cash

        # Staff can confirm deposit to register
        resp = self.client.post(reverse('staff_confirm_payment', args=[order.order_id]))
        self.assertEqual(resp.status_code, 302)
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'success')
        self.assertEqual(payment.display_status, "Cash Collected")

    def test_courier_cannot_collect_cash_on_online_payment(self):
        """
        Security / validation guard: Online orders cannot be marked as cash collected.
        """
        order = Order.objects.create(
            user=self.customer,
            total_amount=200.00,
            branch=self.branch,
            latitude=9.5580,
            longitude=76.7915,
            delivery_address="Pala Road",
            status='in_transit'
        )
        payment = Payment.objects.create(
            order=order,
            payment_method='upi',
            transaction_id='UPI-PAY999',
            status='success',
            amount=200.00
        )
        assignment = DeliveryAssignment.objects.create(
            order=order,
            delivery_boy=self.courier_profile1,
            status='in_transit',
            is_active=True
        )

        self.client.login(username="courier_boy1", password=self.password)
        # Attempt to mark online order as cash collected
        resp = self.client.post(reverse('courier_collect_cash', args=[assignment.id]))
        self.assertEqual(resp.status_code, 302)

        # Payment should NOT change to cash_collected
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'success')
        self.assertIsNone(payment.cash_collected_at)

    def test_courier_cannot_collect_cash_for_another_couriers_order(self):
        """
        Security guard: Courier boy 2 cannot update cash collection for courier boy 1's assignment.
        """
        order = Order.objects.create(
            user=self.customer,
            total_amount=250.00,
            branch=self.branch,
            latitude=9.5580,
            longitude=76.7915,
            delivery_address="Pala Road",
            status='in_transit'
        )
        payment = Payment.objects.create(
            order=order,
            payment_method='cod',
            status='pending',
            amount=250.00
        )
        assignment = DeliveryAssignment.objects.create(
            order=order,
            delivery_boy=self.courier_profile1,
            status='in_transit',
            is_active=True
        )

        # Courier 2 attempts to collect cash for Courier 1's assignment
        self.client.login(username="courier_boy2", password=self.password)
        resp = self.client.post(reverse('courier_collect_cash', args=[assignment.id]))
        self.assertEqual(resp.status_code, 302)

        payment.refresh_from_db()
        self.assertEqual(payment.status, 'pending')
        self.assertIsNone(payment.cash_collected_at)

    def test_complete_delivery_with_cash_collected_checkbox(self):
        """
        Verify that completing delivery with collect_cash='1' also updates COD payment status.
        """
        order = Order.objects.create(
            user=self.customer,
            total_amount=180.00,
            branch=self.branch,
            latitude=9.5580,
            longitude=76.7915,
            delivery_address="Pala Road",
            status='in_transit'
        )
        payment = Payment.objects.create(
            order=order,
            payment_method='cod',
            status='pending',
            amount=180.00
        )
        assignment = DeliveryAssignment.objects.create(
            order=order,
            delivery_boy=self.courier_profile1,
            status='in_transit',
            is_active=True
        )

        self.client.login(username="courier_boy1", password=self.password)
        resp = self.client.post(reverse('complete_delivery', args=[assignment.id]), {
            'collect_cash': '1'
        })
        self.assertEqual(resp.status_code, 302)

        order.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(order.status, 'delivered')
        self.assertEqual(payment.status, 'cash_collected')
        self.assertEqual(payment.cash_collected_by, self.courier_user1)

    def test_9_couriers_with_unique_mobile_numbers_in_staff_dashboard(self):
        """
        Verify that 9 courier boys exist with 9 unique mobile numbers,
        and the staff dashboard displays all 9 with real-time statuses:
        Available, Busy (currently delivering an order), or Offline.
        """
        from django.core.management import call_command
        call_command('seed_couriers')

        couriers = []
        for i in range(1, 10):
            user = User.objects.get(username=f'courier{i}')
            self.assertIsNotNone(user.phone)
            couriers.append((user.username, user.phone, user.delivery_boy_profile))

        # Ensure all 9 mobile numbers are distinct and non-empty
        phone_numbers = [phone for _, phone, _ in couriers]
        self.assertEqual(len(phone_numbers), 9)
        self.assertEqual(len(set(phone_numbers)), 9)

        # Set courier1 to have an active delivery (Busy)
        busy_order = Order.objects.create(
            user=self.customer,
            total_amount=350.00,
            branch=self.branch,
            latitude=9.5580,
            longitude=76.7915,
            delivery_address="College Road",
            status='in_transit'
        )
        c1_profile = couriers[0][2]
        DeliveryAssignment.objects.create(
            order=busy_order,
            delivery_boy=c1_profile,
            status='in_transit',
            is_active=True
        )
        c1_profile.status = 'on_delivery'
        c1_profile.save()

        # Set courier2 to Offline
        c2_profile = couriers[1][2]
        c2_profile.status = 'offline'
        c2_profile.save()

        # Check real-time statuses
        self.assertEqual(c1_profile.realtime_status, 'Busy (currently delivering an order)')
        self.assertEqual(c2_profile.realtime_status, 'Offline')
        c3_profile = couriers[2][2]
        self.assertEqual(c3_profile.realtime_status, 'Available')

        # Staff visits dashboard
        self.client.login(username="staff_user", password=self.password)
        resp = self.client.get(reverse('staff_dashboard'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')

        # Check section header
        self.assertIn("Courier Fleet", content)
        self.assertIn("Real-Time Availability (9 Couriers)", content)
        self.assertIn("Available", content)
        self.assertIn("Busy (currently delivering an order)", content)
        self.assertIn("Offline", content)

        # Check all 9 phone numbers appear on staff dashboard
        for phone in phone_numbers:
            self.assertIn(phone, content)

    def test_courier_status_auto_updates_on_assignment_and_completion(self):
        """
        Verify that courier status automatically updates:
        - When assigned to an order: becomes 'Busy (currently delivering an order)'
        - When delivery completes (with no other active orders): becomes 'Available'
        """
        from django.core.management import call_command
        call_command('seed_couriers')

        c4_user = User.objects.get(username='courier4')
        c4_profile = c4_user.delivery_boy_profile
        c4_profile.status = 'available'
        c4_profile.save()
        self.assertEqual(c4_profile.realtime_status, 'Available')

        # Create ready order
        order = Order.objects.create(
            user=self.customer,
            total_amount=500.00,
            branch=self.branch,
            latitude=9.5580,
            longitude=76.7915,
            delivery_address="Town Square",
            status='ready_pickup'
        )

        # Staff assigns order to courier4
        self.client.login(username="staff_user", password=self.password)
        resp = self.client.post(reverse('staff_assign_delivery', args=[order.order_id]), {
            'delivery_boy_id': c4_profile.id
        })
        self.assertEqual(resp.status_code, 302)

        # Courier 4 is now busy
        c4_profile.refresh_from_db()
        self.assertEqual(c4_profile.realtime_status, 'Busy (currently delivering an order)')

        # Courier picks up food, starts delivery, and completes delivery
        assignment = DeliveryAssignment.objects.get(order=order)
        self.client.login(username="courier4", password="password123")
        
        # Pick up food
        resp = self.client.post(reverse('pickup_order', args=[assignment.id]))
        self.assertEqual(resp.status_code, 302)
        
        # Start delivery
        resp = self.client.post(reverse('start_delivery', args=[assignment.id]))
        self.assertEqual(resp.status_code, 302)

        # Complete delivery
        resp = self.client.post(reverse('complete_delivery', args=[assignment.id]))
        self.assertEqual(resp.status_code, 302)

        # Courier 4 is now automatically Available again
        c4_profile.refresh_from_db()
        self.assertEqual(c4_profile.realtime_status, 'Available')

    def test_cash_collected_button_and_workflow(self):
        """
        Verifies that:
        1. Cash Collected button is disabled before food handover.
        2. Food handover unlocks and enables the "Cash Collected" button.
        3. Courier clicks the button to update status to "Cash Collected".
        4. Staff dashboard displays "Cash Collected Successfully" confirmation message.
        """
        order = Order.objects.create(
            order_id="VR-COD-BTN-01",
            user=self.customer,
            total_amount=320.00,
            branch=self.branch,
            latitude=9.5570,
            longitude=76.7910,
            delivery_address="Main Road, Kanjirappally",
            status='in_transit'
        )
        payment = Payment.objects.create(
            order=order,
            payment_method='cod',
            status='pending',
            amount=320.00
        )
        assignment = DeliveryAssignment.objects.create(
            order=order,
            delivery_boy=self.courier_profile1,
            status='in_transit',
            is_active=True
        )

        # 1. Before food handover: Courier checks tracking page
        self.client.login(username="courier_boy1", password=self.password)
        resp = self.client.get(reverse('delivery_boy_track', args=[assignment.id]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        # Button must be disabled until food handover
        self.assertIn("Disabled until handover", content)

        # 2. Courier hands over food to customer (marks delivered)
        resp = self.client.post(reverse('delivery_boy_update_status', args=[assignment.id]), {
            'status': 'delivered',
            'next': reverse('delivery_boy_track', args=[assignment.id])
        })
        self.assertEqual(resp.status_code, 302)
        assignment.refresh_from_db()
        order.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(order.status, 'delivered')
        self.assertEqual(payment.status, 'pending') # Cash not collected yet

        # 3. After food handover: Cash Collected button is now enabled
        resp = self.client.get(reverse('delivery_boy_track', args=[assignment.id]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn("Cash Collected", content)
        self.assertIn('action="' + reverse('courier_collect_cash', args=[assignment.id]) + '"', content)

        # 4. Courier clicks "Cash Collected" button to confirm cash received
        resp = self.client.post(reverse('courier_collect_cash', args=[assignment.id]), {
            'next': reverse('delivery_boy_track', args=[assignment.id])
        })
        self.assertEqual(resp.status_code, 302)
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'cash_collected')
        self.assertEqual(payment.cash_collected_by, self.courier_user1)

        # 5. Tracking page shows "Cash Collected" badge
        resp = self.client.get(reverse('delivery_boy_track', args=[assignment.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Cash Collected", resp.content.decode('utf-8'))

        # 6. Staff dashboard displays "Cash Collected Successfully" confirmation message
        self.client.login(username="staff_user", password=self.password)
        staff_resp = self.client.get(reverse('staff_dashboard'))
        self.assertEqual(staff_resp.status_code, 200)
        staff_content = staff_resp.content.decode('utf-8')
        self.assertIn("Cash Collected Successfully", staff_content)
        self.assertIn("Courier_Boy1", staff_content)

    def test_courier_single_popup_notification_on_assignment(self):
        """Verifies that all couriers receive a single notification on assignment and dismissing prevents repeated alerts."""
        c2_user = self.courier_user2
        c2_profile = self.courier_profile2

        order = Order.objects.create(
            order_id="VR-POPUP-NOTIF-01",
            user=self.customer,
            total_amount=280.00,
            branch=self.branch,
            latitude=9.5564,
            longitude=76.7909,
            delivery_address="College Junction",
            status='ready_pickup'
        )

        # Staff assigns order to courier 2
        self.client.login(username="staff_user", password=self.password)
        resp = self.client.post(reverse('staff_assign_delivery', args=[order.order_id]), {
            'delivery_boy_id': c2_profile.id
        })
        self.assertEqual(resp.status_code, 302)

        # Courier 2 logs in and fetches notification API for entrance popup
        self.client.login(username="courier_boy2", password=self.password)
        api_resp = self.client.get(reverse('get_courier_notifications'))
        self.assertEqual(api_resp.status_code, 200)
        data = api_resp.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['unread_count'], 1)
        self.assertEqual(data['notifications'][0]['order_id'], order.order_id)
        notif_id = data['notifications'][0]['id']

        # Dismiss notification via AJAX dismiss endpoint
        dismiss_resp = self.client.get(
            reverse('dismiss_courier_notification', args=[notif_id]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(dismiss_resp.status_code, 200)

        # Verify subsequent polling returns 0 unread notifications (no duplicate popups)
        api_resp2 = self.client.get(reverse('get_courier_notifications'))
        self.assertEqual(api_resp2.status_code, 200)
        self.assertEqual(api_resp2.json()['unread_count'], 0)
