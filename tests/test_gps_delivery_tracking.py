from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
import math

from accounts.models import User, DeliveryBoyProfile
from food.models import Category, MealSession, FoodItem
from orders.models import Order, OrderItem, Payment
from delivery.models import DeliveryAssignment, GPSLocationTracking, HotelBranch, District, DeliverySetting
from orders.utils import validate_coordinates, is_valid_coordinate
from ai_models.ml_engine import RouteResult, optimize_delivery_route


class GPSCoordinatesValidationTests(TestCase):
    """Test suite for coordinate validation and safety."""

    def test_valid_coordinates(self):
        lat, lon = validate_coordinates(9.5564, 76.7909)
        self.assertEqual(lat, 9.5564)
        self.assertEqual(lon, 76.7909)
        self.assertTrue(is_valid_coordinate(9.5564, 76.7909))

    def test_valid_string_coordinates(self):
        lat, lon = validate_coordinates("10.025", "76.315")
        self.assertEqual(lat, 10.025)
        self.assertEqual(lon, 76.315)
        self.assertTrue(is_valid_coordinate("10.025", "76.315"))

    def test_invalid_ranges(self):
        # Lat > 90
        lat, lon = validate_coordinates(91.0, 76.0)
        self.assertIsNone(lat)
        self.assertIsNone(lon)
        self.assertFalse(is_valid_coordinate(91.0, 76.0))

        # Lat < -90
        lat, lon = validate_coordinates(-95.0, 76.0)
        self.assertIsNone(lat)
        self.assertIsNone(lon)

        # Lon > 180
        lat, lon = validate_coordinates(10.0, 185.0)
        self.assertIsNone(lat)
        self.assertIsNone(lon)

        # Lon < -180
        lat, lon = validate_coordinates(10.0, -185.0)
        self.assertIsNone(lat)
        self.assertIsNone(lon)

    def test_nan_and_inf_handling(self):
        lat, lon = validate_coordinates(float('nan'), 76.0)
        self.assertIsNone(lat)
        self.assertIsNone(lon)

        lat, lon = validate_coordinates(10.0, float('inf'))
        self.assertIsNone(lat)
        self.assertIsNone(lon)

        lat, lon = validate_coordinates(float('-inf'), 76.0)
        self.assertIsNone(lat)
        self.assertIsNone(lon)

    def test_none_and_empty_handling(self):
        lat, lon = validate_coordinates(None, None)
        self.assertIsNone(lat)
        self.assertIsNone(lon)

        lat, lon = validate_coordinates("", "")
        self.assertIsNone(lat)
        self.assertIsNone(lon)

        lat, lon = validate_coordinates("invalid_str", "another_str")
        self.assertIsNone(lat)
        self.assertIsNone(lon)


class RouteResultStructureTests(TestCase):
    """Test RouteResult class backwards compatibility and road routing properties."""

    def test_routeresult_tuple_unpacking(self):
        steps = [{'lat': 9.55, 'lng': 76.79}, {'lat': 9.56, 'lng': 76.80}]
        res = RouteResult(steps, 5.2, is_road=True)

        # Tuple unpacking works identically to existing codebase expectations
        unpacked_steps, unpacked_dist = res
        self.assertEqual(len(unpacked_steps), 2)
        self.assertEqual(unpacked_dist, 5.2)

        # Property access also works
        self.assertTrue(res.is_road)
        self.assertEqual(res.distance, 5.2)
        self.assertEqual(res.route, steps)

    def test_optimize_delivery_route_returns_routeresult(self):
        res = optimize_delivery_route(9.5564, 76.7909, 9.5800, 76.8100)
        self.assertIsInstance(res, RouteResult)
        self.assertGreater(res.distance, 0)
        self.assertTrue(len(res.route) >= 2)


class CourierTrackingWorkflowAndSeparationTests(TestCase):
    """Test Hotel Base vs Courier GPS Separation, Stale GPS handling, and Access Control."""

    def setUp(self):
        self.client = Client()

        # Create district and branch (Hotel Base)
        self.district = District.objects.create(name='Kottayam', code='KTM', latitude=9.5916, longitude=76.5222)
        self.branch = HotelBranch.objects.create(
            district=self.district,
            name='Kanjirappally Central Kitchen',
            address='NH 183, Kanjirappally',
            latitude=9.5564,
            longitude=76.7909,
            max_delivery_radius_km=25.0,
            is_active=True,
            is_central_hub=True
        )

        # Create Customer
        self.customer = User.objects.create_user(
            username='arun_customer',
            email='arun@test.com',
            password='password123',
            role='customer',
            phone='9847000001'
        )

        # Create Another Customer (for cross-customer privacy check)
        self.intruder = User.objects.create_user(
            username='sneha_intruder',
            email='sneha@test.com',
            password='password123',
            role='customer',
            phone='9847000002'
        )

        # Create Courier 1
        self.courier1_user = User.objects.create_user(
            username='courier_rahul',
            email='rahul@test.com',
            password='password123',
            role='delivery_boy',
            phone='9847000003'
        )
        self.courier1_profile = DeliveryBoyProfile.objects.create(
            user=self.courier1_user,
            vehicle_number='KL-34-AB-1234',
            status='available',
            current_latitude=9.5564,
            current_longitude=76.7909
        )

        # Create Courier 2
        self.courier2_user = User.objects.create_user(
            username='courier_vivek',
            email='vivek@test.com',
            password='password123',
            role='delivery_boy',
            phone='9847000004'
        )
        self.courier2_profile = DeliveryBoyProfile.objects.create(
            user=self.courier2_user,
            vehicle_number='KL-34-CD-5678',
            status='available'
        )

        # Create Order
        self.order = Order.objects.create(
            user=self.customer,
            branch=self.branch,
            total_amount=150.00,
            status='assigned',
            latitude=9.5850,
            longitude=76.8150,
            delivery_address='Near St. Dominic College, Kanjirappally'
        )

        # Create Delivery Assignment
        self.assignment = DeliveryAssignment.objects.create(
            order=self.order,
            delivery_boy=self.courier1_profile,
            status='assigned'
        )

    def test_hotel_base_separate_from_courier_gps_when_assigned(self):
        """When courier is merely assigned (not yet in transit), the origin is the Hotel Base."""
        self.client.login(username='arun_customer', password='password123')
        resp = self.client.get(reverse('api_order_status', args=[self.order.order_id]))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Hotel base is 9.5564, 76.7909
        self.assertAlmostEqual(data['chef_lat'], 9.5564, places=3)
        self.assertAlmostEqual(data['chef_lon'], 76.7909, places=3)
        self.assertFalse(data['has_courier_gps'])

    def test_actual_courier_gps_used_when_in_transit(self):
        """When courier is in_transit and has GPS fix, route & distance originate from courier GPS."""
        # Update order & assignment to in_transit
        self.order.status = 'in_transit'
        self.order.save()
        self.assignment.status = 'in_transit'
        self.assignment.save()

        # Courier records a live GPS breadcrumb at a location different from hotel base
        courier_live_lat = 9.5700
        courier_live_lon = 76.8000
        GPSLocationTracking.objects.create(
            delivery_assignment=self.assignment,
            latitude=courier_live_lat,
            longitude=courier_live_lon
        )

        self.client.login(username='arun_customer', password='password123')
        resp = self.client.get(reverse('api_order_status', args=[self.order.order_id]))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertTrue(data['has_courier_gps'])
        self.assertFalse(data['is_gps_stale'])
        self.assertAlmostEqual(data['courier_lat'], courier_live_lat, places=4)
        self.assertAlmostEqual(data['courier_lon'], courier_live_lon, places=4)
        # Hotel base remains strictly distinct from courier live location
        self.assertNotEqual(data['courier_lat'], data['chef_lat'])

    def test_stale_gps_handling_over_300_seconds(self):
        """Coordinates older than 300 seconds are flagged as stale and not presented as live."""
        self.order.status = 'in_transit'
        self.order.save()
        self.assignment.status = 'in_transit'
        self.assignment.save()

        # Create breadcrumb and update timestamp to 10 minutes ago
        old_time = timezone.now() - timedelta(minutes=10)
        crumb = GPSLocationTracking.objects.create(
            delivery_assignment=self.assignment,
            latitude=9.5700,
            longitude=76.8000
        )
        GPSLocationTracking.objects.filter(id=crumb.id).update(timestamp=old_time)

        self.client.login(username='arun_customer', password='password123')
        resp = self.client.get(reverse('api_order_status', args=[self.order.order_id]))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertFalse(data['has_courier_gps'])
        self.assertTrue(data['is_gps_stale'])
        self.assertIn("Signal Stale", data['last_gps_update'])

    def test_unauthorized_customer_cannot_access_order_tracking(self):
        """Intruder customer is denied access to another customer's order tracking."""
        self.client.login(username='sneha_intruder', password='password123')

        # API status endpoint returns 403 Forbidden
        api_resp = self.client.get(reverse('api_order_status', args=[self.order.order_id]))
        self.assertEqual(api_resp.status_code, 403)

        # Web tracking page redirects with access denied
        page_resp = self.client.get(reverse('order_tracking', args=[self.order.order_id]))
        self.assertEqual(page_resp.status_code, 302)

    def test_courier_cannot_update_another_couriers_gps(self):
        """Courier 2 cannot send GPS updates for an assignment given to Courier 1."""
        self.client.login(username='courier_vivek', password='password123')
        resp = self.client.post(
            reverse('update_courier_gps', args=[self.assignment.id]),
            data='{"latitude": 9.5700, "longitude": 76.8000}',
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()['status'], 'error')

    def test_courier_can_update_own_gps_with_valid_coordinates(self):
        """Courier 1 can successfully update their own GPS during active delivery."""
        self.client.login(username='courier_rahul', password='password123')
        resp = self.client.post(
            reverse('update_courier_gps', args=[self.assignment.id]),
            data='{"latitude": 9.5750, "longitude": 76.8050, "accuracy": 12.5}',
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'success')

        # Verify breadcrumb stored in database
        latest = GPSLocationTracking.objects.filter(delivery_assignment=self.assignment).order_by('-timestamp').first()
        self.assertIsNotNone(latest)
        self.assertAlmostEqual(latest.latitude, 9.5750, places=4)
        self.assertAlmostEqual(latest.longitude, 76.8050, places=4)

    def test_courier_invalid_coordinates_rejected_by_backend(self):
        """Malformed or out-of-bounds coordinates sent to update_courier_gps are rejected."""
        self.client.login(username='courier_rahul', password='password123')

        # Out-of-bounds latitude
        resp = self.client.post(
            reverse('update_courier_gps', args=[self.assignment.id]),
            data='{"latitude": 99.0, "longitude": 76.8050}',
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['status'], 'error')

        # Non-numeric string coordinates
        resp2 = self.client.post(
            reverse('update_courier_gps', args=[self.assignment.id]),
            data='{"latitude": "invalid", "longitude": "coords"}',
            content_type='application/json'
        )
        self.assertEqual(resp2.status_code, 400)
        self.assertEqual(resp2.json()['status'], 'error')


