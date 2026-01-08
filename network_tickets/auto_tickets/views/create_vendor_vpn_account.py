from django.shortcuts import render
from django.contrib.auth.decorators import login_required, permission_required
import openpyxl
from auto_tickets.vpn_tools.create_user_tool import create_vpn_user_tool
from auto_tickets.views.forms_create_vendor_vpn_account import CreateVendorVPNAccountForm

@login_required
@permission_required('auto_tickets.add_vendor_vpn', raise_exception=True)
def create_vendor_vpn_account(request):
    if request.method == 'POST':
        form = CreateVendorVPNAccountForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES['file']
            try:
                wb = openpyxl.load_workbook(uploaded_file)
                result = create_vpn_user_tool(wb)
                successful_res = result.get('success', {})
                error_messages = result.get('errors', [])
                
                # Prepare context
                context = {
                    'res': successful_res,
                }
                
                # Add success message if there are successful accounts
                if successful_res:
                    context['success_message'] = f'Successfully created {len(successful_res)} vendor VPN account(s)!'
                
                # Add error messages if there are any
                if error_messages:
                    context['error_messages'] = error_messages
                    context['has_errors'] = True
                
                return render(request, 'create_vendor_vpn_account.html', context)
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
