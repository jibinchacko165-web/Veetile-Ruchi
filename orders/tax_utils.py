from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings

def get_gst_rate():
    return Decimal(str(getattr(settings, 'GST_RATE_PERCENT', 5.0)))

def get_gst_mode():
    return getattr(settings, 'GST_MODE', 'inclusive')

def calculate_item_pricing(unit_price, quantity=1, gst_rate=None, gst_mode=None):
    """
    Centralized pricing and tax calculation for Veetile Ruchi food items.
    
    Mode A ('exclusive' / 'additional'):
        GST is added on top of the base price.
        base_price = unit_price * quantity
        gst_amount = base_price * (gst_rate / 100)
        final_price = base_price + gst_amount

    Mode B ('inclusive' / 'included'):
        GST is already included in the displayed food price.
        final_price = unit_price * quantity
        gst_amount = final_price * gst_rate / (100 + gst_rate)
        taxable_value = final_price - gst_amount

    Uses Python Decimal with standard ROUND_HALF_UP to guarantee currency accuracy.
    Never doubles or reapplies GST.
    """
    if gst_rate is None:
        gst_rate = get_gst_rate()
    else:
        gst_rate = Decimal(str(gst_rate))

    if gst_mode is None:
        gst_mode = get_gst_mode()

    unit_price = Decimal(str(unit_price))
    qty = Decimal(str(quantity))

    if gst_mode in ('exclusive', 'additional'):
        base_price = (unit_price * qty).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        gst_amount = (base_price * gst_rate / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        final_price = (base_price + gst_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        taxable_value = base_price
    else:
        final_price = (unit_price * qty).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        gst_amount = (final_price * gst_rate / (Decimal('100') + gst_rate)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        taxable_value = (final_price - gst_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    return {
        'unit_price': unit_price,
        'quantity': int(qty),
        'taxable_value': taxable_value,
        'gst_rate': gst_rate,
        'gst_amount': gst_amount,
        'final_price': final_price,
        'mode': gst_mode,
    }
