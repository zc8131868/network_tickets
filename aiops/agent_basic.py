import os
from agents import set_default_openai_key, set_default_openai_client
# ~~~~~~~~~~~~~此项目相关的import~~~~~~~~~~~~~~~~
from agents import Agent, Runner, AsyncOpenAI, OpenAIChatCompletionsModel, ModelSettings, set_tracing_disabled


aihubmix_apikey = os.environ.get("AIHUBMIX")
set_default_openai_key(aihubmix_apikey)

set_tracing_disabled(True)

external_client = AsyncOpenAI(
    api_key=aihubmix_apikey,
    base_url="https://aihubmix.com/v1/",
)

async def simple_question(question):
    agent = Agent(name='Assistant',
                model=OpenAIChatCompletionsModel(model='gpt-5-mini', openai_client=external_client),
                instructions='You are a helpful assistant that can answer questions and help with tasks.If you need to do some network troubleshooting, you can do it by yourself, and then report the result to the user.')
    
    result = await Runner.run(agent, question)
    return result.final_output

if __name__ == '__main__':
    import asyncio

    question = 'I am on wifi and my OS is windows 10, help me check my network health and speed'
    result = asyncio.run(simple_question(question))
    print(result)