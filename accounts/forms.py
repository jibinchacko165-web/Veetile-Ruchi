from django import forms
from .models import User
from .validators import validate_custom_email, validate_email_address
import re

class UserEditProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=True, error_messages={'required': 'First Name is required.'})
    last_name = forms.CharField(max_length=150, required=True, error_messages={'required': 'Last Name is required.'})
    email = forms.EmailField(
        required=True,
        validators=[validate_custom_email],
        error_messages={'required': 'Enter a valid email address.', 'invalid': 'Enter a valid email address.'}
    )
    phone = forms.CharField(max_length=15, required=False)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'address']

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if not email:
            raise forms.ValidationError("Enter a valid email address.")
        is_valid, err_msg = validate_email_address(email)
        if not is_valid:
            raise forms.ValidationError(err_msg)
        if User.objects.filter(email__iexact=email).exclude(id=self.instance.id).exists():
            raise forms.ValidationError("This email address is already in use by another account.")
        return email

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if phone:
            clean_phone = re.sub(r'\D', '', phone)
            if not re.match(r'^[6-9]\d{9}$', clean_phone):
                raise forms.ValidationError("Please enter a valid 10-digit mobile phone number (e.g. 9876543210).")
            if User.objects.filter(phone=clean_phone).exclude(id=self.instance.id).exists():
                raise forms.ValidationError("This phone number is already assigned to another account.")
            return clean_phone
        return phone
