from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User, DeliveryBoyProfile
from food.models import Category, MealSession, FoodItem
from orders.models import Order, OrderItem
from delivery.models import DeliveryAssignment

class CourierWorkflowTests(TestCase):
    def setUp(self):
        self.client = Client()

        # 1. Create Chef
        self.chef = User.objects.create_user(
            username='chef_john',
            email='chef@test.com',
            password='password123',
            role='chef'
        )

        # 2. Create Customer Riya
        self.riya = User.objects.create_user(
            username='riya',
            first_name='Riya',
            last_name='P',
            email='riya@test.com',
            password='password123',
            role='customer',
            phone='9876543210',
            latitude=10.025,
            longitude=76.315
        )

        # 3. Create Staff member
        self.staff = User.objects.create_user(
            username='staff_member',
            email='staff@test.com',
            password='password123',
            role='staff'
        )

        # 4. Create Courier 1 and Courier 2
        self.courier1_user = User.objects.create_user(
            username='courier1',
            email='courier1@test.com',
            password='password123',
            role='delivery_boy',
            phone='9876543210'
        )
        self.courier1_profile = DeliveryBoyProfile.objects.create(
            user=self.courier1_user,
            vehicle_number='KL-07-CD-1001',
            status='available'
        )

        self.courier2_user = User.objects.create_user(
            username='courier2',
            email='courier2@test.com',
            password='password123',
            role='delivery_boy',
            phone='9876543211'
        )
        self.courier2_profile = DeliveryBoyProfile.objects.create(
            user=self.courier2_user,
            vehicle_number='KL-07-CD-1002',
            status='available'
        )

        # 5. Create Category, Session & Food Item (Puttu & Kadala Curry)
        cat = Category.objects.create(name='Vegetarian')
        session = MealSession.objects.create(name='Breakfast', start_time='06:00:00', end_time='12:00:00')
        self.food = FoodItem.objects.create(
            chef=self.chef,
            name='Puttu and Kadala Curry',
            price=70.00,
            category=cat,
            meal_session=session,
            stock_quantity=10,
            is_available=True
        )

    def test_role_based_privacy_and_delivery_workflow(self):
        # Step 1: Customer Riya places an order (status = pending)
        order = Order.objects.create(
            user=self.riya,
            total_amount=70.00,
            status='pending',
            latitude=10.025,
            longitude=76.315
        )
        OrderItem.objects.create(order=order, food_item=self.food, quantity=1, price=70.00)
        self.assertEqual(order.status, 'pending')

        # PRIVACY TEST FOR CHEF: Chef must see food details ONLY, NO customer personal info (name, phone, email, lat, lon)
        self.client.login(username='chef_john', password='password123')
        chef_dash = self.client.get(reverse('chef_dashboard'))
        self.assertEqual(chef_dash.status_code, 200)
        self.assertContains(chef_dash, 'Puttu and Kadala Curry')
        self.assertContains(chef_dash, f'Order ID: #{order.order_id}')
        
        # Verify Chef receives ZERO personal customer info and Food ID is removed
        self.assertNotContains(chef_dash, 'Riya')
        self.assertNotContains(chef_dash, '9876543210')
        self.assertNotContains(chef_dash, 'riya@test.com')

        # Step 2: Staff assigns Courier 1 (MUST NOT automatically set status to DELIVERED)
        self.client.login(username='staff_member', password='password123')
        response = self.client.post(
            reverse('staff_assign_delivery', args=[order.order_id]),
            {'delivery_boy_id': self.courier1_profile.id}
        )
        self.assertEqual(response.status_code, 302)

        order.refresh_from_db()
        self.assertEqual(order.status, 'assigned')
        
        assignment = DeliveryAssignment.objects.get(order=order)
        self.assertEqual(assignment.delivery_boy, self.courier1_profile)
        self.assertEqual(assignment.status, 'assigned')

        # PRIVACY & NOTIFICATION TEST FOR COURIER: Courier 1 sees New Delivery Assigned Alert
        self.client.login(username='courier1', password='password123')
        dash_response = self.client.get(reverse('delivery_boy_dashboard') + '?tab=current')
        self.assertEqual(dash_response.status_code, 200)
        self.assertContains(dash_response, f'data-order-id="{order.order_id}"')
        self.assertContains(dash_response, 'NEW CURRENT ORDER ASSIGNED')
        self.assertContains(dash_response, 'Riya P') # Customer Name VISIBLE to Courier
        self.assertContains(dash_response, '10.025')
        self.assertContains(dash_response, '76.315')
        
        # Verify Courier does NOT see food item names or Food IDs (removed for privacy/secrecy)
        self.assertNotContains(dash_response, 'Puttu and Kadala Curry')
        self.assertNotContains(dash_response, 'Food ID:')

        # URL SECURITY & NOTIFICATION ISOLATION TEST: Courier 2 CANNOT see Courier 1's assigned order or notification
        self.client.login(username='courier2', password='password123')
        courier2_dash = self.client.get(reverse('delivery_boy_dashboard') + '?tab=current')
        self.assertNotContains(courier2_dash, f'data-order-id="{order.order_id}"')
        self.assertNotContains(courier2_dash, 'NEW CURRENT ORDER ASSIGNED')

        # Step 3: Courier 1 clicks View Notification -> Marks Read & opens delivery track page
        self.client.login(username='courier1', password='password123')
        notif = order.notifications.filter(user=self.courier1_user).first()
        if notif:
            notif_resp = self.client.get(reverse('mark_notification_read', args=[notif.id]))
            self.assertEqual(notif_resp.status_code, 302)
            notif.refresh_from_db()
            self.assertTrue(notif.is_read)

        # Step 4: Courier 1 starts delivery (status = in_transit / Out for Delivery)
        self.client.login(username='courier1', password='password123')
        start_response = self.client.post(
            reverse('delivery_boy_update_status', args=[assignment.id]),
            {'status': 'in_transit'}
        )
        self.assertEqual(start_response.status_code, 302)
        
        order.refresh_from_db()
        assignment.refresh_from_db()
        self.assertEqual(order.status, 'in_transit')
        self.assertEqual(assignment.status, 'in_transit')

        # Step 5: Courier 1 delivers food (clicks Mark as Delivered)
        deliver_response = self.client.post(
            reverse('delivery_boy_update_status', args=[assignment.id]),
            {'status': 'delivered'}
        )
        self.assertEqual(deliver_response.status_code, 302)

        order.refresh_from_db()
        assignment.refresh_from_db()
        self.assertEqual(order.status, 'delivered')
        self.assertEqual(assignment.status, 'delivered')

        # Verify order has moved from Current Orders card container to Completed Orders card container
        current_view = self.client.get(reverse('delivery_boy_dashboard') + '?tab=current')
        self.assertNotContains(current_view, f'data-order-id="{order.order_id}"')

        completed_view = self.client.get(reverse('delivery_boy_dashboard') + '?tab=completed')
        self.assertContains(completed_view, f'data-order-id="{order.order_id}"')
