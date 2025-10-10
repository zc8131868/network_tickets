from django import forms

class GetPaNatForm(forms.Form):
    target_ip = forms.CharField(
        label='Target IP',
        required=True,
        initial='e.g. 192.168.1.1',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
        })
    )