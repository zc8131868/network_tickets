from auto_tickets.forms_multisplit import IPDBFORM_MULTISPLIT
from auto_tickets.models import IPDB
from django.shortcuts import render
from auto_tickets.tools import get_location 
from auto_tickets.tools import tickets_split
import ipaddress
import openpyxl

def multi_split(request):
    if request.method == 'POST':
        form = IPDBFORM_MULTISPLIT(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES['file']
            try:
                wb = openpyxl.load_workbook(uploaded_file)
                # sheet = wb['Content']
                sheet = wb.active
                source_ip_list = []
                destination_ip_list = []
                result_list = []

                for row in sheet.iter_rows(min_row=4, max_col=9):
                    if row[2].value and row[4].value:  # Check if cells have values
                        source_ip_list = row[2].value.split()
                        destination_ip_list = row[4].value.split()
                        for source_ip in source_ip_list:
                            for destination_ip in destination_ip_list:
                                result = tickets_split(source_ip, destination_ip)
                                result_list.append(result)

                # Check if we got any results
                if result_list:
                    # Don't pass form when we have results - only show results
                    return render(request, 'multi_split.html', {'result_list': result_list})
                else:
                    # No results found, show error
                    form.add_error('file', 'No valid data found in the Excel file. Please check that your file has data in columns C and E starting from row 4.')
                    return render(request, 'multi_split.html', {'form': form})
            
            except Exception as e:
                # If there's an error processing the file, show the form with error
                form.add_error('file', f'Error processing file: {str(e)}')
                return render(request, 'multi_split.html', {'form': form})
        else:
            # Form is not valid, render with errors
            return render(request, 'multi_split.html', {'form': form})
    else:
        form = IPDBFORM_MULTISPLIT()
        return render(request, 'multi_split.html', {'form': form})