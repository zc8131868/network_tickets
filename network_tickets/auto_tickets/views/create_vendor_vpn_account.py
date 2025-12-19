from django.shortcuts import render
from django.contrib.auth.decorators import login_required
import openpyxl
from auto_tickets.models import Vendor_VPN
from auto_tickets.vpn_tools.create_user_tool import create_vpn_user_tool
from auto_tickets.views.forms_create_vendor_vpn_account import CreateVendorVPNAccountForm

@login_required
def create_vendor_vpn_account(request):
    if request.method == 'POST':
        form = CreateVendorVPNAccountForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES['file']
            try:
                wb = openpyxl.load_workbook(uploaded_file)
                res = create_vpn_user_tool(wb)
                for vendor_name, user_id in res.items():
                    Vendor_VPN.objects.create(vendor_name=vendor_name, vendor_openid=user_id)
                return render(request, 'create_vendor_vpn_account.html', {
                    'res': res,
                    'success_message': f'Successfully created {len(res)} vendor VPN account(s)!'
                })
            except Exception as e:
                # If there's an error processing the file, show the form with error
                error_msg = f'Error processing file: {str(e)}'
                form.add_error('file', error_msg)
                return render(request, 'create_vendor_vpn_account.html', {
                    'form': form,
                    'error_messages': [error_msg],
                    'has_errors': True
                })
        else:
            # Form is not valid, render with errors
            return render(request, 'create_vendor_vpn_account.html', {'form': form})
    else:
        form = CreateVendorVPNAccountForm()
        return render(request, 'create_vendor_vpn_account.html', {'form': form})
