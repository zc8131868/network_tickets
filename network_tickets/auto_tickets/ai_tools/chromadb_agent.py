from agents import Agent, Runner, AsyncOpenAI, OpenAIChatCompletionsModel, set_tracing_disabled
import asyncio
import os
from pathlib import Path
from chromadb_query import query_similar_chunks, build_context_from_chunks  

TOP_K = 25  # Keep at 25 for best accuracy (performance: ~7-8s per query)
TYPE = 'xlsx'  # Changed to xlsx since we're working with Excel files

# Disable tracing to avoid OPENAI_API_KEY warning
set_tracing_disabled(True)

# Load API key
api_key = os.getenv('AIHUBMIX')
if not api_key:
    env_file = Path(__file__).parent / '.env'
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if line.startswith('AIHUBMIX='):
                    api_key = line.strip().split('=', 1)[1].strip('"').strip("'")
                    break

if not api_key:
    raise ValueError("AIHUBMIX API key not found. Please set AIHUBMIX environment variable or create a .env file")

external_client = AsyncOpenAI(
    api_key=api_key,
    base_url="https://aihubmix.com/v1/",
)

async def run_query(question):
    try:
        # 1. search the chunks from chromadb
        top_chunks = query_similar_chunks(
            question=question, 
            top_k=TOP_K, 
            type_=TYPE,
        )
        
        if not top_chunks:
            print("No related content found")
            return
            
        # 2. build the context
        context = build_context_from_chunks(top_chunks)
        
        # 3. initialize the Agent, add the context to the instructions
        agent = Agent(
            name="Assistant",
            model=OpenAIChatCompletionsModel(
                model="gpt-5-mini",
                openai_client=external_client,
            ),
            instructions="Please answer the user's question based on the following knowledge base content. If the knowledge base does not contain related content, please say 'I don't know'. \n" + context
        )
        
        # 4. call the Agent to answer the question
        result = await Runner.run(agent, question)
        return result.final_output
        
    except Exception as e:  
        import traceback
        error_msg = f"Error: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return f"Sorry, I encountered an error. Please try again later."



if __name__ == "__main__":
    question = "show me the devices' name and ip address in the EXT area"
    result = asyncio.run(run_query(question))
    print(result)