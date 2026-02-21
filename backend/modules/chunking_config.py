"""
Chunking configuration and feature flags for gradual rollout.

All new chunking features are behind feature flags for safe deployment.
"""

import os
import hashlib
from typing import Optional

# ============================================================================
# Feature Flags (Phase C: Deterministic rollout)
# ============================================================================

# Master switches
RICH_CHUNK_METADATA_ENABLED = (
    os.getenv("RICH_CHUNK_METADATA_ENABLED", "false").lower() == "true"
)
CONTEXTUAL_EMBEDDING_TEXT_ENABLED = (
    os.getenv("CONTEXTUAL_EMBEDDING_TEXT_ENABLED", "false").lower() == "true"
)
STRUCTURE_AWARE_CHUNKING_ENABLED = (
    os.getenv("STRUCTURE_AWARE_CHUNKING_ENABLED", "false").lower() == "true"
)
SEMANTIC_BOUNDARY_ENABLED = (
    os.getenv("SEMANTIC_BOUNDARY_ENABLED", "false").lower() == "true"
)

# Rollout percentage (0-100)
ROLLOUT_PERCENT = int(os.getenv("CHUNKING_ROLLOUT_PERCENT", "0"))

# Chunk versioning for tracking
CHUNK_VERSION = "2.0"  # New semantic chunking version
EMBEDDING_VERSION = "2.0"  # Contextual embedding text
SCHEMA_VERSION = "2.0"  # Rich metadata schema


# ============================================================================
# Token-based Chunking Configuration (Phase B)
# ============================================================================

# Target chunk sizes in tokens (not characters)
CHUNK_TARGET_TOKENS = int(os.getenv("CHUNK_TARGET_TOKENS", "350"))
CHUNK_MIN_TOKENS = int(os.getenv("CHUNK_MIN_TOKENS", "150"))
CHUNK_MAX_TOKENS = int(os.getenv("CHUNK_MAX_TOKENS", "600"))
CHUNK_OVERLAP_TOKENS = int(os.getenv("CHUNK_OVERLAP_TOKENS", "60"))

# Source-specific policies
TRANSCRIPT_CHUNK_TOKENS = int(os.getenv("TRANSCRIPT_CHUNK_TOKENS", "400"))
TRANSCRIPT_OVERLAP_TOKENS = int(os.getenv("TRANSCRIPT_OVERLAP_TOKENS", "80"))

PDF_CHUNK_TOKENS = int(os.getenv("PDF_CHUNK_TOKENS", "350"))
PDF_OVERLAP_TOKENS = int(os.getenv("PDF_OVERLAP_TOKENS", "60"))

MARKDOWN_CHUNK_TOKENS = int(os.getenv("MARKDOWN_CHUNK_TOKENS", "300"))
MARKDOWN_OVERLAP_TOKENS = int(os.getenv("MARKDOWN_OVERLAP_TOKENS", "50"))


# ============================================================================
# Summary Generation Config
# ============================================================================

CHUNK_SUMMARIZER_MODEL = os.getenv("CHUNK_SUMMARIZER_MODEL", "gpt-4o-mini")
CHUNK_SUMMARY_MAX_TOKENS = int(os.getenv("CHUNK_SUMMARY_MAX_TOKENS", "100"))
CHUNK_SUMMARY_TIMEOUT = float(os.getenv("CHUNK_SUMMARY_TIMEOUT", "5.0"))


# ============================================================================
# Deterministic Rollout Assignment
# ============================================================================

def should_use_new_chunking(source_id: str) -> bool:
    """
    Determine if a document should use the new chunking pipeline.
    
    Uses deterministic bucketing based on source_id for:
    - Safe A/B testing
    - Consistent behavior across re-ingestion
    - Gradual rollout control
    """
    # If master switches are off, always use legacy
    if not any([
        RICH_CHUNK_METADATA_ENABLED,
        CONTEXTUAL_EMBEDDING_TEXT_ENABLED,
        STRUCTURE_AWARE_CHUNKING_ENABLED,
    ]):
        return False
    
    # Deterministic bucket assignment
    hash_input = f"chunking_v2:{source_id}"
    hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
    bucket = hash_value % 100
    
    return bucket < ROLLOUT_PERCENT


def get_chunking_version(source_id: str) -> str:
    """Get the chunking version that will be used for a source."""
    if should_use_new_chunking(source_id):
        return CHUNK_VERSION
    return "1.0"  # Legacy version


# ============================================================================
# Telemetry Helper
# ============================================================================

def get_chunking_telemetry(source_id: str) -> dict:
    """Get telemetry data for chunking decisions."""
    return {
        "chunk_version": get_chunking_version(source_id),
        "embedding_version": EMBEDDING_VERSION if should_use_new_chunking(source_id) else "1.0",
        "schema_version": SCHEMA_VERSION if should_use_new_chunking(source_id) else "1.0",
        "rich_metadata_enabled": RICH_CHUNK_METADATA_ENABLED,
        "contextual_embedding_enabled": CONTEXTUAL_EMBEDDING_TEXT_ENABLED,
        "structure_aware_enabled": STRUCTURE_AWARE_CHUNKING_ENABLED,
        "semantic_boundary_enabled": SEMANTIC_BOUNDARY_ENABLED,
        "rollout_percent": ROLLOUT_PERCENT,
        "source_bucket": int(hashlib.md5(f"chunking_v2:{source_id}".encode()).hexdigest(), 16) % 100,
    }
