import os
from agents import set_default_openai_key, set_default_openai_client
from agents import Agent, Runner, AsyncOpenAI, OpenAIChatCompletionsModel, ModelSettings, set_tracing_disabled
from agents import InputGuardrail, AsyncOpenAI, GuardrailFunctionOutput, Runner
from agents.exceptions import ToolInputGuardrailTripwireTriggered
from pydantic import BaseModel, Field
import asyncio


aihubmix_apikey = os.environ.get("AIHUBMIX")
set_default_openai_key(aihubmix_apikey)

set_tracing_disabled(True)

external_client = AsyncOpenAI(
    api_key=aihubmix_apikey,
    base_url="https://aihubmix.com/v1/",
)

class HomeworkOutput(BaseModel):
    is_homework: bool
    reasoning: str


#define an agent that can check if the user's input is a homework question
guardrail_agent = Agent(name='homework-checker', model=use_model,
)