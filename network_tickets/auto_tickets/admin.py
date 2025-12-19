from django.contrib import admin

# Register your models here.

from django.contrib import admin
from .models import DownloadFile
from .models import IPDB
from .models import IP_Application
from .models import Vendor_VPN


admin.site.register(DownloadFile)
admin.site.register(IPDB)
admin.site.register(IP_Application)
admin.site.register(Vendor_VPN)


