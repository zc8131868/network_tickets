from auto_tickets.views.forms_auto_tickets_pa import AutoTicketsPaForm

from django.shortcuts import render
from auto_tickets.tools import auto_tickets_pa_tools
from django.contrib.auth.decorators import login_required
import openpyxl

@login_required
def auto_tickets_pa(request):
    if request.method == 'POST':
        form = AutoTicketsPaForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES['file']
            try:
                wb = openpyxl.load_workbook(uploaded_file)
                
                # Debug: Print session data
                firewall_username = request.session.get('firewall_username')
                firewall_password = request.session.get('firewall_password')
                print(f"DEBUG - Firewall username from session: {firewall_username}")
                print(f"DEBUG - Firewall password length: {len(firewall_password) if firewall_password else 0}")
                print(f"DEBUG - User object username: {request.user.username}")
                print(f"DEBUG - Session key: {request.session.session_key}")
                print(f"DEBUG - All session keys: {list(request.session.keys())}")
                
                # Fallback if session data is missing
                if not firewall_username or not firewall_password:
                    print("WARNING - Session data missing, using request.user.username")
                    firewall_username = request.user.username
                    firewall_password = "your_password_here"  # You'll need to set this
                
                result_list = auto_tickets_pa_tools(wb, firewall_username, firewall_password)

                # Check if we got any results
                if result_list:
                    # Process the result list to separate errors from other messages
                    error_messages = []
                    
                    for message in result_list:
                        # More specific error detection to avoid false positives
                        if any(keyword in message.lower() for keyword in ['failed:',  'traceback:', 'validation failed', 'connection failed']):
                            error_messages.append(message)
                    
                    # Return results with error messages
                    return render(request, 'auto_tickets_pa.html', {
                        'result_list': result_list,
                        'error_messages': error_messages,
                        'has_errors': len(error_messages) > 0
                    })
                else:
                    # No results found, show error
                    form.add_error('file', 'No valid data found in the Excel file. Please check that your file has data in columns C and E starting from row 4.')
                    return render(request, 'auto_tickets_pa.html', {'form': form})
            
            except Exception as e:
                # If there's an error processing the file, show the form with error
                error_msg = f'Error processing file: {str(e)}'
                form.add_error('file', error_msg)
                return render(request, 'auto_tickets_pa.html', {
                    'form': form,
                    'error_messages': [error_msg],
                    'has_errors': True
                })
        else:
            # Form is not valid, render with errors
            return render(request, 'auto_tickets_pa.html', {'form': form})
    else:
        form = AutoTicketsPaForm()
        return render(request, 'auto_tickets_pa.html', {'form': form})