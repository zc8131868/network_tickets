import openpyxl
import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'network_tickets.settings')
django.setup()
from auto_tickets.models import IPDB



file_path = '/network_tickets/auto_tickets/route_statistic.xlsx'

def insert_ip_data(file_path):
    workbook = openpyxl.load_workbook(file_path)
    sheet = workbook.active
    for row in sheet.iter_rows(min_row=2, max_col=5, values_only=True):
        ip, mask, traffic_oam, location, device = row
        IPDB.objects.create(ip=ip, mask=mask, traffic_oam=traffic_oam, location=location, device=device)
        print(ip, mask, traffic_oam, location, device)

if __name__ == "__main__":
    # insert_ip_data(file_path)
    res = IPDB.objects.all()
    for i in res:
        print(i.device)