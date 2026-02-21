"""
Semantic chunking pipeline with rich metadata.

Phase A + B implementation: Structure-aware, token-based chunking
with contextual embedding text and rich metadata.
"""

import asyncio
import uuid
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from modules.doc_sectioning import extract_section_blocks
from modules.chunking_utils import (
    chunk_with_source_policy,
    detect_heading,
    detect_speaker_turn,
    estimate_tokens,
)
from modules.chunk_summarizer import generate_chunk_summary, generate_chunk_title
from modules.embedding_text_builder import build_embedding_text
from modules.chunking_config import (
    should_use_new_chunking,
    get_chunking_telemetry,
    CHUNK_VERSION,
    EMBEDDING_VERSION,
    SCHEMA_VERSION,
)


@dataclass
class SemanticChunk:
    """Rich chunk with metadata for improved retrieval."""
    
    # Core content
    chunk_text: str  # Full text for citations/grounding
    chunk_summary: str  # 1-2 sentence summary for embedding
    chunk_title: str  # Descriptive title
    
    # Document context
    doc_title: str
    doc_id: str
    source_type: str
    source_id: str
    
    # Structural metadata
    section_title: Optional[str] = None
    section_path: Optional[str] = None
    section_level: int = 0
    
    # Chunk metadata
    chunk_type: str = "paragraph"
    speaker: Optional[str] = None  # For transcripts
    
    # Positioning
    chunk_index: int = 0
    total_chunks: int = 1
    
    # Embedding
    embedding_text: str = ""  # What actually gets embedded
    
    # Version tracking
    chunk_version: str = CHUNK_VERSION
    embedding_version: str = EMBEDDING_VERSION
    schema_version: str = SCHEMA_VERSION
    
    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_vector_metadata(self) -> Dict[str, Any]:
        """Convert to metadata dict for vector store."""
        return {
            # Core content
            "chunk_text": self.chunk_text,
            "chunk_summary": self.chunk_summary,
            "chunk_title": self.chunk_title,
            
            # Document context
            "doc_title": self.doc_title,
            "doc_id": self.doc_id,
            "source_type": self.source_type,
            "source_id": self.source_id,
            
            # Structural metadata
            "section_title": self.section_title,
            "section_path": self.section_path,
            "section_level": self.section_level,
            
            # Chunk metadata
            "chunk_type": self.chunk_type,
            "speaker": self.speaker,
            
            # Positioning
            "chunk_index": self.chunk_index,
            "total_chunks": self.total_chunks,
            
            # Version tracking
            "chunk_version": self.chunk_version,
            "embedding_version": self.embedding_version,
            "schema_version": self.schema_version,
            
            # Timestamp
            "created_at": self.created_at,
        }


async def create_semantic_chunks(
    text: str,
    doc_title: str,
    doc_id: str,
    source_id: str,
    source_type: str = "document",
    twin_id: Optional[str] = None,
) -> List[SemanticChunk]:
    """
    Create semantic chunks with rich metadata.
    
    Process:
    1. Extract structure blocks (headings, sections)
    2. Apply source-aware token-based chunking
    3. Generate summaries
    4. Build contextual embedding text
    
    Args:
        text: Document text to chunk
        doc_title: Document title
        doc_id: Document ID
        source_id: Source ID
        source_type: Type of source (pdf, transcript, etc.)
        twin_id: Optional twin ID for context
    
    Returns:
        List of SemanticChunk objects
    """
    if not text or not text.strip():
        return []
    
    # Step 1: Extract structure blocks
    blocks = extract_section_blocks(text, source_id=source_id)
    
    if not blocks:
        # Fallback: treat entire text as one block
        blocks = [{"text": text, "section_title": None, "section_path": None}]
    
    chunks: List[SemanticChunk] = []
    chunk_index = 0
    
    for block in blocks:
        block_text = str(block.get("text") or "").strip()
        if not block_text:
            continue
        
        section_title = block.get("section_title")
        section_path = block.get("section_path")
        
        # Detect block type
        block_type = block.get("block_type", "paragraph")
        
        # Step 2: Smart chunking based on content type
        if source_type in ("transcript", "youtube") and block_text.count('\n') >= 3:
            # Use speaker-aware chunking for transcripts
            sub_chunks = _chunk_transcript(
                block_text,
                target_policy=source_type,
            )
        else:
            # Use standard token-based chunking
            sub_chunks = chunk_with_source_policy(block_text, source_type)
        
        # Step 3: Create SemanticChunk for each sub-chunk
        for sub_chunk in sub_chunks:
            chunk = await _create_semantic_chunk(
                text=sub_chunk["text"],
                token_count=sub_chunk.get("token_count", estimate_tokens(sub_chunk["text"])),
                doc_title=doc_title,
                doc_id=doc_id,
                source_id=source_id,
                source_type=source_type,
                section_title=section_title,
                section_path=section_path,
                section_level=_detect_section_level(section_title),
                chunk_type=block_type,
                chunk_index=chunk_index,
                speaker=sub_chunk.get("speaker"),
            )
            chunks.append(chunk)
            chunk_index += 1
    
    # Update total_chunks
    total = len(chunks)
    for chunk in chunks:
        chunk.total_chunks = total
    
    return chunks


