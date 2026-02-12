"""
Embeddings Module: Centralized embedding generation and utilities.

This module provides unified embedding generation functions to avoid duplication
across ingestion, verified_qna, and retrieval modules.

PROVIDER SUPPORT (NEW):
- OpenAI: text-embedding-3-large (default, 3072 dims)
- Hugging Face Local: all-MiniLM-L6-v2 (384 dims, 20x faster)

Environment Variables:
- EMBEDDING_PROVIDER: "openai" (default) or "huggingface"
- HF_EMBEDDING_MODEL: Model name (default: all-MiniLM-L6-v2)
- HF_EMBEDDING_DEVICE: "cpu" or "cuda" (auto-detected if not set)

SECURITY FIXES:
- Added timeout handling for all external API calls (HIGH Bug H2)
- Retry logic with exponential backoff
- Circuit breaker pattern for resilience
- Automatic fallback between providers
"""
from typing import List, Optional
import os
import asyncio
import time
import logging
from functools import wraps, lru_cache
from modules.clients import get_openai_client, get_pinecone_client

# Configure logger
logger = logging.getLogger(__name__)

# =============================================================================
# PROVIDER CONFIGURATION (NEW)
# =============================================================================

EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "openai").lower()
EMBEDDING_FALLBACK_ENABLED = os.getenv("EMBEDDING_FALLBACK_ENABLED", "true").lower() == "true"

# Validate provider
if EMBEDDING_PROVIDER not in ["openai", "huggingface"]:
    logger.warning(f"[Embeddings] Unknown provider '{EMBEDDING_PROVIDER}', using 'openai'")
    EMBEDDING_PROVIDER = "openai"

logger.info(f"[Embeddings] Using provider: {EMBEDDING_PROVIDER}")

# =============================================================================
# TIMEOUT AND RETRY CONFIGURATION (CRITICAL BUG FIX: H2)
# =============================================================================

# Default timeouts (seconds)
EMBEDDING_TIMEOUT = int(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "30"))
EMBEDDING_RETRY_ATTEMPTS = int(os.getenv("EMBEDDING_RETRY_ATTEMPTS", "3"))
EMBEDDING_RETRY_DELAY = float(os.getenv("EMBEDDING_RETRY_DELAY", "1.0"))
EMBEDDING_RETRY_BACKOFF = float(os.getenv("EMBEDDING_RETRY_BACKOFF", "2.0"))

# Circuit breaker settings
CIRCUIT_BREAKER_THRESHOLD = int(os.getenv("CIRCUIT_BREAKER_THRESHOLD", "5"))
CIRCUIT_BREAKER_TIMEOUT = int(os.getenv("CIRCUIT_BREAKER_TIMEOUT", "60"))  # Seconds before reset


