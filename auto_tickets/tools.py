import ipaddress
import math
import django
import os
import sys

# Add the parent directory to Python path so we can import network_tickets.settings
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'network_tickets.settings')
django.setup()
from auto_tickets.models import IPDB, IP_Application, PA_Service


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


def get_device(ip_input):
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
                device = IPDB.objects.get(ip=subnet.network_address).device
                return device
        
    except (ValueError, ipaddress.AddressValueError):
        return None 


def tickets_split(source_ip, destination_ip):

    '''
    DMZ SW01: SN OAM, AliCloud,AliCloud-Mylink
    DMZ SW02: NewPrivateCloud, PrivateCloud, SN PCloud
    M09-CORE-SW01: PrivateCloud
    M09-EXT-CORE-SW1: PrivateCloud
    M09-INT-SW01: PrivateCloud
    M09-SB-SW01: South Base
    PA: South Base
    T01-DR-CORE-SW01: PrivateCloud-GNC
    '''

    source_location = get_location(source_ip)
    destination_location = get_location(destination_ip)
    
    source_device = get_device(source_ip)
    destination_device = get_device(destination_ip)

    # Check if we got valid locations
    if source_location is None or destination_location is None:
        return 'Unknown IP. Please report to IT, thank you.'
     #DMZ SW01
    if source_device == 'DMZ SW01' and destination_device == 'DMZ SW02':
        if source_location == 'SN OAM' and destination_location == 'NewPrivateCloud':
            return f'{source_ip} belongs to SN OAM, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n'
        elif source_location == 'SN OAM' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to SN OAM, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n'
        elif source_location == 'SN OAM' and destination_location == 'SN PCloud':
            return f'{source_ip} belongs to SN OAM, {destination_ip} belongs to SN PCloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n'
        elif source_location == 'AliCloud' and destination_location == 'NewPrivateCloud':
            return f'{source_ip} belongs to AliCloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)AliCloud'
        elif source_location == 'AliCloud' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to AliCloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)AliCloud'
        elif source_location == 'AliCloud' and destination_location == 'SN PCloud':
            return f'{source_ip} belongs to AliCloud, {destination_ip} belongs to SN PCloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)AliCloud'
        elif source_location == 'AliCloud-Mylink' and destination_location == 'NewPrivateCloud':
            return f'{source_ip} belongs to AliCloud-Mylink, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)AliCloud'
        elif source_location == 'AliCloud-Mylink' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to AliCloud-Mylink, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)AliCloud'
        elif source_location == 'AliCloud-Mylink' and destination_location == 'SN PCloud':
            return f'{source_ip} belongs to AliCloud-Mylink, {destination_ip} belongs to SN PCloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)AliCloud'
    
    elif source_device == 'DMZ SW01' and destination_device == 'M09-CORE-SW01':
        if source_location == 'SN OAM' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to SN OAM, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR'
        elif source_location == 'AliCloud' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to AliCloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR\n 4)AliCloud'
        elif source_location == 'AliCloud-Mylink' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to AliCloud-Mylink, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR\n 4)AliCloud'
        elif source_location == 'AliCloud-Mylink' and destination_location == 'SN PCloud':
            return f'{source_ip} belongs to AliCloud-Mylink, {destination_ip} belongs to SN PCloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR\n 4)AliCloud'

    elif source_device == 'DMZ SW01' and destination_device == 'M09-EXT-CORE-SW1':
        if source_location == 'SN OAM' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to SN OAM, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR'
        elif source_location == 'AliCloud' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to AliCloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR\n 4)AliCloud'
        elif source_location == 'AliCloud-Mylink' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to AliCloud-Mylink, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR\n 3)AliCloud'

    elif source_device == 'DMZ SW01' and destination_device == 'M09-INT-SW01':
        if source_location == 'SN OAM' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to SN OAM, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR'
        elif source_location == 'AliCloud' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to AliCloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR\n 4)AliCloud'
        elif source_location == 'AliCloud-Mylink' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to AliCloud-Mylink, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR\n 3)AliCloud'

    elif source_device == 'DMZ SW01' and destination_device == 'M09-SB-SW01':
        if source_location == 'SN OAM' and destination_location == 'South Base':
            return f'{source_ip} belongs to SN OAM, {destination_ip} belongs to South Base. Tickets contain: \n 1)EOMS-SN \n 2)ITSR\n 3)South Base (IT will provide support)'
        elif source_location == 'AliCloud' and destination_location == 'South Base':
            return f'{source_ip} belongs to AliCloud, {destination_ip} belongs to South Base. Tickets contain: \n 1)EOMS-SN \n 2)ITSR\n 3)South Base (IT will provide support)\n 4)AliCloud'
        # elif source_location == 'AliCloud-Mylink' and destination_location == 'South Base':
        #     return f'{source_ip} belongs to AliCloud-Mylink, {destination_ip} belongs to South Base. Tickets contain: \n 1)EOMS-SN \n 2)ITSR\n 3)South Base (IT will provide support)\n 4)AliCloud'

    elif source_device == 'DMZ SW01' and destination_device == 'PA':
        if source_location == 'SN OAM' and destination_location == 'South Base':
            return f'{source_ip} belongs to SN OAM, {destination_ip} belongs to South Base. Tickets contain: \n 1)EOMS-SN \n 2)ITSR\n 3)South Base (IT will provide support)'
        elif source_location == 'AliCloud' and destination_location == 'South Base':
            return f'{source_ip} belongs to AliCloud, {destination_ip} belongs to South Base. Tickets contain: \n 1)EOMS-SN \n 2)ITSR\n 3)South Base (IT will provide support)\n 4)AliCloud'
        # elif source_location == 'AliCloud-Mylink' and destination_location == 'South Base':
        #     return f'{source_ip} belongs to AliCloud-Mylink, {destination_ip} belongs to South Base. Tickets contain: \n 1)EOMS-SN \n 2)ITSR\n 3)South Base (IT will provide support)\n 4)AliCloud'

    elif source_device == 'DMZ SW01' and destination_device == 'T01-DR-CORE-SW01':
        if source_location == 'SN OAM' and destination_location == 'PrivateCloud-GNC':
            return f'{source_ip} belongs to SN OAM, {destination_ip} belongs to PrivateCloud-GNC. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR'
        elif source_location == 'AliCloud' and destination_location == 'PrivateCloud-GNC':
            return f'{source_ip} belongs to AliCloud, {destination_ip} belongs to PrivateCloud-GNC. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR\n 4)AliCloud'
        elif source_location == 'AliCloud-Mylink' and destination_location == 'PrivateCloud-GNC':
            return f'{source_ip} belongs to AliCloud-Mylink, {destination_ip} belongs to PrivateCloud-GNC. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR\n 3)AliCloud'
            
    elif source_device == 'DMZ SW02' and destination_device == 'M09-CORE-SW01':
        if source_location == 'SN PCloud' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to SN PCloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR'
        elif source_location == 'PrivateCloud' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'
        elif source_location == 'NewPrivateCloud' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to NewPrivateCloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'

    elif source_device == 'DMZ SW02' and destination_device == 'M09-EXT-CORE-SW1':
        if source_location == 'SN PCloud' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to SN PCloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR'
        elif source_location == 'PrivateCloud' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'
        elif source_location == 'NewPrivateCloud' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to NewPrivateCloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'
        
    elif source_device == 'DMZ SW02' and destination_device == 'M09-INT-SW01':
        if source_location == 'SN PCloud' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to SN PCloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR'
        elif source_location == 'PrivateCloud' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'
        elif source_location == 'NewPrivateCloud' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to NewPrivateCloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'

    elif source_device == 'DMZ SW02' and destination_device == 'M09-SB-SW01':
        if source_location == 'SN PCloud' and destination_location == 'South Base':
            return f'{source_ip} belongs to SN PCloud, {destination_ip} belongs to South Base. Tickets contain: \n 1)EOMS-SN \n 2)ITSR\n 3)South Base (IT will provide support)'
        elif source_location == 'PrivateCloud' and destination_location == 'South Base':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to South Base. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR\n 3)South Base (IT will provide support)'
        elif source_location == 'NewPrivateCloud' and destination_location == 'South Base':
            return f'{source_ip} belongs to NewPrivateCloud, {destination_ip} belongs to South Base. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR\n 3)South Base (IT will provide support)'

    elif source_device == 'DMZ SW02' and destination_device == 'PA':
        if source_location == 'SN PCloud' and destination_location == 'South Base':
            return f'{source_ip} belongs to SN PCloud, {destination_ip} belongs to South Base. Tickets contain: \n 1)EOMS-SN \n 2)ITSR\n 3)South Base (IT will provide support)'
        elif source_location == 'PrivateCloud' and destination_location == 'South Base':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to South Base. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR\n 3)South Base (IT will provide support)'
        elif source_location == 'NewPrivateCloud' and destination_location == 'South Base':
            return f'{source_ip} belongs to NewPrivateCloud, {destination_ip} belongs to South Base. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR\n 3)South Base (IT will provide support)'

    elif source_device == 'DMZ SW02' and destination_device == 'T01-DR-CORE-SW01':
        if source_location == 'SN PCloud' and destination_location == 'PrivateCloud-GNC':
            return f'{source_ip} belongs to SN PCloud, {destination_ip} belongs to PrivateCloud-GNC. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR'
        elif source_location == 'PrivateCloud' and destination_location == 'PrivateCloud-GNC':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to PrivateCloud-GNC. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'    
        elif source_location == 'NewPrivateCloud' and destination_location == 'PrivateCloud-GNC':
            return f'{source_ip} belongs to NewPrivateCloud, {destination_ip} belongs to PrivateCloud-GNC. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'

    elif source_device == 'M09-CORE-SW01' and destination_device == 'M09-EXT-CORE-SW1':
        if source_location == 'PrivateCloud' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'
    
    elif source_device == 'M09-CORE-SW01' and destination_device == 'M09-INT-SW01':
        if source_location == 'PrivateCloud' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'
    
    elif source_device == 'M09-CORE-SW01' and destination_device == 'M09-SB-SW01':
        if source_location == 'PrivateCloud' and destination_location == 'South Base':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to South Base. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR\n 3)South Base (IT will provide support)'
    
    elif source_device == 'M09-CORE-SW01' and destination_device == 'PA':
        if source_location == 'PrivateCloud' and destination_location == 'South Base':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to South Base. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR\n 3)South Base (IT will provide support)'
    
    elif source_device == 'M09-CORE-SW01' and destination_device == 'T01-DR-CORE-SW01':
        if source_location == 'PrivateCloud' and destination_location == 'PrivateCloud-GNC':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to PrivateCloud-GNC. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'
    
    elif source_device == 'M09-EXT-CORE-SW1' and destination_device == 'M09-INT-SW01':
        if source_location == 'PrivateCloud' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'
    
    elif source_device == 'M09-EXT-CORE-SW1' and destination_device == 'M09-SB-SW01':
        if source_location == 'PrivateCloud' and destination_location == 'South Base':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to South Base. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR\n 3)South Base (IT will provide support)'
    
    elif source_device == 'M09-EXT-CORE-SW1' and destination_device == 'PA':
        if source_location == 'PrivateCloud' and destination_location == 'South Base':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to South Base. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR\n 3)South Base (IT will provide support)'
    
    elif source_device == 'M09-EXT-CORE-SW1' and destination_device == 'T01-DR-CORE-SW01':
        if source_location == 'PrivateCloud' and destination_location == 'PrivateCloud-GNC':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to PrivateCloud-GNC. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'
    
    elif source_device == 'M09-INT-SW01' and destination_device == 'M09-SB-SW01':
        if source_location == 'PrivateCloud' and destination_location == 'South Base':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to South Base. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR\n 3)South Base (IT will provide support)'
    
    elif source_device == 'M09-INT-SW01' and destination_device == 'PA':
        if source_location == 'PrivateCloud' and destination_location == 'South Base':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to South Base. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR\n 3)South Base (IT will provide support)'
    
    elif source_device == 'M09-INT-SW01' and destination_device == 'T01-DR-CORE-SW01':
        if source_location == 'PrivateCloud' and destination_location == 'PrivateCloud-GNC':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to PrivateCloud-GNC. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'
    
    elif source_device == 'M09-SB-SW01' and destination_device == 'T01-DR-CORE-SW01':
        if source_location == 'South Base' and destination_location == 'PrivateCloud-GNC':
            return f'{source_ip} belongs to South Base, {destination_ip} belongs to PrivateCloud-GNC. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'
    
    elif source_device == 'PA' and destination_device == 'T01-DR-CORE-SW01':
        if source_location == 'South Base' and destination_location == 'PrivateCloud-GNC':
            return f'{source_ip} belongs to South Base, {destination_ip} belongs to PrivateCloud-GNC. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'

    # Reversed device combinations
    elif source_device == 'DMZ SW02' and destination_device == 'DMZ SW01':
        if source_location == 'NewPrivateCloud' and destination_location == 'SN OAM':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to SN OAM. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n'
        elif source_location == 'PrivateCloud' and destination_location == 'SN OAM':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to SN OAM. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n'
        elif source_location == 'SN PCloud' and destination_location == 'SN OAM':
            return f'{source_ip} belongs to SN PCloud, {destination_ip} belongs to SN OAM. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n'
        elif source_location == 'NewPrivateCloud' and destination_location == 'AliCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to AliCloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)AliCloud'
        elif source_location == 'PrivateCloud' and destination_location == 'AliCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to AliCloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)AliCloud'
        elif source_location == 'SN PCloud' and destination_location == 'AliCloud':
            return f'{source_ip} belongs to SN PCloud, {destination_ip} belongs to AliCloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)AliCloud'


    elif source_device == 'M09-CORE-SW01' and destination_device == 'DMZ SW01':
        if source_location == 'PrivateCloud' and destination_location == 'SN OAM':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to SN OAM. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR'
        elif source_location == 'PrivateCloud' and destination_location == 'AliCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to AliCloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR\n 4)AliCloud'
        elif source_location == 'PrivateCloud' and destination_location == 'AliCloud-Mylink':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to AliCloud-Mylink. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR\n 3)AliCloud'

    elif source_device == 'M09-EXT-CORE-SW1' and destination_device == 'DMZ SW01':
        if source_location == 'PrivateCloud' and destination_location == 'SN OAM':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to SN OAM. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR'
        elif source_location == 'PrivateCloud' and destination_location == 'AliCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to AliCloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR\n 4)AliCloud'
        elif source_location == 'PrivateCloud' and destination_location == 'AliCloud-Mylink':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to AliCloud-Mylink. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR\n 3)AliCloud'

    elif source_device == 'M09-INT-SW01' and destination_device == 'DMZ SW01':
        if source_location == 'PrivateCloud' and destination_location == 'SN OAM':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to SN OAM. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR'
        elif source_location == 'PrivateCloud' and destination_location == 'AliCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to AliCloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR\n 4)AliCloud'
        elif source_location == 'PrivateCloud' and destination_location == 'AliCloud-Mylink':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to AliCloud-Mylink. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR\n 3)AliCloud'

    elif source_device == 'M09-SB-SW01' and destination_device == 'DMZ SW01':
        if source_location == 'South Base' and destination_location == 'SN OAM':
            return f'{source_ip} belongs to South Base, {destination_ip} belongs to SN OAM. Tickets contain: \n 1)EOMS-SN \n 2)ITSR\n 3)South Base (IT will provide support)'
        elif source_location == 'South Base' and destination_location == 'AliCloud':
            return f'{source_ip} belongs to South Base, {destination_ip} belongs to AliCloud. Tickets contain: \n 1)EOMS-SN \n 2)ITSR\n 3)South Base (IT will provide support)\n 4)AliCloud'
        # elif source_location == 'South Base' and destination_location == 'AliCloud-Mylink':
        #     return f'{source_ip} belongs to South Base, {destination_ip} belongs to AliCloud-Mylink. Tickets contain: \n 1)EOMS-SN \n 2)ITSR\n 3)South Base (IT will provide support)\n 4)AliCloud'

    elif source_device == 'PA' and destination_device == 'DMZ SW01':
        if source_location == 'South Base' and destination_location == 'SN OAM':
            return f'{source_ip} belongs to South Base, {destination_ip} belongs to SN OAM. Tickets contain: \n 1)EOMS-SN \n 2)ITSR\n 3)South Base (IT will provide support)'
        elif source_location == 'South Base' and destination_location == 'AliCloud':
            return f'{source_ip} belongs to South Base, {destination_ip} belongs to AliCloud. Tickets contain: \n 1)EOMS-SN \n 2)ITSR\n 3)South Base (IT will provide support)\n 4)AliCloud'
        # elif source_location == 'South Base' and destination_location == 'AliCloud-Mylink':
        #     return f'{source_ip} belongs to South Base, {destination_ip} belongs to AliCloud-Mylink. Tickets contain: \n 1)EOMS-SN \n 2)ITSR\n 3)South Base (IT will provide support)\n 4)AliCloud'

    elif source_device == 'T01-DR-CORE-SW01' and destination_device == 'DMZ SW01':
        if source_location == 'PrivateCloud-GNC' and destination_location == 'SN OAM':
            return f'{source_ip} belongs to PrivateCloud-GNC, {destination_ip} belongs to SN OAM. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR'
        elif source_location == 'PrivateCloud-GNC' and destination_location == 'AliCloud':
            return f'{source_ip} belongs to PrivateCloud-GNC, {destination_ip} belongs to AliCloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR\n 4)AliCloud'
        elif source_location == 'PrivateCloud-GNC' and destination_location == 'AliCloud-Mylink':
            return f'{source_ip} belongs to PrivateCloud-GNC, {destination_ip} belongs to AliCloud-Mylink. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR\n 3)AliCloud'

    elif source_device == 'M09-CORE-SW01' and destination_device == 'DMZ SW02':
        if source_location == 'PrivateCloud' and destination_location == 'SN PCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to SN PCloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR'
        elif source_location == 'PrivateCloud' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'
        elif source_location == 'PrivateCloud' and destination_location == 'NewPrivateCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to NewPrivateCloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'

    elif source_device == 'M09-EXT-CORE-SW1' and destination_device == 'DMZ SW02':
        if source_location == 'PrivateCloud' and destination_location == 'SN PCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to SN PCloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR'
        elif source_location == 'PrivateCloud' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'
        elif source_location == 'PrivateCloud' and destination_location == 'NewPrivateCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to NewPrivateCloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'
        
    elif source_device == 'M09-INT-SW01' and destination_device == 'DMZ SW02':
        if source_location == 'PrivateCloud' and destination_location == 'SN PCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to SN PCloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR'
        elif source_location == 'PrivateCloud' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'
        elif source_location == 'PrivateCloud' and destination_location == 'NewPrivateCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to NewPrivateCloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'

    elif source_device == 'M09-SB-SW01' and destination_device == 'DMZ SW02':
        if source_location == 'South Base' and destination_location == 'SN PCloud':
            return f'{source_ip} belongs to South Base, {destination_ip} belongs to SN PCloud. Tickets contain: \n 1)EOMS-SN \n 2)ITSR\n 3)South Base (IT will provide support)'
        elif source_location == 'South Base' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to South Base, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR\n 3)South Base (IT will provide support)'
        elif source_location == 'South Base' and destination_location == 'NewPrivateCloud':
            return f'{source_ip} belongs to South Base, {destination_ip} belongs to NewPrivateCloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR\n 3)South Base (IT will provide support)'

    elif source_device == 'PA' and destination_device == 'DMZ SW02':
        if source_location == 'South Base' and destination_location == 'SN PCloud':
            return f'{source_ip} belongs to South Base, {destination_ip} belongs to SN PCloud. Tickets contain: \n 1)EOMS-SN \n 2)ITSR\n 3)South Base (IT will provide support)'
        elif source_location == 'South Base' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to South Base, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR\n 3)South Base (IT will provide support)'
        elif source_location == 'South Base' and destination_location == 'NewPrivateCloud':
            return f'{source_ip} belongs to South Base, {destination_ip} belongs to NewPrivateCloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR\n 3)South Base (IT will provide support)'

    elif source_device == 'T01-DR-CORE-SW01' and destination_device == 'DMZ SW02':
        if source_location == 'PrivateCloud-GNC' and destination_location == 'SN PCloud':
            return f'{source_ip} belongs to PrivateCloud-GNC, {destination_ip} belongs to SN PCloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN \n 3)ITSR'
        elif source_location == 'PrivateCloud-GNC' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to PrivateCloud-GNC, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'    
        elif source_location == 'PrivateCloud-GNC' and destination_location == 'NewPrivateCloud':
            return f'{source_ip} belongs to PrivateCloud-GNC, {destination_ip} belongs to NewPrivateCloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'

    elif source_device == 'M09-EXT-CORE-SW1' and destination_device == 'M09-CORE-SW01':
        if source_location == 'PrivateCloud' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'
    
    elif source_device == 'M09-INT-SW01' and destination_device == 'M09-CORE-SW01':
        if source_location == 'PrivateCloud' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'
    
    elif source_device == 'M09-SB-SW01' and destination_device == 'M09-CORE-SW01':
        if source_location == 'South Base' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to South Base, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR\n 3)South Base (IT will provide support)'
    
    elif source_device == 'PA' and destination_device == 'M09-CORE-SW01':
        if source_location == 'South Base' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to South Base, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR\n 3)South Base (IT will provide support)'
    
    elif source_device == 'T01-DR-CORE-SW01' and destination_device == 'M09-CORE-SW01':
        if source_location == 'PrivateCloud-GNC' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to PrivateCloud-GNC, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'
    
    elif source_device == 'M09-INT-SW01' and destination_device == 'M09-EXT-CORE-SW1':
        if source_location == 'PrivateCloud' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'
    
    elif source_device == 'M09-SB-SW01' and destination_device == 'M09-EXT-CORE-SW1':
        if source_location == 'South Base' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to South Base, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR\n 3)South Base (IT will provide support)'
    
    elif source_device == 'PA' and destination_device == 'M09-EXT-CORE-SW1':
        if source_location == 'South Base' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to South Base, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR\n 3)South Base (IT will provide support)'
    
    elif source_device == 'T01-DR-CORE-SW01' and destination_device == 'M09-EXT-CORE-SW1':
        if source_location == 'PrivateCloud-GNC' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to PrivateCloud-GNC, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'
    
    elif source_device == 'M09-SB-SW01' and destination_device == 'M09-INT-SW01':
        if source_location == 'South Base' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to South Base, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR\n 3)South Base (IT will provide support)'
    
    elif source_device == 'PA' and destination_device == 'M09-INT-SW01':
        if source_location == 'South Base' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to South Base, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR\n 3)South Base (IT will provide support)'
    
    elif source_device == 'T01-DR-CORE-SW01' and destination_device == 'M09-INT-SW01':
        if source_location == 'PrivateCloud-GNC' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to PrivateCloud-GNC, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'
    
    elif source_device == 'T01-DR-CORE-SW01' and destination_device == 'M09-SB-SW01':
        if source_location == 'PrivateCloud-GNC' and destination_location == 'South Base':
            return f'{source_ip} belongs to PrivateCloud-GNC, {destination_ip} belongs to South Base. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'
    
    elif source_device == 'T01-DR-CORE-SW01' and destination_device == 'PA':
        if source_location == 'PrivateCloud-GNC' and destination_location == 'South Base':
            return f'{source_ip} belongs to PrivateCloud-GNC, {destination_ip} belongs to South Base. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'
    
    # Additional missing reversed combinations
    elif source_device == 'M09-SB-SW01' and destination_device == 'T01-DR-CORE-SW01':
        if source_location == 'South Base' and destination_location == 'PrivateCloud-GNC':
            return f'{source_ip} belongs to South Base, {destination_ip} belongs to PrivateCloud-GNC. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'
    
    elif source_device == 'PA' and destination_device == 'T01-DR-CORE-SW01':
        if source_location == 'South Base' and destination_location == 'PrivateCloud-GNC':
            return f'{source_ip} belongs to South Base, {destination_ip} belongs to PrivateCloud-GNC. Tickets contain: \n 1)EOMS-Cloud \n 2)ITSR'
    
    # Self-to-self combinations (same device to same device)
    elif source_device == 'DMZ SW01' and destination_device == 'DMZ SW01':
        if source_location == 'SN OAM' and destination_location == 'SN OAM':
            return f'{source_ip} belongs to SN OAM, {destination_ip} belongs to SN OAM. Tickets contain: \n 1)EOMS-SN'
        elif source_location == 'AliCloud' and destination_location == 'AliCloud':
            return f'{source_ip} belongs to AliCloud, {destination_ip} belongs to AliCloud. Tickets contain: \n 1)AliCloud'
        elif source_location == 'AliCloud-Mylink' and destination_location == 'AliCloud-Mylink':
            return f'{source_ip} belongs to AliCloud-Mylink, {destination_ip} belongs to AliCloud-Mylink. Tickets contain: \n 1)AliCloud'
        elif source_location == 'SN OAM' and destination_location == 'AliCloud':
            return f'{source_ip} belongs to SN OAM, {destination_ip} belongs to AliCloud. Tickets contain: \n 1)EOMS-SN \n 2)AliCloud'
        elif source_location == 'AliCloud' and destination_location == 'SN OAM':
            return f'{source_ip} belongs to AliCloud, {destination_ip} belongs to SN OAM. Tickets contain: \n 1)EOMS-SN \n 2)AliCloud'
        elif source_location == 'SN OAM' and destination_location == 'AliCloud-Mylink':
            return f'{source_ip} belongs to SN OAM, {destination_ip} belongs to AliCloud-Mylink. Tickets contain: \n 1)EOMS-SN \n 2)AliCloud'
        elif source_location == 'AliCloud-Mylink' and destination_location == 'SN OAM':
            return f'{source_ip} belongs to AliCloud-Mylink, {destination_ip} belongs to SN OAM. Tickets contain: \n 1)EOMS-SN \n 2)AliCloud'
        elif source_location == 'AliCloud' and destination_location == 'AliCloud-Mylink':
            return f'{source_ip} belongs to AliCloud, {destination_ip} belongs to AliCloud-Mylink. Tickets contain: \n 1)AliCloud'
        elif source_location == 'AliCloud-Mylink' and destination_location == 'AliCloud':
            return f'{source_ip} belongs to AliCloud-Mylink, {destination_ip} belongs to AliCloud. Tickets contain: \n 1)AliCloud'
    
    elif source_device == 'DMZ SW02' and destination_device == 'DMZ SW02':
        if source_location == 'NewPrivateCloud' and destination_location == 'NewPrivateCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud'
        elif source_location == 'PrivateCloud' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud'
        elif source_location == 'SN PCloud' and destination_location == 'SN PCloud':
            return f'{source_ip} belongs to SN PCloud, {destination_ip} belongs to SN PCloud. Tickets contain: \n 1)EOMS-SN'
        elif source_location == 'NewPrivateCloud' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud'
        elif source_location == 'PrivateCloud' and destination_location == 'NewPrivateCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud'
        elif source_location == 'NewPrivateCloud' and destination_location == 'SN PCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to SN PCloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN'
        elif source_location == 'SN PCloud' and destination_location == 'NewPrivateCloud':
            return f'{source_ip} belongs to SN PCloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN'
        elif source_location == 'PrivateCloud' and destination_location == 'SN PCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to SN PCloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN'
        elif source_location == 'SN PCloud' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to SN PCloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud \n 2)EOMS-SN'
    
    elif source_device == 'M09-CORE-SW01' and destination_device == 'M09-CORE-SW01':
        if source_location == 'PrivateCloud' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud'
    
    elif source_device == 'M09-EXT-CORE-SW1' and destination_device == 'M09-EXT-CORE-SW1':
        if source_location == 'PrivateCloud' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud'
    
    elif source_device == 'M09-INT-SW01' and destination_device == 'M09-INT-SW01':
        if source_location == 'PrivateCloud' and destination_location == 'PrivateCloud':
            return f'{source_ip} belongs to Private Cloud, {destination_ip} belongs to Private Cloud. Tickets contain: \n 1)EOMS-Cloud'
    
    elif source_device == 'M09-SB-SW01' and destination_device == 'M09-SB-SW01':
        if source_location == 'South Base' and destination_location == 'South Base':
            return f'{source_ip} belongs to South Base, {destination_ip} belongs to South Base. Tickets contain: \n 1)South Base (IT will provide support)'
    
    elif source_device == 'PA' and destination_device == 'PA':
        if source_location == 'South Base' and destination_location == 'South Base':
            return f'{source_ip} belongs to South Base, {destination_ip} belongs to South Base. Tickets contain: \n 1)South Base (IT will provide support)'
    
    elif source_device == 'T01-DR-CORE-SW01' and destination_device == 'T01-DR-CORE-SW01':
        if source_location == 'PrivateCloud-GNC' and destination_location == 'PrivateCloud-GNC':
            return f'{source_ip} belongs to PrivateCloud-GNC, {destination_ip} belongs to PrivateCloud-GNC. Tickets contain: \n 1)EOMS-Cloud'
    
    else:
        return 'Unknown IP. Please report to IT, thank you.'




