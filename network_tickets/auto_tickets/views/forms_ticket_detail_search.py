from django import forms
from auto_tickets.models import ITSR_Network


class TicketDetailSearchForm(forms.Form):
    required_css_class = 'required'

    handler = forms.ChoiceField(
        label='Handler',
        choices=[('', '---------')] + ITSR_Network.HANDLER_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
        })
    )

    itsr_ticket_number = forms.CharField(
        label='ITSR Ticket Number',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter ITSR ticket number to search'
        })
    )

    itsr_status = forms.ChoiceField(
        label='ITSR Status',
        choices=[('', '---------')] + ITSR_Network.ITSR_STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        handler = cleaned_data.get('handler')
        itsr_ticket_number = cleaned_data.get('itsr_ticket_number')
        itsr_status = cleaned_data.get('itsr_status')

        # At least one field must be provided
        if not handler and not itsr_ticket_number:
            raise forms.ValidationError('Please provide either Handler or ITSR Ticket Number to search.')

        return cleaned_data
