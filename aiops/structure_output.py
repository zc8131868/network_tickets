from openai import OpenAI
from pydantic import BaseModel
from typing import List
from pprint import pprint

import os
from openai import OpenAI

# aihubmix_apikey = os.getenv('AIHUBMIX_APIKEY')

aihubmix_apikey = os.environ.get('AIHUBMIX')

client = OpenAI(api_key=aihubmix_apikey, base_url="https://aihubmix.com/v1")

class CiscoInterface(BaseModel):
    interface: str
    ip_address: str
    ok: bool
    method: str
    status: str
    protocol: str

class CiscoShowIpInterfaceBrief(BaseModel):
    interfaces: List[CiscoInterface]
"""
{'interfaces': [{'interface': 'GigabitEthernet1',
                 'ip_address': '196.21.5.211',
                 'method': 'NVRAM',
                 'ok': True,
                 'protocol': 'up',
                 'status': 'up'},
                {'interface': 'GigabitEthernet2',
                 'ip_address': '10.1.1.1',
                 'method': 'NVRAM',
                 'ok': True,
                 'protocol': 'up',
                 'status': 'up'},
                {'interface': 'GigabitEthernet3',
                 'ip_address': '20.1.1.1',
                 'method': 'manual',
                 'ok': True,
                 'protocol': 'down',
                 'status': 'administratively down'}]}
"""
show_ip_interface_brief = """
Interface              IP-Address      OK? Method Status                Protocol
GigabitEthernet1       196.21.5.211    YES NVRAM  up                    up
GigabitEthernet2       10.1.1.1        YES NVRAM  up                    up
GigabitEthernet3       20.1.1.1        YES manual administratively down down
"""

# show_ip_interface_brief = """
# 你好啊
# """

response = client.responses.parse(
    model='gpt-5-nano',
    input=[
        {
            "role": "system",
            "content": "你是一个专业的网络工程师，请根据给定的文本，提取出Cisco路由器的所有接口信息，并以列表形式返回给用户。",
        },
        {"role": "user", "content": show_ip_interface_brief},
    ],
    text_format=CiscoShowIpInterfaceBrief,
)

cisco_interfaces = response.output_parsed
pprint(cisco_interfaces.model_dump())
print('--------------------------------')
print(cisco_interfaces)

for interface in cisco_interfaces.interfaces:
    print(f"接口: {interface.interface:<20} IP: {interface.ip_address:<15} 状态: {interface.status:<30} 协议: {interface.protocol:<10}")