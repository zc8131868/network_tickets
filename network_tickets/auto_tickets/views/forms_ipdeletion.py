from django import forms
from django.core.validators import RegexValidator
from auto_tickets.models import IP_Application

class IPDeletionForm(forms.Form):
    deleted_ip = forms.CharField(
        label='Deleted IP',
        required=True,
        initial='e.g. 192.168.1.0/24',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
        })
    )