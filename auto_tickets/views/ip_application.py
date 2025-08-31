from django.shortcuts import render
from auto_tickets.tools import generate_subnet
from auto_tickets.views.forms_ipapplication import IPApplicationForm
from auto_tickets.models import IP_Application
import ipaddress
from django.contrib.auth.decorators import login_required

@login_required
def ip_application(request):
    '''
    MITA 10.1.96.0/19     Traffic
    MITA 10.0.192.0/21    OAM
    GNC  10.1.1.0/21      Traffic
    GNC  10.0.208.0/21    OAM
    Taiping 10.1.1.0/21   Traffic
    Taiping 10.0.208.0/21 OAM   
    '''
    # IP_Application.objects.all().delete()


    if request.method == 'POST':
        form = IPApplicationForm(request.POST)
        if form.is_valid():
            location = form.cleaned_data['location']
            usage = form.cleaned_data['usage']
            number = form.cleaned_data['number']
           
            if location == 'MITA':
                if usage == 'Traffic':
                    parent_network = f'10.1.96.0/19'
                else:
                    parent_network = f'10.0.192.0/21'
            elif location == 'GNC':
                if usage == 'Traffic':
                    parent_network = f'10.1.1.0/21'
                else:
                    parent_network = f'10.0.208.0/21'
            elif location == 'Taiping':
                if usage == 'Traffic':
                    parent_network = f'10.1.1.0/21'
                else:
                    parent_network = f'10.0.208.0/21'

            existing_subnets = IP_Application.objects.filter(location=location, usage=usage)
            # Convert existing subnets to ipaddress objects if they're strings
            normalized_existing = []
            if existing_subnets.exists():
                for app in existing_subnets:
                    if app.subnet:
                        normalized_existing.append(ipaddress.ip_network(app.subnet, strict=False))

            subnet = generate_subnet(parent_network, int(number), normalized_existing)

            if subnet:
                IP_Application.objects.create(location=location, usage=usage, number=int(number), subnet=str(subnet))
                form = IPApplicationForm()  # Create fresh form with initial data
                return render(request, 'ip_application.html', {'form': form, 'subnet': subnet})
            else:
                return render(request, 'ip_application.html', {'form': form, 'error': 'Generate subnet failed'})
        else:
            # Form is not valid, return the form with errors
            return render(request, 'ip_application.html', {'form': form})
    else:
        form = IPApplicationForm()
        return render(request, 'ip_application.html', {'form': form})