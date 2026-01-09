from django import forms
from django.core.validators import RegexValidator
from auto_tickets.models import ITSR_Network


class TicketManagementForm(forms.Form):
    # 为了添加必选项前面的星号
    # 下面是模板的内容
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


    itsr_ticket_number = forms.CharField(
        label='ITSR Ticket Number',
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter ITSR ticket number'
        })
    )

    requestor = forms.CharField(
        label='Requestor',
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter requestor name'
        })
    )

    handler = forms.ChoiceField(
        label='Handler',
        choices=ITSR_Network.HANDLER_CHOICES,
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select',
        })
    )

    ticket_status = forms.ChoiceField(
        label='Ticket Status',
        choices=ITSR_Network.TICKET_STATUS_CHOICES,
        required=True,
        initial='incomplete',
        widget=forms.Select(attrs={
            'class': 'form-select',
        })
    )

    itsr_status = forms.ChoiceField(
        label='ITSR Status',
        choices=ITSR_Network.ITSR_STATUS_CHOICES,
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select',
        })
    )

    file = forms.FileField(
        label='Upload File',
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '*/*'
        })
    )

    