class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascading failures.
    
    States:
    - CLOSED: Normal operation
    - OPEN: Failing fast (recent failures exceeded threshold)
    - HALF_OPEN: Testing if service recovered
    """
    
    STATE_CLOSED = "closed"
    STATE_OPEN = "open"
    STATE_HALF_OPEN = "half_open"
    
    def __init__(self, threshold: int = CIRCUIT_BREAKER_THRESHOLD, timeout: int = CIRCUIT_BREAKER_TIMEOUT):
        self.threshold = threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = self.STATE_CLOSED
    
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == self.STATE_OPEN:
            if time.time() - self.last_failure_time > self.timeout:
                self.state = self.STATE_HALF_OPEN
            else:
                raise Exception("Circuit breaker is OPEN - service temporarily unavailable")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        self.state = self.STATE_CLOSED
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.threshold:
            self.state = self.STATE_OPEN


# Global circuit breaker for embeddings
_embedding_circuit_breaker = CircuitBreaker()


def with_retry_and_timeout(max_attempts: int = None, timeout_seconds: int = None):
    """
    Decorator to add retry logic with timeout to embedding operations.
    
    Args:
        max_attempts: Maximum retry attempts
        timeout_seconds: Timeout per attempt in seconds
    """
    max_attempts = max_attempts or EMBEDDING_RETRY_ATTEMPTS
    timeout_seconds = timeout_seconds or EMBEDDING_TIMEOUT
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = EMBEDDING_RETRY_DELAY
            last_error = None
            
            for attempt in range(max_attempts):
                try:
                    # Use asyncio.wait_for for timeout if in async context
                    import concurrent.futures
                    
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(func, *args, **kwargs)
                        return future.result(timeout=timeout_seconds)
                        
                except concurrent.futures.TimeoutError:
                    last_error = TimeoutError(f"Embedding request timed out after {timeout_seconds}s")
                    print(f"[Embedding] Timeout on attempt {attempt + 1}/{max_attempts}")
                except Exception as e:
                    last_error = e
                    error_msg = str(e).lower()
                    
                    # Don't retry on auth errors or invalid input
                    non_retryable = ["authentication", "invalid", "not found", "permission"]
                    if any(nr in error_msg for nr in non_retryable):
                        raise
                    
                    print(f"[Embedding] Error on attempt {attempt + 1}/{max_attempts}: {e}")
                
                if attempt < max_attempts - 1:
                    time.sleep(delay)
                    delay *= EMBEDDING_RETRY_BACKOFF
            
            raise last_error or Exception("Embedding failed after all retries")
        
        return wrapper
    return decorator


# =============================================================================
# PROVIDER-SPECIFIC IMPLEMENTATIONS
# =============================================================================

def _get_embedding_openai(text: str) -> List[float]:
    """Generate embedding using OpenAI API."""
    client = get_openai_client()
    
    def _fetch():
        response = client.embeddings.create(
            input=text,
            model="text-embedding-3-large",
            dimensions=3072
        )
        return response.data[0].embedding
    
    return _embedding_circuit_breaker.call(_fetch)


def _get_embedding_huggingface(text: str) -> List[float]:
    """Generate embedding using local Hugging Face model."""
    from modules.embeddings_hf import HFEmbeddingClient
    
    client = HFEmbeddingClient()
    return client.embed(text)


@lru_cache(maxsize=1)
def _resolve_target_dimension() -> Optional[int]:
    """
    Resolve expected vector dimension for this deployment.

    Priority:
    1. EMBEDDING_TARGET_DIMENSION env override
    2. Pinecone index dimension (if reachable)
    """
    configured_target = os.getenv("EMBEDDING_TARGET_DIMENSION")
    if configured_target:
        try:
            return int(configured_target)
        except ValueError:
            logger.warning(
                "[Embeddings] Invalid EMBEDDING_TARGET_DIMENSION='%s' (must be int). Ignoring.",
                configured_target,
            )

    index_name = os.getenv("PINECONE_INDEX_NAME")
    if not index_name:
        return None

    try:
        pc = get_pinecone_client()
        desc = pc.describe_index(index_name)
        dim = getattr(desc, "dimension", None)
        return int(dim) if dim else None
    except Exception as e:
        logger.warning("[Embeddings] Could not resolve Pinecone target dimension: %s", e)
        return None


def _ensure_hf_dimension_compatibility() -> None:
    """
    Ensure HF embedding dimensions match the active vector index.

    If dimensions differ, fallback to OpenAI (if enabled) or raise.
    """
    from modules.embeddings_hf import HFEmbeddingClient

    target_dim = _resolve_target_dimension()
    if not target_dim:
        return

    hf_client = HFEmbeddingClient()
    hf_dim = int(hf_client.dimension)

    if hf_dim == target_dim:
        return

    msg = (
        f"[Embeddings] HuggingFace dimension mismatch: model_dim={hf_dim}, "
        f"target_dim={target_dim}. Configure a matching index/model or set "
        "EMBEDDING_PROVIDER=openai."
    )
    if EMBEDDING_FALLBACK_ENABLED:
        logger.warning("%s Falling back to OpenAI embeddings.", msg)
        raise RuntimeError("HF_DIMENSION_MISMATCH_FALLBACK")

    raise RuntimeError(msg)


# =============================================================================
# UNIFIED EMBEDDING FUNCTIONS WITH PROVIDER SWITCHING
# =============================================================================

@with_retry_and_timeout()
def get_embedding(text: str) -> List[float]:
    """
    Generate embedding for a single text using configured provider.
    
    Provider is determined by EMBEDDING_PROVIDER environment variable:
    - "openai" (default): Uses OpenAI API (3072 dims, ~340ms)
    - "huggingface": Uses local HF model (dimension depends on selected model)
    
    With EMBEDDING_FALLBACK_ENABLED=true, automatically falls back to OpenAI
    if Hugging Face fails.
    
    Args:
        text: Text to embed
        
    Returns:
        List of floats representing the embedding vector
        
    Raises:
        TimeoutError: If request exceeds timeout
        Exception: On API errors (if fallback disabled or both fail)
    """
    # Try primary provider
    if EMBEDDING_PROVIDER == "huggingface":
        try:
            _ensure_hf_dimension_compatibility()
            return _get_embedding_huggingface(text)
        except Exception as e:
            if EMBEDDING_FALLBACK_ENABLED:
                logger.warning(f"[Embeddings] HuggingFace failed: {e}")
                logger.info("[Embeddings] Falling back to OpenAI")
                return _get_embedding_openai(text)
            raise
    
    # Default: OpenAI
    return _get_embedding_openai(text)


async def _get_embeddings_async_openai(texts: List[str]) -> List[List[float]]:
    """Generate embeddings using OpenAI API (async wrapper)."""
    client = get_openai_client()
    loop = asyncio.get_event_loop()
    
    def _fetch():
        response = client.embeddings.create(
            input=texts,
            model="text-embedding-3-large",
            dimensions=3072,
            timeout=EMBEDDING_TIMEOUT
        )
        return [d.embedding for d in response.data]
    
    return await loop.run_in_executor(None, lambda: _embedding_circuit_breaker.call(_fetch))


async def _get_embeddings_async_huggingface(texts: List[str]) -> List[List[float]]:
    """Generate embeddings using Hugging Face (async wrapper)."""
    from modules.embeddings_hf import HFEmbeddingClient
    
    client = HFEmbeddingClient()
    loop = asyncio.get_event_loop()
    
    def _fetch():
        return client.embed_batch(texts)
    
    return await loop.run_in_executor(None, _fetch)


async def get_embeddings_async(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for multiple texts asynchronously (batch processing).
    
    Provider is determined by EMBEDDING_PROVIDER environment variable.
    Supports automatic fallback if enabled.
    
    Args:
        texts: List of texts to embed
        
    Returns:
        List of embedding vectors (one per input text)
        
    Raises:
        TimeoutError: If request exceeds timeout
        Exception: On API errors (if fallback disabled or both fail)
    """
    # Try primary provider
    if EMBEDDING_PROVIDER == "huggingface":
        try:
            _ensure_hf_dimension_compatibility()
            return await _get_embeddings_async_huggingface(texts)
        except Exception as e:
            if EMBEDDING_FALLBACK_ENABLED:
                logger.warning(f"[Embeddings] HuggingFace async failed: {e}")
                logger.info("[Embeddings] Falling back to OpenAI")
                return await _get_embeddings_async_openai(texts)
            raise
    
    # Default: OpenAI
    try:
        return await _get_embeddings_async_openai(texts)
    except Exception as e:
        if "timeout" in str(e).lower():
            raise TimeoutError(f"Embedding batch request timed out after {EMBEDDING_TIMEOUT}s")
        raise