def _chunk_transcript(text: str, target_policy: str) -> List[Dict[str, Any]]:
    """Chunk transcript with speaker turn awareness."""
    lines = text.split('\n')
    segments = []
    current_speaker = None
    current_text = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        speaker_info = detect_speaker_turn(line)
        
        if speaker_info:
            # Save previous segment
            if current_speaker and current_text:
                segments.append({
                    "speaker": current_speaker,
                    "text": ' '.join(current_text),
                })
            
            # Start new segment
            current_speaker = speaker_info["speaker"]
            current_text = [speaker_info["text"]]
        else:
            current_text.append(line)
    
    # Don't forget last segment
    if current_speaker and current_text:
        segments.append({
            "speaker": current_speaker,
            "text": ' '.join(current_text),
        })
    
    # Now chunk each segment
    result = []
    policy = {"target_tokens": 400, "overlap_tokens": 80, "min_tokens": 100, "max_tokens": 700}
    
    for segment in segments:
        sub_chunks = chunk_with_source_policy(segment["text"], "transcript")
        for sub in sub_chunks:
            sub["speaker"] = segment["speaker"]
            result.append(sub)
    
    return result


async def _create_semantic_chunk(
    text: str,
    token_count: int,
    doc_title: str,
    doc_id: str,
    source_id: str,
    source_type: str,
    section_title: Optional[str],
    section_path: Optional[str],
    section_level: int,
    chunk_type: str,
    chunk_index: int,
    speaker: Optional[str] = None,
) -> SemanticChunk:
    """Create a single semantic chunk with all metadata."""
    
    # Generate summary (async)
    summary = await generate_chunk_summary(
        chunk_text=text,
        doc_title=doc_title,
        section_title=section_title,
    )
    
    # Generate title
    title = generate_chunk_title(text, section_title)
    
    # Build embedding text with context
    embedding = build_embedding_text(
        chunk_summary=summary,
        chunk_title=title,
        doc_title=doc_title,
        section_path=section_path,
        section_title=section_title,
        source_type=source_type,
        chunk_index=chunk_index,
    )
    
    return SemanticChunk(
        chunk_text=text,
        chunk_summary=summary,
        chunk_title=title,
        doc_title=doc_title,
        doc_id=doc_id,
        source_type=source_type,
        source_id=source_id,
        section_title=section_title,
        section_path=section_path,
        section_level=section_level,
        chunk_type=chunk_type,
        speaker=speaker,
        chunk_index=chunk_index,
        embedding_text=embedding,
    )


def _detect_section_level(section_title: Optional[str]) -> int:
    """Detect section level from title (simple heuristic)."""
    if not section_title:
        return 0
    
    # Count indicators of depth
    level = 1
    if '>' in section_title or '→' in section_title:
        level += section_title.count('>') + section_title.count('→')
    if section_title.startswith('  ') or section_title.startswith('\t'):
        level += 1
    
    return min(level, 5)  # Cap at 5 levels


# ============================================================================
# Backward Compatibility
# ============================================================================

async def chunk_text_semantic(
    text: str,
    doc_title: str,
    doc_id: str,
    source_id: str,
    source_type: str = "document",
    twin_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Drop-in replacement for chunk_text_with_metadata.
    
    Returns list of dicts compatible with existing code,
    but with additional rich metadata fields.
    """
    chunks = await create_semantic_chunks(
        text=text,
        doc_title=doc_title,
        doc_id=doc_id,
        source_id=source_id,
        source_type=source_type,
        twin_id=twin_id,
    )
    
    # Convert to dicts for backward compatibility
    return [chunk.to_vector_metadata() for chunk in chunks]
