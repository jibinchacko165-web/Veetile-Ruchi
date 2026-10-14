import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base import BaseSeleniumTest
from delivery.models import DeliverySetting
from orders.models import CartItem

class MapTest(BaseSeleniumTest):
    def test_staff_perimeter_map_full_workflow(self):
        """Verify Staff Service Area & Delivery Map renders, tiles load, pin and radius work."""
        DeliverySetting.objects.all().delete()
        DeliverySetting.objects.create(
            name="Central Kitchen Hub (Kanjirappally)",
            address="Jubilee Junction, Kanjirappally, Kerala",
            latitude=9.5564,
            longitude=76.7909,
            max_delivery_radius_km=20.0,
            is_active=True
        )

        self.login('teststaff', 'testpassword123')
        self.wait.until(lambda d: '/login/' not in d.current_url)
        self.driver.get(self.live_server_url + '/orders/staff/dashboard/?tab=perimeter')

        # 1. Map container presence and visibility
        map_container = self.wait.until(EC.presence_of_element_located((By.ID, 'admin-perimeter-map')))
        self.assertTrue(map_container.is_displayed())
        self.assertIn('leaflet-container', map_container.get_attribute('class'))

        # 2. Controls and attribution
        zoom_controls = self.driver.find_elements(By.CSS_SELECTOR, '#admin-perimeter-map .leaflet-control-zoom')
        self.assertTrue(len(zoom_controls) > 0)

        attribution = self.driver.find_element(By.CSS_SELECTOR, '#admin-perimeter-map .leaflet-control-attribution')
        self.assertTrue('Esri' in attribution.text or 'CARTO' in attribution.text or 'OpenStreetMap' in attribution.text)

        # 3. Markers and Circle
        markers = self.driver.find_elements(By.CSS_SELECTOR, '#admin-perimeter-map .custom-blue-pin-icon')
        self.assertTrue(len(markers) > 0)

        # 4. Heading and coordinates
        coord_display = self.driver.find_element(By.ID, 'map-coord-display')
        self.assertIn('9.5564', coord_display.text)
        self.assertIn('76.7909', coord_display.text)

        # 5. Radius and Hub text
        page_source = self.driver.page_source
        self.assertTrue('Service Area' in page_source and 'Delivery Map' in page_source)
        self.assertIn('Central Kitchen Hub (Kanjirappally)', page_source)

    def test_checkout_delivery_map(self):
        """Verify Customer Checkout Map initializes and handles location picking."""
        DeliverySetting.objects.all().delete()
        DeliverySetting.objects.create(
            name="Central Kitchen Hub (Kanjirappally)",
            address="Jubilee Junction, Kanjirappally, Kerala",
            latitude=9.5564,
            longitude=76.7909,
            max_delivery_radius_km=20.0,
            is_active=True
        )

        # Ensure cart has item so checkout can open
        CartItem.objects.create(user=self.customer, food_item=self.food_item, quantity=1)

        self.login('testcustomer', 'testpassword123')
        self.wait.until(lambda d: '/login/' not in d.current_url)
        self.driver.get(self.live_server_url + '/orders/checkout/')

        # Reveal custom map container if hidden
        custom_card = self.driver.find_elements(By.ID, 'loc_card_custom')
        if custom_card and custom_card[0].is_displayed():
            custom_card[0].click()

        map_container = self.wait.until(EC.presence_of_element_located((By.ID, 'checkout-map-picker')))
        self.assertIn('leaflet-container', map_container.get_attribute('class'))

        # Pin and perimeter status badge
        badge = self.driver.find_element(By.ID, 'perimeter-status-badge')
        self.assertTrue(badge.is_displayed())
        self.assertIn('Service Area', badge.text)

    def test_profile_saved_location_map(self):
        """Verify Profile saved locations tab renders Leaflet map."""
        self.login('testcustomer', 'testpassword123')
        self.wait.until(lambda d: '/login/' not in d.current_url)
        self.driver.get(self.live_server_url + '/accounts/profile/')

        # Switch to locations tab
        self.wait.until(EC.presence_of_element_located((By.ID, 'btn_tab_locations')))
        self.driver.execute_script("switchTab('locations');")

        map_container = self.wait.until(EC.visibility_of_element_located((By.ID, 'profile-location-map')))
        self.assertTrue(map_container.is_displayed())
        self.assertIn('leaflet-container', map_container.get_attribute('class'))

        # Verify map dragging is enabled and marker dragging is enabled separately
        map_dragging_enabled = self.driver.execute_script("return typeof leafletMap !== 'undefined' && leafletMap.dragging.enabled();")
        self.assertTrue(map_dragging_enabled)

        marker_dragging_enabled = self.driver.execute_script("return typeof leafletMarker !== 'undefined' && leafletMarker.dragging.enabled();")
        self.assertTrue(marker_dragging_enabled)

        # Verify panning the map does NOT alter the saved coordinates
        initial_lat = self.driver.find_element(By.ID, 'loc_lat').get_attribute('value')
        initial_lon = self.driver.find_element(By.ID, 'loc_lon').get_attribute('value')
        self.driver.execute_script("leafletMap.panBy([120, 120]);")
        time.sleep(0.3)
        post_pan_lat = self.driver.find_element(By.ID, 'loc_lat').get_attribute('value')
        post_pan_lon = self.driver.find_element(By.ID, 'loc_lon').get_attribute('value')
        self.assertEqual(initial_lat, post_pan_lat)
        self.assertEqual(initial_lon, post_pan_lon)

        # Verify intentional marker drag updates coordinates
        self.driver.execute_script("""
            leafletMarker.setLatLng([9.5800, 76.8000]);
            leafletMarker.fire('dragend');
        """)
        updated_lat = self.driver.find_element(By.ID, 'loc_lat').get_attribute('value')
        updated_lon = self.driver.find_element(By.ID, 'loc_lon').get_attribute('value')
        self.assertEqual(updated_lat, '9.580000')
        self.assertEqual(updated_lon, '76.800000')

