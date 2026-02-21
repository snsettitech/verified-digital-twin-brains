"""
Build contextual embedding text with rich metadata.

This is the core of Phase A: creating embedding_text that includes
document context, section info, and chunk summary for better retrieval.
"""

from typing import Optional, Dict, Any


def build_embedding_text(
    chunk_summary: str,
    chunk_title: Optional[str] = None,
    doc_title: Optional[str] = None,
    section_path: Optional[str] = None,
    section_title: Optional[str] = None,
    source_type: Optional[str] = None,
    chunk_index: int = 0,
    total_chunks: int = 1,
) -> str:
    """
    Build the text that will actually be embedded.
    
    This contextualized text improves retrieval by including:
    - Document title (for context)
    - Section path (for hierarchy)
    - Chunk title/topic (for specificity)
    - Source type (for filtering)
    - Summary (the actual semantic content)
    
    Args:
        chunk_summary: 1-2 sentence summary of chunk content
        chunk_title: Descriptive title for this chunk
        doc_title: Parent document title
        section_path: Hierarchical section path (e.g., "Section A > Subsection B")
        section_title: Immediate section title
        source_type: Source type (pdf, transcript, etc.)
        chunk_index: Position in document
        total_chunks: Total chunks in document
    
    Returns:
        Formatted embedding text with context
    """
    parts = []
    
    # Document context (most general)
    if doc_title:
        parts.append(f"Document: {doc_title}")
    
    # Section hierarchy
    section_display = section_path or section_title
    if section_display:
        parts.append(f"Section: {section_display}")
    
    # Chunk-specific context
    if chunk_title:
        parts.append(f"Topic: {chunk_title}")
    
    # Source type hint
    if source_type:
        parts.append(f"Type: {source_type}")
    
    # Add separator between context and content
    if parts:
        parts.append("")
    
    # Main content (the summary)
    parts.append(chunk_summary)
    
    return "\n".join(parts)


def build_embedding_text_from_chunk(
    chunk: Dict[str, Any],
    doc_title: Optional[str] = None,
    source_type: Optional[str] = None,
) -> str:
    """
    Convenience function to build embedding text from a chunk dict.
    
    Args:
        chunk: Chunk dict with keys like 'summary', 'title', 'section_title', etc.
        doc_title: Document title (if not in chunk)
        source_type: Source type (if not in chunk)
    
    Returns:
        Formatted embedding text
    """
    return build_embedding_text(
        chunk_summary=chunk.get("summary") or chunk.get("text", ""),
        chunk_title=chunk.get("title") or chunk.get("chunk_title"),
        doc_title=chunk.get("doc_title") or doc_title,
        section_path=chunk.get("section_path"),
        section_title=chunk.get("section_title"),
        source_type=chunk.get("source_type") or source_type,
        chunk_index=chunk.get("chunk_index", 0),
        total_chunks=chunk.get("total_chunks", 1),
    )


def build_legacy_embedding_text(
    chunk_text: str,
    section_title: Optional[str] = None,
    section_path: Optional[str] = None,
    block_type: Optional[str] = None,
) -> str:
    """
    Build embedding text using legacy logic (for backward compatibility).
    
    This replicates the existing _build_embedding_text behavior.
    """
    # Replicate existing logic from ingestion.py
    if block_type == "prompt_question":
        descriptor = section_title or section_path
        if descriptor:
            return descriptor
    
    return chunk_text


# ============================================================================
# Unit Test Helpers
# ============================================================================

def validate_embedding_text(embedding_text: str) -> Dict[str, Any]:
    """
    Validate that embedding text is well-formed.
    
    Returns dict with:
        - valid: bool
        - has_context: bool (has document/section context)
        - has_content: bool (has actual content)
        - length: int (character length)
        - warnings: list of warning strings
    """
    warnings = []
    
    # Check length
    length = len(embedding_text)
    if length < 50:
        warnings.append(f"Very short embedding text ({length} chars)")
    if length > 4000:
        warnings.append(f"Very long embedding text ({length} chars)")
    
    # Check for context markers
    has_doc_context = "Document:" in embedding_text
    has_section_context = "Section:" in embedding_text
    has_context = has_doc_context or has_section_context
    
    # Check for content
    lines = embedding_text.split('\n')
    content_lines = [l for l in lines if l.strip() and not l.startswith(("Document:", "Section:", "Topic:", "Type:"))]
    has_content = len(content_lines) > 0
    
    if not has_content:
        warnings.append("No content found in embedding text")
    
    return {
        "valid": has_content,
        "has_context": has_context,
        "has_content": has_content,
        "length": length,
        "warnings": warnings,
    }
