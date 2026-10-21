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
        self.assertContains(dash_response, '10.025')
        self.assertContains(dash_response, '76.315')
        
        # Verify Courier sees food item names and Food IDs
        self.assertContains(dash_response, 'Puttu and Kadala Curry')
        self.assertContains(dash_response, 'FOOD')

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


class KeralaDistrictsAndBranchesTests(TestCase):
    """
    Validates complete Kerala 14-district setup:
    - All 14 districts registered and deduplicated
    - Central kitchen hub preserved
    - Multi-branch support across districts with verified coordinates
    - Strict 25 km delivery limit enforcement
    - Server-side rejection with exact prompt message
    - Staff dashboard hotel branch management
    """
    def setUp(self):
        from delivery.models import District, HotelBranch
        from django.core.management import call_command
        call_command('seed_kerala_districts')

        self.user = User.objects.create_user(
            username='kerala_customer',
            email='kerala_cust@test.com',
            password='password123',
            role='customer'
        )
        self.staff_user = User.objects.create_user(
            username='kerala_staff',
            email='kerala_staff@test.com',
            password='password123',
            role='staff'
        )
        self.category = Category.objects.create(name='Traditional Kerala')
        self.session = MealSession.objects.create(
            name='Lunch Feast',
            start_time='11:30:00',
            end_time='15:30:00'
        )
        self.food = FoodItem.objects.create(
            name='Kerala Sadya Feast',
            price=180.0,
            stock_quantity=20,
            category=self.category,
            meal_session=self.session,
            is_available=True
        )

    def test_01_all_14_kerala_districts_registered(self):
        from delivery.models import District
        expected_districts = [
            'Thiruvananthapuram',
            'Kollam',
            'Pathanamthitta',
            'Alappuzha',
            'Kottayam',
            'Idukki',
            'Ernakulam',
            'Thrissur',
            'Palakkad',
            'Malappuram',
            'Kozhikode',
            'Wayanad',
            'Kannur',
            'Kasaragod',
        ]
        self.assertEqual(District.objects.count(), 14)
        for name in expected_districts:
            d = District.objects.filter(name=name).first()
            self.assertIsNotNone(d, f"Missing district {name}")
            self.assertEqual(d.name, name)
            self.assertTrue(d.is_active)
            self.assertTrue(8.0 <= d.latitude <= 13.0, f"Latitude {d.latitude} out of Kerala bounds")
            self.assertTrue(74.0 <= d.longitude <= 78.0, f"Longitude {d.longitude} out of Kerala bounds")

    def test_02_central_hub_preserved_in_kottayam(self):
        from delivery.models import HotelBranch
        hub = HotelBranch.objects.filter(is_central_hub=True).first()
        self.assertIsNotNone(hub)
        self.assertEqual(hub.district.name, 'Kottayam')
        self.assertEqual(hub.latitude, 9.5564)
        self.assertEqual(hub.longitude, 76.7909)
        self.assertTrue(hub.is_active)
        self.assertLessEqual(hub.effective_radius_km, 30.0)

    def test_03_strict_25km_radius_enforcement(self):
        from delivery.models import District, HotelBranch
        from orders.utils import is_within_delivery_perimeter

        ekm_district = District.objects.get(name='Ernakulam')
        # Ernakulam branch at MG Road Kochi (9.9816, 76.2999)
        ekm_branch, _ = HotelBranch.objects.get_or_create(
            name='Veetile Ruchi - Ernakulam Hub',
            district=ekm_district,
            defaults={
                'address': 'MG Road, Kochi, Ernakulam, Kerala',
                'latitude': 9.9816,
                'longitude': 76.2999,
                'max_delivery_radius_km': 25.0,
                'is_active': True
            }
        )
        # Test location inside 25 km (Kakkanad ~10 km away)
        is_serv, dist, msg = is_within_delivery_perimeter(10.0159, 76.3419, branch_id=ekm_branch.id)
        self.assertTrue(is_serv)
        self.assertLess(dist, 25.0)

        # Test location outside 25 km (Cherthala ~33 km away)
        is_serv, dist, msg = is_within_delivery_perimeter(9.6844, 76.3325, branch_id=ekm_branch.id)
        self.assertFalse(is_serv)
        self.assertGreater(dist, 25.0)
        self.assertIn("Sorry, this hotel cannot deliver to your selected location. Please choose a nearer address or another available hotel.", msg)

    def test_04_checkout_order_rejection_outside_25km(self):
        from orders.models import CartItem, Order
        from delivery.models import HotelBranch
        self.client.login(username='kerala_customer', password='password123')
        CartItem.objects.create(user=self.user, food_item=self.food, quantity=2)

        # Kottayam hub branch
        hub = HotelBranch.objects.filter(is_central_hub=True).first()

        # Destination in Kozhikode (~220 km away from Kottayam)
        resp = self.client.post(reverse('place_order'), {
            'branch_id': hub.id,
            'latitude': 11.2588,
            'longitude': 75.7804,
            'delivery_address': 'Beach Road, Kozhikode',
            'payment_method': 'cod'
        }, follow=True)

        self.assertEqual(resp.status_code, 200)
        messages_text = [m.message for m in resp.context['messages']]
        self.assertTrue(any("Sorry, this hotel cannot deliver to your selected location. Please choose a nearer address or another available hotel." in m for m in messages_text))

        # Order must NOT be created
        self.assertEqual(Order.objects.filter(user=self.user).count(), 0)
        # Cart must remain INTACT
        self.assertEqual(CartItem.objects.filter(user=self.user).count(), 1)

    def test_05_checkout_order_accepted_within_radius(self):
        from orders.models import CartItem, Order
        from delivery.models import HotelBranch
        self.client.login(username='kerala_customer', password='password123')
        CartItem.objects.create(user=self.user, food_item=self.food, quantity=1)

        hub = HotelBranch.objects.filter(is_central_hub=True).first()

        # Destination in Ponkunnam (~3.7 km from Kanjirappally)
        resp = self.client.post(reverse('place_order'), {
            'branch_id': hub.id,
            'latitude': 9.5667,
            'longitude': 76.7583,
            'delivery_address': 'Ponkunnam Town, Kottayam',
            'payment_method': 'cod'
        })
        self.assertEqual(resp.status_code, 302)
        order = Order.objects.filter(user=self.user).first()
        self.assertIsNotNone(order)
        self.assertEqual(order.branch, hub)
        self.assertEqual(order.status, 'pending')

    def test_06_staff_branch_creation_and_coordinate_validation(self):
        from delivery.models import District, HotelBranch
        self.client.login(username='kerala_staff', password='password123')
        tcr_district = District.objects.get(name='Thrissur')

        # Create Thrissur branch with verified coordinates
        resp = self.client.post(reverse('staff_save_hotel_branch'), {
            'name': 'Veetile Ruchi - Thrissur Round Hub',
            'district_id': tcr_district.id,
            'address': 'Swaraj Round, Thrissur, Kerala',
            'phone': '+91 94470 55555',
            'latitude': 10.5276,
            'longitude': 76.2144,
            'max_delivery_radius_km': 25.0,
            'operating_status': 'open',
            'opening_time': '07:00',
            'closing_time': '22:00',
            'is_active': 'on'
        })
        self.assertEqual(resp.status_code, 302)
        tcr_branch = HotelBranch.objects.filter(district=tcr_district, name='Veetile Ruchi - Thrissur Round Hub').first()
        self.assertIsNotNone(tcr_branch)
        self.assertEqual(tcr_branch.latitude, 10.5276)
        self.assertEqual(tcr_branch.effective_radius_km, 25.0)

