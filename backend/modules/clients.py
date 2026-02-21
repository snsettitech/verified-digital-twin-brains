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

def get_cohere_client(required: bool = False):
    """
    Get or create singleton Cohere client.
    
    Args:
        required: If True, raises error if client cannot be created
        
    Returns:
        Cohere client instance or None (if not required)
        
    Raises:
        ValueError: If required=True and COHERE_API_KEY not set or cohere package missing
    """
    global _cohere_client
    if _cohere_client is None:
        api_key = os.getenv("COHERE_API_KEY")
        
        # Validation with clear error messages
        if not api_key:
            error_msg = (
                "COHERE_API_KEY environment variable not set. "
                "Reranking requires Cohere API key. "
                "Get one at: https://dashboard.cohere.com/api-keys"
            )
            if required:
                raise ValueError(error_msg)
            print(f"[Cohere] {error_msg}")
            return None
            
        if cohere is None:
            error_msg = (
                "cohere package not installed. "
                "Run: pip install cohere"
            )
            if required:
                raise ValueError(error_msg)
            print(f"[Cohere] {error_msg}")
            return None
            
        try:
            _cohere_client = cohere.ClientV2(api_key=api_key)
            print("[Cohere] Client initialized successfully")
        except Exception as e:
            error_msg = f"Failed to initialize Cohere client: {e}"
            if required:
                raise ValueError(error_msg) from e
            print(f"[Cohere] {error_msg}")
            return None
            
    return _cohere_client


def validate_cohere_config(strict: bool = True) -> bool:
    """
    Validate Cohere configuration and raise clear errors if invalid.
    
    Args:
        strict: If True, raises ValueError on any issue
        
    Returns:
        True if valid, False if not (only when strict=False)
    """
    api_key = os.getenv("COHERE_API_KEY")
    
    if not api_key:
        if strict:
            raise ValueError(
                "RERANKING ERROR: COHERE_API_KEY environment variable not set. "
                "Reranking is REQUIRED for production. "
                "Get your API key at: https://dashboard.cohere.com/api-keys "
                "Set it with: export COHERE_API_KEY='your-key-here'"
            )
        return False
        
    if cohere is None:
        if strict:
            raise ValueError(
                "RERANKING ERROR: cohere package not installed. "
                "Run: pip install cohere"
            )
        return False
        
    # Try to create client to validate key format
    try:
        client = cohere.ClientV2(api_key=api_key)
        print("[Cohere] Configuration validated successfully")
        return True
    except Exception as e:
        if strict:
            raise ValueError(f"RERANKING ERROR: Invalid Cohere API key: {e}")
        return False

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
        host = (os.getenv("PINECONE_HOST") or "").strip()
        mode = (os.getenv("PINECONE_INDEX_MODE", "vector") or "vector").strip().lower()

        if host.startswith("https://"):
            host = host[len("https://") :]
        elif host.startswith("http://"):
            host = host[len("http://") :]
        host = host.rstrip("/")

        if not host and not index_name:
            raise ValueError("PINECONE_INDEX_NAME not found in environment")
        try:
            if host:
                print(
                    f"[Pinecone] Initializing index via host override "
                    f"(mode={mode}, host_override=true)"
                )
                _pinecone_index = pc.Index(host=host)
            else:
                print(
                    f"[Pinecone] Initializing index by name "
                    f"(mode={mode}, host_override=false, index={index_name})"
                )
                _pinecone_index = pc.Index(index_name)
        except Exception as e:
            target = host or index_name
            print(f"Error connecting to Pinecone index '{target}': {e}")
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
