from auto_tickets.forms import IPDBFORM
from auto_tickets.models import IPDB
from django.shortcuts import render
from auto_tickets.tools import get_location 
from auto_tickets.tools import tickets_split
import ipaddress
import openpyxl

def multi_split(request):
    if request.method == 'POST':
        pass
    else:
        return render(request, 'multi_split.html')