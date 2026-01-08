from django import forms
from django.core.validators import RegexValidator, EmailValidator

class DeleteVendorVPNAccountForm(forms.Form):
    required_css_class = 'required'

    vendor_email = forms.EmailField(
        label='Vendor Email',
        required=True,
        validators=[EmailValidator()],
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter vendor email to delete'
        })
    )

