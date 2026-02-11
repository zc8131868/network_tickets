from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from auto_tickets.views.forms_ticket_management import TicketManagementForm
from auto_tickets.models import ITSR_Network
import os
from django.conf import settings
from datetime import datetime, timedelta
import glob

def cleanup_old_files(itsr_files_dir, retention_months=6):
    """
    Remove files older than the specified number of months from the itsr_files directory.
    
    Args:
        itsr_files_dir: Path to the itsr_files directory
        retention_months: Number of months to keep files (default: 6)
    
    Returns:
        tuple: (deleted_count, error_count)
    """
    if not os.path.exists(itsr_files_dir):
        return 0, 0
    
    deleted_count = 0
    error_count = 0
    cutoff_date = datetime.now() - timedelta(days=retention_months * 30)
    
    try:
        # Get all files in the directory
        all_files = glob.glob(os.path.join(itsr_files_dir, '*'))
        
        for file_path in all_files:
            if os.path.isfile(file_path):
                try:
                    # Get file modification time
                    file_mtime = os.path.getmtime(file_path)
                    file_date = datetime.fromtimestamp(file_mtime)
                    
                    # Delete if older than cutoff date
                    if file_date < cutoff_date:
                        os.remove(file_path)
                        deleted_count += 1
                except Exception as e:
                    # Log error but continue with other files
                    error_count += 1
                    print(f"Error deleting file {file_path}: {str(e)}")
    
    except Exception as e:
        print(f"Error during file cleanup: {str(e)}")
        error_count += 1
    
    return deleted_count, error_count

@login_required
def ticket_management(request):
    if request.method == 'POST':
        form = TicketManagementForm(request.POST, request.FILES)
        if form.is_valid():
            itsr_ticket_number = form.cleaned_data['itsr_ticket_number']
            requestor = form.cleaned_data['requestor']
            handler = form.cleaned_data['handler']
            ticket_status = form.cleaned_data['ticket_status']
            itsr_status = form.cleaned_data['itsr_status']
            description = form.cleaned_data.get('description', '')
            uploaded_file = form.cleaned_data.get('file')
            
            try:
                # Check if ticket number already exists
                if ITSR_Network.objects.filter(itsr_ticket_number=itsr_ticket_number).exists():
                    form.add_error('itsr_ticket_number', 'This ITSR ticket number already exists in the database.')
                    return render(request, 'ticket_management.html', {'form': form})
                
                # Handle file upload if provided
                saved_file_path = None
                if uploaded_file:
                    # Create itsr_files directory if it doesn't exist
                    itsr_files_dir = os.path.join(settings.BASE_DIR, 'auto_tickets', 'itsr_files')
                    os.makedirs(itsr_files_dir, mode=0o755, exist_ok=True)
                    
                    # Check if directory is writable
                    if not os.access(itsr_files_dir, os.W_OK):
                        error_message = f'Error saving ticket: Permission denied. The itsr_files directory is not writable. Please contact the administrator.'
                        return render(request, 'ticket_management.html', {
                            'form': form,
                            'error_message': error_message
                        })
                    
                    # Clean up files older than 6 months before saving new file
                    deleted_count, error_count = cleanup_old_files(itsr_files_dir, retention_months=2)
                    
                    # Generate filename: ticket_number_original_filename_timestamp.ext
                    file_extension = os.path.splitext(uploaded_file.name)[1]
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    safe_ticket_number = itsr_ticket_number.replace('/', '_').replace('\\', '_')
                    original_name = os.path.splitext(uploaded_file.name)[0]
                    # Sanitize filename
                    safe_original_name = "".join(c for c in original_name if c.isalnum() or c in (' ', '-', '_')).strip()
                    safe_original_name = safe_original_name.replace(' ', '_')
                    
                    filename = f"{safe_ticket_number}_{safe_original_name}_{timestamp}{file_extension}"
                    file_path = os.path.join(itsr_files_dir, filename)
                    
                    # Save the file
                    try:
                        with open(file_path, 'wb+') as destination:
                            for chunk in uploaded_file.chunks():
                                destination.write(chunk)
                        saved_file_path = file_path
                    except PermissionError as pe:
                        error_message = f'Error saving ticket: Permission denied when writing to {filename}. Please contact the administrator.'
                        return render(request, 'ticket_management.html', {
                            'form': form,
                            'error_message': error_message
                        })
                    except OSError as ose:
                        error_message = f'Error saving ticket: {str(ose)}. Please contact the administrator.'
                        return render(request, 'ticket_management.html', {
                            'form': form,
                            'error_message': error_message
                        })
                
                # Create new ticket entry
                ITSR_Network.objects.create(
                    itsr_ticket_number=itsr_ticket_number,
                    requestor=requestor,
                    handler=handler,
                    ticket_status=ticket_status,
                    itsr_status=itsr_status,
                    description=description
                )
                
                # Reset form and show success message
                form = TicketManagementForm()
                success_message = f'Successfully created ticket entry for ITSR: {itsr_ticket_number}'
                if saved_file_path:
                    success_message += f' and saved file: {os.path.basename(saved_file_path)}'
                return render(request, 'ticket_management.html', {
                    'form': form,
                    'success_message': success_message
                })
                
            except Exception as e:
                # Handle database constraint errors
                error_str = str(e)
                if 'itsr_ticket_number' in error_str.lower() or 'unique' in error_str.lower():
                    if 'itsr_ticket_number' in error_str.lower():
                        form.add_error('itsr_ticket_number', 'This ITSR ticket number already exists.')
                    elif 'requestor' in error_str.lower():
                        form.add_error('requestor', 'This requestor already exists.')
                else:
                    error_message = f'Error saving ticket: {error_str}'
                    return render(request, 'ticket_management.html', {
                        'form': form,
                        'error_message': error_message
                    })
                return render(request, 'ticket_management.html', {'form': form})
        else:
            # Form is not valid, return the form with errors
            return render(request, 'ticket_management.html', {'form': form})
    else:
        form = TicketManagementForm()
        return render(request, 'ticket_management.html', {'form': form})
