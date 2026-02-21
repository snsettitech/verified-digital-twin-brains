"""
Token-based chunking utilities for structure-aware chunking.

Provides token estimation and chunking logic that respects:
- Document structure (headings, sections)
- Semantic boundaries
- Speaker turns (for transcripts)
"""

import re
from typing import List, Dict, Any, Optional, Tuple
import os

# Try to import tiktoken for accurate token counting
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
    _ENCODING = tiktoken.get_encoding("cl100k_base")  # OpenAI encoding
except ImportError:
    TIKTOKEN_AVAILABLE = False
    _ENCODING = None


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for text.
    
    Uses tiktoken if available, otherwise uses conservative approximation
    (1 token ≈ 0.75 words ≈ 4 characters for English).
    """
    if not text:
        return 0
    
    if TIKTOKEN_AVAILABLE and _ENCODING:
        try:
            return len(_ENCODING.encode(text))
        except Exception:
            pass
    
    # Fallback: conservative estimate (4 chars per token)
    return len(text) // 4


def estimate_tokens_available() -> bool:
    """Check if accurate token counting is available."""
    return TIKTOKEN_AVAILABLE


# ============================================================================
# Structure Detection
# ============================================================================

# Heading patterns
HEADING_PATTERNS = [
    re.compile(r'^#{1,6}\s+(.+)$'),  # Markdown headings
    re.compile(r'^(\d+)[\.\)]\s+(.+)$'),  # Numbered sections
    re.compile(r'^([A-Z][A-Z\s]{2,}[A-Z])$'),  # ALL CAPS headings
    re.compile(r'^(.+):\s*$'),  # Colon endings
]

# Speaker turn patterns (for transcripts)
SPEAKER_PATTERNS = [
    re.compile(r'^([A-Z][a-zA-Z\s]+):\s*(.*)$'),  # "John: Hello"
    re.compile(r'^\[([A-Z][a-zA-Z\s]+)\]\s*(.*)$'),  # "[Sarah] Hello"
    re.compile(r'^(Speaker\s*\d+):\s*(.*)$', re.IGNORECASE),  # "Speaker 1: Hello"
    re.compile(r'^([A-Z]\.\s*[A-Z][a-zA-Z]*):\s*(.*)$'),  # "J. Smith: Hello"
]


def detect_heading(line: str) -> Optional[Dict[str, Any]]:
    """Detect if a line is a heading."""
    line = line.strip()
    if not line:
        return None
    
    for pattern in HEADING_PATTERNS:
        match = pattern.match(line)
        if match:
            groups = match.groups()
            title = groups[-1].strip()
            # Calculate level from markdown or default to 1
            if pattern.pattern.startswith(r'^#'):
                level = len(line) - len(line.lstrip('#'))
            else:
                level = 1
            return {"level": level, "title": title}
    
    return None


def detect_speaker_turn(line: str) -> Optional[Dict[str, str]]:
    """Detect speaker turns in transcript lines."""
    line = line.strip()
    if not line:
        return None
    
    for pattern in SPEAKER_PATTERNS:
        match = pattern.match(line)
        if match:
            return {
                "speaker": match.group(1).strip(),
                "text": match.group(2).strip()
            }
    
    return None


def is_semantic_boundary(
    prev_text: str,
    curr_text: str,
    threshold: float = 0.5
) -> bool:
    """
    Detect if there's a semantic boundary between two text segments.
    
    This is a lightweight heuristic using:
    - Paragraph breaks
    - Heading detection
    - Empty line detection
    
    For full semantic similarity, use the semantic_chunker module.
    """
    # Strong boundary indicators
    if not prev_text.strip() or not curr_text.strip():
        return True
    
    # Heading indicates new section
    if detect_heading(curr_text):
        return True
    
    # Speaker turn indicates new segment
    if detect_speaker_turn(curr_text):
        return True
    
    return False


# ============================================================================
# Token-Based Chunking
# ============================================================================

def split_into_sentences(text: str) -> List[str]:
    """Split text into sentences."""
    # Simple sentence splitting
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def chunk_by_tokens(
    text: str,
    target_tokens: int = 350,
    overlap_tokens: int = 60,
    min_tokens: int = 150,
    max_tokens: int = 600,
) -> List[Dict[str, Any]]:
    """
    Chunk text by token count while respecting sentence boundaries.
    
    Args:
        text: Input text to chunk
        target_tokens: Target tokens per chunk
        overlap_tokens: Tokens to overlap between chunks
        min_tokens: Minimum tokens per chunk
        max_tokens: Maximum tokens per chunk
    
    Returns:
        List of chunk dicts with 'text', 'token_count', 'start_idx', 'end_idx'
    """
    if not text:
        return []
    
    sentences = split_into_sentences(text)
    if not sentences:
        return []
    
    chunks = []
    current_chunk_sentences = []
    current_token_count = 0
    start_idx = 0
    
    for i, sentence in enumerate(sentences):
        sentence_tokens = estimate_tokens(sentence)
        
        # Check if adding this sentence would exceed max
        if current_token_count + sentence_tokens > max_tokens and current_chunk_sentences:
            # Save current chunk
            chunk_text = ' '.join(current_chunk_sentences)
            chunks.append({
                "text": chunk_text,
                "token_count": current_token_count,
                "start_idx": start_idx,
                "end_idx": i - 1,
            })
            
            # Start new chunk with overlap
            overlap_sentences = []
            overlap_tokens_count = 0
            for s in reversed(current_chunk_sentences):
                s_tokens = estimate_tokens(s)
                if overlap_tokens_count + s_tokens <= overlap_tokens:
                    overlap_sentences.insert(0, s)
                    overlap_tokens_count += s_tokens
                else:
                    break
            
            current_chunk_sentences = overlap_sentences + [sentence]
            current_token_count = overlap_tokens_count + sentence_tokens
            start_idx = i - len(overlap_sentences)
        else:
            current_chunk_sentences.append(sentence)
            current_token_count += sentence_tokens
        
        # Check if we've hit target and should start new chunk
        if current_token_count >= target_tokens and len(current_chunk_sentences) > 1:
            chunk_text = ' '.join(current_chunk_sentences)
            chunks.append({
                "text": chunk_text,
                "token_count": current_token_count,
                "start_idx": start_idx,
                "end_idx": i,
            })
            
            # Start new chunk with overlap
            overlap_sentences = []
            overlap_tokens_count = 0
            for s in reversed(current_chunk_sentences):
                s_tokens = estimate_tokens(s)
                if overlap_tokens_count + s_tokens <= overlap_tokens:
                    overlap_sentences.insert(0, s)
                    overlap_tokens_count += s_tokens
                else:
                    break
            
            current_chunk_sentences = overlap_sentences
            current_token_count = overlap_tokens_count
            start_idx = i - len(overlap_sentences) + 1
    
    # Don't forget the last chunk
    if current_chunk_sentences:
        chunk_text = ' '.join(current_chunk_sentences)
        final_tokens = estimate_tokens(chunk_text)
        
        # Only add if it meets minimum size or it's the only chunk
        if final_tokens >= min_tokens or not chunks:
            chunks.append({
                "text": chunk_text,
                "token_count": final_tokens,
                "start_idx": start_idx,
                "end_idx": len(sentences) - 1,
            })
        elif chunks:
            # Merge with previous chunk
            chunks[-1]["text"] += ' ' + chunk_text
            chunks[-1]["token_count"] += final_tokens
            chunks[-1]["end_idx"] = len(sentences) - 1
    
    return chunks


# ============================================================================
# Source-Aware Chunking Policies
# ============================================================================

def get_chunking_policy(source_type: str) -> Dict[str, int]:
    """
    Get chunking parameters based on source type.
    
    Returns dict with:
        - target_tokens
        - overlap_tokens
        - min_tokens
        - max_tokens
    """
    source_type = (source_type or "document").lower()
    
    policies = {
        "transcript": {
            "target_tokens": int(os.getenv("TRANSCRIPT_CHUNK_TOKENS", "400")),
            "overlap_tokens": int(os.getenv("TRANSCRIPT_OVERLAP_TOKENS", "80")),
            "min_tokens": 100,
            "max_tokens": 700,
        },
        "youtube": {
            "target_tokens": int(os.getenv("TRANSCRIPT_CHUNK_TOKENS", "400")),
            "overlap_tokens": int(os.getenv("TRANSCRIPT_OVERLAP_TOKENS", "80")),
            "min_tokens": 100,
            "max_tokens": 700,
        },
        "pdf": {
            "target_tokens": int(os.getenv("PDF_CHUNK_TOKENS", "350")),
            "overlap_tokens": int(os.getenv("PDF_OVERLAP_TOKENS", "60")),
            "min_tokens": 150,
            "max_tokens": 600,
        },
        "markdown": {
            "target_tokens": int(os.getenv("MARKDOWN_CHUNK_TOKENS", "300")),
            "overlap_tokens": int(os.getenv("MARKDOWN_OVERLAP_TOKENS", "50")),
            "min_tokens": 100,
            "max_tokens": 500,
        },
        "document": {
            "target_tokens": int(os.getenv("CHUNK_TARGET_TOKENS", "350")),
            "overlap_tokens": int(os.getenv("CHUNK_OVERLAP_TOKENS", "60")),
            "min_tokens": 150,
            "max_tokens": 600,
        },
    }
    
    return policies.get(source_type, policies["document"])


def chunk_with_source_policy(
    text: str,
    source_type: str,
) -> List[Dict[str, Any]]:
    """Chunk text using source-appropriate policy."""
    policy = get_chunking_policy(source_type)
    
    return chunk_by_tokens(
        text,
        target_tokens=policy["target_tokens"],
        overlap_tokens=policy["overlap_tokens"],
        min_tokens=policy["min_tokens"],
        max_tokens=policy["max_tokens"],
    )