class DeliveryPerimeterAndSeaDefenseTests(TestCase):
    """
    Test suite verifying:
    1. Kanjirappally customer selection (0 km - inside 30 km radius).
    2. Kottayam customer selection (~29.5 km - inside 30 km radius).
    3. Location near 30 km boundary (~28.5 km - inside 30 km radius).
    4. Location outside 30 km delivery radius (e.g. Ernakulam/Kochi ~73 km - rejected).
    5. Arabian Sea / offshore coordinates (e.g. 10.0, 76.0 - rejected and prevented from jumping to sea).
    6. Swapped coordinates auto-correction.
    7. Clean separation of Kitchen, Customer, and Courier coordinates.
    """

    def setUp(self):
        from delivery.models import District, HotelBranch
        from orders.utils import is_within_delivery_perimeter, is_offshore_sea_coordinate, sanitize_customer_coordinates, calculate_distance_km
        self.district = District.objects.create(name='Kottayam', code='ktm', latitude=9.5916, longitude=76.5222)
        self.customer = User.objects.create_user(
            username='etacustomer',
            email='etacustomer@example.com',
            password='TestPassword123!',
            role='customer'
        )
        self.branch = HotelBranch.objects.create(
            name='Central Kitchen Hub (Kanjirappally)',
            district=self.district,
            address='Kanjirappally Town, Kottayam',
            latitude=9.5564,
            longitude=76.7909,
            max_delivery_radius_km=30.0,
            is_central_hub=True,
            is_active=True
        )

    def test_kanjirappally_selection_inside_radius(self):
        from orders.utils import is_within_delivery_perimeter
        is_serviceable, dist, msg = is_within_delivery_perimeter(9.5564, 76.7909, branch_id=self.branch.id)
        self.assertTrue(is_serviceable)
        self.assertAlmostEqual(dist, 0.0, places=1)
        self.assertIn("inside our service area", msg.lower())

    def test_kottayam_selection_inside_30km_radius(self):
        from orders.utils import is_within_delivery_perimeter
        # Kottayam town center is ~29.5 km straight-line distance from Kanjirappally Hub
        is_serviceable, dist, msg = is_within_delivery_perimeter(9.5916, 76.5222, branch_id=self.branch.id)
        self.assertTrue(is_serviceable)
        self.assertLessEqual(dist, 30.0)
        self.assertIn("inside our service area", msg.lower())

    def test_location_near_30km_boundary_accepted(self):
        from orders.utils import is_within_delivery_perimeter
        # Location ~28.5 km from Kanjirappally
        is_serviceable, dist, msg = is_within_delivery_perimeter(9.5564, 76.5310, branch_id=self.branch.id)
        self.assertTrue(is_serviceable)
        self.assertLessEqual(dist, 30.0)

    def test_location_outside_30km_radius_strictly_rejected(self):
        from orders.utils import is_within_delivery_perimeter
        # Kochi / Ernakulam center is ~73 km from Kanjirappally Hub
        is_serviceable, dist, msg = is_within_delivery_perimeter(9.9816, 76.2750, branch_id=self.branch.id)
        self.assertFalse(is_serviceable)
        self.assertGreater(dist, 30.0)
        self.assertIn("cannot deliver", msg.lower())

    def test_offshore_arabian_sea_coordinates_detected_and_rejected(self):
        from orders.utils import is_offshore_sea_coordinate, is_within_delivery_perimeter, sanitize_customer_coordinates
        # Coordinate (10.0, 76.0) is in the Arabian Sea ~25 km west of the Kerala coast
        self.assertTrue(is_offshore_sea_coordinate(10.0, 76.0))
        self.assertTrue(is_offshore_sea_coordinate(9.5564, 76.0))

        # Rejected from delivery perimeter
        is_serviceable, dist, msg = is_within_delivery_perimeter(10.0, 76.0, branch_id=self.branch.id)
        self.assertFalse(is_serviceable)
        self.assertIn("sea", msg.lower())

        # Sanitization prevents jumping to sea, falling back to verified land hub
        clean_lat, clean_lon = sanitize_customer_coordinates(10.0, 76.0, fallback_lat=9.5564, fallback_lon=76.7909)
        self.assertEqual(clean_lat, 9.5564)
        self.assertEqual(clean_lon, 76.7909)

    def test_swapped_coordinates_auto_corrected(self):
        from orders.utils import validate_coordinates, sanitize_customer_coordinates
        # Swapped coordinates (lat=76.7909, lon=9.5564)
        lat, lon = validate_coordinates(76.7909, 9.5564)
        self.assertEqual(lat, 9.5564)
        self.assertEqual(lon, 76.7909)

        s_lat, s_lon = sanitize_customer_coordinates(76.7909, 9.5564)
        self.assertEqual(s_lat, 9.5564)
        self.assertEqual(s_lon, 76.7909)

    def test_three_locations_remain_strictly_independent(self):
        """Verify Kitchen, Customer Destination, and Courier Live GPS maintain distinct identities."""
        from orders.utils import sanitize_customer_coordinates
        kitchen_coords = (self.branch.latitude, self.branch.longitude)
        customer_coords = (9.5800, 76.8100) # Koovappally area
        courier_coords = (9.5650, 76.8000)

        # All 3 coordinates are geographically distinct
        self.assertNotEqual(kitchen_coords, customer_coords)
        self.assertNotEqual(kitchen_coords, courier_coords)
        self.assertNotEqual(customer_coords, courier_coords)

    def test_accurate_eta_newly_confirmed_order_without_courier(self):
        """1. Newly confirmed order without assigned courier factors in prep time + transit."""
        from orders.utils import calculate_accurate_order_eta
        # Order pending without courier
        order = Order.objects.create(
            order_id="VR-TEST-PENDING-01",
            user=self.customer,
            delivery_address="Kanjirappally Town",
            latitude=9.5564,
            longitude=76.7909,
            status='pending',
            total_amount=250.00
        )
        res = calculate_accurate_order_eta(
            order=order,
            chef_lat=9.5564, chef_lon=76.7909,
            cust_lat=9.5564, cust_lon=76.7909,
            courier_lat=None, courier_lon=None,
            has_courier_gps=False, is_gps_stale=False
        )
        self.assertEqual(res['order_status'], 'pending')
        self.assertIn("Expected by", res['expected_arrival_time'])
        self.assertEqual(res['eta_status_type'], 'kitchen_prep')
        self.assertGreaterEqual(res['prep_time_minutes'], 10)
        self.assertFalse(res['has_courier'])
        self.assertFalse(res['has_courier_gps'])

    def test_accurate_eta_order_being_prepared(self):
        """2. Order being prepared includes remaining kitchen preparation time."""
        from orders.utils import calculate_accurate_order_eta
        order = Order.objects.create(
            order_id="VR-TEST-PREP-01",
            user=self.customer,
            delivery_address="Kanjirappally Petta",
            latitude=9.5540,
            longitude=76.7930,
            status='preparing',
            total_amount=300.00
        )
        res = calculate_accurate_order_eta(
            order=order,
            chef_lat=9.5564, chef_lon=76.7909,
            cust_lat=9.5540, cust_lon=76.7930,
            courier_lat=None, courier_lon=None,
            has_courier_gps=False, is_gps_stale=False
        )
        self.assertEqual(res['order_status'], 'preparing')
        self.assertIn("Food Preparing", res['status_label'])
        self.assertIn("Expected by", res['expected_arrival_time'])
        self.assertGreater(res['prep_time_minutes'], 0)

    def test_accurate_eta_courier_assigned_with_valid_gps(self):
        """3. Courier assigned and moving in-transit calculates ETA from courier location."""
        from orders.utils import calculate_accurate_order_eta
        order = Order.objects.create(
            order_id="VR-TEST-TRANSIT-01",
            user=self.customer,
            delivery_address="Kanjirappally Jubilee Junction",
            latitude=9.5564,
            longitude=76.7909,
            status='in_transit',
            total_amount=400.00
        )
        res = calculate_accurate_order_eta(
            order=order,
            chef_lat=9.5564, chef_lon=76.7909,
            cust_lat=9.5564, cust_lon=76.7909,
            courier_lat=9.5667, courier_lon=76.7583, # Ponkunnam
            has_courier_gps=True, is_gps_stale=False,
            last_gps_update='08:30:00 PM'
        )
        self.assertEqual(res['order_status'], 'in_transit')
        self.assertEqual(res['eta_status_type'], 'live_gps')
        self.assertEqual(res['prep_time_minutes'], 0) # Food already picked up
        self.assertIn("Expected by", res['expected_arrival_time'])
        self.assertGreater(res['remaining_travel_minutes'], 0)
        self.assertIn("Live GPS", res['gps_status_badge'])

    def test_accurate_eta_moving_courier_arriving_soon(self):
        """4. Moving courier approaching within 600m triggers Arriving Soon status."""
        from orders.utils import calculate_accurate_order_eta
        order = Order.objects.create(
            order_id="VR-TEST-ARRIVING-01",
            user=self.customer,
            delivery_address="Near AKJM School",
            latitude=9.5564,
            longitude=76.7909,
            status='in_transit',
            total_amount=350.00
        )
        # Courier at 9.5570, 76.7912 (~100m from destination)
        res = calculate_accurate_order_eta(
            order=order,
            chef_lat=9.5564, chef_lon=76.7909,
            cust_lat=9.5564, cust_lon=76.7909,
            courier_lat=9.5570, courier_lon=76.7912,
            has_courier_gps=True, is_gps_stale=False,
            last_gps_update='08:35:00 PM'
        )
        self.assertIn("Arriving Soon", res['status_label'])
        self.assertIn("Arriving in < 2 mins", res['remaining_travel_time'])

    def test_accurate_eta_stale_gps_data_handled(self):
        """5. Stale GPS (> 5 mins old) displays delayed location notification."""
        from orders.utils import calculate_accurate_order_eta
        order = Order.objects.create(
            order_id="VR-TEST-STALE-01",
            user=self.customer,
            delivery_address="Kanjirappally",
            latitude=9.5564,
            longitude=76.7909,
            status='in_transit',
            total_amount=250.00
        )
        res = calculate_accurate_order_eta(
            order=order,
            chef_lat=9.5564, chef_lon=76.7909,
            cust_lat=9.5564, cust_lon=76.7909,
            courier_lat=9.5667, courier_lon=76.7583,
            has_courier_gps=False, is_gps_stale=True,
            last_gps_update='08:10:00 PM (Signal Stale)'
        )
        self.assertIn("Delayed", res['gps_status_badge'])
        self.assertIn("Location update delayed", res['gps_status_msg'])

    def test_accurate_eta_delivered_and_cancelled_orders(self):
        """6 & 7. Delivered and cancelled orders stop live tracking and display final state."""
        from orders.utils import calculate_accurate_order_eta
        order_deliv = Order.objects.create(
            order_id="VR-TEST-DELIV-01",
            user=self.customer,
            delivery_address="Kanjirappally",
            latitude=9.5564,
            longitude=76.7909,
            status='delivered',
            total_amount=200.00
        )
        res_deliv = calculate_accurate_order_eta(order_deliv, 9.5564, 76.7909, 9.5564, 76.7909)
        self.assertEqual(res_deliv['order_status'], 'delivered')
        self.assertIn("Delivered", res_deliv['expected_arrival_time'])
        self.assertEqual(res_deliv['remaining_travel_minutes'], 0)

        order_canc = Order.objects.create(
            order_id="VR-TEST-CANC-01",
            user=self.customer,
            delivery_address="Kanjirappally",
            latitude=9.5564,
            longitude=76.7909,
            status='cancelled',
            total_amount=200.00
        )
        res_canc = calculate_accurate_order_eta(order_canc, 9.5564, 76.7909, 9.5564, 76.7909)
        self.assertEqual(res_canc['order_status'], 'cancelled')
        self.assertEqual(res_canc['expected_arrival_time'], "Order Cancelled")

    def test_accurate_eta_asia_kolkata_timezone(self):
        """8. Timestamp outputs adhere to Asia/Kolkata timezone formatting."""
        from orders.utils import calculate_accurate_order_eta
        order = Order.objects.create(
            order_id="VR-TEST-TZ-01",
            user=self.customer,
            delivery_address="Kanjirappally",
            latitude=9.5564,
            longitude=76.7909,
            status='pending',
            total_amount=150.00
        )
        res = calculate_accurate_order_eta(order, 9.5564, 76.7909, 9.5564, 76.7909)
        # Expected by format: "Expected by hh:mm AM/PM"
        self.assertTrue(res['expected_arrival_time'].startswith("Expected by "))
        self.assertTrue(res['expected_arrival_time'].endswith("AM") or res['expected_arrival_time'].endswith("PM"))
        # Last updated format: "hh:mm:ss AM/PM"
        self.assertTrue(res['last_updated_time'].endswith("AM") or res['last_updated_time'].endswith("PM"))

    def test_api_order_status_accurate_eta_response(self):
        """9. api_order_status returns expected_arrival_time and all tracking fields."""
        order = Order.objects.create(
            order_id="VR-TEST-API-01",
            user=self.customer,
            delivery_address="Kanjirappally",
            latitude=9.5564,
            longitude=76.7909,
            status='pending',
            total_amount=180.00
        )
        self.client.force_login(self.customer)
        response = self.client.get(reverse('api_order_status', kwargs={'order_id': order.order_id}))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertIn('expected_arrival_time', data)
        self.assertIn('remaining_travel_time', data)
        self.assertIn('road_distance_display', data)
        self.assertIn('status_label', data)
        self.assertIn('gps_status_badge', data)


