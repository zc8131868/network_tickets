import os
from openai import OpenAI

# aihubmix_apikey = os.getenv('AIHUBMIX_APIKEY')

aihubmix_apikey = os.environ.get('AIHUBMIX')

client = OpenAI(api_key=aihubmix_apikey, base_url="https://aihubmix.com/v1")



##############response api######################################################################
response = client.responses.create(

    model='gpt-5-nano',
    instructions='You are a helpful assistant that can answer questions and help with tasks.',
    input = [
        {'role': 'developer', 'content': 'You are a helpful assistant that can answer questions and help with tasks.'},
        {'role': 'assistant', 'content': 'I live in Hong Kong.'},
        {'role': 'user', 'content': 'What is the average income?'},
        
]
)
print(response.output_text) 

##############chat api######################################################################

# completion = client.chat.completions.create(
#     model='gpt-5-nano',
#     messages=[
#         {'role': 'user', 'content': 'What is the capital of France?'}
#     ]
# )
# print(completion.choices[0].message.content)


