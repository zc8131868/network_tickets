from django import forms
from django.core.validators import RegexValidator
from auto_tickets.models import IP_Application


class IPApplicationForm(forms.Form):
    # 为了添加必选项前面的星号
    # 下面是模板内的内
    """
    < style type = "text/css" >
    label.required::before
    {
        content: "*";
    color: red;
    }
    < / style >
    """
    required_css_class = 'required'  # 这是Form.required_css_class属性, use to add class attributes to required rows


    location = forms.ChoiceField(
        label='Target Location',
        choices=[('MITA', 'MITA'), ('GNC', 'GNC'), ('Taiping', 'Taiping')],
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select',
        })
    )

    usage = forms.ChoiceField(
        label='Usage',
        choices=[('Traffic', 'Traffic'), ('OAM', 'OAM')],
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select',
        })
    )

    number = forms.ChoiceField(
        label='Desired IP number(pls contact IT if you need more than 30 IPs)',
        choices=[('6', '6'), ('14', '14'), ('30', '30')],
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select',
        })
    )

    # deleted_ip = forms.CharField(
    #     label='Deleted IP',
    #     required=False,
    #     initial='e.g. 192.168.1.1/24',
    #     widget=forms.TextInput(attrs={
    #         'class': 'form-control',
    #     })
    # )
    