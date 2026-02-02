from auto_tickets.forms_multisplit import IPDBFORM_MULTISPLIT
from django.shortcuts import render
from django.contrib import messages
from auto_tickets.tools import tickets_split
from auto_tickets.views.ITSR_Tools.eoms_automation import create_ticket
import openpyxl
import re
import asyncio

def multi_split(request):
    if request.method == 'POST':
        # Check if this is a ticket creation request
        if 'create_ticket' in request.POST:
            target_department = request.POST.get('target_department')
            if target_department in ['Cloud', 'SN']:
                # Validate that the selected department was actually detected in the results
                session_button_key = f'last_show_{target_department.lower()}_button'
                department_detected = request.session.get(session_button_key, False)
                
                if not department_detected:
                    messages.error(request, f'❌ Invalid request: {target_department} department was not detected in the results. Please process the file again.')
                else:
                    # Prevent duplicate submissions: check if ticket was created recently (within 30 seconds)
                    import time
                    session_key = f'ticket_creation_{target_department.lower()}_timestamp'
                    last_creation_time = request.session.get(session_key, 0)
                    current_time = time.time()
                    cooldown_seconds = 30  # 30 seconds cooldown between ticket creations
                    
                    if current_time - last_creation_time < cooldown_seconds:
                        remaining_time = int(cooldown_seconds - (current_time - last_creation_time))
                        messages.warning(request, f'⏳ Please wait {remaining_time} seconds before creating another ticket for {target_department} department. This prevents duplicate ticket creation.')
                    else:
                        try:
                            # Mark that we're creating a ticket (set timestamp before creation to prevent race conditions)
                            request.session[session_key] = current_time
                            request.session.save()
                            
                            
                            # Call create_ticket directly (async function)
                            if target_department == 'Cloud':
                                eoms_cloud_file_path = 'auto_tickets/views/EOMS_Ticket_file/eoms_cloud.xlsx'
                                cloud_requestor = request.session.get('last_cloud_requestor', '')
                                result = asyncio.run(create_ticket(target_department=target_department, file_path=eoms_cloud_file_path, originator=cloud_requestor if cloud_requestor else None))
                            elif target_department == 'SN':
                                eoms_sn_file_path = 'auto_tickets/views/EOMS_Ticket_file/eoms_sn.xlsx'
                                sn_requestor = request.session.get('last_sn_requestor', '')
                                result = asyncio.run(create_ticket(target_department=target_department, file_path=eoms_sn_file_path, originator=sn_requestor if sn_requestor else None))
                            
                            if result.get('success'):
                                inst_id = result.get('inst_id')
                                if inst_id:
                                    messages.success(request, f'✅ Ticket created successfully for {target_department} department! Ticket Number: {inst_id}')
                                else:
                                    messages.success(request, f'✅ Ticket created successfully for {target_department} department!')
                                if result.get('message'):
                                    messages.info(request, f"Message: {result.get('message')}")
                            else:
                                error_msg = result.get('error', 'Unknown error occurred')
                                messages.error(request, f'❌ Failed to create ticket for {target_department}: {error_msg}')
                                # On failure, allow retry sooner (remove the timestamp so user can try again)
                                request.session.pop(session_key, None)
                        except Exception as e:
                            messages.error(request, f'❌ Error creating ticket: {str(e)}')
                            # On exception, allow retry sooner
                            request.session.pop(session_key, None)
            
            # Redirect back to show results again
            return render(request, 'multi_split.html', {
                'result_list': request.session.get('last_result_list', []),
                'error_messages': request.session.get('last_error_messages', []),
                'has_errors': request.session.get('last_has_errors', False),
                'show_cloud_button': request.session.get('last_show_cloud_button', False),
                'show_sn_button': request.session.get('last_show_sn_button', False),
            })
        
        # Original file processing logic
        form = IPDBFORM_MULTISPLIT(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES['file']
            try:
                wb = openpyxl.load_workbook(uploaded_file)
                # sheet = wb['Content']
                sheet = wb.active
                source_ip_list = []
                destination_ip_list = []
                destination_port_list = []
                protocol_list = []
                requestor_list = []
                result_list = []
                pattern = r'[ ,\n、]'

                sn_sip_dic = {}
                sn_dip_dic = {}
                sn_dport_dic = {}
                sn_protocol_dic = {}
                sn_requestor_dic = {}

                
                cloud_sip_dic = {}
                cloud_dip_dic = {}
                cloud_dport_dic = {}
                cloud_protocol_dic = {}
                cloud_requestor_dic = {}

                # Track detected departments
                detected_cloud = False
                detected_sn = False

                cloud_num = 4
                sn_num = 4
                # Track processed IP pairs to avoid duplicates
                cloud_processed_pairs = set()
                sn_processed_pairs = set()
                
                for row_num, row in enumerate(sheet.iter_rows(min_row=4, max_col=8), start=4):
                    try:
                        if row[2].value and row[4].value and row[5].value and row[6].value:  # Check if cells have values
                            source_ip_list = [item for item in re.split(pattern, str(row[2].value)) if item.strip()]
                            destination_ip_list = [item for item in re.split(pattern, str(row[4].value)) if item.strip()]
                            destination_port_list = [item for item in re.split(pattern, str(row[5].value)) if item.strip()]
                            protocol_list = [item for item in re.split(pattern, str(row[6].value)) if item.strip()]
                            requestor_list = [item for item in re.split(pattern, str(row[7].value if row[7].value else '')) if item.strip()]
                            for i in source_ip_list:
                                source_ip = i.strip().replace('\u200b', '')
                                judge_source_ip = re.search(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', source_ip)
                                if judge_source_ip:
                                    for destination_ip in destination_ip_list:
                                        destination_ip = destination_ip.strip().replace('\u200b', '')
                                        judge_destination_ip = re.search(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', destination_ip)
                                        if judge_destination_ip:
                                            try:
                                                # Get list result first to check for Cloud/SN
                                                ticket_list = tickets_split(source_ip, destination_ip, return_list=True)
                                                
                                                # Check if Cloud or SN is needed for this IP pair
                                                needs_cloud = False
                                                needs_sn = False
                                                
                                                for ticket in ticket_list:
                                                    ticket_lower = ticket.lower()
                                                    if 'cloud' in ticket_lower:
                                                        needs_cloud = True
                                                        if not detected_cloud:
                                                            detected_cloud = True
                                                        # Also check for specific patterns
                                                        if any(keyword in ticket_lower for keyword in ['eoms-cloud', 'privatecloud', 'alicloud', 'newprivatecloud']):
                                                            detected_cloud = True

                                                    if 'sn' in ticket_lower:
                                                        needs_sn = True
                                                        if not detected_sn:
                                                            detected_sn = True
                                                        # Also check for specific patterns
                                                        if any(keyword in ticket_lower for keyword in ['sn oam', 'sn pcloud', 'eoms-sn']):
                                                            detected_sn = True
                                                
                                                # Store data per unique combination of IP pair + protocol + ports
                                                # Sort port list to ensure consistent key regardless of input order
                                                sorted_ports = sorted(destination_port_list)
                                                sorted_protocols = sorted(protocol_list)
                                                unique_key = f"{source_ip}_{destination_ip}_{','.join(sorted_protocols)}_{','.join(sorted_ports)}"
                                                
                                                if needs_cloud and unique_key not in cloud_processed_pairs:
                                                    cloud_sip_dic[cloud_num] = source_ip
                                                    cloud_dip_dic[cloud_num] = destination_ip
                                                    cloud_dport_dic[cloud_num] = destination_port_list
                                                    cloud_protocol_dic[cloud_num] = protocol_list
                                                    cloud_requestor_dic[cloud_num] = requestor_list[0] if requestor_list else ''
                                                    cloud_processed_pairs.add(unique_key)
                                                    cloud_num += 1
                                                
                                                if needs_sn and unique_key not in sn_processed_pairs:
                                                    sn_sip_dic[sn_num] = source_ip
                                                    sn_dip_dic[sn_num] = destination_ip
                                                    sn_dport_dic[sn_num] = destination_port_list
                                                    sn_protocol_dic[sn_num] = protocol_list
                                                    sn_requestor_dic[sn_num] = requestor_list[0] if requestor_list else ''
                                                    sn_processed_pairs.add(unique_key)
                                                    sn_num += 1
                                                
                                                # Get string result for display (this will print again, but that's acceptable)
                                                result_str = tickets_split(source_ip, destination_ip, return_list=False)
                                                result_list.append(result_str)
                                                
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

                #fill in the SN and Cloud ticket xlsx 
                # Write SN data - iterate through dictionary keys to ensure all data is written
                if sn_sip_dic:
                    wb_sn = openpyxl.load_workbook('auto_tickets/views/EOMS_Ticket_file/eoms_sn.xlsx')
                    sheet_sn = wb_sn.active
                    # Clear existing data rows (from row 4 onwards) to prevent duplicates and stale data
                    for row in range(4, sheet_sn.max_row + 1):
                        for col in [3, 5, 6, 7, 8]:  # Columns C, E, F, G, H
                            sheet_sn.cell(row=row, column=col).value = None
                    # Write new data
                    for row_num in sn_sip_dic.keys():
                        sheet_sn.cell(row=row_num, column=3).value = sn_sip_dic[row_num]
                        sheet_sn.cell(row=row_num, column=5).value = sn_dip_dic.get(row_num, '')
                        # Convert lists to newline-separated strings for Excel cells
                        dport_val = sn_dport_dic.get(row_num, '')
                        protocol_val = sn_protocol_dic.get(row_num, '')
                        sheet_sn.cell(row=row_num, column=6).value = '\n '.join(dport_val) if isinstance(dport_val, list) else dport_val
                        sheet_sn.cell(row=row_num, column=7).value = '\n '.join(protocol_val) if isinstance(protocol_val, list) else protocol_val
                        sheet_sn.cell(row=row_num, column=8).value = sn_requestor_dic.get(row_num, '')
                    wb_sn.save('auto_tickets/views/EOMS_Ticket_file/eoms_sn.xlsx')
                
                # Write Cloud data - iterate through dictionary keys to ensure all data is written
                if cloud_sip_dic:
                    wb_cloud = openpyxl.load_workbook('auto_tickets/views/EOMS_Ticket_file/eoms_cloud.xlsx')
                    sheet_cloud = wb_cloud.active
                    # Clear existing data rows (from row 4 onwards) to prevent duplicates and stale data
                    for row in range(4, sheet_cloud.max_row + 1):
                        for col in [3, 5, 6, 7, 8]:  # Columns C, E, F, G, H
                            sheet_cloud.cell(row=row, column=col).value = None
                    # Write new data
                    for row_num in cloud_sip_dic.keys():
                        sheet_cloud.cell(row=row_num, column=3).value = cloud_sip_dic[row_num]
                        sheet_cloud.cell(row=row_num, column=5).value = cloud_dip_dic.get(row_num, '')
                        # Convert lists to newline-separated strings for Excel cells
                        dport_val = cloud_dport_dic.get(row_num, '')
                        protocol_val = cloud_protocol_dic.get(row_num, '')
                        sheet_cloud.cell(row=row_num, column=6).value = ' \n'.join(dport_val) if isinstance(dport_val, list) else dport_val
                        sheet_cloud.cell(row=row_num, column=7).value = ' \n'.join(protocol_val) if isinstance(protocol_val, list) else protocol_val
                        sheet_cloud.cell(row=row_num, column=8).value = cloud_requestor_dic.get(row_num, '')
                    wb_cloud.save('auto_tickets/views/EOMS_Ticket_file/eoms_cloud.xlsx')
                
                
                # Check if we got any results
                if result_list:
                    # Process the result list to separate errors from other messages
                    error_messages = []
                    
                    for message in result_list:
                        # More specific error detection to avoid false positives
                        if message and any(keyword in message.lower() for keyword in ['failed:', 'traceback:', 'validation failed', 'connection failed', 'error:']):
                            error_messages.append(message)
                    
                    # Store results in session for ticket creation redirect
                    request.session['last_result_list'] = result_list
                    request.session['last_error_messages'] = error_messages
                    request.session['last_has_errors'] = len(error_messages) > 0
                    request.session['last_show_cloud_button'] = detected_cloud
                    request.session['last_show_sn_button'] = detected_sn
                    # Store first requestor for each department
                    request.session['last_cloud_requestor'] = cloud_requestor_dic.get(4, '') if cloud_requestor_dic else ''
                    request.session['last_sn_requestor'] = sn_requestor_dic.get(4, '') if sn_requestor_dic else ''
                    
                    # Return results with error messages and department detection
                    return render(request, 'multi_split.html', {
                        'result_list': result_list,
                        'error_messages': error_messages,
                        'has_errors': len(error_messages) > 0,
                        'show_cloud_button': detected_cloud,
                        'show_sn_button': detected_sn,
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