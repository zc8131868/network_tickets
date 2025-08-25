from django import forms
from django.core.validators import RegexValidator
from auto_tickets.models import IPDB


class IPDBFORM(forms.Form):
    # 为了添加必选项前面的星号
    # 下面是模板内的内
    """
    < style type = "text/css" >
    label.required::before
    {
        content: "*";
    color: red;
    }
    < / style >
    """
    required_css_class = 'required'  # 这是Form.required_css_class属性, use to add class attributes to required rows
    # 添加效果如下
    # <label class="required" for="id_name">学员姓名:</label>
    # 不添加效果如下
    # <label for="id_name">学员姓名:</label>

    # 学员姓名,最小长度2,最大长度10,
    # label后面填写的内容,在表单中显示为名字,
    # 必选(required=True其实是默认值)
    # attrs={"class": "form-control"} 主要作用是style it in Bootstrap
    ip_regex = RegexValidator(regex=r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b',
                                message="IP地址格式不正确")  
    source_ip = forms.CharField(validators=[ip_regex],
                            max_length=15,
                            min_length=7,
                            label='Source IP',
                            required=True,
                            widget=forms.TextInput(attrs={
                               'class': "form-control",
                               'placeholder': "please input ip prefix like 192.168.1.1"
                               }))
    destination_ip = forms.CharField(validators=[ip_regex],
                            max_length=15,
                            min_length=7,
                            label='Destination IP',
                            required=True,
                            widget=forms.TextInput(attrs={
                               'class': "form-control",
                               'placeholder': "please input ip prefix like 192.168.1.1"
                               }))
    # mask = forms.CharField(validators=[ip_regex],
    #                         max_length=15,
    #                         min_length=7,
    #                         label='Mask',
    #                         required=True,
    #                         widget=forms.TextInput(attrs={
    #                            'class': "form-control",
    #                            'placeholder': "please input ip prefix like 255.255.255.0"
    #                            }))
    # 对电话号码进行校验,校验以1开头的11位数字
    # phone_regex = RegexValidator(regex=r'^1\d{10}$',
    #                              message="手机号码需要使用11位数字, 例如:'13911153335'")
                      
    # phone_number = forms.CharField(validators=[phone_regex],
    #                                min_length=11,
    #                                max_length=11,
    #                                label='手机号码',
    #                                required=True,
    #                                widget=forms.NumberInput(attrs={
    #                                    "class": "form-control",
    #                                    'placeholder': "请输入手机号码"
    #                                    }))
    # qq_regex = RegexValidator(regex=r'^\d{5,20}$',
    #                           message="QQ号码需要使用5到20位数字, 例如:'605658506'")
    # qq_number = forms.CharField(validators=[qq_regex],
    #                             min_length=5,
    #                             max_length=20,
    #                             label='QQ号码',
    #                             required=True,
    #                             widget=forms.NumberInput(attrs={
    #                                 "class": "form-control",
    #                                 'placeholder': "请输入QQ号码"
    #                                 }))
    # mail = forms.EmailField(required=False,
    #                         label='学员邮件',
    #                         widget=forms.EmailInput(attrs={
    #                             'class': "form-control",
    #                             'placeholder': "请输入学员邮件"
    #                             }))

    # department_choices = [(depart.id, depart.department_name) for depart in Department.objects.all()]
    # department = forms.CharField(max_length=10,
    #                              label='部门',
    #                              widget=forms.Select(choices=department_choices,
    #                                                  attrs={"class": "form-control"}))

    # department = forms.ModelChoiceField(
    #     label='部门',
    #     required=True,
    #     queryset=Department.objects.all(),
    #     initial=0,
    #     widget=forms.Select(attrs={"class": "form-control"})
    # )
    # banzhuren_choices = [(banzhuren.id, banzhuren.name) for banzhuren in Banzhuren.objects.all()]
    # banzhuren = forms.CharField(max_length=10,
    #                             label='班主任',
    #                             widget=forms.Select(choices=banzhuren_choices,
    #                                                 attrs={"class": "form-control"}))

    # banzhuren = forms.ModelChoiceField(
    #     label='班主任',
    #     required=True,
    #     queryset=Banzhuren.objects.all(),
    #     initial=0,
    #     widget=forms.Select(attrs={"class": "form-control"})
    # )

    # payed_choices = ((True, '已缴费'), (False, '未交费'))
    # payed = forms.BooleanField(label='缴费情况',
    #                            required=False,
    #                            widget=forms.Select(choices=payed_choices,
    #                                                attrs={"class": "form-control"}))


#uniqueness check
    # def clean_phone_number(self):  # 对电话号码的唯一性进行校验,注意格式为clean+校验变量
    #     phone_number = self.cleaned_data['phone_number']  # 提取客户输入的电话号码
    #     # 在数据库中查找是否存在这个电话号
    #     # 如果存在就显示校验错误信息
    #     if StudentsDB.objects.filter(phone_number=phone_number):
    #         raise forms.ValidationError("电话号码已经存在")
    #     # 如果校验成功就返回电话号码
    #     return phone_number

    # def clean_qq_number(self):
    #     qq_number = self.cleaned_data['qq_number']
    #     if StudentsDB.objects.filter(qq_number=qq_number):
    #         raise forms.ValidationError("QQ号码已经存在")
    #     return qq_number

    # def clean_mail(self):
    #     student_mail = self.cleaned_data.get('mail')
    #     if StudentsDB.objects.filter(mail=student_mail):
    #         raise forms.ValidationError('邮件已经存在!')
    #     return student_mail