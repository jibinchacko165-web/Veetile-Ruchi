from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta, date, time
from decimal import Decimal
import json
from django.core.management import call_command

from accounts.models import User, ChefProfile, DeliveryBoyProfile, PasswordResetOTP
from health.models import HealthProfile
from food.models import FoodItem, Category, MealSession, NutritionInfo, ReviewSentiment
from orders.models import CartItem, Coupon, Order, OrderItem, Payment, Wishlist, Notification
from delivery.models import DeliveryAssignment, DeliveryFeedback

class CustomerWorkflowAndSecurityTests(TestCase):
    def setUp(self):
        self.client = Client()

        # 1. Primary Customer (Kanjirappally)
        self.customer1 = User.objects.create_user(
            username='customer_one',
            email='cust1@test.com',
            password='Password123!',
            role='customer',
            dob='1995-03-20',
            phone='9876543210',
            latitude=9.5564,
            longitude=76.7909
        )
        HealthProfile.objects.create(user=self.customer1)

        # 2. Secondary Customer (Ponkunnam)
        self.customer2 = User.objects.create_user(
            username='customer_two',
            email='cust2@test.com',
            password='Password123!',
            role='customer',
            dob='1996-07-14',
            phone='9876543211',
            latitude=9.5667,
            longitude=76.7583
        )
        HealthProfile.objects.create(user=self.customer2)

        # 3. Chef User
        self.chef_user = User.objects.create_user(
            username='chef_mary',
            email='chef@test.com',
            password='Password123!',
            role='chef',
            dob='1985-01-10'
        )
        self.chef_profile = ChefProfile.objects.create(
            user=self.chef_user,
            specialty='Traditional Kerala Cuisine',
            kitchen_name="Mary's Home Kitchen",
            is_approved=True
        )

        # 4. Courier User
        self.courier_user = User.objects.create_user(
            username='courier_arun',
            email='courier@test.com',
            password='Password123!',
            role='delivery_boy',
            dob='1998-11-25',
            phone='9876500000'
        )
        self.courier_profile = DeliveryBoyProfile.objects.create(
            user=self.courier_user,
            vehicle_number='KL-07-CC-9999',
            status='available'
        )

        # Categories & Meal Sessions
        self.cat_veg = Category.objects.create(name='Vegetarian', description='Authentic vegetarian dishes')
        self.cat_seafood = Category.objects.create(name='Seafood', description='Fresh coastal seafood')

        self.session_lunch = MealSession.objects.create(
            name='Lunch',
            start_time=time(11, 0),
            end_time=time(15, 0)
        )
        self.session_dinner = MealSession.objects.create(
            name='Dinner',
            start_time=time(18, 30),
            end_time=time(22, 30)
        )

        # Food Items
        self.food1 = FoodItem.objects.create(
            chef=self.chef_user,
            name='Kerala Sadya Feast',
            description='Traditional 24-item festive vegetarian lunch',
            price=Decimal('220.00'),
            category=self.cat_veg,
            meal_session=self.session_lunch,
            stock_quantity=15,
            is_available=True
        )
        NutritionInfo.objects.create(
            food_item=self.food1,
            calories=650,
            sugar=4.5,
            cholesterol=0.0,
            sodium=420,
            protein=18.0,
            fat=12.0,
            carbohydrates=85.0,
            fiber=8.0
        )

        self.food2 = FoodItem.objects.create(
            chef=self.chef_user,
            name='Karimeen Pollichathu',
            description='Pearl spot fish marinated in masala and wrapped in banana leaf',
            price=Decimal('350.00'),
            category=self.cat_seafood,
            meal_session=self.session_dinner,
            stock_quantity=8,
            is_available=True
        )

        # Coupon
        self.coupon = Coupon.objects.create(
            code='VRFEST10',
            discount_percentage=Decimal('10.00'),
            min_purchase_amount=Decimal('100.00'),
            is_active=True,
            expiry_date=timezone.now().date() + timedelta(days=30)
        )

    # =========================================================================
    # 1. FOOD CATALOG & FOOD DETAILS
    # =========================================================================

    def test_01_food_catalog_browsing_and_filtering(self):
        """Test food catalog listing, category filtering, and keyword search"""
        self.client.login(username='customer_one', password='Password123!')

        # 1. Base Catalog (with session=All to bypass time-of-day filter)
        resp = self.client.get(reverse('food_catalog') + '?session=All')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Kerala Sadya Feast')
        self.assertContains(resp, 'Karimeen Pollichathu')

        # 2. Filter by Category
        resp_cat = self.client.get(reverse('food_catalog') + '?category=Vegetarian&session=All')
        self.assertEqual(resp_cat.status_code, 200)
        self.assertContains(resp_cat, 'Kerala Sadya Feast')
        self.assertNotContains(resp_cat, 'Karimeen Pollichathu')

        # 3. Search by keyword
        resp_search = self.client.get(reverse('food_catalog') + '?q=Pearl&session=All')
        self.assertEqual(resp_search.status_code, 200)
        self.assertContains(resp_search, 'Karimeen Pollichathu')
        self.assertNotContains(resp_search, 'Kerala Sadya Feast')


    def test_02_food_details_and_review_submission(self):
        """Test food detail view with nutrition metrics and customer review with AI sentiment"""
        self.client.login(username='customer_one', password='Password123!')

        # View Details
        resp = self.client.get(reverse('food_detail', args=[self.food1.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Kerala Sadya Feast')
        self.assertContains(resp, '650') # Calories
        self.assertContains(resp, 'Nutritional Facts')

        # Submit Review
        post_review = self.client.post(reverse('food_detail', args=[self.food1.id]), {
            'rating': '5',
            'review_text': 'Exceptional delicious homemade taste and authentic spices!'
        })
        self.assertRedirects(post_review, reverse('food_detail', args=[self.food1.id]))

        # Verify Review created with Sentiment
        review = ReviewSentiment.objects.filter(food_item=self.food1, user=self.customer1).first()
        self.assertIsNotNone(review)
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.sentiment, 'positive')

    # =========================================================================
    # 2. WISHLIST & CART WORKFLOW
    # =========================================================================

    def test_03_wishlist_toggle_and_view(self):
        """Test wishlist adding, removing, and AJAX toggle"""
        self.client.login(username='customer_one', password='Password123!')

        # 1. Toggle Add to Wishlist
        toggle_resp = self.client.get(reverse('wishlist_toggle', args=[self.food1.id]))
        self.assertEqual(toggle_resp.status_code, 302)
        self.assertTrue(Wishlist.objects.filter(user=self.customer1, food_item=self.food1).exists())

        # 2. View Wishlist
        wish_view = self.client.get(reverse('wishlist_view'))
        self.assertEqual(wish_view.status_code, 200)
        self.assertContains(wish_view, 'Kerala Sadya Feast')

        # 3. AJAX Wishlist Toggle (Remove)
        ajax_resp = self.client.get(
            reverse('wishlist_toggle', args=[self.food1.id]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(ajax_resp.status_code, 200)
        data = json.loads(ajax_resp.content.decode('utf-8'))
        self.assertEqual(data['status'], 'success')
        self.assertFalse(data['is_favorited'])
        self.assertFalse(Wishlist.objects.filter(user=self.customer1, food_item=self.food1).exists())

    def test_04_cart_management_add_increment_remove(self):
        """Test adding items to cart, quantity increments, and removing items"""
        self.client.login(username='customer_one', password='Password123!')

        # 1. Add Food 1 to Cart
        add1 = self.client.get(reverse('cart_add', args=[self.food1.id]))
        self.assertRedirects(add1, reverse('cart_view'))
        cart_item = CartItem.objects.get(user=self.customer1, food_item=self.food1)
        self.assertEqual(cart_item.quantity, 1)

        # 2. Add again -> Quantity increments to 2
        add2 = self.client.get(reverse('cart_add', args=[self.food1.id]))
        cart_item.refresh_from_db()
        self.assertEqual(cart_item.quantity, 2)

        # 3. View Cart with Subtotal
        cart_view = self.client.get(reverse('cart_view'))
        self.assertEqual(cart_view.status_code, 200)
        self.assertContains(cart_view, 'Kerala Sadya Feast')
        self.assertContains(cart_view, '440') # 220 * 2

        # 4. Apply Coupon
        coupon_view = self.client.get(reverse('cart_view') + f'?coupon_code={self.coupon.code}')
        self.assertEqual(coupon_view.status_code, 200)
        self.assertContains(coupon_view, 'VRFEST10')

        # 5. Remove Item from Cart
        rem = self.client.get(reverse('cart_remove', args=[cart_item.id]))
        self.assertRedirects(rem, reverse('cart_view'))
        self.assertFalse(CartItem.objects.filter(id=cart_item.id).exists())

    # =========================================================================
    # 3. CHECKOUT, PAYMENT & ORDER CREATION WORKFLOW
    # =========================================================================

    def test_05_checkout_and_place_order_cod(self):
        """Test complete checkout and order placement using Cash On Delivery (COD)"""
        self.client.login(username='customer_one', password='Password123!')

        # Add item to cart
        self.client.get(reverse('cart_add', args=[self.food1.id]))

        # Checkout Screen
        chk_resp = self.client.get(reverse('checkout_view'))
        self.assertEqual(chk_resp.status_code, 200)
        self.assertContains(chk_resp, 'Delivery Location')

        initial_stock = self.food1.stock_quantity

        # Place Order (COD)
        place_resp = self.client.post(reverse('place_order'), {
            'latitude': '9.556400',
            'longitude': '76.790900',
            'payment_method': 'cod',
        })
        self.assertEqual(place_resp.status_code, 302)

        # Verify Order Created
        order = Order.objects.filter(user=self.customer1).first()
        self.assertIsNotNone(order)
        self.assertTrue(order.order_id.startswith('VR-'))
        self.assertEqual(order.status, 'pending')
        self.assertEqual(order.total_amount, Decimal('220.00'))

        # Verify Stock Decremented
        self.food1.refresh_from_db()
        self.assertEqual(self.food1.stock_quantity, initial_stock - 1)

        # Verify Payment Record
        payment = Payment.objects.get(order=order)
        self.assertEqual(payment.payment_method, 'cod')
        self.assertEqual(payment.status, 'pending')

        # Verify Customer Notification Generated
        notif = Notification.objects.filter(user=self.customer1, order=order).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.notification_type, 'order_confirmed')

        # Verify Cart Cleared
        self.assertFalse(CartItem.objects.filter(user=self.customer1).exists())

        # Verify Redirect to Order Tracking
        self.assertRedirects(place_resp, reverse('order_tracking', args=[order.order_id]))

    def test_06_checkout_and_place_order_upi(self):
        """Test checkout and order placement with instant UPI payment and coupon discount"""
        self.client.login(username='customer_one', password='Password123!')

        # Add item to cart
        self.client.get(reverse('cart_add', args=[self.food2.id]))

        # Place Order (UPI with Coupon)
        place_resp = self.client.post(reverse('place_order'), {
            'coupon_id': str(self.coupon.id),
            'latitude': '9.556400',
            'longitude': '76.790900',
            'payment_method': 'upi',
            'upi_ref': '987654321098'
        })
        self.assertEqual(place_resp.status_code, 302)

        order = Order.objects.filter(user=self.customer1, total_amount=Decimal('315.00')).first() # 350 - 10% = 315
        self.assertIsNotNone(order)

        payment = Payment.objects.get(order=order)
        self.assertEqual(payment.payment_method, 'upi')
        self.assertEqual(payment.status, 'success')
        self.assertIn('987654321098', payment.transaction_id)

    def test_07_empty_cart_checkout_blocked(self):
        """Test that checkout and order placement are blocked when cart is empty"""
        self.client.login(username='customer_one', password='Password123!')

        # Empty cart checkout view
        chk_resp = self.client.get(reverse('checkout_view'))
        self.assertRedirects(chk_resp, reverse('food_catalog'))

        # Empty cart place order POST
        place_resp = self.client.post(reverse('place_order'), {
            'payment_method': 'cod',
            'latitude': '10.0',
            'longitude': '76.0'
        })
        self.assertRedirects(place_resp, reverse('food_catalog'))
        self.assertFalse(Order.objects.filter(user=self.customer1).exists())

    # =========================================================================
    # 4. CUSTOMER ORDER SECURITY & ISOLATION
    # =========================================================================

    def test_08_order_history_displays_only_own_orders(self):
        """Test customer only sees their own orders in order history"""
        # Create Order for Customer 1
        order1 = Order.objects.create(
            user=self.customer1,
            total_amount=Decimal('220.00'),
            status='pending'
        )
        OrderItem.objects.create(order=order1, food_item=self.food1, quantity=1, price=Decimal('220.00'))

        # Create Order for Customer 2
        order2 = Order.objects.create(
            user=self.customer2,
            total_amount=Decimal('350.00'),
            status='pending'
        )
        OrderItem.objects.create(order=order2, food_item=self.food2, quantity=1, price=Decimal('350.00'))

        # Customer 1 visits history
        self.client.login(username='customer_one', password='Password123!')
        hist_resp = self.client.get(reverse('order_history'))
        self.assertEqual(hist_resp.status_code, 200)
        self.assertContains(hist_resp, order1.order_id)
        self.assertContains(hist_resp, 'Kerala Sadya Feast')
        self.assertNotContains(hist_resp, order2.order_id)
        self.assertNotContains(hist_resp, 'Karimeen Pollichathu')

        # Customer 2 visits history
        self.client.login(username='customer_two', password='Password123!')
        hist2_resp = self.client.get(reverse('order_history'))
        self.assertEqual(hist2_resp.status_code, 200)
        self.assertContains(hist2_resp, order2.order_id)
        self.assertContains(hist2_resp, 'Karimeen Pollichathu')
        self.assertNotContains(hist2_resp, order1.order_id)
        self.assertNotContains(hist2_resp, 'Kerala Sadya Feast')

    def test_09_order_tracking_security_blocks_cross_customer_access(self):
        """SECURITY TEST: Customer 2 CANNOT access Customer 1's order tracking by changing Order ID"""
        # Create Order for Customer 1
        order1 = Order.objects.create(
            user=self.customer1,
            total_amount=Decimal('220.00'),
            status='pending',
            latitude=10.025,
            longitude=76.315
        )
        OrderItem.objects.create(order=order1, food_item=self.food1, quantity=1, price=Decimal('220.00'))
        Payment.objects.create(order=order1, payment_method='cod', status='pending', amount=Decimal('220.00'))

        # 1. Customer 1 accesses own order -> SUCCESS
        self.client.login(username='customer_one', password='Password123!')
        own_resp = self.client.get(reverse('order_tracking', args=[order1.order_id]))
        self.assertEqual(own_resp.status_code, 200)
        self.assertContains(own_resp, order1.order_id)
        self.assertContains(own_resp, 'Kerala Sadya Feast')

        # 2. Customer 2 attempts to access Customer 1's order by Order ID in URL -> ACCESS DENIED
        self.client.login(username='customer_two', password='Password123!')
        intruder_resp = self.client.get(reverse('order_tracking', args=[order1.order_id]))
        self.assertEqual(intruder_resp.status_code, 302)
        # Verify redirect occurred and user was blocked
        self.assertIn(reverse('dashboard_redirect'), intruder_resp.url)

    def test_10_live_gps_and_feedback_security_blocks_unauthorized_customers(self):
        """SECURITY TEST: Customer 2 cannot call Live GPS API or submit feedback on Customer 1's order"""
        order1 = Order.objects.create(
            user=self.customer1,
            total_amount=Decimal('220.00'),
            status='delivered',
            latitude=10.025,
            longitude=76.315
        )
        DeliveryAssignment.objects.create(
            order=order1,
            delivery_boy=self.courier_profile,
            status='delivered'
        )

        self.client.login(username='customer_two', password='Password123!')

        # 1. Unauthorized GPS request -> 403 Forbidden
        gps_resp = self.client.get(reverse('get_live_gps_location', args=[order1.order_id]))
        self.assertEqual(gps_resp.status_code, 403)

        # 2. Unauthorized Feedback submission -> Blocked
        fb_resp = self.client.post(reverse('submit_delivery_feedback', args=[order1.order_id]), {
            'rating': '5',
            'comment': 'Hacked feedback'
        })
        self.assertRedirects(fb_resp, reverse('order_history'))
        self.assertFalse(DeliveryFeedback.objects.filter(order=order1).exists())

    # =========================================================================
    # 5. CUSTOMER PROFILE & NOTIFICATIONS
    # =========================================================================

    def test_11_customer_profile_view_and_edit(self):
        """Test viewing and updating customer personal and health profile"""
        self.client.login(username='customer_one', password='Password123!')

        # View Profile
        prof_resp = self.client.get(reverse('profile'))
        self.assertEqual(prof_resp.status_code, 200)
        self.assertContains(prof_resp, 'customer_one')

        # Edit Profile
        edit_resp = self.client.post(reverse('profile'), {
            'action': 'edit_profile',
            'first_name': 'Rohan',
            'last_name': 'Menon',
            'email': 'rohan.menon@test.com',
            'phone': '9876599999',
            'address': 'House 12, River View Enclave, Kochi',
            'has_diabetes': 'on',
            'dietary_preference': 'veg',
            'caloric_limit': '1800'
        })
        self.assertRedirects(edit_resp, reverse('profile') + '?tab=view')

        self.customer1.refresh_from_db()
        self.assertEqual(self.customer1.first_name, 'Rohan')
        self.assertEqual(self.customer1.email, 'rohan.menon@test.com')
        self.assertEqual(self.customer1.phone, '9876599999')
        self.assertEqual(self.customer1.address, 'House 12, River View Enclave, Kochi')

        health_prof = HealthProfile.objects.get(user=self.customer1)
        self.assertTrue(health_prof.has_diabetes)
        self.assertEqual(health_prof.dietary_preference, 'veg')
        self.assertEqual(health_prof.daily_calorie_target, 1800.0)

    def test_12_customer_notifications_and_context_processors(self):
        """Test customer notifications list, mark-as-read redirect, and navbar badges"""
        order = Order.objects.create(user=self.customer1, total_amount=Decimal('100.00'), status='pending')
        notif = Notification.objects.create(
            user=self.customer1,
            order=order,
            title="Food is on the way",
            message="Your order is out for delivery",
            notification_type='out_for_delivery'
        )

        self.client.login(username='customer_one', password='Password123!')

        # Check Context Processor count in Catalog response
        cat_resp = self.client.get(reverse('food_catalog'))
        self.assertEqual(cat_resp.status_code, 200)
        self.assertEqual(cat_resp.context['unread_notif_count'], 1)

        # Mark Notification as Read -> redirects to order tracking
        read_resp = self.client.get(reverse('mark_notification_read', args=[notif.id]))
        self.assertRedirects(read_resp, reverse('order_tracking', args=[order.order_id]))

        notif.refresh_from_db()
        self.assertTrue(notif.is_read)

    def test_13_cart_quantity_update_stepper_and_stock_limits(self):
        """Test cart quantity stepper: increment, decrement, and stock ceiling."""
        self.client.login(username='customer_one', password='Password123!')
        cart_item = CartItem.objects.create(user=self.customer1, food_item=self.food1, quantity=1)

        # 1. Increase quantity
        inc_resp = self.client.post(reverse('cart_update_quantity', args=[cart_item.id]), {'action': 'increase'})
        self.assertRedirects(inc_resp, reverse('cart_view'))
        cart_item.refresh_from_db()
        self.assertEqual(cart_item.quantity, 2)

        # 2. Decrease quantity
        dec_resp = self.client.post(reverse('cart_update_quantity', args=[cart_item.id]), {'action': 'decrease'})
        self.assertRedirects(dec_resp, reverse('cart_view'))
        cart_item.refresh_from_db()
        self.assertEqual(cart_item.quantity, 1)

        # 3. Decrease when quantity is 1 -> removes item from cart
        del_resp = self.client.post(reverse('cart_update_quantity', args=[cart_item.id]), {'action': 'decrease'})
        self.assertRedirects(del_resp, reverse('cart_view'))
        self.assertFalse(CartItem.objects.filter(id=cart_item.id).exists())

    def test_14_delivery_perimeter_inside_service_area(self):
        """Test delivery location within 20km radius succeeds."""
        self.client.login(username='customer_one', password='Password123!')
        CartItem.objects.create(user=self.customer1, food_item=self.food1, quantity=1)

        # Ponkunnam (~3.7 km from Kanjirappally hub)
        resp = self.client.post(reverse('place_order'), {
            'latitude': 9.5667,
            'longitude': 76.7583,
            'delivery_address': 'Ponkunnam Bus Stand Road',
            'payment_method': 'cod'
        })
        self.assertEqual(resp.status_code, 302)
        order = Order.objects.filter(user=self.customer1).order_by('-created_at').first()
        self.assertIsNotNone(order)
        self.assertEqual(order.latitude, 9.5667)

    def test_15_delivery_perimeter_outside_service_area_blocks_order(self):
        """Test delivery location far away (>20km e.g. Kozhikode/Bengaluru) is blocked with friendly message."""
        self.client.login(username='customer_one', password='Password123!')
        CartItem.objects.create(user=self.customer1, food_item=self.food1, quantity=1)

        # Kozhikode (~180 km away from Kanjirappally hub)
        resp = self.client.post(reverse('place_order'), {
            'latitude': 11.2588,
            'longitude': 75.7804,
            'delivery_address': 'Kozhikode Beach Road',
            'payment_method': 'cod'
        })
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse('checkout_view'))
        # Ensure order was NOT created
        self.assertFalse(Order.objects.filter(latitude=11.2588).exists())

    def test_16_checkout_with_saved_location(self):
        """Test checkout seamlessly applies SavedLocation details."""
        from accounts.models import SavedLocation
        saved_loc = SavedLocation.objects.create(
            user=self.customer1,
            name='My Home',
            location_type='home',
            description='House 10, Kanjirappally Town',
            landmark='Near Church Gate',
            latitude=9.5564,
            longitude=76.7909,
            is_default=True
        )

        self.client.login(username='customer_one', password='Password123!')
        CartItem.objects.create(user=self.customer1, food_item=self.food1, quantity=1)

        resp = self.client.post(reverse('place_order'), {
            'saved_location_id': saved_loc.id,
            'payment_method': 'cod'
        })
        self.assertEqual(resp.status_code, 302)
        order = Order.objects.filter(user=self.customer1).order_by('-created_at').first()
        self.assertIsNotNone(order)
        self.assertEqual(order.latitude, 9.5564)
        self.assertIn('My Home', order.delivery_address)
        self.assertIn('Near Church Gate', order.delivery_address)

    def test_17_delivery_setting_and_perimeter_calculation(self):
        """Test DeliverySetting model and calculate_distance_km/is_within_delivery_perimeter."""
        from delivery.models import DeliverySetting
        from orders.utils import calculate_distance_km, is_within_delivery_perimeter, get_active_delivery_setting

        setting = DeliverySetting.get_settings()
        self.assertIsNotNone(setting)
        self.assertEqual(setting.latitude, 9.5564)
        self.assertEqual(setting.longitude, 76.7909)
        self.assertEqual(setting.max_delivery_radius_km, 20.0)

        # Distance calculation
        dist = calculate_distance_km(9.5564, 76.7909, 9.5667, 76.7583) # Ponkunnam ~3.7 km
        self.assertLess(dist, 5.0)

        # Ponkunnam is inside 20 km perimeter
        is_serviceable, dist_km, msg = is_within_delivery_perimeter(9.5667, 76.7583)
        self.assertTrue(is_serviceable)
        self.assertIn("inside our service area", msg)

        # Ernakulam (~71 km) is outside perimeter
        is_serviceable, dist_km, msg = is_within_delivery_perimeter(9.9816, 76.2999)
        self.assertFalse(is_serviceable)
        self.assertIn("Sorry, delivery is currently available only within 20 km of Kanjirappally.", msg)

    def test_18_staff_save_delivery_perimeter_endpoint(self):
        """Test Admin/Staff configuring Delivery Center and radius via POST."""
        staff = User.objects.create_user(username='staff_admin', email='staff_admin@test.com', password='Password123!', role='staff')
        self.client.login(username='staff_admin', password='Password123!')

        resp = self.client.post(reverse('staff_save_delivery_perimeter'), {
            'name': 'Kanjirappally Central Hub',
            'address': 'Main Town Road, Kanjirappally',
            'latitude': '9.5564',
            'longitude': '76.7909',
            'max_delivery_radius_km': '20.0'
        })
        self.assertEqual(resp.status_code, 302)

        from delivery.models import DeliverySetting
        setting = DeliverySetting.get_settings()
        self.assertEqual(setting.name, 'Kanjirappally Central Hub')
        self.assertEqual(setting.latitude, 9.5564)
        self.assertEqual(setting.longitude, 76.7909)
        self.assertEqual(setting.max_delivery_radius_km, 20.0)

    def test_19_delivery_perimeter_outside_shows_exact_service_area_message(self):
        """Test placing an order outside perimeter displays the exact required warning message."""
        self.client.login(username='customer_one', password='Password123!')
        CartItem.objects.create(user=self.customer1, food_item=self.food1, quantity=1)

        # Bangalore coordinates (~550 km away)
        resp = self.client.post(reverse('place_order'), {
            'latitude': 12.9716,
            'longitude': 77.5946,
            'delivery_address': 'MG Road Bangalore',
            'payment_method': 'cod'
        }, follow=True)
        self.assertEqual(resp.status_code, 200)

        # Check messages for exact phrase
        messages_list = [m.message for m in resp.context['messages']]
        self.assertIn("Sorry, delivery is currently available only within 20 km of Kanjirappally.", messages_list)

    def test_20_order_gps_linked_to_courier_and_privacy(self):
        """Test customer coordinates correctly link to Order ID, and courier navigation does not expose private sensitive info."""
        self.client.login(username='customer_one', password='Password123!')
        CartItem.objects.create(user=self.customer1, food_item=self.food1, quantity=1)

        # Place valid order inside perimeter
        resp = self.client.post(reverse('place_order'), {
            'latitude': 9.5564,
            'longitude': 76.7909,
            'delivery_address': 'Kanjirappally Town, near yellow gate',
            'payment_method': 'cod'
        })
        self.assertEqual(resp.status_code, 302)

        order = Order.objects.filter(user=self.customer1).order_by('-created_at').first()
        self.assertIsNotNone(order)
        self.assertEqual(order.latitude, 9.5564)
        self.assertEqual(order.longitude, 76.7909)

        # Assign to courier
        assign = DeliveryAssignment.objects.create(
            order=order,
            delivery_boy=self.courier_profile,
            status='assigned'
        )

        # Courier views track page
        self.client.login(username='courier_arun', password='Password123!')
        track_resp = self.client.get(reverse('delivery_boy_track', kwargs={'assignment_id': assign.id}))
        self.assertEqual(track_resp.status_code, 200)

        # Verify coordinates are present in context
        self.assertEqual(track_resp.context['cust_lat'], 9.5564)
        self.assertEqual(track_resp.context['cust_lon'], 76.7909)

        # Verify Google Maps turn-by-turn navigation URL is present
        content = track_resp.content.decode('utf-8')
        self.assertIn('https://www.google.com/maps/dir/?api=1&', content)
        self.assertIn('destination=9.5564,76.7909', content)

        # Verify Privacy: sensitive fields like password hash, email, and DOB are NOT displayed to the courier
        self.assertNotIn('cust1@test.com', content)
        self.assertNotIn('1995-03-20', content)

    def test_21_nine_couriers_setup_and_api(self):
        """Test exact 9 courier records setup with required phone numbers and API retrieval."""
        from django.core.management import call_command
        call_command('seed_couriers')
        
        required_phones = [
            "7510672351", "7510672352", "7510672353",
            "7510672354", "7510672355", "7510672356",
            "7510672357", "7510672358", "7510672359"
        ]
        for ph in required_phones:
            self.assertTrue(
                User.objects.filter(role='delivery_boy', phone=ph).exists(),
                f"Courier phone {ph} not found in database"
            )
            
        # Test API endpoint as Staff user
        staff_u = User.objects.create_user(username='staff_test_user', password='Password123!', role='staff', is_staff=True)
        self.client.login(username='staff_test_user', password='Password123!')
        response = self.client.get(reverse('api_list_couriers'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertGreaterEqual(data['total_count'], 9)
        
        phone_set = {c['phone'] for c in data['couriers']}
        for ph in required_phones:
            self.assertIn(ph, phone_set)

    def test_22_full_staff_courier_customer_workflow(self):
        """Test complete 15-step Staff -> Courier5 -> Customer workflow using Jagan / 7510571727 & courier / 7510672355."""
        from django.core.management import call_command
        call_command('seed_couriers')

        # 1. Customer Jagan (phone: 7510571727) places order
        jagan = User.objects.create_user(
            username='jagan_cust',
            first_name='Jagan',
            email='jagan@test.com',
            password='password123',
            role='customer',
            phone='7510571727',
            latitude=9.5564,
            longitude=76.7909
        )
        self.client.login(username='jagan_cust', password='password123')
        CartItem.objects.create(user=jagan, food_item=self.food1, quantity=1)

        place_resp = self.client.post(reverse('place_order'), {
            'latitude': 9.5564,
            'longitude': 76.7909,
            'delivery_address': 'Parathode, Kanjirappally',
            'payment_method': 'cod'
        })
        self.assertEqual(place_resp.status_code, 302)

        order = Order.objects.filter(user=jagan).order_by('-created_at').first()
        self.assertIsNotNone(order)
        self.assertEqual(order.user.first_name, 'Jagan')
        self.assertEqual(order.user.phone, '7510571727')

        # 2. Chef updates status to ready_pickup (Ready for Pickup)
        self.client.login(username='chef_mary', password='Password123!')
        chef_resp = self.client.post(reverse('chef_order_status_update', kwargs={'order_id': order.order_id}), {
            'status': 'ready_pickup'
        })
        self.assertEqual(chef_resp.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, 'ready_pickup')

        # 3. Staff sees Ready for Pickup order & assigns to Courier 5 (courier / 7510672355)
        staff_u = User.objects.filter(role='staff').first() or User.objects.create_user(username='staff_test', password='password123', role='staff', is_staff=True)
        self.client.login(username=staff_u.username, password='password123')
        staff_dash = self.client.get(reverse('staff_dashboard'))
        self.assertEqual(staff_dash.status_code, 200)
        self.assertIn(order.order_id, staff_dash.content.decode('utf-8'))

        courier5 = User.objects.filter(phone='7510672355').first()
        self.assertIsNotNone(courier5)
        courier5_profile = courier5.delivery_boy_profile

        assign_resp = self.client.post(reverse('staff_assign_delivery', kwargs={'order_id': order.order_id}), {
            'delivery_boy_id': courier5_profile.id
        })
        self.assertEqual(assign_resp.status_code, 302)

        order.refresh_from_db()
        self.assertTrue(hasattr(order, 'delivery_assignment'))
        self.assertEqual(order.delivery_assignment.delivery_boy, courier5_profile)
        self.assertEqual(order.status, 'ready_pickup')

        # 4. Courier logs in with username: 'courier5', password: 'password123'
        self.client.login(username='courier5', password='password123')
        courier_dash = self.client.get(reverse('delivery_boy_dashboard'))
        self.assertEqual(courier_dash.status_code, 200)

        dash_content = courier_dash.content.decode('utf-8')
        self.assertIn(order.order_id, dash_content)
        self.assertIn('Jagan', dash_content)
        self.assertIn('7510571727', dash_content)

        # 5. Courier marks Picked Up
        assign_id = order.delivery_assignment.id
        pickup_resp = self.client.post(reverse('pickup_order', kwargs={'assignment_id': assign_id}))
        self.assertEqual(pickup_resp.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, 'picked_up')

        # 6. Courier marks Out for Delivery (in_transit)
        start_resp = self.client.post(reverse('start_delivery', kwargs={'assignment_id': assign_id}))
        self.assertEqual(start_resp.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, 'in_transit')

        # 7. Courier marks Delivered
        done_resp = self.client.post(reverse('complete_delivery', kwargs={'assignment_id': assign_id}))
        self.assertEqual(done_resp.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, 'delivered')

    def test_23_courier_identification_and_visibility(self):
        """Verify all 9 couriers have exact Courier Number/Name, Username, and Phone visibility for Staff."""
        call_command('seed_couriers')

        expected_map = {
            'courier1': ('Courier 1', '7510672352'),
            'courier2': ('Courier 2', '7510672351'),
            'courier3': ('Courier 3', '7510672353'),
            'courier4': ('Courier 4', '7510672354'),
            'courier5': ('Courier 5', '7510672355'),
            'courier6': ('Courier 6', '7510672356'),
            'courier7': ('Courier 7', '7510672357'),
            'courier8': ('Courier 8', '7510672358'),
            'courier9': ('Courier 9', '7510672359'),
        }

        for username, (exp_name, exp_phone) in expected_map.items():
            user = User.objects.get(username=username)
            profile = user.delivery_boy_profile
            self.assertEqual(profile.courier_name, exp_name)
            self.assertEqual(user.phone, exp_phone)

        # Verify Staff dropdown and assigned order display
        order = Order.objects.create(
            user=self.customer1,
            total_amount=Decimal('450.00'),
            status='ready_pickup',
            delivery_address='Main Street'
        )

        c5_profile = User.objects.get(username='courier5').delivery_boy_profile

        staff_u = User.objects.filter(role='staff').first()
        if not staff_u:
            staff_u = User.objects.create_user(username='staff_test', password='password123', role='staff', is_staff=True)
        else:
            staff_u.set_password('password123')
            staff_u.save()
        self.client.login(username=staff_u.username, password='password123')
        assign_resp = self.client.post(reverse('staff_assign_delivery', kwargs={'order_id': order.order_id}), {
            'delivery_boy_id': c5_profile.id
        })
        self.assertEqual(assign_resp.status_code, 302)

        # Check Staff dashboard output
        staff_dash = self.client.get(reverse('staff_dashboard'))
        self.assertEqual(staff_dash.status_code, 200)
        content = staff_dash.content.decode('utf-8')

        self.assertIn('Courier 5', content)
        self.assertIn('courier5', content)
        self.assertIn('7510672355', content)
        self.assertIn('KL-34-A-1005', content)

        # Check API list couriers
        api_resp = self.client.get(reverse('api_list_couriers'))
        self.assertEqual(api_resp.status_code, 200)
        api_data = api_resp.json()
        self.assertEqual(api_data['status'], 'success')
        c5_api_item = next(item for item in api_data['couriers'] if item['username'] == 'courier5')
        self.assertEqual(c5_api_item['courier_name'], 'Courier 5')
        self.assertEqual(c5_api_item['phone'], '7510672355')

    def test_24_admin_revenue_and_food_sales_analytics(self):
        """Test Admin Revenue and Food Sales Analytics calculations, date filtering, and order/item exclusions."""
        # 1. Create Admin User
        admin_user = User.objects.create_user(
            username='admin_boss',
            email='admin@test.com',
            password='Password123!',
            role='admin',
            is_staff=True,
            is_superuser=True
        )

        # 2. Create Foods
        dosa = FoodItem.objects.create(
            chef=self.chef_user,
            name='Crispy Dosa',
            description='Ghee roast dosa',
            price=Decimal('50.00'),
            category=self.cat_veg,
            meal_session=self.session_lunch,
            stock_quantity=50,
            is_available=True
        )
        chapati = FoodItem.objects.create(
            chef=self.chef_user,
            name='Soft Chapati',
            description='Whole wheat chapati',
            price=Decimal('40.00'),
            category=self.cat_veg,
            meal_session=self.session_lunch,
            stock_quantity=50,
            is_available=True
        )

        # 3. Create Valid Completed Order 1 (2 Dosa * 50 = 100)
        order1 = Order.objects.create(
            user=self.customer1,
            total_amount=Decimal('100.00'),
            status='delivered',
            delivery_address='Kanjirappally Town'
        )
        OrderItem.objects.create(order=order1, food_item=dosa, quantity=2, price=Decimal('50.00'))
        Payment.objects.create(order=order1, payment_method='upi', status='success', amount=Decimal('100.00'))

        # 4. Create Valid Completed Order 2 (3 Dosa * 50 = 150 + 1 Chapati * 40 = 40; Total = 190)
        order2 = Order.objects.create(
            user=self.customer2,
            total_amount=Decimal('190.00'),
            status='confirmed',
            delivery_address='Ponkunnam'
        )
        OrderItem.objects.create(order=order2, food_item=dosa, quantity=3, price=Decimal('50.00'))
        OrderItem.objects.create(order=order2, food_item=chapati, quantity=1, price=Decimal('40.00'))
        Payment.objects.create(order=order2, payment_method='cod', status='pending', amount=Decimal('190.00'))

        # 5. Create Cancelled Order (MUST BE EXCLUDED from revenue calculations)
        order_cancelled = Order.objects.create(
            user=self.customer1,
            total_amount=Decimal('250.00'),
            status='cancelled',
            delivery_address='Kanjirappally'
        )
        OrderItem.objects.create(order=order_cancelled, food_item=dosa, quantity=5, price=Decimal('50.00'))
        Payment.objects.create(order=order_cancelled, payment_method='upi', status='failed', amount=Decimal('250.00'))

        # 6. Admin logs in
        self.client.login(username='admin_boss', password='Password123!')

        # 7. GET Admin Dashboard
        resp = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(resp.status_code, 200)

        # Context Assertions
        self.assertEqual(resp.context['filtered_revenue'], 290.00) # 100 + 190
        self.assertEqual(resp.context['filtered_orders_count'], 2)
        self.assertEqual(resp.context['filtered_items_sold'], 6) # 2 Dosa + 3 Dosa + 1 Chapati = 6 items

        # Top selling food
        self.assertIsNotNone(resp.context['most_purchased_food'])
        self.assertEqual(resp.context['most_purchased_food']['name'], 'Crispy Dosa')

        # Food sales analytics list check
        sales_analysis = resp.context['food_sales_analysis']
        dosa_stat = next(item for item in sales_analysis if item['id'] == dosa.id)
        chapati_stat = next(item for item in sales_analysis if item['id'] == chapati.id)

        self.assertEqual(dosa_stat['qty_sold'], 5) # 2 + 3 = 5 (cancelled order's 5 is excluded)
        self.assertEqual(dosa_stat['orders_count'], 2)
        self.assertEqual(dosa_stat['revenue'], 250.00) # 5 * 50 = 250

        self.assertEqual(chapati_stat['qty_sold'], 1)
        self.assertEqual(chapati_stat['orders_count'], 1)
        self.assertEqual(chapati_stat['revenue'], 40.00)

        # Response HTML check
        content = resp.content.decode('utf-8')
        self.assertIn('Revenue &amp; Food Sales Analytics', content)
        self.assertIn('Crispy Dosa', content)
        self.assertIn('Soft Chapati', content)
        self.assertIn('290', content)

        # 8. Test Date Filtering (period=today)
        resp_today = self.client.get(reverse('admin_dashboard') + '?period=today')
        self.assertEqual(resp_today.status_code, 200)
        self.assertEqual(resp_today.context['filtered_revenue'], 290.00)

        # 9. Test Date Filtering (period=custom date range)
        today_str = timezone.localtime().strftime('%Y-%m-%d')
        resp_custom = self.client.get(reverse('admin_dashboard') + f'?period=custom&start_date={today_str}&end_date={today_str}')
        self.assertEqual(resp_custom.status_code, 200)
        self.assertEqual(resp_custom.context['filtered_revenue'], 290.00)






