#!/usr/bin/env python
"""
Test script to analyze sample_test.xlsx IPs against the IPDB database.
Run this from the Django project root: python auto_tickets/test_sample_analysis.py
Or use: python manage.py shell < auto_tickets/test_sample_analysis.py
"""

import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'network_tickets.settings')
django.setup()

from auto_tickets.tools import get_location, get_device, tickets_split

# Sample data from the Excel file (Row 4 and Row 5)
test_data = [
    {
        'row': 4,
        'source_ips': ['10.51.200.0/23', '10.51.203.0/24'],
        'dest_ip': '10.0.28.138',
        'protocol': 'UDP',
        'ports': ['3306']
    },
    {
        'row': 5,
        'source_ips': ['10.0.57.21', '10.51.203.0/24'],
        'dest_ip': '10.0.8.0/24',
        'protocol': 'TCP',
        'ports': ['3128', '3129']
    }
]

print("=" * 80)
print("SAMPLE TEST ANALYSIS")
print("=" * 80)

# First, show location and device for each unique IP
all_ips = set()
for row_data in test_data:
    all_ips.update(row_data['source_ips'])
    all_ips.add(row_data['dest_ip'])

print("\n1. IP LOCATION AND DEVICE LOOKUP")
print("-" * 80)
print(f"{'IP/Subnet':<25} {'Location':<20} {'Device':<20}")
print("-" * 80)

for ip in sorted(all_ips):
    location = get_location(ip)
    device = get_device(ip)
    print(f"{ip:<25} {str(location):<20} {str(device):<20}")

print("\n2. TICKET SPLIT RESULTS FOR EACH IP PAIR")
print("-" * 80)

cloud_data = []
sn_data = []

for row_data in test_data:
    print(f"\n--- Row {row_data['row']} ---")
    print(f"Source IPs: {row_data['source_ips']}")
    print(f"Dest IP: {row_data['dest_ip']}")
    print(f"Protocol: {row_data['protocol']}, Ports: {row_data['ports']}")
    print()
    
    for source_ip in row_data['source_ips']:
        dest_ip = row_data['dest_ip']
        
        print(f"\n  Processing: {source_ip} → {dest_ip}")
        print(f"  Source Location: {get_location(source_ip)}, Device: {get_device(source_ip)}")
        print(f"  Dest Location: {get_location(dest_ip)}, Device: {get_device(dest_ip)}")
        
        # Get ticket list
        ticket_list = tickets_split(source_ip, dest_ip, return_list=True)
        result_str = tickets_split(source_ip, dest_ip, return_list=False)
        
        print(f"\n  Ticket List: {ticket_list}")
        print(f"  Result: {result_str}")
        
        # Check for Cloud/SN
        needs_cloud = any('cloud' in t.lower() for t in ticket_list)
        needs_sn = any('sn' in t.lower() for t in ticket_list)
        
        print(f"\n  Needs Cloud Ticket: {needs_cloud}")
        print(f"  Needs SN Ticket: {needs_sn}")
        
        if needs_cloud:
            cloud_data.append({
                'source_ip': source_ip,
                'dest_ip': dest_ip,
                'ports': row_data['ports'],
                'protocol': row_data['protocol']
            })
        
        if needs_sn:
            sn_data.append({
                'source_ip': source_ip,
                'dest_ip': dest_ip,
                'ports': row_data['ports'],
                'protocol': row_data['protocol']
            })

print("\n" + "=" * 80)
print("3. SUMMARY")
print("=" * 80)

print(f"\nCloud Tickets Data ({len(cloud_data)} entries):")
for i, data in enumerate(cloud_data, 1):
    print(f"  {i}. {data['source_ip']} → {data['dest_ip']} | {data['protocol']} | {', '.join(data['ports'])}")

print(f"\nSN Tickets Data ({len(sn_data)} entries):")
for i, data in enumerate(sn_data, 1):
    print(f"  {i}. {data['source_ip']} → {data['dest_ip']} | {data['protocol']} | {', '.join(data['ports'])}")

print("\n" + "=" * 80)
print("Show Cloud Button: ", len(cloud_data) > 0)
print("Show SN Button: ", len(sn_data) > 0)
print("=" * 80)
