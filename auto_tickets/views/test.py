import re
from netmiko import ConnectHandler
from time import sleep
import openpyxl

def auto_tickets_pa(source_ip, destination_ip, dport):
    wb = openpyxl.load_workbook('auto_tickets/views/pa_nat_policy.xlsx')
    sheet = wb['Content']

    firewall_PA = {'device_type': 'paloalto_panos',
               'host': '10.254.0.14',
               'username': 'ZhengCheng',
               'password': 'Cmhk@941'
               }
    net_connect = ConnectHandler(**firewall_PA)
    # net_connect.config_mode()

    sip_dic = {}
    dip_dic = {}
    dport_dic = {}

    sip_list = []
    dip_list = []
    dport_list = []

    pattern = r'[ ,\n]'

    start_row = 4
    end_row = sheet.max_row

    for row in range(start_row, end_row+1):
    # print(f'row: {row}')
        sip = sheet.cell(row=row, column=3).value
        dip = sheet.cell(row=row, column=5).value
        dport = sheet.cell(row=row, column=6).value

        if sip is not None:
            sip_list = re.split(pattern, sip)
            sip_dic[row] = sip_list
        else:
            raise Exception('ROW'+str(row)+' :Source IP is not defined')

        if dip is not None:
            dip_list = re.split(pattern, dip)
            dip_dic[row] = dip_list
        else:
            raise Exception('ROW'+str(row)+' :Destination IP is not defined')
            
            
        if dport is not None:
            dport_list = re.split(pattern, dport)
            dport_dic[row] = dport_list
        else:
            raise Exception('ROW'+str(row)+' :Destination Port is not defined')

        
    for sip in sip_list:
        for dip in dip_list:
            check_sip_raw = net_connect.send_command('test routing fib-lookup virtual-router vr_vsys1 ip ' + sip)
            for dport in dport_list:
                
                    
            
   






    for row in sheet.iter_rows(min_row=2, max_col=9):
        source_ip = row[2].value
        destination_ip = row[4].value
        dport = row[5].value
        auto_tickets_pa(source_ip, destination_ip, dport)
    firewall_PA = {'device_type': 'paloalto_panos',
                'host': '10.254.0.14',
                'username': 'ZhengCheng',
                'password': 'Cmhk@941'
                }
    net_connect = ConnectHandler(**firewall_PA)
    output = net_connect.send_command('show session all filter | match ' + target_ip)



    output_str = '''
                1380783      ssl            ACTIVE  FLOW  NS   172.19.1.193[64363]/Internal/6  (43.252.52.2[53865])
                1788626      ssl            ACTIVE  FLOW  NS   172.19.1.180[63100]/Internal/6  (43.252.52.2[40906])
                237626       wechat-base    ACTIVE  FLOW  NS   172.19.1.136[54176]/Internal/6  (43.252.52.2[51325])
                812034       ssl            ACTIVE  FLOW  NS   172.19.1.252[55376]/Internal/6  (43.252.52.2[9834])
                2388246      bittorrent     ACTIVE  FLOW  NS   172.19.1.224[51413]/Internal/17  (43.252.52.2[34251])
                1169254      bittorrent     ACTIVE  FLOW  NS   172.19.1.224[51413]/Internal/17  (43.252.52.2[8335])
                2249456      google-base    ACTIVE  FLOW  NS   172.19.1.237[52493]/Internal/6  (43.252.52.2[30334])
                vsys1                                          43.252.52.231[2123]/External  (43.252.52.231[2123])
                '''
    net_connect.disconnect()

    res = re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\[(\d+)\][^(]*\((\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\[(\d+)\]\)', output)
    print('Getting nat config Done')

    return res


    print('Getting nat config Done')


res = get_nat_config('43.252.52.2')
for i in res:
    print(i)
    print(f'source_ip: {i[0]}')
    print(f'source_port: {i[1]}')
    print(f'destination_ip: {i[2]}')
    print(f'destination_port: {i[3]}')
    print('-' * 50)

# sleep(5)


# def get_nat_info(target_ip = None):
#     res_list = []
#     with open('/it_network/network_tickets/media/pa-nat-policy-test.txt', 'r') as file:
#         output = file.read()
#         # print(output)
        
#         res_all = re.findall(r'^"[^"]*"[^}]*}', output, re.MULTILINE | re.DOTALL)
#         for i in res_all:
#             # Updated regex to match the actual format
#             res = re.findall(r'source\s+([^;]+);[^}]*destination\s+([^;]+);[^}]*translate-to\s+([^;]+);', i, re.MULTILINE | re.DOTALL)
#             if res:
#                 res_list.append(res[0])  # Take the first match

#         # print(len(res_list))
#         ip_list = []
#         count = 0
#         try:
#             for j in res_list:
#                 print(j)
#                 print("Policy entry:", j)
#                 source = j[0].strip()
#                 destination = j[1].strip()
#                 translate_to = j[2].strip()
#                 print(f"Source: {source}")
#                 print(f"Destination: {destination}")
#                 print(f"Translate-to: {translate_to}")
#                 count += 1
#                 print(f"Count: {count}")
#                 print("-" * 50)
#         except Exception as e:
#             print(f"Error processing entry: {e}")
#             return 'No IP found'



# a = get_nat_info()



