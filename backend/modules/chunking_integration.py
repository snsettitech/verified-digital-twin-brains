"""
Integration layer for semantic chunking into existing ingestion pipeline.

This module provides the bridge between the new semantic chunking
and the existing process_and_index_text function.
"""

import asyncio
from typing import List, Dict, Any, Optional

from modules.chunking_config import (
    should_use_new_chunking,
    get_chunking_telemetry,
    RICH_CHUNK_METADATA_ENABLED,
    CONTEXTUAL_EMBEDDING_TEXT_ENABLED,
    STRUCTURE_AWARE_CHUNKING_ENABLED,
)
from modules.semantic_chunker import create_semantic_chunks, chunk_text_semantic
from modules.ingestion import chunk_text_with_metadata
from modules.embedding_text_builder import build_embedding_text, build_legacy_embedding_text


async def get_chunk_entries(
    text: str,
    source_id: str,
    doc_title: str,
    doc_id: str,
    source_type: str = "document",
    twin_id: Optional[str] = None,
    metadata_override: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Get chunk entries using either new or legacy chunking based on feature flags.
    
    This is the main entry point for chunking during ingestion.
    
    Args:
        text: Document text to chunk
        source_id: Source ID
        doc_title: Document title
        doc_id: Document ID
        source_type: Type of source (pdf, transcript, etc.)
        twin_id: Optional twin ID
        metadata_override: Optional metadata to merge
    
    Returns:
        List of chunk entry dicts compatible with existing pipeline
    """
    # Check if we should use new chunking
    use_new = should_use_new_chunking(source_id)
    
    # Get telemetry
    telemetry = get_chunking_telemetry(source_id)
    
    if use_new and STRUCTURE_AWARE_CHUNKING_ENABLED:
        print(f"[Chunking] Using semantic chunking for {source_id} (bucket: {telemetry['source_bucket']})")
        
        # Use new semantic chunking
        chunk_entries = await chunk_text_semantic(
            text=text,
            doc_title=doc_title,
            doc_id=doc_id,
            source_id=source_id,
            source_type=source_type,
            twin_id=twin_id,
        )
        
        # Add telemetry to each chunk
        for entry in chunk_entries:
            entry["_chunking_telemetry"] = telemetry
        
    else:
        print(f"[Chunking] Using legacy chunking for {source_id} (bucket: {telemetry['source_bucket']})")
        
        # Use legacy chunking
        chunk_entries = chunk_text_with_metadata(
            text,
            chunk_size=1000,
            overlap=200,
        )
        
        # Add legacy telemetry
        telemetry["chunk_version"] = "1.0"
        telemetry["embedding_version"] = "1.0"
        telemetry["schema_version"] = "1.0"
        
        for entry in chunk_entries:
            entry["_chunking_telemetry"] = telemetry
    
    # Apply metadata override if provided
    if metadata_override:
        for entry in chunk_entries:
            entry.update(metadata_override)
    
    return chunk_entries


def get_embedding_text_for_chunk(
    chunk_entry: Dict[str, Any],
    chunk_text_value: str,
) -> str:
    """
    Get embedding text for a chunk, using either new or legacy logic.
    
    This replaces the existing _build_embedding_text function.
    
    Args:
        chunk_entry: Chunk metadata dict
        chunk_text_value: Raw chunk text
    
    Returns:
        Text to use for embedding
    """
    # Check if this is a new-format chunk
    telemetry = chunk_entry.get("_chunking_telemetry", {})
    chunk_version = telemetry.get("chunk_version", "1.0")
    
    if chunk_version >= "2.0" and CONTEXTUAL_EMBEDDING_TEXT_ENABLED:
        # Use new contextual embedding text
        if "embedding_text" in chunk_entry and chunk_entry["embedding_text"]:
            return chunk_entry["embedding_text"]
        
        # Build on the fly if not present
        return build_embedding_text(
            chunk_summary=chunk_entry.get("chunk_summary", chunk_text_value),
            chunk_title=chunk_entry.get("chunk_title"),
            doc_title=chunk_entry.get("doc_title"),
            section_path=chunk_entry.get("section_path"),
            section_title=chunk_entry.get("section_title"),
            source_type=chunk_entry.get("source_type"),
            chunk_index=chunk_entry.get("chunk_index", 0),
        )
    else:
        # Use legacy logic
        block_type = str(chunk_entry.get("block_type") or "").strip().lower()
        section_title = str(chunk_entry.get("section_title") or "").strip()
        section_path = str(chunk_entry.get("section_path") or "").strip()
        
        return build_legacy_embedding_text(
            chunk_text=chunk_text_value,
            section_title=section_title,
            section_path=section_path,
            block_type=block_type,
        )


def should_generate_summary(chunk_entry: Dict[str, Any]) -> bool:
    """Check if this chunk needs summary generation."""
    if not RICH_CHUNK_METADATA_ENABLED:
        return False
    
    telemetry = chunk_entry.get("_chunking_telemetry", {})
    return telemetry.get("chunk_version") == "2.0"


def get_chunk_metadata_for_storage(
    chunk_entry: Dict[str, Any],
    base_metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build final metadata dict for vector storage.
    
    Merges chunk-specific metadata with base metadata.
    """
    metadata = dict(base_metadata)
    
    # Add chunk-specific fields
    chunk_fields = [
        "chunk_text",
        "chunk_summary",
        "chunk_title",
        "doc_title",
        "doc_id",
        "source_type",
        "section_title",
        "section_path",
        "section_level",
        "chunk_type",
        "speaker",
        "chunk_index",
        "total_chunks",
        "chunk_version",
        "embedding_version",
        "schema_version",
    ]
    
    for field in chunk_fields:
        if field in chunk_entry:
            metadata[field] = chunk_entry[field]
    
    # Add telemetry
    if "_chunking_telemetry" in chunk_entry:
        telemetry = chunk_entry["_chunking_telemetry"]
        metadata["_chunking_metadata"] = {
            "version": telemetry.get("chunk_version"),
            "bucket": telemetry.get("source_bucket"),
            "rich_metadata": telemetry.get("rich_metadata_enabled"),
            "contextual_embedding": telemetry.get("contextual_embedding_enabled"),
        }
    
    return metadata
