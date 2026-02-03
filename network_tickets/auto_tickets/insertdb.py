import openpyxl
import django
import os
import sys

# Add the parent directory to Python path so we can import network_tickets.settings
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'network_tickets.settings')
django.setup()
from auto_tickets.models import IPDB, IP_Application



file_path = '/it_network/network_tickets/auto_tickets/1.xlsx'

def insert_ip_data(file_path):
    workbook = openpyxl.load_workbook(file_path)
    sheet = workbook.active
    for row in sheet.iter_rows(min_row=1, max_col=5, values_only=True):
        ip, mask, traffic_oam, location, device = row
        IPDB.objects.create(ip=ip, mask=mask, traffic_oam=traffic_oam, location=location, device=device)
        print(ip, mask, traffic_oam, location, device)


# class IP_Application(models.Model):
#     location = models.CharField(max_length=100, unique=False, verbose_name='location')
#     # usage = models.CharField(max_length=100, unique=False, default='Traffic', verbose_name='Application Usage')
#     # number = models.IntegerField(default=6, verbose_name='Number of IPs')
#     # subnet = models.CharField(max_length=100, unique=True, default='', verbose_name='subnet')
#     usage = models.CharField(max_length=100, unique=False, blank=True, verbose_name='Application Usage')
#     number = models.IntegerField(blank=True, verbose_name='Number of IPs')
#     subnet = models.CharField(max_length=100, unique=True, blank=True, verbose_name='subnet')
#     create_datetime = models.DateTimeField(auto_now_add=True, verbose_name='create time')


if __name__ == "__main__":
    # insert_ip_data(file_path)
    # res = IPDB.objects.all()
    # for i in res:
    #     print(i.device)
    IPDB.objects.create(ip='10.51.203.0', mask='255.255.255.0', traffic_oam='NA', location='SZ-VPN', device='DMZ SW01')