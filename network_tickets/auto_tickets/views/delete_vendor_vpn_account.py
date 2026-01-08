from django.shortcuts import render
from django.contrib.auth.decorators import login_required, permission_required
from auto_tickets.vpn_tools.delete_user_tool import call_delete_user_api
from auto_tickets.views.forms_delete_vendor_vpn_account import DeleteVendorVPNAccountForm

@login_required
@permission_required('auto_tickets.delete_vendor_vpn', raise_exception=True)
def delete_vendor_vpn_account(request):
    if request.method == 'POST':
        form = DeleteVendorVPNAccountForm(request.POST)
        if form.is_valid():
            vendor_email = form.cleaned_data['vendor_email']
            try:

                # Call the delete API
                result = call_delete_user_api(vendor_email)
                
                if result == 'success':
                    success_message = f'Successfully deleted VPN account for vendor: {vendor_email}'
                    return render(request, 'delete_vendor_vpn_account.html', {
                        'form': DeleteVendorVPNAccountForm(),
                        'success_message': success_message
                    })
                else:
                    error_message = f'Failed to delete VPN account: {result}'
                    return render(request, 'delete_vendor_vpn_account.html', {
                        'form': form,
                        'error_message': error_message
                    })

            except Exception as e:
                error_message = f'Error deleting VPN account: {str(e)}'
                return render(request, 'delete_vendor_vpn_account.html', {
                    'form': form,
                    'error_message': error_message
                })
        else:
            # Form is not valid, render with errors
            return render(request, 'delete_vendor_vpn_account.html', {'form': form})
    else:
        form = DeleteVendorVPNAccountForm()
        return render(request, 'delete_vendor_vpn_account.html', {'form': form})

