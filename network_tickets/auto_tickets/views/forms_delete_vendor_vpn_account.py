from django import forms
from django.core.validators import RegexValidator
from auto_tickets.models import Vendor_VPN

class DeleteVendorVPNAccountForm(forms.Form):
    required_css_class = 'required'

    vendor_name = forms.CharField(
        label='Vendor Name',
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter vendor name to delete'
        })
    )

