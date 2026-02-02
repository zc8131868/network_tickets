from django.shortcuts import render
from django.db.models import Q
from auto_tickets.models import EOMS_Tickets
from datetime import datetime


def tickets_search(request):
    """
    View to search EOMS tickets by:
    1. Ticket number
    2. Create time (date range)
    3. Staff number (requestor)
    Displays ticket number, status, creation time, and requestor.
    """
    tickets = []
    error_message = None
    searched = False
    search_type = None
    
    if request.method == 'POST':
        searched = True
        search_type = request.POST.get('search_type', 'ticket_number')
        
        if search_type == 'ticket_number':
            ticket_number = request.POST.get('ticket_number', '').strip()
            if ticket_number:
                tickets = EOMS_Tickets.objects.filter(eoms_ticket_number__icontains=ticket_number)
                if not tickets.exists():
                    error_message = f"No tickets found matching '{ticket_number}'."
            else:
                error_message = "Please enter a ticket number."
                
        elif search_type == 'create_time':
            start_date = request.POST.get('start_date', '').strip()
            end_date = request.POST.get('end_date', '').strip()
            
            if start_date and end_date:
                try:
                    start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
                    end_datetime = datetime.strptime(end_date + ' 23:59:59', '%Y-%m-%d %H:%M:%S')
                    tickets = EOMS_Tickets.objects.filter(
                        create_datetime__gte=start_datetime,
                        create_datetime__lte=end_datetime
                    ).order_by('-create_datetime')
                    if not tickets.exists():
                        error_message = f"No tickets found between {start_date} and {end_date}."
                except ValueError:
                    error_message = "Invalid date format. Please use YYYY-MM-DD."
            else:
                error_message = "Please enter both start and end dates."
                
        elif search_type == 'staff_number':
            staff_number = request.POST.get('staff_number', '').strip().lower()
            if staff_number:
                tickets = EOMS_Tickets.objects.filter(requestor__icontains=staff_number)
                if not tickets.exists():
                    error_message = f"No tickets found for staff number '{staff_number}'."
            else:
                error_message = "Please enter a staff number."
    
    return render(request, 'tickets_search.html', {
        'tickets': tickets,
        'error_message': error_message,
        'searched': searched,
        'search_type': search_type,
    })
