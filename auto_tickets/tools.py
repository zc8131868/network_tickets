import ipaddress

import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'network_tickets.settings')
django.setup()
from auto_tickets.models import IPDB


# print(network)
# print(type(network))

# ip_mask = [{'ip_prefix': '10.244.0.0', 'mask': ' 255.255.248.0'}, 
#         {'ip_prefix': '2.1.1.2', 'mask': '255.255.255.255'}]

def get_location(ip_input):
    if not ip_input:
        return None
        
    try:
        ip_mask = [{'ip_prefix': i.ip, 'mask': i.mask} for i in IPDB.objects.all()]        

        network_list = []

        for i in ip_mask:
            network = ipaddress.ip_network(f"{i['ip_prefix']}/{i['mask'].replace(' ', '')}")
            network_list.append(network)

        ip = ipaddress.ip_address(ip_input)

        for subnet in network_list:
            if ip in subnet:
                location = IPDB.objects.get(ip=subnet.network_address).location
                return location
        
    except (ValueError, ipaddress.AddressValueError):
        return None 

def tickets_split(source_ip, destination_ip):
    source_location = get_location(source_ip)
    destination_location = get_location(destination_ip)
    
    # Check if we got valid locations
    if source_location is None or destination_location is None:
        return 'Unknown IP. Please report to IT, thank you.'
     #NewPrivateCloud to South Base
    if source_location == 'NewPrivateCloud' and destination_location == 'South Base':   
        return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to South Base. Tickets contain: \n 1) ITSR \n 2)EOMS-Cloud \n 3)South Base (IT will provide support)'
    #PrivateCloud to South Base
    elif source_location == 'PrivateCloud' and destination_location == 'South Base':    
        return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to South Base. Tickets contain: \n 1) ITSR \n 2)EOMS-Cloud \n 3)South Base (IT will provide support)'
    #PrivateCloud-GNC to South Base
    elif source_location == 'PrivateCloud-GNC' and destination_location == 'South Base':    
        return f'{source_ip} belongs to Private Cloud GNC, {destination_ip} belongs to South Base. Tickets contain: \n 1) ITSR \n 2)EOMS-Cloud \n 3)South Base (IT will provide support)'
    #PrivateCloud to PrivateCloud
    elif source_location == 'PrivateCloud' and destination_location == 'PrivateCloud':
        return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud'
    #NewPrivateCloud to NewPrivateCloud
    elif source_location == 'NewPrivateCloud' and destination_location == 'NewPrivateCloud':
        return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud'
    #PrivateCloud to NewPrivateCloud
    elif source_location == 'PrivateCloud' and destination_location == 'NewPrivateCloud':
        return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud'
    #NewPrivateCloud to PrivateCloud 
    elif source_location == 'NewPrivateCloud' and destination_location == 'PrivateCloud':
        return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud'
    #NewPrivateCloud to PrivateCloud-GNC
    elif source_location == 'NewPrivateCloud' and destination_location == 'PrivateCloud-GNC':
        return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to Private Cloud GNC. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'
    #PrivateCloud-GNC to NewPrivateCloud
    elif source_location == 'PrivateCloud-GNC' and destination_location == 'NewPrivateCloud':
        return f'{source_ip} belongs to Private Cloud GNC, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'
    #PrivateCloud to PrivateCloud-GNC
    elif source_location == 'PrivateCloud' and destination_location == 'PrivateCloud-GNC':
        return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to Private Cloud GNC. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'
    #PrivateCloud-GNC to PrivateCloud
    elif source_location == 'PrivateCloud-GNC' and destination_location == 'PrivateCloud':
        return f'{source_ip} belongs to Private Cloud GNC, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'
    #PrivateCloud-GNC to PrivateCloud-GNC
    elif source_location == 'PrivateCloud-GNC' and destination_location == 'PrivateCloud-GNC':
        return f'{source_ip} belongs to Private Cloud GNC, {destination_ip} belongs to Private Cloud GNC. Tickets contain: \n 1)EOMS-Cloud'
    #NewPrivateCloud to SN OAM
    elif source_location == 'NewPrivateCloud' and destination_location == 'SN OAM':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to SN OAM. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR'
    #PrivateCloud to SN OAM
    elif source_location == 'PrivateCloud' and destination_location == 'SN OAM':
        return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to SN OAM. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR'
    #PrivateCloud-GNC to SN OAM
    elif source_location == 'PrivateCloud-GNC' and destination_location == 'SN OAM':
        return f'{source_ip} belongs to Private Cloud GNC, {destination_ip} belongs to SN OAM. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR'
    #SN OAM to NewPrivateCloud
    elif source_location == 'SN OAM' and destination_location == 'NewPrivateCloud':
        return f'{source_ip} belongs to SN OAM, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR'
    #SN OAM to PrivateCloud
    elif source_location == 'SN OAM' and destination_location == 'PrivateCloud':
        return f'{source_ip} belongs to SN OAM, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR'
    #SN OAM to PrivateCloud-GNC
    elif source_location == 'SN OAM' and destination_location == 'PrivateCloud-GNC':
        return f'{source_ip} belongs to SN OAM, {destination_ip} belongs to Private Cloud GNC. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR'
    #NewPrivateCloud to SN PCloud
    elif source_location == 'NewPrivateCloud' and destination_location == 'SN PCloud':
        return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to SN PCloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN'
    #PrivateCloud to SN PCloud
    elif source_location == 'PrivateCloud' and destination_location == 'SN PCloud':
        return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to SN PCloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN'
    #PrivateCloud-GNC to SN PCloud
    elif source_location == 'PrivateCloud-GNC' and destination_location == 'SN PCloud':
        return f'{source_ip} belongs to Private Cloud GNC, {destination_ip} belongs to SN PCloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR'
    #SN PCloud to NewPrivateCloud
    elif source_location == 'SN PCloud' and destination_location == 'NewPrivateCloud':
        return f'{source_ip} belongs to SN PCloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN'
    #SN PCloud to PrivateCloud
    elif source_location == 'SN PCloud' and destination_location == 'PrivateCloud':
        return f'{source_ip} belongs to SN PCloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN'
    #SN PCloud to PrivateCloud-GNC
    elif source_location == 'SN PCloud' and destination_location == 'PrivateCloud-GNC':
        return f'{source_ip} belongs to SN PCloud, {destination_ip} belongs to Private Cloud GNC. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR'
    #NewPrivateCloud to AliCloud
    elif source_location == 'NewPrivateCloud' and destination_location == 'AliCloud':
        return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to AliCloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)AliCloud'
    #PrivateCloud to AliCloud
    elif source_location == 'PrivateCloud' and destination_location == 'AliCloud':
        return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to AliCloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)AliCloud'
    #PrivateCloud-GNC to AliCloud
    elif source_location == 'PrivateCloud-GNC' and destination_location == 'AliCloud':
        return f'{source_ip} belongs to Private Cloud GNC, {destination_ip} belongs to AliCloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR \n 3)EOMS-SN \n 4)AliCloud'
    #SN PCloud to AliCloud
    elif source_location == 'SN PCloud' and destination_location == 'AliCloud':
        return f'{source_ip} belongs to SN PCloud, {destination_ip} belongs to AliCloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)AliCloud'
    #AliCloud to NewPrivateCloud
    elif source_location == 'AliCloud' and destination_location == 'NewPrivateCloud':
        return f'{source_ip} belongs to AliCloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)AliCloud'
    #AliCloud to PrivateCloud
    elif source_location == 'AliCloud' and destination_location == 'PrivateCloud':
        return f'{source_ip} belongs to AliCloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)AliCloud'
    #AliCloud to PrivateCloud-GNC
    elif source_location == 'AliCloud' and destination_location == 'PrivateCloud-GNC':
        return f'{source_ip} belongs to AliCloud, {destination_ip} belongs to Private Cloud GNC. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR \n 3)EOMS-SN \n 4)AliCloud'
    #AliCloud to SN PCloud
    elif source_location == 'AliCloud' and destination_location == 'SN PCloud':
        return f'{source_ip} belongs to AliCloud, {destination_ip} belongs to SN PCloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)AliCloud'
    #AliCloud to SN OAM
    elif source_location == 'AliCloud' and destination_location == 'SN OAM':
        return f'{source_ip} belongs to AliCloud, {destination_ip} belongs to SN OAM. Tickets contain: 1)EOMS-Cloud \n 2)EOMS-SN \n 3)AliCloud'
    else:
        return 'Unknown IP. Please report to IT, thank you.'



if __name__ == '__main__':
    print(get_location('10.244.0.1'))
    print(tickets_split('10.244.0.1', '10.244.0.2'))