import os
from pinecone import Pinecone
from openai import OpenAI, AsyncOpenAI
from dotenv import load_dotenv

try:
    import cohere
except ImportError:
    cohere = None

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
        if api_key and cohere is not None:
            _cohere_client = cohere.ClientV2(api_key=api_key)
        elif api_key and cohere is None:
            print("Warning: cohere package not installed. Run: pip install -r requirements-ml.txt")
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

# ElevenLabs TTS Client
_elevenlabs_client = None

def get_elevenlabs_client():
    """Get or create singleton ElevenLabs client."""
    global _elevenlabs_client
    if _elevenlabs_client is None:
        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            print("Warning: ELEVENLABS_API_KEY not found. Voice features disabled.")
            return None
        try:
            from elevenlabs.client import ElevenLabs
            _elevenlabs_client = ElevenLabs(api_key=api_key)
        except ImportError:
            print("Warning: elevenlabs package not installed. Run: pip install elevenlabs")
            return None
    return _elevenlabs_client
