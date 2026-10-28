import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base import BaseSeleniumTest
from delivery.models import DeliverySetting
from orders.models import CartItem

class MapTest(BaseSeleniumTest):
    def test_staff_perimeter_map_full_workflow(self):
        """Verify Staff Dashboard renders cleanly and no map or Earth interface is present."""
        self.login('teststaff', 'testpassword123')
        self.wait.until(lambda d: '/login/' not in d.current_url)
        self.driver.get(self.live_server_url + '/orders/staff/dashboard/')

        # Verify staff dashboard loads orders successfully
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'scrollable-pill-bar')))
        page_source = self.driver.page_source
        self.assertIn('Customer Orders', page_source)
        # Verify no map containers or Leaflet/MapLibre elements exist on staff dashboard
        map_containers = self.driver.find_elements(By.ID, 'admin-perimeter-map')
        self.assertEqual(len(map_containers), 0)
        self.assertNotIn('leaflet-container', page_source)
        self.assertNotIn('maplibregl-map', page_source)

    def test_checkout_delivery_location(self):
        """Verify Customer Checkout loads delivery address workflow without duplicate mapping libraries."""
        DeliverySetting.objects.all().delete()
        DeliverySetting.objects.create(
            name="Central Kitchen Hub (Kanjirappally)",
            address="Jubilee Junction, Kanjirappally, Kerala",
            latitude=9.5564,
            longitude=76.7909,
            max_delivery_radius_km=30.0,
            is_active=True
        )

        CartItem.objects.create(user=self.customer, food_item=self.food_item, quantity=1)

        self.login('testcustomer', 'testpassword123')
        self.wait.until(lambda d: '/login/' not in d.current_url)
        self.driver.get(self.live_server_url + '/orders/checkout/')

        page_source = self.driver.page_source
        self.assertIn('Order Summary', page_source)
        self.assertNotIn('earth.google.com/web', page_source)
        self.assertNotIn('maplibregl-map', page_source)

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

        # Verify map dragging is enabled and marker dragging is disabled
        map_dragging_enabled = self.driver.execute_script("return typeof leafletMap !== 'undefined' && leafletMap.dragging.enabled();")
        self.assertTrue(map_dragging_enabled)

        marker_dragging_enabled = self.driver.execute_script("return typeof leafletMarker !== 'undefined' && leafletMarker.dragging && leafletMarker.dragging.enabled();")
        self.assertFalse(marker_dragging_enabled)

        # Verify intentional selection updates coordinates (via preset, map click or syncProfileCoordinates)
        time.sleep(0.5)
        self.driver.execute_script("""
            if (typeof syncProfileCoordinates === 'function') {
                syncProfileCoordinates(9.5800, 76.8000);
            } else {
                leafletMap.fire('click', {latlng: L.latLng(9.5800, 76.8000)});
            }
        """)
        updated_lat = self.driver.find_element(By.ID, 'loc_lat').get_attribute('value')
        updated_lon = self.driver.find_element(By.ID, 'loc_lon').get_attribute('value')
        self.assertEqual(updated_lat, '9.580000')
        self.assertEqual(updated_lon, '76.800000')


