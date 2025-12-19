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


class PA_Service(models.Model):
    PROTOCOL_CHOICES = [
        ('tcp', 'TCP'),
        ('udp', 'UDP'),
    ]
    
    protocol = models.CharField(max_length=10, choices=PROTOCOL_CHOICES, verbose_name='protocol')
    port = models.CharField(max_length=100, unique=False, verbose_name='port')
    create_datetime = models.DateTimeField(auto_now_add=True, verbose_name='create time')

    def __str__(self):
        return f"{self.__class__.__name__}(protocol: {self.protocol} | port: {self.port})"


class Vendor_VPN(models.Model):
    vendor_name = models.CharField(max_length=100, unique=True, verbose_name='vendor name')
    vendor_openid = models.CharField(max_length=100, unique=True, verbose_name='vendor openid')
    create_datetime = models.DateTimeField(auto_now_add=True, verbose_name='create time')
    
    def __str__(self):
        return f"{self.__class__.__name__}(vendor_name: {self.vendor_name} | vendor_openid: {self.vendor_openid})"