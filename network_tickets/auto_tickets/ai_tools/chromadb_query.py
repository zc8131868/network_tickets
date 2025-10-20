import sys
from pysqlite3 import dbapi2 as sqlite3
sys.modules['sqlite3'] = sqlite3

import chromadb
from chromadb import PersistentClient
from openai import OpenAI

import os
import glob
import time
from datetime import datetime
from pathlib import Path


DB_PATH = '/it_network/network_tickets/auto_tickets/ai_tools/chromadb.db'
MODEL = 'text-embedding-3-small'
COLLECTION_NAME = 'NetCare_RAG'

TOP_K = 2
TYPE = 'xlsx'


# Load API key
aihubmix_apikey = os.environ.get("AIHUBMIX")
if not aihubmix_apikey:
    env_file = Path(__file__).parent / '.env'
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if line.startswith('AIHUBMIX='):
                    aihubmix_apikey = line.strip().split('=', 1)[1].strip('"').strip("'")
                    break

if not aihubmix_apikey:
    raise ValueError("AIHUBMIX API key not found. Please set AIHUBMIX environment variable or create a .env file")

def embed_question(question: str) -> list:
    """Embed a question into a vector"""
    openai_client = OpenAI(
        api_key=aihubmix_apikey,
        base_url="https://aihubmix.com/v1/"
    )
    resp = openai_client.embeddings.create(
        input=question,
        model=MODEL
    )
    return resp.data[0].embedding

def query_similar_chunks(question, 
                         top_k, 
                         type_=TYPE):
    """Query similar chunks from the collection"""
    question_embedding = embed_question(question)

    client = PersistentClient(path=DB_PATH)
    collection = client.get_collection(COLLECTION_NAME)

    kwargs = {
        'query_embeddings': [question_embedding],
        'n_results': top_k,
        'include': ['documents', 'metadatas', 'distances']
    }

    results = collection.query(**kwargs)


    formatted_results = []
    if results and len(results["ids"]) > 0 and len(results["ids"][0]) > 0:
        for i, (doc_id, doc, metadata, distance) in enumerate(zip(
            results["ids"][0], 
            results["documents"][0], 
            results["metadatas"][0], 
            results["distances"][0]
        )):
            similarity = abs(1 - distance)
            formatted_results.append({
                'id': doc_id,
                'document': doc,
                'metadata': metadata,
                'similarity': similarity
            })
    return formatted_results

def build_context_from_chunks(chunks: list) -> str:
    """Build context from chunks"""
    if not chunks:
        return "No relevant content found in the knowledge base."
    context = "The following is the relevant content from the knowledge base:\n"
    for idx, chunk in enumerate(chunks, 1):
        context += "~" * 10 + f"Chunk {idx} (File: {chunk['metadata']['filename']}), Similarity: {chunk['similarity']:.2f}" + "~" * 10 + "\n"
        context += f"{chunk['document']}\n"
    return context

if __name__ == '__main__':

    
    # execute query
    results = query_similar_chunks(
        question="What is the IP address of the router?", 
        top_k=TOP_K, 
    )
    
    # print results
    print(build_context_from_chunks(results))
