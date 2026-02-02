from django.db import models
# Create your models here.

class IPDB(models.Model):
    
    ip = models.CharField(max_length=100, unique=True, verbose_name='IP')

    mask = models.CharField(max_length=100, unique=False, verbose_name='subnet mask')

    change_datetime = models.DateTimeField(auto_now=True, verbose_name='change time')

    create_datetime = models.DateTimeField(auto_now_add=True, verbose_name='create time')

    traffic_oam = models.CharField(max_length=100, unique=False, verbose_name='traffic oam')

    location = models.CharField(max_length=100, unique=False, verbose_name='location')

    device = models.CharField(max_length=100, unique=False, verbose_name='device')

    def __str__(self):
        return f"{self.__class__.__name__}(ip: {self.ip} | mask: {self.mask})"

    def ip_dict(self):
        return {'id': self.id,
                'ip': self.ip,
                'mask': self.mask,
                'traffic_oam': self.traffic_oam,
                'location': self.location,
                'device': self.device,
                'date': self.change_datetime}



class DownloadFile(models.Model):
    title = models.CharField(max_length=100, unique=True, verbose_name='title')
    file = models.FileField(upload_to='download_files/', verbose_name='file')
    create_datetime = models.DateTimeField(auto_now_add=True, verbose_name='create time')

    def __str__(self):
        return f"{self.__class__.__name__}(title: {self.title})"


class IP_Application(models.Model):
    location = models.CharField(max_length=100, unique=False, verbose_name='location')
    # usage = models.CharField(max_length=100, unique=False, default='Traffic', verbose_name='Application Usage')
    # number = models.IntegerField(default=6, verbose_name='Number of IPs')
    # subnet = models.CharField(max_length=100, unique=True, default='', verbose_name='subnet')
    description = models.CharField(max_length=100, unique=False, blank=True, verbose_name='description')
    usage = models.CharField(max_length=100, unique=False, blank=True, verbose_name='Application Usage')
    number = models.IntegerField(blank=True, verbose_name='Number of IPs')
    subnet = models.CharField(max_length=100, unique=True, blank=True, verbose_name='subnet')
    create_datetime = models.DateTimeField(auto_now_add=True, verbose_name='create time')

    def __str__(self):
        return f"{self.__class__.__name__}(location: {self.location} | usage: {self.usage} | number: {self.number} | subnet: {self.subnet} | description: {self.description})"


class Vendor_VPN(models.Model):
    vendor_name = models.CharField(max_length=100, unique=True, verbose_name='vendor name')
    vendor_openid = models.CharField(max_length=100, unique=True, verbose_name='vendor openid')
    create_datetime = models.DateTimeField(auto_now_add=True, verbose_name='create time')
    
    def __str__(self):
        return f"{self.__class__.__name__}(vendor_name: {self.vendor_name} | vendor_openid: {self.vendor_openid})"


class ITSR_Network(models.Model):
    HANDLER_CHOICES = [
        ('ZHENG Cheng', 'ZHENG Cheng'),
        ('Kobe', 'Kobe'),
        ('Wayne', 'Wayne'),
    ]
    
    TICKET_STATUS_CHOICES = [
        ('complete', 'Complete'),
        ('incomplete', 'Incomplete'),
    ]
    
    ITSR_STATUS_CHOICES = [
        ('open', 'Open'),
        ('closed', 'Closed'),
    ]
    
    itsr_ticket_number = models.CharField(max_length=100, unique=True, verbose_name='itsr ticket number')
    requestor = models.CharField(max_length=100, unique=False, verbose_name='requestor')
    handler = models.CharField(max_length=100, choices=HANDLER_CHOICES, verbose_name='handler')
    ticket_status = models.CharField(max_length=100, choices=TICKET_STATUS_CHOICES, verbose_name='ticket status')
    itsr_status = models.CharField(max_length=100, choices=ITSR_STATUS_CHOICES, verbose_name='itsr status')
    create_datetime = models.DateTimeField(auto_now_add=True, verbose_name='create time')
    description = models.CharField(max_length=500, unique=False, blank=True, verbose_name='description')

    def __str__(self):
        return f"{self.__class__.__name__}(itsr_ticket_number: {self.itsr_ticket_number} | requestor: {self.requestor} | handler: {self.handler} | ticket_status: {self.ticket_status} | itsr_status: {self.itsr_status})"



class EOMS_Tickets(models.Model):
    TICKET_STATUS_CHOICES = [
        ('complete', 'Complete'),
        ('incomplete', 'Incomplete'),
    ]
    
    DEPARTMENT_CHOICES = [
        ('Cloud', 'Cloud'),
        ('SN', 'SN'),
    ]

    eoms_ticket_number = models.CharField(max_length=100, unique=True, verbose_name='eoms ticket number')
    create_datetime = models.DateTimeField(auto_now_add=True, verbose_name='create time')
    ticket_status = models.CharField(max_length=100, choices=TICKET_STATUS_CHOICES, default='incomplete', verbose_name='ticket status')
    requestor = models.CharField(max_length=100, blank=True, default='', verbose_name='requestor')
    department = models.CharField(max_length=50, choices=DEPARTMENT_CHOICES, blank=True, default='', verbose_name='department')

    def save(self, *args, **kwargs):
        # Normalize requestor to lowercase for consistency
        if self.requestor:
            self.requestor = self.requestor.lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.__class__.__name__}(eoms_ticket_number: {self.eoms_ticket_number} | create_datetime: {self.create_datetime} | description: {getattr(self, 'description', '')} | attachment: {getattr(self, 'attachment', '')})"

# ---

# To create this table in your MySQL database, run the following Django management commands from your project root:

# 1. Make migrations for your app (replace 'auto_tickets' with your app name if different)
#       python manage.py makemigrations auto_tickets

# 2. Apply the migration to create the table in the database:
#       python manage.py migrate auto_tickets

# This will generate and run the SQL needed to create the EOMS_Tickets table in MySQL.
