"""
Embeddings Module: Centralized embedding generation and utilities.

This module provides unified embedding generation functions to avoid duplication
across ingestion, verified_qna, and retrieval modules.
"""
from typing import List
import asyncio
from modules.clients import get_openai_client


def get_embedding(text: str) -> List[float]:
    """
    Generate embedding for a single text using OpenAI.
    
    Args:
        text: Text to embed
        
    Returns:
        List of floats representing the embedding vector
    """
    client = get_openai_client()
    response = client.embeddings.create(
        input=text,
        model="text-embedding-3-large",
        dimensions=3072
    )
    return response.data[0].embedding


async def get_embeddings_async(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for multiple texts asynchronously (batch processing).
    
    Args:
        texts: List of texts to embed
        
    Returns:
        List of embedding vectors (one per input text)
    """
    client = get_openai_client()
    loop = asyncio.get_event_loop()
    
    # OpenAI client is thread-safe, we use run_in_executor for the blocking network call
    def _fetch():
        response = client.embeddings.create(
            input=texts,
            model="text-embedding-3-large",
            dimensions=3072
        )
        return [d.embedding for d in response.data]
        
    return await loop.run_in_executor(None, _fetch)


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

