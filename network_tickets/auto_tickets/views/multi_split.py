from auto_tickets.forms_multisplit import IPDBFORM_MULTISPLIT
from auto_tickets.models import IPDB
from django.shortcuts import render
from auto_tickets.tools import get_location 
from auto_tickets.tools import tickets_split
import ipaddress
import openpyxl
import re

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
                pattern = r'[ ,\n、]'

                for row_num, row in enumerate(sheet.iter_rows(min_row=4, max_col=8), start=4):
                    try:
                        if row[2].value and row[4].value:  # Check if cells have values
                            source_ip_list = [item for item in re.split(pattern, str(row[2].value)) if item.strip()]
                            destination_ip_list = [item for item in re.split(pattern, str(row[4].value)) if item.strip()]
                            
                            for i in source_ip_list:
                                source_ip = i.strip().replace('\u200b', '')
                                judge_source_ip = re.search(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', source_ip)
                                if judge_source_ip:
                                    for destination_ip in destination_ip_list:
                                        destination_ip = destination_ip.strip().replace('\u200b', '')
                                        judge_destination_ip = re.search(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', destination_ip)
                                        if judge_destination_ip:
                                            try:
                                                result = tickets_split(source_ip, destination_ip)
                                                result_list.append(result)
                                            except Exception as e:
                                                error_msg = f"ERROR: Row {row_num} - Failed to process {source_ip} to {destination_ip}: {str(e)}"
                                                result_list.append(error_msg)
                                        else:
                                            error_msg = f"ERROR: Row {row_num} - Invalid destination IP format: {destination_ip}"
                                            result_list.append(error_msg)
                                else:
                                    error_msg = f"ERROR: Row {row_num} - Invalid source IP format: {source_ip}"
                                    result_list.append(error_msg)
                    except Exception as e:
                        error_msg = f"ERROR: Row {row_num} - Error processing row: {str(e)}"
                        result_list.append(error_msg)

                # Check if we got any results
                if result_list:
                    # Process the result list to separate errors from other messages
                    error_messages = []
                    
                    for message in result_list:
                        # More specific error detection to avoid false positives
                        if any(keyword in message.lower() for keyword in ['failed:', 'traceback:', 'validation failed', 'connection failed', 'error:']):
                            error_messages.append(message)
                    
                    # Return results with error messages
                    return render(request, 'multi_split.html', {
                        'result_list': result_list,
                        'error_messages': error_messages,
                        'has_errors': len(error_messages) > 0
                    })
                else:
                    # No results found, show error
                    form.add_error('file', 'No valid data found in the Excel file. Please check that your file has data in columns C and E starting from row 4.')
                    return render(request, 'multi_split.html', {'form': form})
            
            except Exception as e:
                # If there's an error processing the file, show the form with error
                error_msg = f'Error processing file: {str(e)}'
                form.add_error('file', error_msg)
                return render(request, 'multi_split.html', {
                    'form': form,
                    'error_messages': [error_msg],
                    'has_errors': True
                })
        else:
            # Form is not valid, render with errors
            return render(request, 'multi_split.html', {'form': form})
    else:
        form = IPDBFORM_MULTISPLIT()
        return render(request, 'multi_split.html', {'form': form})