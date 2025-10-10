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
                model=OpenAIChatCompletionsModel(model='gpt-5-nano', openai_client=external_client),
                model_settings=ModelSettings(temperature=1.0),
                instructions='You are a helpful assistant that can answer questions and help with tasks.')
    
    result = await Runner.run(agent, question)
    return result.final_output

if __name__ == '__main__':
    import asyncio

    question = 'What is the capital of France?'
    result = asyncio.run(simple_question(question))
    print(result)