from django import forms


class IPOwnerQueryForm(forms.Form):
    ip_address = forms.CharField(
        label='IP Address / Subnet',
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. 10.0.8.50 or 10.0.8.0/24',
        })
    )
