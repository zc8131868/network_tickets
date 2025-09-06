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
                result_list = auto_tickets_pa_tools(wb)

                # Check if we got any results
                if result_list:
                    # Don't pass form when we have results - only show results
                    return render(request, 'auto_tickets_pa.html', {'result_list': result_list})
                else:
                    # No results found, show error
                    form.add_error('file', 'No valid data found in the Excel file. Please check that your file has data in columns C and E starting from row 4.')
                    return render(request, 'auto_tickets_pa.html', {'form': form})
            
            except Exception as e:
                # If there's an error processing the file, show the form with error
                form.add_error('file', f'Error processing file: {str(e)}')
                return render(request, 'auto_tickets_pa.html', {'form': form})
        else:
            # Form is not valid, render with errors
            return render(request, 'auto_tickets_pa.html', {'form': form})
    else:
        form = AutoTicketsPaForm()
        return render(request, 'auto_tickets_pa.html', {'form': form})