from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
import math

from accounts.models import User, DeliveryBoyProfile
from food.models import Category, MealSession, FoodItem
from orders.models import Order, OrderItem
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