def get_embedding_with_timeout(text: str, timeout_seconds: int = None) -> Optional[List[float]]:
    """
    Generate embedding with explicit timeout, returns None on failure.
    
    Args:
        text: Text to embed
        timeout_seconds: Custom timeout (uses default if not specified)
        
    Returns:
        Embedding vector or None if failed
    """
    timeout = timeout_seconds or EMBEDDING_TIMEOUT
    
    try:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(get_embedding, text)
            return future.result(timeout=timeout)
    except Exception as e:
        print(f"[Embedding] Failed to get embedding: {e}")
        return None


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def cosine_similarity(a: List[float], b: List[float]) -> float:
    """
    Calculate cosine similarity between two embedding vectors.
    
    Args:
        a: First embedding vector
        b: Second embedding vector
        
    Returns:
        Cosine similarity score between 0 and 1
    """
    if len(a) != len(b):
        return 0.0
    
    # Calculate dot product
    dot_product = sum(x * y for x, y in zip(a, b))
    
    # Calculate norms
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    
    # Avoid division by zero
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    
    return dot_product / (norm_a * norm_b)


def get_embedding_health_status() -> dict:
    """Get health status of embedding service."""
    target_dim = _resolve_target_dimension()
    return {
        "provider": EMBEDDING_PROVIDER,
        "circuit_breaker_state": _embedding_circuit_breaker.state,
        "failure_count": _embedding_circuit_breaker.failure_count,
        "last_failure": _embedding_circuit_breaker.last_failure_time,
        "target_dimension": target_dim,
        "timeout_config": EMBEDDING_TIMEOUT,
        "retry_config": {
            "attempts": EMBEDDING_RETRY_ATTEMPTS,
            "delay": EMBEDDING_RETRY_DELAY,
            "backoff": EMBEDDING_RETRY_BACKOFF
        }
    }
