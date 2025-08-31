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

    # def __str__(self):
    #     return f"{self.__class__.__name__}(Name: {self.name} " \
    #         f"| Direction: {self.department.department_name} " \
    #         f"| Email: {self.mail} " \
    #         f"| Phone: {self.phone_number})"


# # 部门
# class Department(models.Model):
#     # 部门名称
#     department_name = models.CharField(max_length=100, unique=True, verbose_name='部门名称')
#     # 部门描述
#     description = models.CharField(max_length=100, blank=True, null=True, verbose_name='部门描述')
#     # 老师
#     teacher = models.OneToOneField(Teacher,
#                                    related_name='department',
#                                    blank=True,
#                                    null=True,
#                                    on_delete=models.SET_NULL,
#                                    verbose_name='老师')
#     # 特色
#     characteristic = models.CharField(max_length=100, blank=True, null=True, verbose_name='部门特色')
#     # 是否提供试验台
#     if_provide_lab = models.BooleanField(default=False, verbose_name='是否提供试验台')

#     def __str__(self):
#         return f"{self.__class__.__name__}(名称: {self.department_name} | 描述: {self.description} )"


# # 课程
# class Courses(models.Model):
#     # 部门
#     department = models.ForeignKey(Department, related_name='courses', on_delete=models.CASCADE, verbose_name='部门')
#     # 课程名称
#     course_name = models.CharField(max_length=100, unique=True, verbose_name='课程名称')
#     # 课程描述
#     description = models.CharField(max_length=100, blank=True, null=True, verbose_name='课程描述')
#     # 修改时间
#     change_datetime = models.DateTimeField(auto_now=True, verbose_name='修改时间')
#     # 创建时间
#     create_datetime = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

#     def __str__(self):
#         return f"{self.__class__.__name__}(课程名称: {self.course_name} | 部门: {self.department.department_name})"

# # 班主任
# class Banzhuren(models.Model):
#     # 班主任姓名
#     name = models.CharField(max_length=100, unique=True, verbose_name='班主任姓名')
#     # 电话号码
#     phone_number = models.CharField(max_length=11, unique=True, verbose_name='电话号码')
#     # QQ号码
#     qq_number = models.CharField(max_length=20, unique=True, verbose_name='QQ号码')
#     # 修改时间
#     change_datetime = models.DateTimeField(auto_now=True, verbose_name='修改时间')
#     # 创建时间
#     create_datetime = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

#     def get_all_students(self):
#         return [s.name for s in self.students.all()]

#     def __str__(self):
#         return f"{self.__class__.__name__}( 姓名: {self.name} | 电话: {self.phone_number} | QQ: {self.qq_number} )"

# # 学员
# class StudentsDB(models.Model):
#     name = models.CharField(max_length=100, verbose_name='学员姓名')
#     # 电话号码
#     phone_number = models.CharField(max_length=11, blank=False, unique=True, verbose_name='电话号码')
#     # QQ号码
#     qq_number = models.CharField(max_length=20, blank=False, unique=True, verbose_name='QQ号码')
#     # 邮件
#     mail = models.EmailField(max_length=100, unique=True, verbose_name='邮件')
#     # 部门
#     department = models.ForeignKey(Department, related_name='students', on_delete=models.CASCADE, verbose_name='部门')
#     # 班主任
#     banzhuren = models.ForeignKey(Banzhuren, related_name='students', on_delete=models.CASCADE, verbose_name='班主任')
#     # 缴费情况
#     payed = models.BooleanField(default=False, verbose_name='缴费情况')
#     # 修改时间
#     change_datetime = models.DateTimeField(auto_now=True, verbose_name='修改时间')
#     # 创建时间
#     create_datetime = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    # def student_dict(self):
    #     return {'id': self.id,
    #             'name': self.name,
    #             'phone_number': self.phone_number,
    #             'qq_number': self.qq_number,
    #             'mail': self.mail,
    #             'department': self.department.department_name,
    #             'banzhuren': self.banzhuren.name,
    #             'payed': '已交费' if self.payed else '未交费',
    #             'date': self.change_datetime,
    #             'delete_url': '/deletestudent/' + str(self.id)}

    # def __str__(self):
    #     return f"{self.__class__.__name__}(Name: {self.name} " \
    #         f"| Direction: {self.department.department_name} " \
    #         f"| Email: {self.mail} " \
    #         f"| Phone: {self.phone_number})"


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
    usage = models.CharField(max_length=100, unique=False, blank=True, verbose_name='Application Usage')
    number = models.IntegerField(blank=True, verbose_name='Number of IPs')
    subnet = models.CharField(max_length=100, unique=True, blank=True, verbose_name='subnet')
    create_datetime = models.DateTimeField(auto_now_add=True, verbose_name='create time')

    def __str__(self):
        return f"{self.__class__.__name__}(location: {self.location} | usage: {self.usage} | number: {self.number} | subnet: {self.subnet})"