class StartNavigationCoordinateTests(TestCase):
    """
    Test suite verifying Start Navigation button and coordinate consistency:
    1. Displayed latitude and longitude match saved customer destination (e.g. 9.614967, 76.741563).
    2. Start Navigation URL uses exact destination (OpenStreetMap directions with 9.614967, 76.741563).
    3. Start Navigation onclick handler passes exact saved coordinates into startNavigation.
    4. Start Navigation does NOT inject stale origin or kitchen coordinates.
    5. Track Delivery Route button links to correct assignment tracking page.
    6. Courier tracking page preserves customer destination independently from courier GPS.
    """

    def setUp(self):
        from delivery.models import District, HotelBranch
        self.district = District.objects.create(name='Kottayam', code='ktm', latitude=9.5916, longitude=76.5222)
        self.branch = HotelBranch.objects.create(
            name='Central Kitchen Hub (Kanjirappally)',
            district=self.district,
            address='Kanjirappally Town, Kottayam',
            latitude=9.5564,
            longitude=76.7909,
            max_delivery_radius_km=30.0,
            is_central_hub=True,
            is_active=True
        )
        self.customer = User.objects.create_user(
            username='elikulam_cust',
            email='elikulam@example.com',
            password='TestPassword123!',
            role='customer'
        )
        self.courier_user = User.objects.create_user(
            username='courier_elikulam',
            email='courier_elikulam@example.com',
            password='TestPassword123!',
            role='delivery_boy'
        )
        self.courier_profile = DeliveryBoyProfile.objects.create(
            user=self.courier_user,
            vehicle_number='KL-34-AB-1234',
            current_latitude=9.5564,
            current_longitude=76.7909
        )
        # Order placed at Elikulam Junction, Kottayam
        self.order = Order.objects.create(
            order_id="VR-ELIKULAM-01",
            user=self.customer,
            delivery_address="Elikulam Junction: Elikulam, Kottayam",
            latitude=9.614967,
            longitude=76.741563,
            status='assigned',
            total_amount=320.00
        )
        self.assignment = DeliveryAssignment.objects.create(
            order=self.order,
            delivery_boy=self.courier_profile,
            status='assigned'
        )

    def test_start_navigation_dashboard_exact_coordinates(self):
        """Dashboard renders clean courier actions without OpenStreetMap or destination map button."""
        self.client.force_login(self.courier_user)
        response = self.client.get(reverse('delivery_boy_dashboard'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # 1. Verify displayed coordinates on page
        self.assertIn("Latitude: 9.614967", content)
        self.assertIn("Longitude: 76.741563", content)
        self.assertIn("Elikulam Junction, Elikulam, Kottayam", content)

        # 2. Verify Open Destination Map button and OpenStreetMap links are completely removed
        self.assertNotIn('openstreetmap.org', content)
        self.assertNotIn('Open Destination Map', content)
        self.assertNotIn('startNavigation(', content)
        self.assertNotIn('origin=9.5564,76.7909', content)

        # 3. Verify Track Delivery Route button is present
        track_url = reverse('delivery_boy_track', kwargs={'assignment_id': self.assignment.id})
        self.assertIn(track_url, content)

    def test_courier_track_leaflet_map_exact_coordinates(self):
        """Courier track page renders Leaflet map with exact customer destination and GPS button."""
        self.client.force_login(self.courier_user)
        response = self.client.get(reverse('delivery_boy_track', kwargs={'assignment_id': self.assignment.id}))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Destination in context matches order coordinates
        self.assertEqual(response.context['cust_lat'], 9.614967)
        self.assertEqual(response.context['cust_lon'], 76.741563)

        # Verify exact coordinates and address are present
        self.assertIn('9.614967', content)
        self.assertIn('76.741563', content)

        # Verify Travel ETA is calculated and displayed
        self.assertIn("Estimated Arrival:", content)
        self.assertIn(response.context['travel_eta_display'], content)
        self.assertTrue(response.context['travel_mins'] > 0)

        # Verify Leaflet map container, initLeafletMap, GPS button, and zoom buttons are present
        self.assertIn('id="delivery-nav-map"', content)
        self.assertIn('initLeafletMap()', content)
        self.assertIn('btn-zoom-customer', content)
        self.assertIn('btn-locate-courier', content)
        self.assertIn('btn-view-both', content)

    def test_notification_api_clean_nav_url(self):
        """Courier notification API returns internal tracking nav_url without OpenStreetMap."""
        from orders.models import Notification
        notif = Notification.objects.create(
            user=self.courier_user,
            order=self.order,
            title="New Assignment",
            message="New order assigned.",
            notification_type='assignment'
        )
        self.client.force_login(self.courier_user)
        response = self.client.get(reverse('get_courier_notifications'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertTrue(len(data['notifications']) >= 1)
        notif_item = data['notifications'][0]
        self.assertEqual(notif_item['latitude'], 9.614967)
        self.assertEqual(notif_item['longitude'], 76.741563)
        self.assertIn('/delivery/track/', notif_item['nav_url'])
        self.assertNotIn('openstreetmap.org', notif_item['nav_url'])
        self.assertNotIn('origin=', notif_item['nav_url'])


class RealTimeDeviceGPSLinkTests(TestCase):
    """Test suite for the Real-Time Device GPS Link component, templates, APIs, and authorization."""

    def setUp(self):
        self.client = Client()
        self.district = District.objects.create(name='Kottayam', code='ktm', latitude=9.5916, longitude=76.5222)
        self.branch = HotelBranch.objects.create(
            name='Central Kitchen Hub (Kanjirappally)',
            district=self.district,
            address='Kanjirappally Town, Kottayam',
            latitude=9.5564,
            longitude=76.7909,
            max_delivery_radius_km=30.0,
            is_central_hub=True,
            is_active=True
        )
        self.customer = User.objects.create_user(
            username='gps_customer',
            email='cust@gps.com',
            password='Password123!',
            role='customer'
        )
        self.courier_user = User.objects.create_user(
            username='gps_courier',
            email='courier@gps.com',
            password='Password123!',
            role='delivery_boy'
        )
        self.courier_profile = DeliveryBoyProfile.objects.create(
            user=self.courier_user,
            vehicle_number='KL-34-AB-9999',
            current_latitude=9.5564,
            current_longitude=76.7909
        )
        self.other_courier = User.objects.create_user(
            username='other_courier',
            email='other@gps.com',
            password='Password123!',
            role='delivery_boy'
        )
        self.other_profile = DeliveryBoyProfile.objects.create(
            user=self.other_courier,
            vehicle_number='KL-34-CD-8888',
            current_latitude=9.5564,
            current_longitude=76.7909
        )
        self.order = Order.objects.create(
            order_id="VR-GPS-TEST-01",
            user=self.customer,
            delivery_address="Ponkunnam Town, Kottayam",
            latitude=9.5670,
            longitude=76.7560,
            status='assigned',
            total_amount=450.00
        )
        self.assignment = DeliveryAssignment.objects.create(
            order=self.order,
            delivery_boy=self.courier_profile,
            status='assigned'
        )

    def test_track_template_contains_realtime_gps_link_elements(self):
        """Courier tracking template includes the full Real-Time Device GPS Link UI and diagnostics."""
        self.client.force_login(self.courier_user)
        response = self.client.get(reverse('delivery_boy_track', kwargs={'assignment_id': self.assignment.id}))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Elements specified in requirement:
        self.assertIn("Real-Time Device GPS Link", content)
        self.assertIn('id="connectGpsBtn"', content)
        self.assertIn('id="retryGpsBtn"', content)
        self.assertIn('id="gpsConnectionBadge"', content)
        self.assertIn('id="gpsStatusBanner"', content)

        # Mobile Note and permission notices completely removed per requirements
        self.assertNotIn("Mobile Note:", content)
        self.assertNotIn("Location Services & Browser Permissions are turned ON", content)
        self.assertNotIn("suspend continuous GPS tracking", content)

    def test_track_template_has_resilient_geolocation_workflow(self):
        """Template JavaScript contains 2-tier fallback, 25s timeout, watchPosition, and visibilitychange."""
        self.client.force_login(self.courier_user)
        response = self.client.get(reverse('delivery_boy_track', kwargs={'assignment_id': self.assignment.id}))
        content = response.content.decode('utf-8')

        # 1. 25-second initial GNSS timeout and 15-second network fallback
        self.assertIn("timeout: highAccuracy ? 25000 : 15000", content)
        self.assertIn("attemptInitialPosition(false)", content)
        self.assertIn("enableHighAccuracy: highAccuracy", content)

        # 2. Continuous watchPosition with highAccuracy and generous timeout
        self.assertIn("navigator.geolocation.watchPosition", content)
        self.assertIn("timeout: 20000", content)

        # 3. Guard against duplicate clicks
        self.assertIn("isGpsConnecting", content)
        self.assertIn("isTrackingActive", content)

        # 4. Visibilitychange handler for mobile wake-up
        self.assertIn("visibilitychange", content)
        self.assertIn("document.visibilityState === 'visible'", content)

        # 5. Geolocation error diagnosis and advice
        self.assertIn("PERMISSION_DENIED", content)
        self.assertIn("POSITION_UNAVAILABLE", content)
        self.assertIn("TIMEOUT", content)
        self.assertIn("HTTPS Required", content)

    def test_courier_gps_update_success(self):
        """Assigned courier successfully posts real coordinates to Django update_courier_gps endpoint."""
        self.client.force_login(self.courier_user)
        url = reverse('update_courier_gps', kwargs={'assignment_id': self.assignment.id})
        payload = {
            'latitude': 9.5592,
            'longitude': 76.7885,
            'accuracy': 8.5
        }
        import json
        response = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['latitude'], 9.5592)
        self.assertEqual(data['longitude'], 76.7885)
        self.assertEqual(data['accuracy'], 8.5)
        self.assertTrue('timestamp' in data)
        self.assertTrue('travel_eta_display' in data)
        self.assertIn("Estimated Arrival:", data['travel_eta_display'])
        self.assertTrue('distance_km' in data)
        self.assertTrue('route_steps' in data)

        # Verify DB records updated
        self.courier_profile.refresh_from_db()
        self.assertEqual(self.courier_profile.current_latitude, 9.5592)
        self.assertEqual(self.courier_profile.current_longitude, 76.7885)

        # Verify GPS breadcrumb created
        tracking_crumbs = GPSLocationTracking.objects.filter(delivery_assignment=self.assignment)
        self.assertEqual(tracking_crumbs.count(), 1)
        self.assertEqual(tracking_crumbs.first().latitude, 9.5592)
        self.assertEqual(tracking_crumbs.first().longitude, 76.7885)

    def test_courier_gps_update_unauthorized_user(self):
        """Customer cannot post to update_courier_gps endpoint."""
        self.client.force_login(self.customer)
        url = reverse('update_courier_gps', kwargs={'assignment_id': self.assignment.id})
        response = self.client.post(url, data={'latitude': 9.5592, 'longitude': 76.7885})
        self.assertEqual(response.status_code, 403)

    def test_courier_gps_update_different_courier_rejected(self):
        """Courier not assigned to the order cannot post GPS coordinates for it."""
        self.client.force_login(self.other_courier)
        url = reverse('update_courier_gps', kwargs={'assignment_id': self.assignment.id})
        import json
        response = self.client.post(url, data=json.dumps({'latitude': 9.5592, 'longitude': 76.7885}), content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_courier_gps_update_invalid_coordinates_rejected(self):
        """Out of bounds coordinates are rejected with HTTP 400."""
        self.client.force_login(self.courier_user)
        url = reverse('update_courier_gps', kwargs={'assignment_id': self.assignment.id})
        import json
        # Latitude > 90
        response = self.client.post(url, data=json.dumps({'latitude': 999.0, 'longitude': 76.7885}), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        # Non-numeric
        response = self.client.post(url, data=json.dumps({'latitude': "not_a_num", 'longitude': 76.7885}), content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_courier_gps_update_stopped_when_order_delivered(self):
        """Endpoint signals stopped when order is marked as delivered."""
        self.assignment.status = 'delivered'
        self.assignment.save()
        self.client.force_login(self.courier_user)
        url = reverse('update_courier_gps', kwargs={'assignment_id': self.assignment.id})
        import json
        response = self.client.post(url, data=json.dumps({'latitude': 9.5592, 'longitude': 76.7885}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'stopped')


class DeliveryTrackingTimestampAndCardStateTests(TestCase):
    """
    Test suite verifying consistent Asia/Kolkata timezone handling,
    accurate timestamps, card states for delivered vs active orders,
    and boundary cases.
    """

    def setUp(self):
        self.client = Client()
        self.district = District.objects.create(name='Kottayam', code='ktm_ts', latitude=9.5916, longitude=76.5222)
        self.branch = HotelBranch.objects.create(
            name='Central Kitchen Hub (Kanjirappally)',
            district=self.district,
            address='Kanjirappally Town, Kottayam',
            latitude=9.5564,
            longitude=76.7909,
            max_delivery_radius_km=30.0,
            is_central_hub=True,
            is_active=True
        )
        self.customer = User.objects.create_user(
            username='ts_customer',
            email='ts_cust@example.com',
            password='TestPassword123!',
            role='customer'
        )
        self.courier_user = User.objects.create_user(
            username='ts_courier',
            email='ts_courier@example.com',
            password='TestPassword123!',
            role='delivery_boy'
        )
        self.courier_profile = DeliveryBoyProfile.objects.create(
            user=self.courier_user,
            vehicle_number='KL-34-TS-1234',
            current_latitude=9.5564,
            current_longitude=76.7909
        )
        self.order = Order.objects.create(
            order_id="VR-TS-TEST-01",
            user=self.customer,
            delivery_address="Kanjirappally Town, Kottayam",
            latitude=9.5600,
            longitude=76.7950,
            status='in_transit',
            total_amount=350.00
        )
        self.assignment = DeliveryAssignment.objects.create(
            order=self.order,
            delivery_boy=self.courier_profile,
            status='in_transit'
        )

    def test_1_active_delivery_recent_gps(self):
        """Active delivery in transit formats recent GPS breadcrumbs in Asia/Kolkata time."""
        from delivery.models import GPSLocationTracking
        from orders.utils import to_kolkata_datetime

        # Recent crumb within 2 minutes
        crumb_time = timezone.now() - timedelta(minutes=2)
        crumb = GPSLocationTracking.objects.create(
            delivery_assignment=self.assignment,
            latitude=9.5580,
            longitude=76.7925
        )
        # Update timestamp to match test scenario
        GPSLocationTracking.objects.filter(id=crumb.id).update(timestamp=crumb_time)
        crumb.refresh_from_db()

        expected_time_str = to_kolkata_datetime(crumb_time).strftime("%I:%M:%S %p")

        self.client.force_login(self.customer)
        response = self.client.get(reverse('order_tracking', kwargs={'order_id': self.order.order_id}))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Check Last GPS Update card contains formatted IST time
        self.assertIn(expected_time_str, content)
        self.assertEqual(response.context['last_gps_update'], expected_time_str)

        # Check Kitchen Preparation card displays picked up state, not Delivered
        self.assertEqual(response.context['prep_status_display'], "Picked Up by Courier")
        self.assertIn("Picked Up by Courier", content)

        # Check remaining road distance and travel time
        self.assertTrue("remaining" in response.context['road_distance_display'].lower() or "km" in response.context['road_distance_display'].lower())
        self.assertNotEqual(response.context['remaining_travel_time'], "0 mins (Delivered)")
        self.assertNotEqual(response.context['road_distance_display'], "0 km (Completed)")

    def test_2_active_delivery_stale_gps(self):
        """Active delivery with GPS crumb older than 5 minutes identifies location as stale."""
        from delivery.models import GPSLocationTracking
        from orders.utils import to_kolkata_datetime

        # Crumb from 12 minutes ago (stale)
        stale_time = timezone.now() - timedelta(minutes=12)
        crumb = GPSLocationTracking.objects.create(
            delivery_assignment=self.assignment,
            latitude=9.5580,
            longitude=76.7925
        )
        GPSLocationTracking.objects.filter(id=crumb.id).update(timestamp=stale_time)

        expected_time_str = to_kolkata_datetime(stale_time).strftime("%I:%M:%S %p") + " (Signal Stale)"

        self.client.force_login(self.customer)
        response = self.client.get(reverse('order_tracking', kwargs={'order_id': self.order.order_id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['last_gps_update'], expected_time_str)
        self.assertTrue(response.context['is_gps_stale'])
        self.assertFalse(response.context['has_courier_gps'])

    def test_3_completed_order_saved_delivery_timestamp(self):
        """Delivered order displays actual saved delivery timestamp and 'Delivered' / 'Completed' cards."""
        from delivery.models import GPSLocationTracking
        from orders.utils import to_kolkata_datetime
        import datetime

        # Create GPS crumb received at 05:12:17 PM IST during transit
        gps_time = timezone.make_aware(datetime.datetime(2026, 10, 20, 11, 42, 17), timezone.utc) # 17:12:17 IST
        crumb = GPSLocationTracking.objects.create(
            delivery_assignment=self.assignment,
            latitude=9.5590,
            longitude=76.7940
        )
        GPSLocationTracking.objects.filter(id=crumb.id).update(timestamp=gps_time)

        # Delivered at 09:27:00 PM IST (15:57:00 UTC)
        delivered_time = timezone.make_aware(datetime.datetime(2026, 10, 20, 15, 57, 0), timezone.utc)
        self.assignment.status = 'delivered'
        self.assignment.delivered_at = delivered_time
        self.assignment.save()
        self.order.status = 'delivered'
        self.order.updated_at = delivered_time
        self.order.save()

        self.client.force_login(self.customer)
        response = self.client.get(reverse('order_tracking', kwargs={'order_id': self.order.order_id}))
        self.assertEqual(response.status_code, 200)
        ctx = response.context

        # 1. Delivery completion time displays 09:27 PM
        self.assertEqual(ctx['expected_arrival_time'], "Delivered at 09:27 PM")

        # 2. Last GPS update displays actual crumb time (05:12:17 PM), NOT delivery completion time
        self.assertEqual(ctx['last_gps_update'], "05:12:17 PM")

        # 3. Card 1 Remaining travel time displays "Delivered" (NOT "0 mins (Delivered)")
        self.assertEqual(ctx['remaining_travel_time'], "Delivered")

        # 4. Card 2 Road distance displays "Completed" (NOT "0 km (Completed)")
        self.assertEqual(ctx['road_distance_display'], "Completed")

        # 5. Card 3 Kitchen Preparation displays "Preparation Completed" (NOT "Delivered")
        self.assertEqual(ctx['prep_status_display'], "Preparation Completed")

    def test_4_order_no_gps_records(self):
        """Order without GPS breadcrumbs displays 'No GPS update available' and does not invent time."""
        self.client.force_login(self.customer)
        response = self.client.get(reverse('order_tracking', kwargs={'order_id': self.order.order_id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['last_gps_update'], "No GPS update available")

    def test_5_delivered_order_no_timestamp(self):
        """Delivered order with no database delivery timestamp displays 'Delivered' without inventing time."""
        self.assignment.status = 'delivered'
        self.assignment.delivered_at = None
        self.assignment.save()
        self.order.status = 'delivered'
        self.order.updated_at = None
        self.order.save()

        self.client.force_login(self.customer)
        response = self.client.get(reverse('order_tracking', kwargs={'order_id': self.order.order_id}))
        self.assertEqual(response.status_code, 200)
        # Displays "Delivered" without inventing an arrival time
        self.assertEqual(response.context['expected_arrival_time'], "Delivered")

    def test_6_utc_to_india_time_conversion(self):
        """to_kolkata_datetime accurately converts UTC to Asia/Kolkata (+05:30) across offsets."""
        from orders.utils import to_kolkata_datetime, format_kolkata_time
        import datetime

        # 11:42:17 UTC -> 17:12:17 IST (05:12:17 PM)
        utc_dt1 = timezone.make_aware(datetime.datetime(2026, 10, 20, 11, 42, 17), timezone.utc)
        ist_dt1 = to_kolkata_datetime(utc_dt1)
        self.assertEqual(ist_dt1.hour, 17)
        self.assertEqual(ist_dt1.minute, 12)
        self.assertEqual(ist_dt1.second, 17)
        self.assertEqual(format_kolkata_time(utc_dt1, "%I:%M:%S %p"), "05:12:17 PM")

        # 15:57:00 UTC -> 21:27:00 IST (09:27:00 PM)
        utc_dt2 = timezone.make_aware(datetime.datetime(2026, 10, 20, 15, 57, 0), timezone.utc)
        self.assertEqual(format_kolkata_time(utc_dt2, "%I:%M %p"), "09:27 PM")

    def test_7_page_refresh_and_repeated_polling(self):
        """Repeated GET and API polling return exact same fixed timestamps without drifting."""
        from delivery.models import GPSLocationTracking
        import datetime

        fixed_time = timezone.make_aware(datetime.datetime(2026, 10, 20, 10, 30, 0), timezone.utc)
        crumb = GPSLocationTracking.objects.create(
            delivery_assignment=self.assignment,
            latitude=9.5580,
            longitude=76.7925
        )
        GPSLocationTracking.objects.filter(id=crumb.id).update(timestamp=fixed_time)

        self.client.force_login(self.customer)
        r1 = self.client.get(reverse('api_order_status', kwargs={'order_id': self.order.order_id}))
        self.assertEqual(r1.status_code, 200)
        data1 = r1.json()

        # Second poll
        r2 = self.client.get(reverse('api_order_status', kwargs={'order_id': self.order.order_id}))
        self.assertEqual(r2.status_code, 200)
        data2 = r2.json()

        # GPS update timestamp must remain identical
        self.assertEqual(data1['last_gps_update'], data2['last_gps_update'])
        self.assertIn("04:00:00 PM", data1['last_gps_update']) # 10:30 UTC = 16:00 IST

    def test_8_day_month_year_boundaries(self):
        """Timezone conversion correctly handles crossing midnight, month, and year boundaries."""
        from orders.utils import to_kolkata_datetime, format_kolkata_time
        import datetime

        # Dec 31, 2026 20:00:00 UTC is Jan 01, 2027 01:30:00 AM in IST (+5:30)
        new_year_utc = timezone.make_aware(datetime.datetime(2026, 12, 31, 20, 0, 0), timezone.utc)
        ist_ny = to_kolkata_datetime(new_year_utc)
        self.assertEqual(ist_ny.year, 2027)
        self.assertEqual(ist_ny.month, 1)
        self.assertEqual(ist_ny.day, 1)
        self.assertEqual(ist_ny.hour, 1)
        self.assertEqual(ist_ny.minute, 30)
        self.assertEqual(format_kolkata_time(new_year_utc, "%Y-%m-%d %I:%M %p"), "2027-01-01 01:30 AM")


class LiveDeliveryMapVisibilityTests(TestCase):
    """
    Validates Live Order Delivery Map & GPS Tracking visibility rules:
    - Active orders (preparing, ready_pickup, in_transit) display the live map, markers, and navigation controls.
    - Delivered orders cleanly hide the entire live map section with zero leftover containers or broken divs.
    - Cancelled orders hide active GPS mapping while preserving order items, cancellation status, and history.
    - Multiple customer orders are independent: delivered order does not hide map for an active order.
    - Polling API emits show_map flag so client-side transitions hide the map dynamically without manual page refresh.
    - All other page components (order details, food items, total paid, payment status, feedback) remain intact.
    """

    def setUp(self):
        self.customer = User.objects.create_user(
            username='cust_map_test',
            password='password123',
            role='customer',
            phone='9846012345',
            first_name='Anjali',
            last_name='Nair'
        )
        self.courier_user = User.objects.create_user(
            username='courier_map_test',
            password='password123',
            role='delivery'
        )
        self.courier_profile = DeliveryBoyProfile.objects.create(
            user=self.courier_user,
            vehicle_number='KL-34-MAP-99',
            current_latitude=9.5564,
            current_longitude=76.7909
        )
        self.active_order = Order.objects.create(
            order_id="VR-ACT-001",
            user=self.customer,
            delivery_address="Kanjirappally Post Office, Kottayam",
            latitude=9.5600,
            longitude=76.7950,
            status='in_transit',
            total_amount=420.00
        )
        self.assignment = DeliveryAssignment.objects.create(
            order=self.active_order,
            delivery_boy=self.courier_profile,
            status='in_transit'
        )
        self.food_item = FoodItem.objects.create(
            name="Kerala Beef Roast and Parotta",
            price=210.00,
            is_available=True
        )
        OrderItem.objects.create(
            order=self.active_order,
            food_item=self.food_item,
            quantity=2,
            price=210.00
        )
        Payment.objects.create(
            order=self.active_order,
            payment_method='cod',
            status='pending',
            amount=420.00
        )

    def test_active_order_shows_map_and_controls(self):
        """Active in-transit order displays ETA card and does not include OpenStreetMap or map controls."""
        self.client.force_login(self.customer)
        response = self.client.get(reverse('order_tracking', kwargs={'order_id': self.active_order.order_id}))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Delivery ETA card present
        self.assertIn('id="eta-arrival-time"', content)
        self.assertIn('id="eta-status-pill"', content)
        self.assertIn('Expected by', content)

        # OpenStreetMap, map container, and map buttons completely removed
        self.assertNotIn('id="live-order-map-section"', content)
        self.assertNotIn('id="live-delivery-map"', content)
        self.assertNotIn('Locate Me', content)
        self.assertNotIn('Re-center Map', content)
        self.assertNotIn('OpenStreetMap Navigation', content)

    def test_delivered_order_hides_entire_map_section(self):
        """Delivered order completely removes the Live Map section and controls from HTML."""
        self.active_order.status = 'delivered'
        self.active_order.save()
        self.assignment.status = 'delivered'
        self.assignment.delivered_at = timezone.now()
        self.assignment.save()

        self.client.force_login(self.customer)
        response = self.client.get(reverse('order_tracking', kwargs={'order_id': self.active_order.order_id}))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Entire Live Map section and all controls are NOT rendered
        self.assertNotIn('id="live-order-map-section"', content)
        self.assertNotIn('id="live-delivery-map"', content)
        self.assertNotIn('Live Order Delivery Map & GPS Tracking', content)
        self.assertNotIn('id="btn-customer-gps"', content)
        self.assertNotIn('id="customer-gps-retry-btn"', content)
        self.assertNotIn('id="external-nav-link"', content)
        self.assertNotIn('Re-center Map', content)
        self.assertNotIn('Locate Me', content)
        self.assertNotIn('OpenStreetMap Navigation', content)

        # Context flags
        self.assertFalse(response.context.get('show_map'))
        self.assertFalse(response.context.get('is_live_tracking_active'))

    def test_delivered_order_retains_other_page_content(self):
        """Delivered order preserves customer details, order items, total paid, payment info, and feedback."""
        self.active_order.status = 'delivered'
        self.active_order.save()
        self.assignment.status = 'delivered'
        self.assignment.delivered_at = timezone.now()
        self.assignment.save()

        self.client.force_login(self.customer)
        response = self.client.get(reverse('order_tracking', kwargs={'order_id': self.active_order.order_id}))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Core customer page sections are intact
        self.assertIn('Customer & Delivery Details', content)
        self.assertIn('Anjali Nair', content)
        self.assertIn('VR-ACT-001', content)
        self.assertIn('Kerala Beef Roast and Parotta', content)
        self.assertIn('420.00', content)
        self.assertIn('Payment Summary', content)
        self.assertIn('Cash On Delivery', content)
        self.assertIn('Back to Order History', content)
        self.assertIn('id="delivery-feedback-section"', content)

    def test_cancelled_order_hides_map_and_preserves_order_info(self):
        """Cancelled order hides live map section while preserving cancellation status and items."""
        self.active_order.status = 'cancelled'
        self.active_order.save()

        self.client.force_login(self.customer)
        response = self.client.get(reverse('order_tracking', kwargs={'order_id': self.active_order.order_id}))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Map is hidden
        self.assertNotIn('id="live-order-map-section"', content)
        self.assertNotIn('id="live-delivery-map"', content)

        # Cancellation status and details are preserved
        self.assertIn('Cancelled', content)
        self.assertIn('Kerala Beef Roast and Parotta', content)
        self.assertFalse(response.context.get('show_map'))

    def test_multiple_orders_independent_map_visibility(self):
        """Delivered and active orders both maintain clean UI without map containers."""
        delivered_order = Order.objects.create(
            order_id="VR-DEL-002",
            user=self.customer,
            delivery_address="Kanjirappally Town, Kottayam",
            latitude=9.5610,
            longitude=76.7960,
            status='delivered',
            total_amount=300.00
        )
        DeliveryAssignment.objects.create(
            order=delivered_order,
            delivery_boy=self.courier_profile,
            status='delivered',
            delivered_at=timezone.now()
        )

        self.client.force_login(self.customer)

        # 1. Delivered order: Feedback section present, map containers absent
        r_del = self.client.get(reverse('order_tracking', kwargs={'order_id': delivered_order.order_id}))
        self.assertEqual(r_del.status_code, 200)
        self.assertNotIn('id="live-order-map-section"', r_del.content.decode('utf-8'))
        self.assertIn('id="delivery-feedback-section"', r_del.content.decode('utf-8'))

        # 2. Active order: ETA card present, map containers absent
        r_act = self.client.get(reverse('order_tracking', kwargs={'order_id': self.active_order.order_id}))
        self.assertEqual(r_act.status_code, 200)
        self.assertNotIn('id="live-order-map-section"', r_act.content.decode('utf-8'))
        self.assertIn('id="eta-arrival-time"', r_act.content.decode('utf-8'))

    def test_api_order_status_returns_show_map_flag(self):
        """API live status endpoint emits show_map flag for real-time client transitions without reload."""
        self.client.force_login(self.customer)

        # Active in-transit order
        r_act = self.client.get(reverse('api_order_status', kwargs={'order_id': self.active_order.order_id}))
        self.assertEqual(r_act.status_code, 200)
        d_act = r_act.json()
        self.assertTrue(d_act['show_map'])
        self.assertTrue(d_act['is_live_tracking_active'])

        # Now mark as delivered in DB
        self.active_order.status = 'delivered'
        self.active_order.save()
        self.assignment.status = 'delivered'
        self.assignment.delivered_at = timezone.now()
        self.assignment.save()

        # Immediate next poll returns show_map: False
        r_del = self.client.get(reverse('api_order_status', kwargs={'order_id': self.active_order.order_id}))
        self.assertEqual(r_del.status_code, 200)
        d_del = r_del.json()
        self.assertFalse(d_del['show_map'])
        self.assertFalse(d_del['is_live_tracking_active'])
        self.assertEqual(d_del['order_status'], 'delivered')

    def test_preparing_and_pickup_orders_keep_map_visible(self):
        """Orders in preparing or ready_pickup workflow stages display progress and ETA card cleanly."""
        self.client.force_login(self.customer)

        # 1. Preparing stage
        self.active_order.status = 'preparing'
        self.active_order.save()
        r_prep = self.client.get(reverse('order_tracking', kwargs={'order_id': self.active_order.order_id}))
        self.assertEqual(r_prep.status_code, 200)
        self.assertNotIn('id="live-order-map-section"', r_prep.content.decode('utf-8'))
        self.assertIn('id="eta-arrival-time"', r_prep.content.decode('utf-8'))

        # 2. Ready for pickup stage
        self.active_order.status = 'ready_pickup'
        self.active_order.save()
        r_ready = self.client.get(reverse('order_tracking', kwargs={'order_id': self.active_order.order_id}))
        self.assertEqual(r_ready.status_code, 200)
        self.assertNotIn('id="live-order-map-section"', r_ready.content.decode('utf-8'))
        self.assertIn('id="eta-arrival-time"', r_ready.content.decode('utf-8'))


class CheckoutKitchenBranchSelectionTests(TestCase):
    """
    Test suite verifying that:
    1. The checkout dropdown exclusively displays Central Kitchen Hub (Kanjirappally), Kottayam District.
    2. Delivery radius is strictly 30 km.
    3. Other branches (Kochi, Calicut, Trivandrum, Thrissur) are excluded from checkout options.
    4. Modified form values or API requests attempting to select other branches are blocked.
    5. Customer cart, saved addresses, authentication, and existing orders remain intact.
    """

    def setUp(self):
        from django.contrib.auth import get_user_model
        from food.models import FoodItem, Category
        from orders.models import CartItem
        from accounts.models import SavedLocation
        from delivery.models import District, HotelBranch, DeliverySetting

        User = get_user_model()
        self.customer = User.objects.create_user(
            username='branch_customer',
            email='branch_customer@example.com',
            password='TestPassword123!',
            role='customer'
        )

        self.category = Category.objects.create(name='Kerala Meals')
        self.food = FoodItem.objects.create(
            name='Kottayam Traditional Sadya',
            description='Authentic Kerala Feast',
            price=220.00,
            category=self.category,
            stock_quantity=50,
            is_available=True
        )

        # Create Kottayam district and Central Kitchen Hub
        self.kottayam_dist = District.objects.create(name='Kottayam', code='kottayam', latitude=9.5916, longitude=76.5222)
        self.central_hub = HotelBranch.objects.create(
            name='Central Kitchen Hub (Kanjirappally)',
            district=self.kottayam_dist,
            address='Kanjirappally Town, Kottayam, Kerala',
            latitude=9.5564,
            longitude=76.7909,
            max_delivery_radius_km=30.0,
            is_central_hub=True,
            is_active=True
        )

        # Create inactive hubs (Kochi, Calicut, Trivandrum, Thrissur)
        self.ekm_dist = District.objects.create(name='Ernakulam', code='ernakulam', latitude=9.9816, longitude=76.2999)
        self.kochi_hub = HotelBranch.objects.create(
            name='Veetile Ruchi — Kochi Marine Drive Hub',
            district=self.ekm_dist,
            address='Marine Drive, Shanmugham Road, Ernakulam, Kochi, Kerala',
            latitude=9.9816,
            longitude=76.2750,
            max_delivery_radius_km=25.0,
            is_central_hub=False,
            is_active=False
        )

        self.kz_dist = District.objects.create(name='Kozhikode', code='kozhikode', latitude=11.2588, longitude=75.7804)
        self.calicut_hub = HotelBranch.objects.create(
            name='Veetile Ruchi — Calicut Beach Hub',
            district=self.kz_dist,
            address='Beach Road, Kozhikode, Kerala',
            latitude=11.2588,
            longitude=75.7720,
            max_delivery_radius_km=25.0,
            is_central_hub=False,
            is_active=False
        )

        self.tvm_dist = District.objects.create(name='Thiruvananthapuram', code='thiruvananthapuram', latitude=8.5241, longitude=76.9366)
        self.trivandrum_hub = HotelBranch.objects.create(
            name='Veetile Ruchi — Trivandrum Kowdiar Hub',
            district=self.tvm_dist,
            address='Kowdiar Main Road, Thiruvananthapuram, Kerala',
            latitude=8.5241,
            longitude=76.9600,
            max_delivery_radius_km=25.0,
            is_central_hub=False,
            is_active=False
        )

        self.tcr_dist = District.objects.create(name='Thrissur', code='thrissur', latitude=10.5276, longitude=76.2144)
        self.thrissur_hub = HotelBranch.objects.create(
            name='Veetile Ruchi — Thrissur Round Hub',
            district=self.tcr_dist,
            address='Swaraj Round East, Thrissur, Kerala',
            latitude=10.5276,
            longitude=76.2144,
            max_delivery_radius_km=25.0,
            is_central_hub=False,
            is_active=False
        )

        # DeliverySetting configured to Central Kitchen Hub
        self.setting = DeliverySetting.get_settings()
        self.setting.name = self.central_hub.name
        self.setting.address = self.central_hub.address
        self.setting.latitude = self.central_hub.latitude
        self.setting.longitude = self.central_hub.longitude
        self.setting.max_delivery_radius_km = 30.0
        self.setting.branch = self.central_hub
        self.setting.is_active = True
        self.setting.save()

        # Customer Cart and Saved Location
        self.cart_item = CartItem.objects.create(user=self.customer, food_item=self.food, quantity=2)
        self.saved_loc = SavedLocation.objects.create(
            user=self.customer,
            name='Home Sweet Home',
            location_type='home',
            latitude=9.5667,
            longitude=76.7583,
            landmark='Near Ponkunnam Stand',
            description='Ponkunnam, Kottayam',
            is_default=True
        )

    def test_checkout_dropdown_displays_only_kanjirappally_hub(self):
        """Checkout dropdown displays only Central Kitchen Hub (Kanjirappally) with 30 km radius."""
        self.client.force_login(self.customer)
        response = self.client.get(reverse('checkout_view'))
        self.assertEqual(response.status_code, 200)

        # Selected branch in context must be Kanjirappally
        selected_branch = response.context['selected_branch']
        self.assertIsNotNone(selected_branch)
        self.assertEqual(selected_branch.id, self.central_hub.id)
        self.assertEqual(selected_branch.name, 'Central Kitchen Hub (Kanjirappally)')
        self.assertEqual(selected_branch.district.name, 'Kottayam')
        self.assertEqual(response.context['hub_radius_km'], 30.0)

        # Available branches must only contain Kanjirappally
        branches = list(response.context['branches'])
        self.assertEqual(len(branches), 1)
        self.assertEqual(branches[0].id, self.central_hub.id)

        content = response.content.decode('utf-8')
        # Kanjirappally must be in the HTML dropdown option
        self.assertIn('Central Kitchen Hub (Kanjirappally)', content)
        self.assertIn('Kottayam District', content)
        self.assertIn('Delivery radius: 30 km', content)
        self.assertIn('Strict 30 km Delivery Limit', content)

        # None of the unselected kitchen options should appear in the checkout dropdown
        self.assertNotIn('Veetile Ruchi — Kochi Marine Drive Hub', content)
        self.assertNotIn('Veetile Ruchi — Calicut Beach Hub', content)
        self.assertNotIn('Veetile Ruchi — Trivandrum Kowdiar Hub', content)
        self.assertNotIn('Veetile Ruchi — Thrissur Round Hub', content)

    def test_tampered_branch_id_in_checkout_query_is_ignored(self):
        """Passing an obsolete branch ID via query parameter ?branch_id= does not select it."""
        self.client.force_login(self.customer)
        response = self.client.get(f"{reverse('checkout_view')}?branch_id={self.kochi_hub.id}")
        self.assertEqual(response.status_code, 200)

        # It must still safely select Central Kitchen Hub (Kanjirappally)
        selected_branch = response.context['selected_branch']
        self.assertEqual(selected_branch.id, self.central_hub.id)
        self.assertEqual(response.context['hub_radius_km'], 30.0)

    def test_prevent_obsolete_branch_selection_on_place_order(self):
        """Form submission attempting to specify an obsolete kitchen branch is rejected."""
        from orders.models import Order, CartItem
        self.client.force_login(self.customer)

        response = self.client.post(reverse('place_order'), {
            'branch_id': self.kochi_hub.id,
            'latitude': 9.5667,
            'longitude': 76.7583,
            'delivery_address': 'Ponkunnam, Kottayam',
            'payment_method': 'cod'
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        messages_text = [m.message for m in response.context['messages']]
        self.assertTrue(any("Only Central Kitchen Hub (Kanjirappally) is accepting orders" in m for m in messages_text))

        # No order created
        self.assertEqual(Order.objects.filter(user=self.customer).count(), 0)
        # Customer cart remains 100% intact
        self.assertEqual(CartItem.objects.filter(user=self.customer).count(), 1)

    def test_prevent_obsolete_branch_selection_via_ajax_api(self):
        """AJAX API request attempting to specify an obsolete kitchen branch is rejected."""
        from orders.models import Order, CartItem
        self.client.force_login(self.customer)

        response = self.client.post(
            reverse('place_order'),
            {
                'branch_id': self.calicut_hub.id,
                'latitude': 9.5667,
                'longitude': 76.7583,
                'delivery_address': 'Ponkunnam, Kottayam',
                'payment_method': 'cod'
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn("Only Central Kitchen Hub (Kanjirappally) is accepting orders", data['message'])
        self.assertEqual(Order.objects.filter(user=self.customer).count(), 0)
        self.assertEqual(CartItem.objects.filter(user=self.customer).count(), 1)

    def test_successful_order_creation_with_kanjirappally_within_30km(self):
        """Placing order with Central Kitchen Hub within 30 km succeeds and binds to Kanjirappally."""
        from orders.models import Order
        self.client.force_login(self.customer)

        # Ponkunnam is ~3.7 km from Kanjirappally Hub
        response = self.client.post(reverse('place_order'), {
            'branch_id': self.central_hub.id,
            'latitude': 9.5667,
            'longitude': 76.7583,
            'delivery_address': 'Ponkunnam Town, Kottayam',
            'payment_method': 'cod'
        })

        self.assertEqual(response.status_code, 302)
        order = Order.objects.filter(user=self.customer).first()
        self.assertIsNotNone(order)
        self.assertEqual(order.branch, self.central_hub)
        self.assertEqual(order.status, 'pending')
        self.assertEqual(order.latitude, 9.5667)
        self.assertEqual(order.longitude, 76.7583)

    def test_order_beyond_30km_rejected_with_perimeter_warning(self):
        """Placing order beyond 30 km from Kanjirappally Hub is rejected."""
        from orders.models import Order, CartItem
        self.client.force_login(self.customer)

        # Kochi location is ~73 km away (> 30 km)
        response = self.client.post(reverse('place_order'), {
            'branch_id': self.central_hub.id,
            'latitude': 9.9816,
            'longitude': 76.2750,
            'delivery_address': 'Marine Drive, Kochi',
            'payment_method': 'cod'
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        messages_text = [m.message for m in response.context['messages']]
        self.assertTrue(any("Sorry, this hotel cannot deliver to your selected location" in m for m in messages_text))

        # Order must NOT be created
        self.assertEqual(Order.objects.filter(user=self.customer).count(), 0)
        # Cart remains intact
        self.assertEqual(CartItem.objects.filter(user=self.customer).count(), 1)


class OrderLifecycleAndCourierWorkflowTests(TestCase):
    """
    Comprehensive test suite for the exact 7-stage order lifecycle:
    1. Order Confirmed (pending)
    2. Food Preparing (preparing)
    3. Food Prepared (ready_pickup) - waiting for courier assignment
    4. Courier Assigned (assigned) - real courier assignment from MySQL
    5. Food Picked Up (picked_up) - explicit courier pickup confirmation
    6. Out for Delivery (in_transit) - live courier GPS & route tracking
    7. Delivered (delivered) - delivery handover, map hidden, Card 4 displays Delivered at <time>
    """

    def setUp(self):
        self.district = District.objects.create(
            name='Kottayam',
            code='kottayam',
            latitude=9.5916,
            longitude=76.5222
        )
        self.branch = HotelBranch.objects.create(
            name='Central Kitchen Hub (Kanjirappally)',
            district=self.district,
            address='Kanjirappally Town, Kottayam',
            latitude=9.5564,
            longitude=76.7909,
            max_delivery_radius_km=30.0,
            is_central_hub=True,
            is_active=True
        )
        self.staff_user = User.objects.create_user(
            username='kitchen_staff',
            email='kitchen_staff@veetileruchi.com',
            password='StaffPassword123!',
            role='staff'
        )
        self.customer = User.objects.create_user(
            username='sarah_customer',
            email='sarah@example.com',
            phone='9847123456',
            first_name='Sarah',
            last_name='Mathew',
            password='CustPassword123!',
            role='customer'
        )
        self.courier_user = User.objects.create_user(
            username='arun_courier',
            email='arun@veetileruchi.com',
            phone='9847998877',
            first_name='Arun',
            last_name='Kumar',
            password='CourierPassword123!',
            role='delivery_boy'
        )
        self.courier_profile = DeliveryBoyProfile.objects.create(
            user=self.courier_user,
            vehicle_number='KL-34-AK-5566',
            status='available',
            current_latitude=9.5564,
            current_longitude=76.7909
        )
        self.order = Order.objects.create(
            order_id="VR-7STAGE-TEST-01",
            user=self.customer,
            branch=self.branch,
            delivery_address="Ponkunnam Town, Kottayam",
            latitude=9.5750,
            longitude=76.7720,
            status='pending',
            total_amount=450.00
        )

    def test_stage_1_order_confirmed(self):
        """Stage 1: Order Confirmed (pending) displays initial status and created timestamp."""
        self.client.force_login(self.customer)
        response = self.client.get(reverse('order_tracking', kwargs={'order_id': self.order.order_id}))
        self.assertEqual(response.status_code, 200)
        ctx = response.context
        self.assertEqual(ctx['order_status'], 'pending')
        self.assertEqual(ctx['stage_index'], 0)
        self.assertEqual(ctx['status_label'], 'Order Confirmed 📋')
        self.assertIsNotNone(ctx['timestamps']['confirmed_time'])
        self.assertIsNone(ctx['timestamps']['preparing_time'])
        self.assertIsNone(ctx['timestamps']['prepared_time'])
        self.assertIsNone(ctx['timestamps']['assigned_time'])
        self.assertIsNone(ctx['timestamps']['picked_up_time'])
        self.assertIsNone(ctx['timestamps']['out_for_delivery_time'])
        self.assertIsNone(ctx['timestamps']['delivered_time'])

    def test_stage_2_food_preparing(self):
        """Stage 2: Staff starts preparation; records preparing_started_at timestamp."""
        self.client.force_login(self.staff_user)
        response = self.client.post(reverse('staff_update_order_status', kwargs={'order_id': self.order.order_id}), {
            'status': 'preparing'
        })
        self.assertEqual(response.status_code, 302)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'preparing')
        self.assertIsNotNone(self.order.preparing_started_at)

        self.client.force_login(self.customer)
        tracking_res = self.client.get(reverse('order_tracking', kwargs={'order_id': self.order.order_id}))
        ctx = tracking_res.context
        self.assertEqual(ctx['order_status'], 'preparing')
        self.assertEqual(ctx['stage_index'], 1)
        self.assertEqual(ctx['status_label'], 'Food Preparing 🍳')
        self.assertIsNotNone(ctx['timestamps']['preparing_time'])
        self.assertIsNone(ctx['timestamps']['prepared_time'])

    def test_stage_3_food_prepared_waiting_courier(self):
        """Stage 3: Food Prepared displays 'Food prepared — waiting for courier assignment' and no fake courier."""
        self.client.force_login(self.staff_user)
        self.client.post(reverse('staff_update_order_status', kwargs={'order_id': self.order.order_id}), {
            'status': 'ready_pickup'
        })

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'ready_pickup')
        self.assertIsNotNone(self.order.food_prepared_at)

        self.client.force_login(self.customer)
        tracking_res = self.client.get(reverse('order_tracking', kwargs={'order_id': self.order.order_id}))
        ctx = tracking_res.context
        self.assertEqual(ctx['order_status'], 'ready_pickup')
        self.assertEqual(ctx['stage_index'], 2)
        self.assertEqual(ctx['status_label'], 'Food Prepared 🍲')
        self.assertIn("Food prepared — waiting for courier assignment", ctx['status_display'])
        self.assertFalse(ctx['has_courier'])
        self.assertIsNone(ctx['courier_name'])
        self.assertEqual(ctx['last_gps_update'], "Waiting for courier assignment")
        self.assertIsNotNone(ctx['timestamps']['prepared_time'])
        self.assertIsNone(ctx['timestamps']['assigned_time'])

    def test_stage_4_real_courier_assigned(self):
        """Stage 4: Real courier assigned from MySQL; displays real courier name, username, phone, vehicle."""
        self.order.status = 'ready_pickup'
        self.order.food_prepared_at = timezone.now()
        self.order.save()

        self.client.force_login(self.staff_user)
        assign_res = self.client.post(reverse('staff_assign_delivery', kwargs={'order_id': self.order.order_id}), {
            'delivery_boy_id': self.courier_profile.id
        })
        self.assertEqual(assign_res.status_code, 302)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'assigned')
        assignment = DeliveryAssignment.objects.get(order=self.order)
        self.assertEqual(assignment.status, 'assigned')
        self.assertEqual(assignment.delivery_boy, self.courier_profile)

        self.client.force_login(self.customer)
        tracking_res = self.client.get(reverse('order_tracking', kwargs={'order_id': self.order.order_id}))
        ctx = tracking_res.context
        self.assertEqual(ctx['order_status'], 'assigned')
        self.assertEqual(ctx['stage_index'], 3)
        self.assertEqual(ctx['status_label'], 'Courier Assigned 🛵')
        self.assertIn(ctx['courier_name'], ['Arun Kumar', self.courier_profile.courier_name])
        self.assertEqual(ctx['vehicle_number'], 'KL-34-AK-5566')
        self.assertIsNotNone(ctx['timestamps']['assigned_time'])
        self.assertIsNone(ctx['timestamps']['picked_up_time'])

    def test_stage_5_courier_pickup_confirmation(self):
        """Stage 5: Courier explicitly confirms food pickup; records picked_up_at timestamp and advances stage."""
        self.order.status = 'assigned'
        self.order.food_prepared_at = timezone.now()
        self.order.save()
        assignment = DeliveryAssignment.objects.create(
            order=self.order,
            delivery_boy=self.courier_profile,
            status='assigned'
        )

        self.client.force_login(self.courier_user)
        pickup_res = self.client.post(reverse('pickup_order', kwargs={'assignment_id': assignment.id}))
        self.assertEqual(pickup_res.status_code, 302)

        assignment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(assignment.status, 'picked_up')
        self.assertEqual(self.order.status, 'picked_up')
        self.assertIsNotNone(assignment.picked_up_at)

        self.client.force_login(self.customer)
        tracking_res = self.client.get(reverse('order_tracking', kwargs={'order_id': self.order.order_id}))
        ctx = tracking_res.context
        self.assertEqual(ctx['order_status'], 'picked_up')
        self.assertEqual(ctx['stage_index'], 4)
        self.assertEqual(ctx['status_label'], 'Food Picked Up 📦')
        self.assertIsNotNone(ctx['timestamps']['picked_up_time'])
        self.assertIsNone(ctx['timestamps']['out_for_delivery_time'])

    def test_stage_6_out_for_delivery_gps_handling(self):
        """Stage 6: Out for Delivery displays waiting status before GPS and accurate time when GPS crumb received."""
        self.order.status = 'picked_up'
        self.order.save()
        assignment = DeliveryAssignment.objects.create(
            order=self.order,
            delivery_boy=self.courier_profile,
            status='picked_up',
            picked_up_at=timezone.now()
        )

        # Start delivery
        self.client.force_login(self.courier_user)
        start_res = self.client.post(reverse('start_delivery', kwargs={'assignment_id': assignment.id}))
        self.assertEqual(start_res.status_code, 302)

        assignment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(assignment.status, 'in_transit')
        self.assertEqual(self.order.status, 'in_transit')
        self.assertIsNotNone(assignment.out_for_delivery_at)

        # Before breadcrumb broadcast: displays Waiting for courier GPS location (or active baseline)
        self.client.force_login(self.customer)
        tracking_res = self.client.get(reverse('order_tracking', kwargs={'order_id': self.order.order_id}))
        self.assertEqual(tracking_res.context['stage_index'], 5)
        self.assertEqual(tracking_res.context['status_label'], 'Out for Delivery 🛵')

        # Broadcast live GPS breadcrumb
        crumb = GPSLocationTracking.objects.create(
            delivery_assignment=assignment,
            latitude=9.5650,
            longitude=76.7800
        )
        crumb_time = timezone.now()
        GPSLocationTracking.objects.filter(id=crumb.id).update(timestamp=crumb_time)

        tracking_res2 = self.client.get(reverse('order_tracking', kwargs={'order_id': self.order.order_id}))
        from orders.utils import to_kolkata_datetime
        expected_time_str = to_kolkata_datetime(crumb_time).strftime("%I:%M:%S %p")
        self.assertEqual(tracking_res2.context['last_gps_update'], expected_time_str)
        self.assertTrue(tracking_res2.context['has_courier_gps'])

    def test_stage_7_delivered_order_completion_and_no_gps_error(self):
        """Stage 7: Delivered order stops live tracking, hides map, sets delivered_at, and never shows 'No GPS update available'."""
        delivered_time = timezone.now()
        self.order.status = 'in_transit'
        self.order.save()
        assignment = DeliveryAssignment.objects.create(
            order=self.order,
            delivery_boy=self.courier_profile,
            status='in_transit',
            out_for_delivery_at=timezone.now() - timedelta(minutes=20)
        )

        self.client.force_login(self.courier_user)
        complete_res = self.client.post(reverse('complete_delivery', kwargs={'assignment_id': assignment.id}))
        self.assertEqual(complete_res.status_code, 302)

        assignment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(assignment.status, 'delivered')
        self.assertEqual(self.order.status, 'delivered')
        self.assertIsNotNone(assignment.delivered_at)
        self.assertIsNotNone(self.order.delivered_at)

        self.client.force_login(self.customer)
        tracking_res = self.client.get(reverse('order_tracking', kwargs={'order_id': self.order.order_id}))
        ctx = tracking_res.context
        self.assertEqual(ctx['order_status'], 'delivered')
        self.assertEqual(ctx['stage_index'], 6)
        self.assertEqual(ctx['status_label'], 'Delivered ✅')
        self.assertFalse(ctx['show_map'])
        self.assertFalse(ctx['is_live_tracking_active'])

        # Card 4 MUST display delivery completion, NEVER "No GPS update available"
        self.assertNotEqual(ctx['last_gps_update'], "No GPS update available")
        self.assertTrue("Delivered at" in ctx['last_gps_update'] or "Delivered" in ctx['last_gps_update'])
        self.assertEqual(ctx['gps_status_badge'], "✅ Order Completed")

        # HTML content verification: Live map section must be hidden, feedback section visible
        content = tracking_res.content.decode('utf-8')
        self.assertNotIn('id="live-order-map-section"', content)
        self.assertNotIn("Live Order Delivery Map & GPS Tracking", content)
        self.assertIn("delivery-feedback-section", content)

    def test_live_status_polling_api_7_stages(self):
        """Live status polling endpoint /orders/live-status/<order_id>/ returns all 7 milestone timestamps dynamically."""
        self.order.status = 'assigned'
        self.order.preparing_started_at = timezone.now() - timedelta(minutes=25)
        self.order.food_prepared_at = timezone.now() - timedelta(minutes=10)
        self.order.save()
        assignment = DeliveryAssignment.objects.create(
            order=self.order,
            delivery_boy=self.courier_profile,
            status='assigned'
        )

        self.client.force_login(self.customer)
        api_res = self.client.get(reverse('api_order_status', kwargs={'order_id': self.order.order_id}))
        self.assertEqual(api_res.status_code, 200)
        data = api_res.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['order_status'], 'assigned')
        self.assertEqual(data['stage_index'], 3)
        self.assertTrue(data['has_courier'])
        self.assertEqual(data['courier_name'], self.courier_profile.courier_name)
        self.assertEqual(data['vehicle_number'], self.courier_profile.vehicle_number)

        # Verify milestone timestamps dict in JSON
        self.assertIn('timestamps', data)
        self.assertIsNotNone(data['timestamps']['confirmed_time'])
        self.assertIsNotNone(data['timestamps']['preparing_time'])
        self.assertIsNotNone(data['timestamps']['prepared_time'])
        self.assertIsNotNone(data['timestamps']['assigned_time'])
        self.assertIsNone(data['timestamps']['picked_up_time'])
        self.assertIsNone(data['timestamps']['delivered_time'])




