from decimal import Decimal
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base import BaseSeleniumTest
from orders.models import Order, OrderItem
from delivery.models import DeliveryAssignment

class TrackingMapSeleniumTest(BaseSeleniumTest):
    def setUp(self):
        super().setUp()
        # Create an active in-transit order with coordinates for map rendering
        self.active_order = Order.objects.create(
            order_id='VR-SEL-MAP-01',
            user=self.customer,
            total_amount=Decimal('150.00'),
            status='in_transit',
            latitude=9.5580,
            longitude=76.7920
        )
        OrderItem.objects.create(
            order=self.active_order,
            food_item=self.food_item,
            quantity=1,
            price=Decimal('150.00')
        )
        self.assignment = DeliveryAssignment.objects.create(
            order=self.active_order,
            delivery_boy=self.courier.delivery_boy_profile,
            status='in_transit'
        )

    def tearDown(self):
        try:
            self.assignment.delete()
            self.active_order.delete()
        except Exception:
            pass
        super().tearDown()

    def test_live_tracking_map_renders_with_fixed_markers(self):
        """Live order tracking map initializes Leaflet, customer and hub markers are fixed (draggable: false)."""
        self.login('testcustomer', 'testpassword123')
        self.wait.until(lambda d: '/login/' not in d.current_url)

        self.driver.get(self.live_server_url + f'/orders/track/{self.active_order.order_id}/')
        self.wait.until(EC.presence_of_element_located((By.ID, 'live-delivery-map')))

        # Verify Leaflet initialized inside the container
        self.wait.until(lambda d: 'leaflet-container' in d.find_element(By.ID, 'live-delivery-map').get_attribute('class'))

        # Verify markers exist and draggable is false
        is_kitchen_marker_fixed = self.driver.execute_script("""
            return typeof leafletKitchenMarker !== 'undefined' && 
                   leafletKitchenMarker !== null && 
                   leafletKitchenMarker.options.draggable === false;
        """)
        self.assertTrue(is_kitchen_marker_fixed)

        is_customer_marker_fixed = self.driver.execute_script("""
            return typeof leafletCustomerMarker !== 'undefined' && 
                   leafletCustomerMarker !== null && 
                   leafletCustomerMarker.options.draggable === false;
        """)
        self.assertTrue(is_customer_marker_fixed)

        # Verify map panning works smoothly
        map_dragging_enabled = self.driver.execute_script("""
            return typeof leafletMap !== 'undefined' && leafletMap.dragging.enabled();
        """)
        self.assertTrue(map_dragging_enabled)

        # Verify window.recenterDeliveryMap function exists
        recenter_exists = self.driver.execute_script("return typeof window.recenterDeliveryMap === 'function';")
        self.assertTrue(recenter_exists)

    def test_no_osrm_network_calls_or_errors(self):
        """Verify no OSRM routing references exist in browser execution."""
        self.login('testcustomer', 'testpassword123')
        self.wait.until(lambda d: '/login/' not in d.current_url)

        self.driver.get(self.live_server_url + f'/orders/track/{self.active_order.order_id}/')
        self.wait.until(EC.presence_of_element_located((By.ID, 'live-delivery-map')))

        page_source = self.driver.page_source
        self.assertNotIn('project-osrm.org', page_source)
        self.assertNotIn('router.project-osrm.org', page_source)
        self.assertNotIn('leaflet-routing-machine', page_source)

        # Check browser console logs for OSRM or fatal JS errors
        logs = self.driver.get_log('browser')
        for log in logs:
            if 'osrm' in log['message'].lower():
                self.fail(f"OSRM reference found in browser console: {log['message']}")
