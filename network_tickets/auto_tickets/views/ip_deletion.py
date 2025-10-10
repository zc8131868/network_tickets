from django.shortcuts import render
from auto_tickets.models import IP_Application
from auto_tickets.views.forms_ipdeletion import IPDeletionForm
from django.contrib.auth.decorators import permission_required

@permission_required('auto_tickets.delete_ip_application')
def ip_deletion(request):
    if request.method == 'POST':
        form = IPDeletionForm(request.POST)
        if form.is_valid() and request.user.has_perm('auto_tickets.delete_ip_application'):
            deleted_ip = form.cleaned_data['deleted_ip']
            # Check if the IP exists before deletion
            existing_ips = IP_Application.objects.filter(subnet=deleted_ip)
            if existing_ips.exists():
                existing_ips.delete()
                form = IPDeletionForm(initial={'deleted_ip': 'e.g. 192.168.1.0/24'})  # Reset form with initial value
                return render(request, 'ip_deletion.html', {'form': form, 'deleted_ip': deleted_ip, 'success': True})
            else:
                form = IPDeletionForm(initial={'deleted_ip': 'e.g. 192.168.1.0/24'})
                return render(request, 'ip_deletion.html', {'form': form, 'error': f'IP {deleted_ip} not found in database'})
        else:
            # Form is not valid, return the form with errors
            return render(request, 'ip_deletion.html', {'form': form})
    else:
        form = IPDeletionForm(initial={'deleted_ip': 'e.g. 192.168.1.0/24'})
        return render(request, 'ip_deletion.html', {'form': form})