from django import forms
from auto_tickets.models import ITSR_Network


class TicketAnalyzerForm(forms.Form):
    date_from = forms.DateField(
        label='From Date',
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'id': 'date_from'
        })
    )
    
    date_to = forms.DateField(
        label='To Date',
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'id': 'date_to'
        })
    )
    
    handler = forms.ChoiceField(
        label='Handler',
        choices=[('', 'All Handlers')] + list(ITSR_Network.HANDLER_CHOICES),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'handler_filter'
        })
    )
    
    ticket_status = forms.ChoiceField(
        label='Ticket Status',
        choices=[('', 'All Statuses')] + list(ITSR_Network.TICKET_STATUS_CHOICES),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'ticket_status_filter'
        })
    )
