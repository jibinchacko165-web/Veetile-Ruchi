from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from food.models import FoodItem
from orders.models import CartItem, Order, OrderItem
from orders.tax_utils import calculate_item_pricing

class FoodPricingAndGSTTests(TestCase):
    """
    Validates dynamic quantity pricing, centralized GST calculations, and cart consistency.
    """

    def setUp(self):
        self.customer = User.objects.create_user(
            username='test_pricing_cust',
            password='password123',
            role='customer',
            phone='9846011122'
        )
        self.food_65 = FoodItem.objects.create(
            name='Kerala Fish Curry Meal',
            price=Decimal('65.00'),
            stock_quantity=20,
            is_available=True
        )
        self.food_75 = FoodItem.objects.create(
            name='Thalassery Chicken Biryani Mini',
            price=Decimal('75.00'),
            stock_quantity=15,
            is_available=True
        )

    def test_decimal_precision_pricing_65_rupees_quantities(self):
        """
        Verify ₹65.00 unit price produces exact totals for quantities 1, 2, 3, 4:
        Qty 1 -> ₹65.00
        Qty 2 -> ₹130.00
        Qty 3 -> ₹195.00
        Qty 4 -> ₹260.00
        """
        for qty, expected_total in [(1, Decimal('65.00')), (2, Decimal('130.00')), (3, Decimal('195.00')), (4, Decimal('260.00'))]:
            res = calculate_item_pricing(unit_price=Decimal('65.00'), quantity=qty, gst_rate=Decimal('5.0'), gst_mode='inclusive')
            self.assertEqual(res['final_price'], expected_total)
            self.assertEqual(res['quantity'], qty)
            # Ensure taxable + gst == final_price (no double tax or discrepancy)
            self.assertEqual(res['taxable_value'] + res['gst_amount'], expected_total)

    def test_gst_mode_a_additional_tax_75_rupees_table(self):
        """
        Mode A (GST is additional):
        Unit price: ₹75.00, GST rate: 5%
        Qty 1: ₹78.75 (base 75.00, GST 3.75)
        Qty 2: ₹157.50 (base 150.00, GST 7.50)
        Qty 3: ₹236.25 (base 225.00, GST 11.25)
        Qty 4: ₹315.00 (base 300.00, GST 15.00)
        """
        expected_table = [
            (1, Decimal('75.00'), Decimal('3.75'), Decimal('78.75')),
            (2, Decimal('150.00'), Decimal('7.50'), Decimal('157.50')),
            (3, Decimal('225.00'), Decimal('11.25'), Decimal('236.25')),
            (4, Decimal('300.00'), Decimal('15.00'), Decimal('315.00')),
        ]
        for qty, exp_base, exp_gst, exp_final in expected_table:
            res = calculate_item_pricing(unit_price=Decimal('75.00'), quantity=qty, gst_rate=Decimal('5.0'), gst_mode='exclusive')
            self.assertEqual(res['taxable_value'], exp_base)
            self.assertEqual(res['gst_amount'], exp_gst)
            self.assertEqual(res['final_price'], exp_final)

    def test_gst_mode_b_included_tax_75_rupees_table(self):
        """
        Mode B (GST is included in displayed price):
        Displayed price: ₹75.00, GST rate: 5%
        Qty 1: ₹75.00 (taxable 71.43, included GST 3.57)
        Qty 2: ₹150.00 (taxable 142.86, included GST 7.14)
        Qty 3: ₹225.00 (taxable 214.29, included GST 10.71)
        Qty 4: ₹300.00 (taxable 285.71, included GST 14.29)
        """
        expected_table = [
            (1, Decimal('71.43'), Decimal('3.57'), Decimal('75.00')),
            (2, Decimal('142.86'), Decimal('7.14'), Decimal('150.00')),
            (3, Decimal('214.29'), Decimal('10.71'), Decimal('225.00')),
            (4, Decimal('285.71'), Decimal('14.29'), Decimal('300.00')),
        ]
        for qty, exp_taxable, exp_gst, exp_final in expected_table:
            res = calculate_item_pricing(unit_price=Decimal('75.00'), quantity=qty, gst_rate=Decimal('5.0'), gst_mode='inclusive')
            self.assertEqual(res['taxable_value'], exp_taxable)
            self.assertEqual(res['gst_amount'], exp_gst)
            self.assertEqual(res['final_price'], exp_final)

    def test_food_detail_template_renders_unit_price_and_dynamic_total_container(self):
        """Food detail page includes Total Price, Order Total, dynamic total container, and steppers."""
        self.client.force_login(self.customer)
        response = self.client.get(reverse('food_detail', kwargs={'pk': self.food_65.id}))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Top label changed to Total Price and bottom label is Order Total
        self.assertIn('Total Price:', content)
        self.assertIn('Order Total:', content)
        self.assertIn('Unit Price per Portion:', content)
        self.assertIn('65.00', content)

        # Dynamic price and total elements present
        self.assertIn('id="detail-top-label"', content)
        self.assertIn('id="detail-bottom-label"', content)
        self.assertIn('id="detail-unit-price"', content)
        self.assertIn('id="dynamic-total-container"', content)
        self.assertIn('id="detail-total-price"', content)
        self.assertIn('id="btn-qty-minus"', content)
        self.assertIn('id="btn-qty-plus"', content)
        self.assertIn('id="detail-qty"', content)
        self.assertIn('updateFoodPriceAndTotals', content)

    def test_add_to_cart_each_quantity_1_to_4(self):
        """
        Verify adding quantities 1, 2, 3, and 4 sets exact quantity and calculated price in PostgreSQL:
        - Qty 1: ₹65.00
        - Qty 2: ₹130.00
        - Qty 3: ₹195.00
        - Qty 4: ₹260.00
        """
        expected_pricing = [
            (1, Decimal('65.00')),
            (2, Decimal('130.00')),
            (3, Decimal('195.00')),
            (4, Decimal('260.00')),
        ]
        self.client.force_login(self.customer)
        for qty, exp_total in expected_pricing:
            CartItem.objects.filter(user=self.customer).delete()
            resp = self.client.post(
                reverse('cart_add', kwargs={'food_id': self.food_65.id}),
                {'quantity': qty},
                follow=True
            )
            self.assertEqual(resp.status_code, 200)
            item = CartItem.objects.get(user=self.customer, food_item=self.food_65)
            self.assertEqual(item.quantity, qty)
            self.assertEqual(item.total_price, exp_total)
            content = resp.content.decode('utf-8')
            self.assertIn(f'{exp_total}', content)

    def test_add_to_cart_with_selected_quantity_3(self):
        """Adding quantity 3 of ₹65 item stores quantity 3 in PostgreSQL and calculates ₹195 total."""
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse('cart_add', kwargs={'food_id': self.food_65.id}),
            {'quantity': 3},
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        cart_item = CartItem.objects.get(user=self.customer, food_item=self.food_65)
        self.assertEqual(cart_item.quantity, 3)
        self.assertEqual(cart_item.total_price, Decimal('195.00'))

        # View cart receipt summary
        cart_content = response.content.decode('utf-8')
        self.assertIn('195.00', cart_content)
        self.assertIn('Taxable Value', cart_content)
        self.assertIn('Applicable GST', cart_content)

    def test_cart_quantity_updates_reliably(self):
        """Cart item increment and decrement adjust total price accurately."""
        self.client.force_login(self.customer)
        cart_item = CartItem.objects.create(
            user=self.customer,
            food_item=self.food_65,
            quantity=1
        )
        self.assertEqual(cart_item.total_price, Decimal('65.00'))

        # Increment to 2
        self.client.post(reverse('cart_update_quantity', kwargs={'item_id': cart_item.id}), {'action': 'increase'})
        cart_item.refresh_from_db()
        self.assertEqual(cart_item.quantity, 2)
        self.assertEqual(cart_item.total_price, Decimal('130.00'))

        # Increment to 3
        self.client.post(reverse('cart_update_quantity', kwargs={'item_id': cart_item.id}), {'action': 'increase'})
        cart_item.refresh_from_db()
        self.assertEqual(cart_item.quantity, 3)
        self.assertEqual(cart_item.total_price, Decimal('195.00'))

        # Increment to 4
        self.client.post(reverse('cart_update_quantity', kwargs={'item_id': cart_item.id}), {'action': 'increase'})
        cart_item.refresh_from_db()
        self.assertEqual(cart_item.quantity, 4)
        self.assertEqual(cart_item.total_price, Decimal('260.00'))

        # Decrement back to 3
        self.client.post(reverse('cart_update_quantity', kwargs={'item_id': cart_item.id}), {'action': 'decrease'})
        cart_item.refresh_from_db()
        self.assertEqual(cart_item.quantity, 3)
        self.assertEqual(cart_item.total_price, Decimal('195.00'))
