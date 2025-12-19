from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from auto_tickets.models import Vendor_VPN
from auto_tickets.vpn_tools.delete_user_tool import call_delete_user_api
from auto_tickets.views.forms_delete_vendor_vpn_account import DeleteVendorVPNAccountForm

@login_required
def delete_vendor_vpn_account(request):
    if request.method == 'POST':
        form = DeleteVendorVPNAccountForm(request.POST)
        if form.is_valid():
            vendor_name = form.cleaned_data['vendor_name']
            
            try:
                # Look up vendor_openid from database
                vendor_vpn = Vendor_VPN.objects.get(vendor_name=vendor_name)
                vendor_openid = vendor_vpn.vendor_openid
                
                # Call the delete API
                result = call_delete_user_api(vendor_openid)
                
                if result == 'success':
                    # Delete from database
                    vendor_vpn.delete()
                    success_message = f'Successfully deleted VPN account for vendor: {vendor_name}'
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
            except Vendor_VPN.DoesNotExist:
                error_message = f'Vendor "{vendor_name}" not found in the database.'
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

