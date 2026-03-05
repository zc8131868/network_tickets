from django.shortcuts import render
from auto_tickets.views.forms_ip_owner_query import IPOwnerQueryForm
from auto_tickets.models import IP_Application
import ipaddress


def ip_owner_query(request):
    if request.method == 'POST':
        form = IPOwnerQueryForm(request.POST)
        if form.is_valid():
            ip_input = form.cleaned_data['ip_address'].strip()
            try:
                result = query_ip_owner(ip_input)
                if result:
                    return render(request, 'ip_owner_query.html', {
                        'form': form,
                        'result': result,
                        'success': True,
                        'ip_input': ip_input
                    })
                else:
                    return render(request, 'ip_owner_query.html', {
                        'form': form,
                        'error': 'No record',
                        'ip_input': ip_input
                    })
            except Exception as e:
                return render(request, 'ip_owner_query.html', {
                    'form': form,
                    'error': f'Error: {str(e)}'
                })
    else:
        form = IPOwnerQueryForm()
    return render(request, 'ip_owner_query.html', {'form': form})


def query_ip_owner(ip_input):
    """
    Query IP_Application table to find the owner (staff_number) for a given IP or subnet.
    Returns a dict with matching record info, or None if not found.
    """
    all_records = IP_Application.objects.exclude(subnet__isnull=True).exclude(subnet='')
    
    if '/' in ip_input:
        try:
            input_network = ipaddress.ip_network(ip_input, strict=False)
        except ValueError:
            return None
        
        for record in all_records:
            try:
                db_network = ipaddress.ip_network(record.subnet, strict=False)
                if input_network.overlaps(db_network) or db_network.overlaps(input_network):
                    return {
                        'staff_number': record.staff_number or 'Not assigned',
                        'subnet': record.subnet,
                        'location': record.location,
                        'usage': record.usage,
                        'description': record.description
                    }
            except ValueError:
                continue
    else:
        try:
            input_ip = ipaddress.ip_address(ip_input)
        except ValueError:
            return None
        
        for record in all_records:
            try:
                db_network = ipaddress.ip_network(record.subnet, strict=False)
                if input_ip in db_network:
                    return {
                        'staff_number': record.staff_number or 'Not assigned',
                        'subnet': record.subnet,
                        'location': record.location,
                        'usage': record.usage,
                        'description': record.description
                    }
            except ValueError:
                continue
    
    return None
