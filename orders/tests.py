from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta, date, time
from decimal import Decimal
import json

from accounts.models import User, ChefProfile, DeliveryBoyProfile, PasswordResetOTP
from health.models import HealthProfile
from food.models import FoodItem, Category, MealSession, NutritionInfo, ReviewSentiment
from orders.models import CartItem, Coupon, Order, OrderItem, Payment, Wishlist, Notification
from delivery.models import DeliveryAssignment, DeliveryFeedback

class CustomerWorkflowAndSecurityTests(TestCase):
    def setUp(self):
        self.client = Client()

        # 1. Primary Customer
        self.customer1 = User.objects.create_user(
            username='customer_one',
            email='cust1@test.com',
            password='Password123!',
            role='customer',
            dob='1995-03-20',
            phone='9876543210',
            latitude=10.025,
            longitude=76.315
        )
        HealthProfile.objects.create(user=self.customer1)

        # 2. Secondary Customer (for cross-customer isolation & security checks)
        self.customer2 = User.objects.create_user(
            username='customer_two',
            email='cust2@test.com',
            password='Password123!',
            role='customer',
            dob='1996-07-14',
            phone='9876543211',
            latitude=10.040,
            longitude=76.290
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

        # 1. Base Catalog
        resp = self.client.get(reverse('food_catalog'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Kerala Sadya Feast')
        self.assertContains(resp, 'Karimeen Pollichathu')

        # 2. Filter by Category
        resp_cat = self.client.get(reverse('food_catalog') + '?category=Vegetarian')
        self.assertEqual(resp_cat.status_code, 200)
        self.assertContains(resp_cat, 'Kerala Sadya Feast')
        self.assertNotContains(resp_cat, 'Karimeen Pollichathu')

        # 3. Search by keyword
        resp_search = self.client.get(reverse('food_catalog') + '?q=Pearl')
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
        self.assertContains(chk_resp, 'Delivery Details')

        initial_stock = self.food1.stock_quantity

        # Place Order (COD)
        place_resp = self.client.post(reverse('place_order'), {
            'latitude': '10.025000',
            'longitude': '76.315000',
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
            'latitude': '10.025000',
            'longitude': '76.315000',
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

