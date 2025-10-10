from datetime import datetime
from django.shortcuts import render
from auto_tickets.models import IPDB
# from qytdb.models import Department
# from django.contrib.auth.decorators import login_required


# @login_required()
def show_ipdb(request):
    # mytime = int(datetime.now().strftime("%w"))
    # # mytime = int(datetime.strptime('2025-04-28', '%Y-%m-%d').strftime("%w"))
    # depart_list = [c.department_name for c in Department.objects.all()]
    # teacher_list = [{'depart': c.department_name, 'teacher': c.teacher.teacher_name} for c in Department.objects.all()]
    # # return render(request, 'qyt_department_summary.html', locals())
    ipset = [i.ip for i in IPDB.objects.all()]
    maskset = [i.mask for i in IPDB.objects.all()]
    ipmask = zip(ipset, maskset)
    # ipmask = [{'ip_prefix': i.ip, 'mask': i.mask} for i in IPDB.objects.all()]
    return render(request, 'qyt_department_summary.html', {'qytsummary': 'Tickets Split!',
                                                           'ipmask': ipmask,
                                                        #    'teacher_list': teacher_list,
                                                        #    'mytime': mytime
                                                           })