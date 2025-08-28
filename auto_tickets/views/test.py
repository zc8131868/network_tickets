import openpyxl


path = '/it_network/network_tickets/auto_tickets/ITSR_sample.xlsx'

workbook = openpyxl.load_workbook(path)
sheet = workbook.active

for row in sheet.iter_rows(min_row=4, max_row=4):
    source_ip_str = row[2].value
    destination_ip = row[4].value
    # print(source_ip_list)
    # print(type(source_ip_list))
    source_ip_list = source_ip_str.split()
    print(source_ip_list)