def generate_subnet(network, num_ip_addresses, existing_subnets=None):
    """
    Generate a subnet from a given network with enough capacity for specified IPs and check for overlaps.
    
    Args:
        network (str or ipaddress.IPv4Network/IPv6Network): The parent network
        num_ip_addresses (int): Number of IP addresses needed in the new subnet
        existing_subnets (list): List of existing subnets to check against
        
    Returns:
        ipaddress.IPv4Network/IPv6Network: The generated subnet if no overlap
        None: If no valid subnet can be generated or there's an overlap
        
    Raises:
        ValueError: If input parameters are invalid
    """
    # Validate number of IP addresses
    if not isinstance(num_ip_addresses, int) or num_ip_addresses <= 0:
        raise ValueError("Number of IP addresses must be a positive integer")
        
    # Normalize input network to ipaddress object
    if isinstance(network, str):
        network = ipaddress.ip_network(network, strict=False)
    elif not isinstance(network, (ipaddress.IPv4Network, ipaddress.IPv6Network)):
        raise ValueError("Invalid network format. Provide a string or ipaddress Network object.")
    
    # Calculate required prefix length
    # We need to account for network and broadcast addresses in IPv4 (hence +2)
    if isinstance(network, ipaddress.IPv4Network):
        required_hosts = num_ip_addresses + 2  # +2 for network and broadcast addresses
    else:  # IPv6 doesn't use broadcast addresses
        required_hosts = num_ip_addresses
    
    # Calculate minimum prefix length needed
    if required_hosts <= 1:
        prefix_length = network.max_prefixlen
    else:
        # Calculate the number of host bits needed
        host_bits = math.ceil(math.log2(required_hosts))
        prefix_length = network.max_prefixlen - host_bits
    
    # Validate prefix length
    if prefix_length <= network.prefixlen:
        raise ValueError(f"Not enough space in network {network} to accommodate {num_ip_addresses} IP addresses")
        
    if prefix_length > network.max_prefixlen:
        raise ValueError(f"Calculated prefix length ({prefix_length}) is invalid for this network type")
    
    # Initialize existing subnets list if not provided
    existing_subnets = existing_subnets or []
    
    # Convert existing subnets to ipaddress objects if they're strings
    normalized_existing = []
    for subnet in existing_subnets:
        if isinstance(subnet, str):
            normalized_existing.append(ipaddress.ip_network(subnet, strict=False))
        elif isinstance(subnet, (ipaddress.IPv4Network, ipaddress.IPv6Network)):
            normalized_existing.append(subnet)
        else:
            raise ValueError("Existing subnets must be strings or ipaddress Network objects")
    
    # Generate possible subnets and find the first available one
    for subnet in network.subnets(new_prefix=prefix_length):
        # Check if this subnet overlaps with any existing subnet
        overlap = any(subnet.overlaps(existing) for existing in normalized_existing)
        
        if not overlap:
            return subnet
            
    # If no available subnet found
    return None



import re
from netmiko import ConnectHandler


def get_nat_config(target_ip):
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

    pa_res = re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\[(\d+)\][^(]*\((\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\[(\d+)\]\)', output)
    
    return pa_res
    # for i in res:
    #     print(f'source_ip: {i[0]}')
    #     print(f'source_port: {i[1]}')
    #     print(f'destination_ip: {i[2]}')
    #     print(f'destination_port: {i[3]}')
    #     print('-' * 50)

