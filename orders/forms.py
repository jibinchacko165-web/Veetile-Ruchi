# file: orders/forms.py
from django import forms
from .models import Order


class CheckoutForm(forms.ModelForm):
    """Collect delivery address and contact details."""

    class Meta:
        model = Order
        fields = [
            "delivery_address",
            "customer_delivery_notes",
            "latitude",
            "longitude",
        ]
        widgets = {
            "delivery_address": forms.Textarea(attrs={"placeholder": "Full delivery address", "rows": 3}),
            "customer_delivery_notes": forms.TextInput(attrs={"placeholder": "Optional delivery notes"}),
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
        }
