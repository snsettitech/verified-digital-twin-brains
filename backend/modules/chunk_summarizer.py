"""
Chunk summarization for contextual embeddings.

Generates 1-2 sentence summaries of chunks for use in embedding text.
"""

import os
import asyncio
from typing import Optional
from datetime import datetime

from modules.clients import get_openai_client
from modules.chunking_config import (
    CHUNK_SUMMARIZER_MODEL,
    CHUNK_SUMMARY_MAX_TOKENS,
    CHUNK_SUMMARY_TIMEOUT,
)

# Cache for LLM client
_llm_client = None


def _get_llm_client():
    """Get cached LLM client."""
    global _llm_client
    if _llm_client is None:
        _llm_client = get_openai_client()
    return _llm_client


def _extractive_fallback(chunk_text: str, max_words: int = 30) -> str:
    """
    Extractive fallback when LLM summarization fails.
    
    Takes first sentence(s) up to max_words.
    """
    sentences = []
    word_count = 0
    
    # Split by sentence boundaries
    import re
    raw_sentences = re.split(r'(?<=[.!?])\s+', chunk_text)
    
    for sentence in raw_sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        
        sentence_words = len(sentence.split())
        if word_count + sentence_words > max_words and sentences:
            break
        
        sentences.append(sentence)
        word_count += sentence_words
    
    summary = ' '.join(sentences)
    
    # If still too long, truncate
    words = summary.split()
    if len(words) > max_words:
        summary = ' '.join(words[:max_words]) + '...'
    
    return summary


async def generate_chunk_summary(
    chunk_text: str,
    doc_title: Optional[str] = None,
    section_title: Optional[str] = None,
    timeout: float = CHUNK_SUMMARY_TIMEOUT,
) -> str:
    """
    Generate a 1-2 sentence summary of a chunk.
    
    This summary is used in embedding_text to improve retrieval.
    
    Args:
        chunk_text: The full chunk text to summarize
        doc_title: Optional document title for context
        section_title: Optional section title for context
        timeout: Timeout for LLM call
    
    Returns:
        1-2 sentence summary (fallback to extractive if LLM fails)
    """
    if not chunk_text or len(chunk_text) < 100:
        return chunk_text
    
    # Build context prefix
    context_parts = []
    if doc_title:
        context_parts.append(f"Document: {doc_title}")
    if section_title:
        context_parts.append(f"Section: {section_title}")
    
    context_str = "\n".join(context_parts)
    
    # Truncate chunk if too long
    max_input_chars = 2000
    truncated_chunk = chunk_text[:max_input_chars]
    if len(chunk_text) > max_input_chars:
        truncated_chunk += "..."
    
    prompt = f"""Summarize the following text in 1-2 sentences. Focus on the key information, facts, or main point.

{context_str}

Text:
{truncated_chunk}

Summary (1-2 sentences):"""
    
    try:
        client = _get_llm_client()
        
        # Run in executor to not block event loop
        loop = asyncio.get_event_loop()
        
        def _call_llm():
            return client.chat.completions.create(
                model=CHUNK_SUMMARIZER_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You create concise, factual summaries. Capture the main point in 1-2 sentences."
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=CHUNK_SUMMARY_MAX_TOKENS,
                temperature=0.3,  # Low temperature for consistency
            )
        
        # Call with timeout
        response = await asyncio.wait_for(
            loop.run_in_executor(None, _call_llm),
            timeout=timeout
        )
        
        summary = response.choices[0].message.content.strip()
        
        # Validate summary
        if not summary or len(summary) < 10:
            raise ValueError("Summary too short")
        
        return summary
        
    except asyncio.TimeoutError:
        print(f"[ChunkSummarizer] Timeout after {timeout}s, using fallback")
        return _extractive_fallback(chunk_text)
    except Exception as e:
        print(f"[ChunkSummarizer] LLM failed: {e}, using fallback")
        return _extractive_fallback(chunk_text)


def generate_chunk_title(
    chunk_text: str,
    section_title: Optional[str] = None,
) -> str:
    """
    Generate a descriptive title for a chunk.
    
    Uses heuristics first, only calls LLM if needed.
    """
    # If section title exists, use it
    if section_title:
        return section_title
    
    # Try to extract first line as title if it looks like a heading
    first_line = chunk_text.split('\n')[0].strip()
    if len(first_line) < 100 and not first_line.endswith('.'):
        # Check if it looks like a heading (short, no period)
        return first_line
    
    # Use first sentence truncated
    first_sentence = chunk_text.split('.')[0].strip()
    if len(first_sentence) > 80:
        first_sentence = first_sentence[:77] + "..."
    
    return first_sentence


async def generate_chunk_summary_batch(
    chunks: list,
    doc_title: Optional[str] = None,
    max_concurrent: int = 5,
) -> list:
    """
    Generate summaries for multiple chunks with concurrency control.
    
    Args:
        chunks: List of chunk dicts with 'text' key
        doc_title: Optional document title
        max_concurrent: Max concurrent LLM calls
    
    Returns:
        List of chunk dicts with added 'summary' key
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def _summarize_one(chunk: dict) -> dict:
        async with semaphore:
            summary = await generate_chunk_summary(
                chunk_text=chunk.get("text", ""),
                doc_title=doc_title,
                section_title=chunk.get("section_title"),
            )
            chunk["summary"] = summary
            return chunk
    
    tasks = [_summarize_one(chunk) for chunk in chunks]
    return await asyncio.gather(*tasks)
