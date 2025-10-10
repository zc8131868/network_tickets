from auto_tickets.forms import IPDBFORM
from auto_tickets.models import IPDB
from django.shortcuts import render
from auto_tickets.tools import get_location 
from auto_tickets.tools import tickets_split
import ipaddress
# from django.contrib.auth.decorators import permission_required

# 添加学员
# @permission_required('qytdb.add_studentsdb')
def single_split(request):
    if request.method == 'POST':
        form = IPDBFORM(request.POST)

        if form.is_valid():


            source_ip = form.cleaned_data.get('source_ip')
            destination_ip = form.cleaned_data.get('destination_ip')

            # Validate that IPs are not None
            if source_ip and destination_ip:
                result = tickets_split(source_ip, destination_ip)
            else:
                fresh_form = IPDBFORM()
                return render(request, 'qyt_department_addstudent.html', {'form': fresh_form,
                                                                        'errormessage': 'Source IP and Destination IP are required!'})

            # Create a fresh empty form to clear historical data
            fresh_form = IPDBFORM()
            return render(request, 'qyt_department_addstudent.html', {'form': fresh_form,
                                                                       'result': result,
                                                                       'successmessage': 'IP input successfully!'})
       
        else:
            return render(request, 'qyt_department_addstudent.html', {'form': form,
                                                                    'errormessage': 'IP input failed!'})

        # form = IPDBFORM(request.POST)
        # # 如果请求为POST,并且Form校验通过,把新添加的学员信息写入数据库
        # if form.is_valid():
        #     source_ip = request.POST.get('ip_prefix')
        #     destination_ip = request.POST.get('destination_ip')
        #     # student = StudentsDB(name=request.POST.get('name'),
        #     #                      phone_number=request.POST.get('phone_number'),
        #     #                      qq_number=request.POST.get('qq_number'),
        #     #                      mail=request.POST.get('mail'),
        #     #                      department=Department.objects.get(id=request.POST.get('department')),
        #     #                      banzhuren=Banzhuren.objects.get(id=request.POST.get('banzhuren')),
        #     #                      payed=request.POST.get('payed'),
        #     #                      )
        #     # student.save()
        #     # 写入成功后,显示'学员添加成功'信息!,并且显示空表单

        #     # form = StudentsForm()
        
        # else:  # 如果Form校验失败,返回客户在Form中输入的内容和报错信息
        #     # 如果检查到错误,会添加错误内容到form内,例如:<ul class="errorlist"><li>QQ号码已经存在</li></ul>
        #     return render(request, 'qyt_department_addstudent.html', {'form': form})
    else:  # 如果不是POST,就是GET,表示为初始访问, 显示表单内容给客户
        form = IPDBFORM()
        return render(request, 'qyt_department_addstudent.html', {'form': form})