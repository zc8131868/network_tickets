from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from auto_tickets.views.forms_ticket_detail_search import TicketDetailSearchForm
from auto_tickets.models import ITSR_Network
import os
from django.conf import settings
import glob
import logging

logger = logging.getLogger(__name__)

@login_required
def ticket_detail_search(request):
    if request.method == 'POST':
        # Note: Close ITSR functionality now uses API endpoints:
        # - /api/itsr_close/create_session/
        # - /api/itsr_close/submit_credentials/
        # - /api/itsr_close/submit_sms/
        # The old form-based handler has been removed in favor of the multi-step API workflow.

        # Handle status update (disabled in close_itsr_mode)
        if 'update_ticket_status' in request.POST:
            close_itsr_mode = request.POST.get('close_itsr_mode', '') == 'true'
            
            # Don't allow status updates in close_itsr_mode
            if close_itsr_mode:
                messages.warning(request, 'Ticket status modification is not available in Close ITSR mode.')
                handler = request.POST.get('handler', '')
                redirect_url = f'/ticket_detail_search/?handler={handler}&close_itsr=true'
                return redirect(redirect_url)
            
            ticket_id = request.POST.get('ticket_id')
            new_status = request.POST.get('ticket_status')
            
            try:
                ticket = ITSR_Network.objects.get(id=ticket_id)
                old_status = ticket.ticket_status
                ticket.ticket_status = new_status
                ticket.save()
                messages.success(request, f'Successfully updated ticket {ticket.itsr_ticket_number} status from {old_status.title()} to {new_status.title()}.')
            except ITSR_Network.DoesNotExist:
                messages.error(request, 'Ticket not found.')
            except Exception as e:
                messages.error(request, f'Error updating ticket status: {str(e)}')
            
            # Redirect back to search with same parameters
            handler = request.POST.get('handler', '')
            itsr_ticket_number = request.POST.get('itsr_ticket_number', '')
            itsr_status = request.POST.get('itsr_status', '')
            redirect_url = f'/ticket_detail_search/?handler={handler}&itsr_ticket_number={itsr_ticket_number}'
            if itsr_status:
                redirect_url += f'&itsr_status={itsr_status}'
            return redirect(redirect_url)
        
        # Handle Close ITSR search
        if 'search_action' in request.POST and request.POST.get('search_action') == 'close_itsr':
            handler = request.POST.get('handler', '').strip()
            itsr_status = request.POST.get('itsr_status', '').strip()
            if not itsr_status:
                # Close-ITSR mode defaults to Open tickets
                itsr_status = 'open'
            
            if not handler:
                form = TicketDetailSearchForm(request.POST)
                form.add_error('handler', 'Handler is required for Close ITSR function.')
                return render(request, 'ticket_detail_search.html', {'form': form})
            
            # Create form with handler for display
            form = TicketDetailSearchForm({'handler': handler, 'itsr_status': itsr_status})
            
            # Filter: handler, ticket_status='complete', optional itsr_status (open/closed)
            query = ITSR_Network.objects.filter(
                handler=handler,
                ticket_status='complete',
            )
            if itsr_status:
                query = query.filter(itsr_status=itsr_status)
            tickets = query.order_by('-create_datetime')
            
            # Create tickets_with_files structure (without actual file lookup for this mode)
            tickets_with_files = []
            for ticket in tickets:
                tickets_with_files.append({
                    'ticket': ticket,
                    'files': []  # No files needed for Close ITSR mode
                })
            
            context = {
                'form': form,
                'tickets_with_files': tickets_with_files,
                'search_type': 'close_itsr',
                'handler': handler,
                'itsr_status': itsr_status,
                'has_results': len(tickets_with_files) > 0,
                'close_itsr_mode': True
            }
            
            return render(request, 'ticket_detail_search.html', context)
        
        # Handle regular search
        form = TicketDetailSearchForm(request.POST)
        if form.is_valid():
            handler = form.cleaned_data.get('handler', '').strip()
            itsr_ticket_number = form.cleaned_data.get('itsr_ticket_number', '').strip()
            itsr_status = form.cleaned_data.get('itsr_status', '').strip()
            
            tickets = []
            search_type = None
            
            if itsr_ticket_number:
                # Search by ticket number
                try:
                    ticket = ITSR_Network.objects.get(itsr_ticket_number=itsr_ticket_number)
                    tickets = [ticket]
                    search_type = 'ticket_number'
                except ITSR_Network.DoesNotExist:
                    tickets = []
                    search_type = 'ticket_number'
            elif handler:
                # Search by handler - always show incomplete tickets
                query = ITSR_Network.objects.filter(
                    handler=handler,
                    ticket_status='incomplete'
                )
                # If ITSR Status is selected, filter by it as well
                if itsr_status:
                    query = query.filter(itsr_status=itsr_status)
                tickets = query.order_by('-create_datetime')
                search_type = 'handler'
            
            # Get associated files for each ticket
            itsr_files_dir = os.path.join(settings.BASE_DIR, 'auto_tickets', 'itsr_files')
            tickets_with_files = []
            
            for ticket in tickets:
                # Find files that start with the ticket number
                safe_ticket_number = ticket.itsr_ticket_number.replace('/', '_').replace('\\', '_')
                pattern = os.path.join(itsr_files_dir, f"{safe_ticket_number}_*")
                matching_files = glob.glob(pattern)
                
                # Get file info
                file_list = []
                for file_path in matching_files:
                    if os.path.isfile(file_path):
                        file_name = os.path.basename(file_path)
                        file_size = os.path.getsize(file_path)
                        file_mtime = os.path.getmtime(file_path)
                        from datetime import datetime
                        file_date = datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d %H:%M:%S')
                        # Get relative path for URL
                        relative_path = os.path.relpath(file_path, os.path.join(settings.BASE_DIR, 'auto_tickets', 'itsr_files'))
                        file_list.append({
                            'name': file_name,
                            'path': file_path,
                            'size': file_size,
                            'date': file_date,
                            'url_name': file_name  # Use filename for URL
                        })
                
                tickets_with_files.append({
                    'ticket': ticket,
                    'files': sorted(file_list, key=lambda x: x['date'], reverse=True)
                })
            
            context = {
                'form': form,
                'tickets_with_files': tickets_with_files,
                'search_type': search_type,
                'handler': handler,
                'itsr_ticket_number': itsr_ticket_number,
                'itsr_status': itsr_status,
                'has_results': len(tickets_with_files) > 0,
                'show_close_button': search_type == 'handler' and bool(itsr_status),
                'close_itsr_mode': False
            }
            
            return render(request, 'ticket_detail_search.html', context)
        else:
            return render(request, 'ticket_detail_search.html', {'form': form})
    
    else:
        # GET request - check for query parameters
        handler = request.GET.get('handler', '').strip()
        itsr_ticket_number = request.GET.get('itsr_ticket_number', '').strip()
        itsr_status = request.GET.get('itsr_status', '').strip()
        close_itsr = request.GET.get('close_itsr', '').strip() == 'true'
        
        form = TicketDetailSearchForm(initial={
            'handler': handler,
            'itsr_ticket_number': itsr_ticket_number,
            'itsr_status': itsr_status
        })
        
        # Handle Close ITSR mode
        if close_itsr and handler:
            query = ITSR_Network.objects.filter(
                handler=handler,
                ticket_status='complete',
            )
            if not itsr_status:
                # Close-ITSR mode defaults to Open tickets
                itsr_status = 'open'
            if itsr_status:
                query = query.filter(itsr_status=itsr_status)
            tickets = query.order_by('-create_datetime')
            
            tickets_with_files = []
            for ticket in tickets:
                tickets_with_files.append({
                    'ticket': ticket,
                    'files': []
                })
            
            context = {
                'form': form,
                'tickets_with_files': tickets_with_files,
                'search_type': 'close_itsr',
                'handler': handler,
                'itsr_status': itsr_status,
                'has_results': len(tickets_with_files) > 0,
                'close_itsr_mode': True
            }
            
            return render(request, 'ticket_detail_search.html', context)
        
        # If parameters provided, perform regular search
        if handler or itsr_ticket_number:
            tickets = []
            search_type = None
            
            if itsr_ticket_number:
                try:
                    ticket = ITSR_Network.objects.get(itsr_ticket_number=itsr_ticket_number)
                    tickets = [ticket]
                    search_type = 'ticket_number'
                except ITSR_Network.DoesNotExist:
                    tickets = []
                    search_type = 'ticket_number'
            elif handler:
                # Search by handler - always show incomplete tickets
                query = ITSR_Network.objects.filter(
                    handler=handler,
                    ticket_status='incomplete'
                )
                # If ITSR Status is selected, filter by it as well
                if itsr_status:
                    query = query.filter(itsr_status=itsr_status)
                tickets = query.order_by('-create_datetime')
                search_type = 'handler'
            
            # Get associated files
            itsr_files_dir = os.path.join(settings.BASE_DIR, 'auto_tickets', 'itsr_files')
            tickets_with_files = []
            
            for ticket in tickets:
                safe_ticket_number = ticket.itsr_ticket_number.replace('/', '_').replace('\\', '_')
                pattern = os.path.join(itsr_files_dir, f"{safe_ticket_number}_*")
                matching_files = glob.glob(pattern)
                
                file_list = []
                for file_path in matching_files:
                    if os.path.isfile(file_path):
                        file_name = os.path.basename(file_path)
                        file_size = os.path.getsize(file_path)
                        file_mtime = os.path.getmtime(file_path)
                        from datetime import datetime
                        file_date = datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d %H:%M:%S')
                        # Get relative path for URL
                        relative_path = os.path.relpath(file_path, os.path.join(settings.BASE_DIR, 'auto_tickets', 'itsr_files'))
                        file_list.append({
                            'name': file_name,
                            'path': file_path,
                            'size': file_size,
                            'date': file_date,
                            'url_name': file_name  # Use filename for URL
                        })
                
                tickets_with_files.append({
                    'ticket': ticket,
                    'files': sorted(file_list, key=lambda x: x['date'], reverse=True)
                })
            
            context = {
                'form': form,
                'tickets_with_files': tickets_with_files,
                'search_type': search_type,
                'handler': handler,
                'itsr_ticket_number': itsr_ticket_number,
                'itsr_status': itsr_status,
                'has_results': len(tickets_with_files) > 0,
                'show_close_button': search_type == 'handler' and bool(itsr_status),
                'close_itsr_mode': False
            }
            
            return render(request, 'ticket_detail_search.html', context)
        
        return render(request, 'ticket_detail_search.html', {'form': form})
