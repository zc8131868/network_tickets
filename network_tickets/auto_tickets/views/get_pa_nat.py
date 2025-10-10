from django.shortcuts import render
from auto_tickets.views.forms_get_pa_nat import GetPaNatForm
from auto_tickets.tools import get_nat_config as get_nat_config_tool       
# from django.contrib.auth.decorators import login_required

# @login_required
def get_pa_nat(request):
    if request.method == 'POST':
        form = GetPaNatForm(request.POST)
        if form.is_valid():
            target_ip = form.cleaned_data['target_ip']
            try:
                res = get_nat_config_tool(target_ip)
                if res:
                    return render(request, 'get_pa_nat.html', {
                        'form': form, 
                        'res': res, 
                        'success': True,
                        'target_ip': target_ip
                    })
                else:
                    return render(request, 'get_pa_nat.html', {
                        'form': form, 
                        'error': 'No NAT sessions found for this IP address.',
                        'target_ip': target_ip
                    })
            except Exception as e:
                return render(request, 'get_pa_nat.html', {
                    'form': form, 
                    'error': f'Error getting NAT config: {str(e)}'
                })
    else:
        form = GetPaNatForm()
        return render(request, 'get_pa_nat.html', {'form': form})
