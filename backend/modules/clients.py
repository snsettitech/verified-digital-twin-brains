import os
from pinecone import Pinecone
from openai import OpenAI, AsyncOpenAI
import cohere
from dotenv import load_dotenv

load_dotenv()

_pc_client = None
_pinecone_index = None
_openai_client = None
_async_openai_client = None
_cohere_client = None

def get_cohere_client():
    global _cohere_client
    if _cohere_client is None:
        api_key = os.getenv("COHERE_API_KEY")
        if api_key:
            _cohere_client = cohere.ClientV2(api_key=api_key)
    return _cohere_client

def get_openai_client():
    global _openai_client
    if _openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        _openai_client = OpenAI(api_key=api_key)
    return _openai_client

def get_async_openai_client():
    global _async_openai_client
    if _async_openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        _async_openai_client = AsyncOpenAI(api_key=api_key)
    return _async_openai_client

def get_pinecone_client():
    global _pc_client
    if _pc_client is None:
        api_key = os.getenv("PINECONE_API_KEY")
        if not api_key:
            raise ValueError("PINECONE_API_KEY not found in environment")
        _pc_client = Pinecone(api_key=api_key)
    return _pc_client

def get_pinecone_index():
    global _pinecone_index
    if _pinecone_index is None:
        pc = get_pinecone_client()
        index_name = os.getenv("PINECONE_INDEX_NAME")
        if not index_name:
            raise ValueError("PINECONE_INDEX_NAME not found in environment")
        try:
            _pinecone_index = pc.Index(index_name)
        except Exception as e:
            print(f"Error connecting to Pinecone index '{index_name}': {e}")
            raise e
    return _pinecone_index
