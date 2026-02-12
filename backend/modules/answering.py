"""
Answering Module: Answer generation with provider switching.

Supports multiple inference providers:
- OpenAI: GPT-4/GPT-4-turbo (default, high quality)
- Cerebras: Llama 3.3 70B (10x faster, lower cost)

Environment Variables:
    INFERENCE_PROVIDER: "openai" (default) or "cerebras"
    CEREBRAS_API_KEY: Required if using Cerebras

Usage:
    from modules.answering import generate_answer
    
    # Uses provider from environment
    result = generate_answer(query, contexts)
    print(result["answer"])
"""
from modules.clients import get_openai_client
import os
import logging
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Provider configuration
INFERENCE_PROVIDER = os.getenv("INFERENCE_PROVIDER", "openai").lower()
INFERENCE_FALLBACK_ENABLED = os.getenv("INFERENCE_FALLBACK_ENABLED", "true").lower() == "true"

if INFERENCE_PROVIDER not in ["openai", "cerebras"]:
    logger.warning(f"[Answering] Unknown provider '{INFERENCE_PROVIDER}', using 'openai'")
    INFERENCE_PROVIDER = "openai"

logger.info(f"[Answering] Using inference provider: {INFERENCE_PROVIDER}")


def _build_prompt(query: str, contexts: List[Dict]) -> str:
    """Build the prompt from query and contexts."""
    context_text = "\n\n".join([
        f"Source {i+1}: {c['text']}" 
        for i, c in enumerate(contexts)
    ])
    
    return f"""You are a Verified Digital Twin Brain. Your goal is to provide accurate answers based ONLY on the provided context.
If the answer is not in the context, say "I don't have enough information to answer this based on my knowledge base."

Always provide citations in the format [Source N] where N is the number of the source.

Context:
{context_text}

User Query: {query}

Answer:"""


def _calculate_confidence(contexts: List[Dict]) -> float:
    """Calculate average confidence score from contexts."""
    return sum([c.get('score', 0) for c in contexts]) / len(contexts) if contexts else 0


def _generate_answer_openai(query: str, contexts: List[Dict]) -> Dict[str, Any]:
    """Generate answer using OpenAI."""
    client = get_openai_client()
    prompt = _build_prompt(query, contexts)
    
    response = client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[
            {"role": "system", "content": "You are a helpful and accurate digital twin."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    
    answer = response.choices[0].message.content
    avg_score = _calculate_confidence(contexts)
    
    return {
        "answer": answer,
        "confidence_score": avg_score,
        "citations": [c['source_id'] for c in contexts],
        "provider": "openai",
        "model": "gpt-4-turbo-preview"
    }


def _generate_answer_cerebras(query: str, contexts: List[Dict]) -> Dict[str, Any]:
    """Generate answer using Cerebras."""
    from modules.inference_cerebras import CerebrasClient
    
    client = CerebrasClient()
    prompt = _build_prompt(query, contexts)
    
    response = client.generate(
        messages=[
            {"role": "system", "content": "You are a helpful and accurate digital twin."},
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        max_tokens=2048
    )
    
    answer = response.choices[0].message.content
    avg_score = _calculate_confidence(contexts)
    
    return {
        "answer": answer,
        "confidence_score": avg_score,
        "citations": [c['source_id'] for c in contexts],
        "provider": "cerebras",
        "model": client.model
    }


def generate_answer(query: str, contexts: List[Dict]) -> Dict[str, Any]:
    """
    Generate answer using configured provider.
    
    Provider is determined by INFERENCE_PROVIDER environment variable:
    - "openai" (default): Uses GPT-4-turbo-preview
    - "cerebras": Uses Llama 3.3 70B on Cerebras
    
    With INFERENCE_FALLBACK_ENABLED=true, automatically falls back to OpenAI
    if Cerebras fails.
    
    Args:
        query: User query string
        contexts: List of context dicts with 'text', 'score', 'source_id'
        
    Returns:
        Dict with 'answer', 'confidence_score', 'citations', 'provider', 'model'
    """
    # Try primary provider
    if INFERENCE_PROVIDER == "cerebras":
        try:
            return _generate_answer_cerebras(query, contexts)
        except Exception as e:
            logger.warning(f"[Answering] Cerebras failed: {e}")
            if INFERENCE_FALLBACK_ENABLED:
                logger.info("[Answering] Falling back to OpenAI")
                return _generate_answer_openai(query, contexts)
            raise
    
    # Default: OpenAI
    return _generate_answer_openai(query, contexts)


async def _generate_answer_stream_openai(query: str, contexts: List[Dict]):
    """Generate streaming answer using OpenAI."""
    client = get_openai_client()
    prompt = _build_prompt(query, contexts)
    
    stream = client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[
            {"role": "system", "content": "You are a helpful and accurate digital twin."},
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        stream=True
    )
    
    for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            yield chunk.choices[0].delta.content


async def _generate_answer_stream_cerebras(query: str, contexts: List[Dict]):
    """Generate streaming answer using Cerebras."""
    from modules.inference_cerebras import CerebrasClient
    
    client = CerebrasClient()
    prompt = _build_prompt(query, contexts)
    
    async for chunk in client.generate_stream_async(
        messages=[
            {"role": "system", "content": "You are a helpful and accurate digital twin."},
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        max_tokens=2048
    ):
        yield chunk


async def generate_answer_stream(query: str, contexts: List[Dict]):
    """
    Generate streaming answer using configured provider.
    
    Args:
        query: User query string
        contexts: List of context dicts
        
    Yields:
        Text chunks of the generated answer
    """
    # Try primary provider
    if INFERENCE_PROVIDER == "cerebras":
        try:
            async for chunk in _generate_answer_stream_cerebras(query, contexts):
                yield chunk
            return
        except Exception as e:
            logger.warning(f"[Answering] Cerebras streaming failed: {e}")
            if INFERENCE_FALLBACK_ENABLED:
                logger.info("[Answering] Falling back to OpenAI streaming")
                async for chunk in _generate_answer_stream_openai(query, contexts):
                    yield chunk
                return
            raise
    
    # Default: OpenAI
    async for chunk in _generate_answer_stream_openai(query, contexts):
        yield chunk


def get_answering_health() -> Dict[str, Any]:
    """
    Get health status of answering module.
    
    Returns:
        Dict with provider status
    """
    return {
        "provider": INFERENCE_PROVIDER,
        "fallback_enabled": INFERENCE_FALLBACK_ENABLED,
        "status": "healthy"
    }
