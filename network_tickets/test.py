# Python基础 第五天作业
# 正则表达式练习：查看linux网关

# 作业提示:
# import os
# route_n_result = os.popen("route -n").read() # 执行并返回命令的结果

# 作业标准:

# 提供完整的代码（Windows或者Linux）粘贴后注意行间距-参考作业标准
# 对打印结果进行截图




# import os
# import re

# route_n_result = os.popen("route -n").read()

# gateway = re.search(r'0\.0\.0\.0\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+0\.0\.0\.0\s+UG', route_n_result)

# print(f'网关为：{gateway.group(1)}')




# 列表作业：L2是L1的排序（由小到大）

# 作业标准:

# 提供完整的代码（Windows或者Linux）粘贴后注意行间距-参考作业标准
# 对打印结果进行截图


l1 = [4,5,7,1,3,9,0]

l2 = sorted(l1)

for i in range(len(l1)):
    print(l1[i], l2[i])
