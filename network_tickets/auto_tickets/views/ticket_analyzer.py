from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from datetime import datetime, timedelta
from auto_tickets.views.forms_ticket_analyzer import TicketAnalyzerForm
from auto_tickets.models import ITSR_Network
import json


@login_required
def ticket_analyzer(request):
    form = TicketAnalyzerForm(request.GET or None)
    tickets = []
    chart_data = {}
    total_count = 0
    
    if request.method == 'GET' and any(request.GET.values()):
        # Get filter parameters
        date_from = request.GET.get('date_from', '').strip()
        date_to = request.GET.get('date_to', '').strip()
        handler = request.GET.get('handler', '').strip()
        ticket_status = request.GET.get('ticket_status', '').strip()
        
        # Build query
        query = ITSR_Network.objects.all()
        
        # Date filter
        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
                query = query.filter(create_datetime__date__gte=date_from_obj)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
                # Include the entire day
                date_to_obj = date_to_obj + timedelta(days=1)
                query = query.filter(create_datetime__date__lt=date_to_obj)
            except ValueError:
                pass
        
        # Handler filter
        if handler:
            query = query.filter(handler=handler)
        
        # Ticket status filter
        if ticket_status:
            query = query.filter(ticket_status=ticket_status)
        
        # Get tickets ordered by creation date (for table display)
        tickets_queryset = query.order_by('-create_datetime')
        total_count = tickets_queryset.count()
        
        # Prepare data for pie chart - group by ticket_status
        # Use the original query (not the ordered one) to ensure proper grouping
        status_counts = query.values('ticket_status').annotate(count=Count('id')).order_by('ticket_status')
        
        chart_data = {
            'labels': [],
            'data': [],
            'colors': []
        }
        
        status_colors = {
            'complete': '#10b981',  # Green
            'incomplete': '#f59e0b',  # Amber
        }
        
        # Create a dictionary from the queried status counts
        status_dict = {item['ticket_status']: item['count'] for item in status_counts}
        
        # Get total counts for complete and incomplete
        complete_count = status_dict.get('complete', 0)
        incomplete_count = status_dict.get('incomplete', 0)
        
        # Only add statuses that have tickets (count > 0)
        for status_key, status_label in ITSR_Network.TICKET_STATUS_CHOICES:
            count = status_dict.get(status_key, 0)
            if count > 0:
                chart_data['labels'].append(status_label)
                chart_data['data'].append(count)
                chart_data['colors'].append(status_colors.get(status_key, '#6b7280'))
        
        # If no data, provide default empty structure
        if not chart_data['labels']:
            chart_data = {
                'labels': ['No Data'],
                'data': [0],
                'colors': ['#e5e7eb']
            }
        
        # Paginate tickets - 50 per page
        paginator = Paginator(tickets_queryset, 50)
        page_number = request.GET.get('page', 1)
        try:
            tickets_page = paginator.page(page_number)
        except:
            tickets_page = paginator.page(1)
        
        tickets = tickets_page
    else:
        # Create empty paginator for when no search is performed
        empty_queryset = ITSR_Network.objects.none()
        paginator = Paginator(empty_queryset, 50)
        tickets = paginator.page(1)
        complete_count = 0
        incomplete_count = 0
        chart_data = {
            'labels': ['No Data'],
            'data': [0],
            'colors': ['#e5e7eb']
        }
    
    context = {
        'form': form,
        'tickets': tickets,
        'total_count': total_count,
        'complete_count': complete_count,
        'incomplete_count': incomplete_count,
        'chart_data': json.dumps(chart_data),
        'has_results': total_count > 0
    }
    
    return render(request, 'ticket_analyzer.html', context)
