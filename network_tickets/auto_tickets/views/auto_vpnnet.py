from auto_tickets.views.forms_auto_vpnnet import AutoVpnNetForm

from django.shortcuts import render
from auto_tickets.vpn_tools.auto_vpnnet_tool import create_vpn_access_policy_tool
from django.contrib.auth.decorators import login_required
import openpyxl

@login_required
def auto_vpnnet(request):
    if request.method == 'POST':
        form = AutoVpnNetForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES['file']
            print(f'[DEBUG] Processing file: {uploaded_file.name}')
            try:
                wb = openpyxl.load_workbook(uploaded_file)
                print(f'[DEBUG] Workbook loaded, active sheet: {wb.active.title}, max_row: {wb.active.max_row}')
                result = create_vpn_access_policy_tool(wb)
                
                success_results = result.get('success', [])
                error_messages = result.get('errors', [])
                
                print(f'[DEBUG] Results - success: {len(success_results)}, errors: {len(error_messages)}')
                
                # Prepare context - always include form for re-upload
                context = {
                    'form': AutoVpnNetForm(),  # Fresh form for re-upload
                    'result_list': success_results,
                    'processed': True,  # Flag to indicate processing was done
                }
                
                # Add success message if there are successful results
                if success_results:
                    context['success_message'] = f'Successfully created {len(success_results)} VPN network policy/policies!'
                
                # Add error messages if there are any
                if error_messages:
                    context['error_messages'] = error_messages
                    context['has_errors'] = True
                
                # If no results and no errors, show a warning message
                if not success_results and not error_messages:
                    context['warning_message'] = f'No valid data found in the uploaded file. Please ensure data starts from row 4 with all required columns (Ticket Number, Destination IP, Protocol, Destination Port, Vendor Name).'
                
                return render(request, 'auto_vpnnet.html', context)
            
            except Exception as e:
                import traceback
                print(f'[DEBUG] Exception: {str(e)}')
                print(f'[DEBUG] Traceback: {traceback.format_exc()}')
                # If there's an error processing the file, show the form with error
                error_msg = f'Error processing file: {str(e)}'
                form.add_error('file', error_msg)
                return render(request, 'auto_vpnnet.html', {
                    'form': form,
                    'error_messages': [error_msg],
                    'has_errors': True
                })
        else:
            # Form is not valid, render with errors
            return render(request, 'auto_vpnnet.html', {'form': form})
    else:
        form = AutoVpnNetForm()
        return render(request, 'auto_vpnnet.html', {'form': form})

