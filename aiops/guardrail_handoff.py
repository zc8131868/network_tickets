import asyncio
import os
from agents import set_default_openai_key, set_default_openai_client, set_default_openai_key
from agents import Agent, Runner, AsyncOpenAI, OpenAIChatCompletionsModel, OpenAIResponsesModel, ModelSettings, set_tracing_disabled
from agents import (
    Agent,
    Runner,
    WebSearchTool,
    FileSearchTool,
    function_tool,
    set_tracing_disabled,
    InputGuardrail,
    GuardrailFunctionOutput,
)
from pydantic import BaseModel

aihubmix_apikey = os.environ.get("AIHUBMIX")
set_default_openai_key(aihubmix_apikey)

set_tracing_disabled(True)

external_client = AsyncOpenAI(
    api_key=aihubmix_apikey,
    base_url="https://aihubmix.com/v1/",
)

# =========== 3. 定义自定义函数（网络设备查询） ===========
@function_tool
def get_all_devices_name() -> list:
    """
    To fetch the name of all devices

    :return: 包含设备名称的列表
    """
    return ['C8Kv1', 'C8Kv2', 'Nexus1']

@function_tool
def get_device_version(device_name: str) -> str:
    """
    To fetch the version of a specific device

    :param device_name: 设备名称
    :return: 对应设备的系统版本, 如果未找到则返回 '未知版本'
    """
    device_versions = {
        'C8Kv1': 'version 11.1',
        'C8Kv2': 'version 12.2',
        'Nexus1': 'version 13.0'
    }
    return device_versions.get(device_name, '未知版本')

@function_tool
def get_device_interface_info(device_name: str) -> dict:
    """
    To fetch the interface information of a specific device, including IP address, MAC address and speed

    :param device_name: 设备名称
    :return: The interface information of the device, including ip_address, mac_address, speed
    """
    device_interfaces = {
        'C8Kv1': {"ip_address": "10.1.1.1", "mac_address": "00:11:22:33:44:55", "speed": "10G"},
        'C8Kv2': {"ip_address": "10.1.1.2", "mac_address": "00:11:22:66:BA:55", "speed": "40G"},
        'Nexus1': {"ip_address": "10.1.11.1", "mac_address": "00:11:22:78:1A:55", "speed": "100G"},
    }
    return device_interfaces.get(device_name, {device_name: '接口信息未找到'})

# =========== 4. 定义专家智能体 ===========
# (1) 通用互联网搜索智能体
web_search_agent = Agent(
    name="WebSearchAgent",
    model=OpenAIResponsesModel(
        model='gpt-4.1',
        openai_client=external_client,
        ),
    instructions="你是一个擅长使用互联网搜索的智能体。只回答需要上网搜索才能解决的通用问题。",
    tools=[WebSearchTool()],
    handoff_description="如果用户问题需要上网搜索才能回答，就把对话交给我。",
) 

# (2) 网络设备查询智能体
device_query_agent = Agent(
    name="DeviceQueryAgent",
    model=OpenAIResponsesModel(
        model='gpt-5-nano',
        openai_client=external_client,
    ),
    instructions="You are a network device expert. You can answer questions about network devices.",
    tools=[get_all_devices_name, get_device_version, get_device_interface_info],
    handoff_description="If the user's question is related to network device query, hand it over to me.",
)

# =========== 5. 新增默认智能体 (FallbackAgent) ===========
fallback_agent = Agent(
    name="FallbackAgent",
    model=OpenAIResponsesModel(
        model='gpt-5-nano',
        openai_client=external_client,
    ),
    instructions="You are a general answer agent. If no other agent can handle the user's question, hand it over to you."
)

# =========== 6. define output model ===========
class TriageCheckOutput(BaseModel):
    target_agent: str
    reasoning: str

# =========== 7. define Guardrail Agent ===========
triage_guardrail_agent = Agent(
    name="TriageGuardrailAgent",
    model=OpenAIResponsesModel(
        model='gpt-4.1',
        openai_client=external_client,
    ),
    instructions='''
    you are a guardrail agent that will decide which agent to handoff the conversation to.
    1) if the user's question is related to the internet, handoff to WebSearchAgent
    2) if the user's question is related to the network devices, like the name of the network devices, the version of the network devices, the interface information of the network devices, handoff to DeviceQueryAgent
    3) if the user's question is related to the general questions, handoff to FallbackAgent
    please output the data with json format:{'target_agent':'...', 'reasoning':'...'}
    ''',
    output_type=TriageCheckOutput,
)

async def triage_guardrail(ctx, agent, input_data):
    '''
    Decide which agent to handoff the conversation to with the triage_guardrail_agent.
    If none of the agents can handle the user's question, target_agent='None'
    tripwire_triggered=False means do not raise an exception.
    '''
    result = await Runner.run(triage_guardrail_agent, input_data, context=ctx.context)

    final_output = result.final_output_as(TriageCheckOutput)
    return GuardrailFunctionOutput(
        output_info=final_output,
        tripwire_triggered=False,
    )

# =========== 8. define Triage Agent ===========
triage_agent = Agent(
    name="TriageAgent",
    model=OpenAIResponsesModel(
        model='gpt-5-nano',
        openai_client=external_client,
    ),
    instructions='''
    you are a triage agent that will get the output from the guardrail agent. The output includes the target_agent and the reasoning.
    You will then handoff the conversation to the target_agent.
    If the target_agent is 'None', you will handoff the conversation to the fallback_agent.
    If the target_agent is not 'None', you will handoff the conversation to the target_agent.
    ''',
    handoffs=[web_search_agent, device_query_agent, fallback_agent],
    # set the input guardrail to the triage_guardrail
    input_guardrails=[InputGuardrail(guardrail_function=triage_guardrail)],
)


async def main():
    test_questions = [
        "How many network devices? What are the versions of these network devices?",
    ]
    for question in test_questions:
        print(f"Question: {question}")
        result = await Runner.run(triage_agent, question)
        print(f"Result: {result}")
        print(f'[answer from the agent] {result.final_output}')

if __name__ == "__main__":
    asyncio.run(main())