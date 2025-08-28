from django import forms
from django.core.validators import RegexValidator
from auto_tickets.models import IPDB


class IPDBFORM_MULTISPLIT(forms.Form):
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


    file = forms.FileField(
        label='Excel File (.xlsx)', 
        required=True,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.xlsx,.xls'
        })
    )

    