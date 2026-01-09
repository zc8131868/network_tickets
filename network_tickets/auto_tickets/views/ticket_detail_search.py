from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from auto_tickets.views.forms_ticket_detail_search import TicketDetailSearchForm
from auto_tickets.models import ITSR_Network
import os
from django.conf import settings
import glob


@login_required
def ticket_detail_search(request):
    if request.method == 'POST':
        # Handle status update
        if 'update_status' in request.POST:
            ticket_id = request.POST.get('ticket_id')
            new_status = request.POST.get('ticket_status')
            
            try:
                ticket = ITSR_Network.objects.get(id=ticket_id)
                if ticket.ticket_status == 'incomplete' and new_status == 'complete':
                    ticket.ticket_status = 'complete'
                    ticket.save()
                    messages.success(request, f'Successfully updated ticket {ticket.itsr_ticket_number} status to Complete.')
                else:
                    messages.warning(request, 'Only incomplete tickets can be updated to complete.')
            except ITSR_Network.DoesNotExist:
                messages.error(request, 'Ticket not found.')
            
            # Redirect back to search with same parameters
            handler = request.POST.get('handler', '')
            itsr_ticket_number = request.POST.get('itsr_ticket_number', '')
            itsr_status = request.POST.get('itsr_status', '')
            redirect_url = f'/ticket_detail_search/?handler={handler}&itsr_ticket_number={itsr_ticket_number}'
            if itsr_status:
                redirect_url += f'&itsr_status={itsr_status}'
            return redirect(redirect_url)
        
        # Handle search
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
                # Search by handler
                if itsr_status:
                    # When ITSR Status is selected: show complete tickets with matching ITSR status
                    query = ITSR_Network.objects.filter(
                        handler=handler,
                        ticket_status='complete',
                        itsr_status=itsr_status
                    )
                else:
                    # Default: show incomplete tickets
                    query = ITSR_Network.objects.filter(
                        handler=handler,
                        ticket_status='incomplete'
                    )
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
                'has_results': len(tickets_with_files) > 0
            }
            
            return render(request, 'ticket_detail_search.html', context)
        else:
            return render(request, 'ticket_detail_search.html', {'form': form})
    
    else:
        # GET request - check for query parameters
        handler = request.GET.get('handler', '').strip()
        itsr_ticket_number = request.GET.get('itsr_ticket_number', '').strip()
        itsr_status = request.GET.get('itsr_status', '').strip()
        
        form = TicketDetailSearchForm(initial={
            'handler': handler,
            'itsr_ticket_number': itsr_ticket_number,
            'itsr_status': itsr_status
        })
        
        # If parameters provided, perform search
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
                # Search by handler
                if itsr_status:
                    # When ITSR Status is selected: show complete tickets with matching ITSR status
                    query = ITSR_Network.objects.filter(
                        handler=handler,
                        ticket_status='complete',
                        itsr_status=itsr_status
                    )
                else:
                    # Default: show incomplete tickets
                    query = ITSR_Network.objects.filter(
                        handler=handler,
                        ticket_status='incomplete'
                    )
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
                'has_results': len(tickets_with_files) > 0
            }
            
            return render(request, 'ticket_detail_search.html', context)
        
        return render(request, 'ticket_detail_search.html', {'form': form})
