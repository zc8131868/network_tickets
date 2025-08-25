#通过字符串拼接的方式，打印出QYTANG'day 2014-9-28。不要忘记中间的空格。

# a = 'QYTANG\''
# b = '2014-9-28'
# c = a + 'day ' + b

# if __name__ == '__main__':
#     print(c)


# 现在有个字符串word = " scallywag"，创建一个变量sub_word，通过切片的方式获得字符串"ally"，将字符串的内容赋予sub_word。

# word = " scallywag"
# sub_word = word[3:7]

# if __name__ == '__main__':
#     print(sub_word)

#创造自己的语言 我们将在英语的基础上创建自己的语言：在单词的最后加上-，然后将单词的第一个字母拿出来放到单词的最后，然后在单词的最后加上y，例如，Python，就变成了ython-Py
#提示:试着用切片的方式完成这个小游戏。

# def game(word):
#     new_word = word[1::] +'-' + word[0] + 'y'
#     return new_word

# if __name__ == '__main__':
#     print(game('Python'))


# 完成课堂作业(1) 补齐被删除的代码

# department1 = 'Security'
# department2 = 'Python'
# depart1_m = 'cq_bomb'
# depart2_m = 'qinke'

# COURSE_FEES_SEC = 456789.12456
# COURSE_FEES_Python = 1234.3456

# line1 = 'Department1 name:%s'%department1 + '  ' + 'Manager:%s'%depart1_m + '   ' + 'COURSE FEES:%s'%COURSE_FEES_SEC + '  ' + 'The End!'
# line2 = f'Department2 name:{department2}    Manager:{depart2_m}     COURSE FEES:{COURSE_FEES_Python}     The End!'

# length = len(line1)
# print('='*length)
# print(line1)
# print(line2)
# print('='*length)


#完成课堂作业(2)  RE 匹配IP地址

import re

str1 = 'Port-channel1.189       192.168.189.254  YES    CONFIG  up'

ip = re.search(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', str1).group()

# the range of port is 1-48, the range of vlan is 1-4094
port = re.search(r'Port-channel\d{1,2}\.\d{1,4}', str1).group()

port_status = re.search(r'CONFIG\s+(\w+)', str1).group(1)

print(f'接口     :{port}\nIP地址   :{ip}\n状态     :{port_status}')







