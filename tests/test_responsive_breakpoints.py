import os
from django.test import TestCase, Client
from django.urls import reverse
from django.conf import settings
from accounts.models import User, ChefProfile, DeliveryBoyProfile
from food.models import Category, MealSession, FoodItem
from orders.models import Order, Payment, OrderItem, CartItem
from delivery.models import DeliveryAssignment, District, HotelBranch


class ResponsiveBreakpointsTestCase(TestCase):
    """
    Test suite validating mobile-friendly responsive design across all 6 specified breakpoints:
    1. Small mobile: 320px–374px
    2. Standard mobile: 375px–479px
    3. Large mobile: 480px–767px
    4. Tablet: 768px–1023px
    5. Laptop: 1024px–1439px
    6. Desktop and large screens: 1440px and above
    Plus orientation handling and touch targets.
    """

    def setUp(self):
        self.client = Client()
        self.password = "TestPass123!@"

        # District and Branch
        self.district = District.objects.create(name="Kottayam", code="kottayam", latitude=9.5564, longitude=76.7909)
        self.branch = HotelBranch.objects.create(
            name="Central Kitchen Hub",
            district=self.district,
            latitude=9.5564,
            longitude=76.7909,
            max_delivery_radius_km=30.0,
            is_central_hub=True,
            is_active=True
        )

        # Users
        self.customer = User.objects.create_user(
            username="cust_mobile",
            email="cust_m@example.com",
            password=self.password,
            role="customer",
            phone="9876543210"
        )
        self.chef_user = User.objects.create_user(
            username="chef_mobile",
            email="chef_m@example.com",
            password=self.password,
            role="chef",
            phone="9876543211"
        )
        self.chef_profile = ChefProfile.objects.create(user=self.chef_user, is_approved=True)

        self.courier_user = User.objects.create_user(
            username="courier_mobile",
            email="courier_m@example.com",
            password=self.password,
            role="delivery_boy",
            phone="9876543212"
        )
        self.courier_profile = DeliveryBoyProfile.objects.create(
            user=self.courier_user,
            vehicle_number="KL-05-RESP-01",
            status="available",
            current_latitude=9.5564,
            current_longitude=76.7909
        )

        self.staff_user = User.objects.create_user(
            username="staff_mobile",
            email="staff_m@example.com",
            password=self.password,
            role="staff",
            phone="9876543213"
        )
        self.admin_user = User.objects.create_superuser(
            username="admin_mobile",
            email="admin_m@example.com",
            password=self.password,
            role="admin",
            phone="9876543214"
        )

        # Food & Category
        self.category = Category.objects.create(name="Breakfast")
        self.session = MealSession.objects.create(
            name="Morning Breakfast",
            start_time="07:00:00",
            end_time="11:00:00"
        )
        self.food = FoodItem.objects.create(
            name="Kerala Appam & Stew",
            description="Steaming soft appams with aromatic vegetable stew",
            price=60.00,
            category=self.category,
            meal_session=self.session,
            chef=self.chef_user,
            stock_quantity=25,
            is_available=True
        )

        # Order & Assignment
        self.order = Order.objects.create(
            order_id="VR-RESP-001",
            user=self.customer,
            total_amount=120.00,
            branch=self.branch,
            latitude=9.5564,
            longitude=76.7909,
            delivery_address="Civil Station Road, Kottayam",
            status="in_transit"
        )
        self.payment = Payment.objects.create(
            order=self.order,
            payment_method="cod",
            status="pending",
            amount=120.00
        )
        self.assignment = DeliveryAssignment.objects.create(
            order=self.order,
            delivery_boy=self.courier_profile,
            status="in_transit",
            is_active=True
        )

    def test_css_contains_all_specified_breakpoints(self):
        """Validates that style.css defines media queries for all 6 exact breakpoints and orientations."""
        css_path = os.path.join(settings.BASE_DIR, 'static', 'css', 'style.css')
        self.assertTrue(os.path.exists(css_path), "style.css must exist in static/css/")

        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        # 1. Small mobile: 320px–374px
        self.assertIn("320px", css_content)
        self.assertIn("374px", css_content)

        # 2. Standard mobile: 375px–479px
        self.assertIn("375px", css_content)
        self.assertIn("479px", css_content)

        # 3. Large mobile: 480px–767px
        self.assertIn("480px", css_content)
        self.assertIn("767px", css_content)

        # 4. Tablet: 768px–1023px
        self.assertIn("768px", css_content)
        self.assertIn("1023px", css_content)

        # 5. Laptop: 1024px–1439px
        self.assertIn("1024px", css_content)
        self.assertIn("1439px", css_content)

        # 6. Desktop and large screens: 1440px and above
        self.assertIn("1440px", css_content)

        # Landscape orientation handling
        self.assertIn("orientation: landscape", css_content)

        # Touch-friendly rules
        self.assertIn("touch-action: manipulation", css_content)

    def test_base_template_has_viewport_meta_tag(self):
        """Validates that base.html has responsive viewport meta tag."""
        resp = self.client.get(reverse('food_catalog'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('<meta name="viewport" content="width=device-width, initial-scale=1.0">', content)
        self.assertIn('kerala-navbar', content)
        self.assertIn('mobile-toggle', content)
        self.assertIn('mobile-drawer', content)

    def test_customer_catalog_responsive_elements(self):
        """Verifies customer food catalog renders with responsive grid and food cards."""
        resp = self.client.get(reverse('food_catalog'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('grid-3', content)
        self.assertIn('food-card', content)
        self.assertIn('container', content)

    def test_customer_cart_and_checkout_responsiveness(self):
        """Verifies cart and checkout pages load with responsive containers and map wrappers."""
        self.client.login(username="cust_mobile", password=self.password)

        CartItem.objects.create(user=self.customer, food_item=self.food, quantity=2)

        cart_resp = self.client.get(reverse('cart_view'))
        self.assertEqual(cart_resp.status_code, 200)

        checkout_resp = self.client.get(reverse('checkout_view'))
        self.assertEqual(checkout_resp.status_code, 200)
        checkout_content = checkout_resp.content.decode('utf-8')
        self.assertIn('Order Summary', checkout_content)
        self.assertIn('Payment Method', checkout_content)

    def test_customer_order_history_and_tracking_responsiveness(self):
        """Verifies order history and live GPS tracking pages load with responsive containers."""
        self.client.login(username="cust_mobile", password=self.password)

        hist_resp = self.client.get(reverse('order_history'))
        self.assertEqual(hist_resp.status_code, 200)
        self.assertIn("overflow-x: auto", hist_resp.content.decode('utf-8'))

        track_resp = self.client.get(reverse('order_tracking', args=[self.order.order_id]))
        self.assertEqual(track_resp.status_code, 200)
        track_content = track_resp.content.decode('utf-8')
        self.assertIn('live-order-map-section', track_content)
        self.assertIn('live-delivery-map', track_content)
        self.assertNotIn('earth.google.com/web', track_content)

    def test_chef_dashboard_responsiveness(self):
        """Verifies chef dashboard renders with responsive grid, modal, and table wrapper."""
        self.client.login(username="chef_mobile", password=self.password)
        resp = self.client.get(reverse('chef_dashboard'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('overflow-x: auto', content)
        self.assertIn('new-order-modal-card', content)

    def test_courier_dashboard_and_track_responsiveness(self):
        """Verifies courier dashboard and live navigation tracking load with responsive containers."""
        self.client.login(username="courier_mobile", password=self.password)

        dash_resp = self.client.get(reverse('delivery_boy_dashboard'))
        self.assertEqual(dash_resp.status_code, 200)

        track_resp = self.client.get(reverse('delivery_boy_track', args=[self.assignment.id]))
        self.assertEqual(track_resp.status_code, 200)
        track_content = track_resp.content.decode('utf-8')
        self.assertIn('map-section-card', track_content)
        self.assertIn('delivery-nav-map', track_content)
        self.assertNotIn('earth.google.com/web', track_content)

    def test_staff_dashboard_responsiveness(self):
        """Verifies staff dashboard loads with responsive columns and fleet panel."""
        self.client.login(username="staff_mobile", password=self.password)
        resp = self.client.get(reverse('staff_dashboard'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('scrollable-pill-bar', content)

    def test_base_template_uses_django_static_tag(self):
        """Validates that base.html uses Django static tags for hosting and WhiteNoise compatibility."""
        base_path = os.path.join(settings.BASE_DIR, 'templates', 'base.html')
        with open(base_path, 'r', encoding='utf-8') as f:
            base_content = f.read()

        self.assertIn('{% load static %}', base_content, "base.html must load static tag library")
        self.assertIn("{% static 'css/style.css' %}", base_content, "base.html must use static tag for style.css")
        self.assertIn("{% static 'leaflet/leaflet.css' %}", base_content)
        self.assertIn("{% static 'leaflet/leaflet.js' %}", base_content)
        self.assertNotIn('window.GOOGLE_EARTH_WEB_URL', base_content)
        self.assertNotIn("{% static 'maplibre/maplibre-gl.css' %}", base_content)
        self.assertNotIn("{% static 'maplibre/maplibre-gl.js' %}", base_content)
        self.assertNotIn("{% static 'js/veetile-maps.js' %}", base_content)
        self.assertIn('id="mobile-drawer-overlay"', base_content, "mobile-drawer-overlay must be defined for backdrop click")

    def test_multi_role_mobile_drawer_navigation(self):
        """Validates that the mobile drawer renders role-specific dashboard links for all 5 user roles."""
        # 1. Customer
        self.client.login(username="cust_mobile", password=self.password)
        c_resp = self.client.get(reverse('food_catalog'))
        c_content = c_resp.content.decode('utf-8')
        self.assertIn('Cart', c_content)
        self.assertIn('My Orders', c_content)
        self.assertIn('Wishlist', c_content)

        # 2. Chef
        self.client.login(username="chef_mobile", password=self.password)
        chef_resp = self.client.get(reverse('food_catalog'))
        chef_content = chef_resp.content.decode('utf-8')
        self.assertIn('Chef Dashboard', chef_content)
        self.assertIn('Add New Dish', chef_content)

        # 3. Delivery Boy
        self.client.login(username="courier_mobile", password=self.password)
        courier_resp = self.client.get(reverse('delivery_boy_dashboard'))
        self.assertEqual(courier_resp.status_code, 200)
        courier_content = courier_resp.content.decode('utf-8')
        self.assertIn('Courier Portal', courier_content)

        # 4. Staff
        self.client.login(username="staff_mobile", password=self.password)
        staff_resp = self.client.get(reverse('food_catalog'))
        staff_content = staff_resp.content.decode('utf-8')
        self.assertIn('Staff Console', staff_content)

        # 5. Administrator
        self.client.login(username="admin_mobile", password=self.password)
        admin_resp = self.client.get(reverse('food_catalog'))
        admin_content = admin_resp.content.decode('utf-8')
        self.assertIn('Admin Dashboard', admin_content)
        self.assertIn('AI Analytics', admin_content)

    def test_admin_dashboard_responsiveness_and_sidebar_toggle(self):
        """Verifies admin dashboard has responsive sidebar toggle, backdrop overlay, and media queries."""
        self.client.login(username="admin_mobile", password=self.password)
        resp = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')

        self.assertIn('id="menu-toggle"', content)
        self.assertIn('id="sidebar-overlay"', content)
        self.assertIn('toggleAdminSidebar', content)
        self.assertIn('sidebar.open', content)
        self.assertIn('logout-text', content)

    def test_css_map_resizing_across_all_breakpoints(self):
        """Validates that .maplibregl-map and #checkout-map-picker-wrapper are styled across all breakpoints."""
        css_path = os.path.join(settings.BASE_DIR, 'static', 'css', 'style.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            css = f.read()

        self.assertIn('.maplibregl-map', css)
        self.assertIn('#checkout-map-picker-wrapper', css)
        self.assertIn('height: 260px !important;', css)
        self.assertIn('height: 300px !important;', css)
        self.assertIn('height: 350px !important;', css)
        self.assertIn('height: 420px !important;', css)
        self.assertIn('height: 480px !important;', css)
        self.assertIn('height: 540px !important;', css)
        self.assertIn('height: 220px !important;', css)

    def test_mobile_density_and_min_width_resets(self):
        """Validates that style.css prevents horizontal overflow on ultra-compact 320px screens."""
        css_path = os.path.join(settings.BASE_DIR, 'static', 'css', 'style.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            css = f.read()

        self.assertIn('div[style*="min-width: 320px"]', css)
        self.assertIn('input[style*="min-width"]', css)
        self.assertIn('select[style*="min-width"]', css)
        self.assertIn('button[style*="min-width"]', css)
        self.assertIn('.table-responsive', css)
        self.assertIn('.catalog-search-form', css)
        self.assertIn('.quick-track-form', css)

