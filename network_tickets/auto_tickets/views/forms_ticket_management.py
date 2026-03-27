from django import forms
from django.core.exceptions import ValidationError
from auto_tickets.models import ITSR_Network


class MultipleFileInput(forms.FileInput):
    def __init__(self, attrs=None):
        super().__init__(attrs)
        if self.attrs is not None:
            self.attrs.setdefault('multiple', True)
        else:
            self.attrs = {'multiple': True}

    def value_from_datadict(self, data, files, name):
        if files is not None and hasattr(files, 'getlist'):
            return files.getlist(name)
        if files:
            return files.get(name)
        return None


class MultipleFileField(forms.Field):
    """Optional multi-file upload; cleaned value is a list of UploadedFile."""

    def __init__(self, *args, **kwargs):
        wattrs = kwargs.pop('widget_attrs', None) or {}
        kwargs.setdefault('required', False)
        kwargs.setdefault(
            'widget',
            MultipleFileInput(attrs=wattrs),
        )
        super().__init__(*args, **kwargs)

    def clean(self, value):
        value = super().clean(value)
        if not value:
            return []
        if not isinstance(value, (list, tuple)):
            value = [value]
        files = [f for f in value if f and getattr(f, 'name', None)]
        if len(files) > 25:
            raise ValidationError('You can upload at most 25 files at once.')
        return list(files)


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

    description = forms.CharField(
        label='Description',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Enter ticket description (optional)',
            'rows': 3
        })
    )

    files = MultipleFileField(
        label='Attachments',
        widget_attrs={
            'class': 'form-control',
            'accept': '*/*',
        },
    )

