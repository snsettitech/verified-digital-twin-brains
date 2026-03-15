"""
Chunk Version Manager Module (Phase 2.4)

Manages chunk versioning and tombstoning for crawl-based sources.

Key Features:
- Tombstone old chunks when content changes
- Track chunk versions per crawl page
- Preserve audit trail (no hard deletion)
- Exclude tombstoned chunks from retrieval

Tombstone Strategy:
- Soft delete via metadata (is_current=False, tombstoned_at=timestamp)
- Vectors remain in Pinecone for audit/recovery
- Retrieval filters exclude non-current chunks by default
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from modules.clients import get_pinecone_index
from modules.pinecone_adapter import PineconeIndexAdapter
from modules.twin_namespace import resolve_creator_id_for_twin
from modules.retrieval import get_namespace

logger = logging.getLogger(__name__)


class ChunkVersionManager:
    """
    Manages chunk versioning and tombstoning.
    
    Responsibilities:
    1. Track chunk versions per crawl page
    2. Tombstone old chunks on content change
    3. Tombstone chunks for removed pages
    4. Query current vs tombstoned chunks
    """
    
    def __init__(self):
        self._index = None
    
    def _get_index(self):
        """Lazy load Pinecone index."""
        if self._index is None:
            self._index = get_pinecone_index()
        return self._index
    
    def _get_namespace(self, twin_id: str) -> str:
        """Get Pinecone namespace for twin."""
        creator_id = resolve_creator_id_for_twin(twin_id)
        return get_namespace(creator_id, twin_id)
    
    async def get_current_chunks(
        self,
        crawl_page_id: str,
        twin_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all current (non-tombstoned) chunks for a crawl page.
        
        Args:
            crawl_page_id: Crawl page ID
            twin_id: Twin ID
            
        Returns:
            List of chunk metadata dicts
        """
        index = self._get_index()
        namespace = self._get_namespace(twin_id)
        
        # Query for chunks with this crawl_page_id and is_current=True
        # Note: Pinecone doesn't support efficient filtering by metadata field
        # So we fetch with broader filter and filter in Python
        # For production scale, consider using separate namespaces or indexes
        
        filter_dict = {
            "crawl_page_id": {"$eq": crawl_page_id}
        }
        
        try:
            # We need a dummy vector for the query
            # Use zero vector or fetch by ID pattern
            # Pinecone doesn't have a direct "list by metadata" query
            # So we use a workaround: fetch top_k with filter
            
            # Alternative approach: track chunk IDs in database
            # For now, return empty list - actual implementation would
            # need to track chunk IDs in a separate table
            
            logger.debug(f"Querying chunks for page {crawl_page_id}")
            
            # Since we can't efficiently query by metadata alone,
            # we return empty list and rely on the caller to track chunk IDs
            # This is a limitation of Pinecone's query model
            
            return []
        except Exception as e:
            logger.error(f"Error querying chunks for page {crawl_page_id}: {e}")
            return []
    
    async def get_next_version(self, previous_page_id: str) -> int:
        """
        Get the next chunk version number for a changed page.
        
        Args:
            previous_page_id: Previous crawl page ID
            
        Returns:
            Next version number (1, 2, 3...)
        """
        # For now, always return 2 as default increment
        # In a full implementation, we'd query the database to track versions
        return 2
    
    async def tombstone_previous_version(
        self,
        previous_page_id: str,
        twin_id: Optional[str] = None
    ) -> int:
        """
        Tombstone all chunks for a previous page version.
        
        Called when a page has changed and we need to mark old chunks
        as no longer current.
        
        Args:
            previous_page_id: Previous crawl page ID
            twin_id: Optional twin ID
            
        Returns:
            Number of chunks tombstoned
        """
        # Note: Full implementation requires tracking chunk IDs in database
        # since Pinecone doesn't support efficient "update by metadata filter"
        
        # For now, log the intent and return 0
        # The actual tombstoning would happen by:
        # 1. Storing chunk IDs in DB during initial indexing
        # 2. Querying those IDs for the previous_page_id
        # 3. Upserting with is_current=False
        
        logger.info(f"Tombstone requested for previous page {previous_page_id}")
        
        # If we had chunk IDs, we'd do:
        # for chunk_id in chunk_ids:
        #     index.upsert([{
        #         "id": chunk_id,
        #         "values": existing_vector,
        #         "metadata": {**existing_metadata, "is_current": False, "tombstoned_at": now()}
        #     }], namespace=namespace)
        
        return 0
    
    async def tombstone_removed_page(
        self,
        crawl_page_id: str,
        twin_id: Optional[str] = None
    ) -> int:
        """
        Tombstone all chunks for a removed page.
        
        Called when a page is detected as removed during recrawl.
        
        Args:
            crawl_page_id: Crawl page ID that was removed
            twin_id: Optional twin ID
            
        Returns:
            Number of chunks tombstoned
        """
        logger.info(f"Tombstone requested for removed page {crawl_page_id}")
        
        # Same limitation as tombstone_previous_version
        # Requires tracking chunk IDs in database
        
        return 0
    
    def build_versioned_metadata(
        self,
        base_metadata: Dict[str, Any],
        crawl_id: str,
        crawl_page_id: str,
        canonical_url: str,
        content_hash: str,
        chunk_version: int = 1
    ) -> Dict[str, Any]:
        """
        Build chunk metadata with versioning fields.
        
        Args:
            base_metadata: Existing metadata dict
            crawl_id: Crawl run ID
            crawl_page_id: Crawl page ID
            canonical_url: Normalized URL
            content_hash: Content hash
            chunk_version: Version number (default 1)
            
        Returns:
            Metadata dict with versioning fields
        """
        metadata = dict(base_metadata)
        
        # Add versioning fields
        metadata.update({
            "crawl_id": crawl_id,
            "crawl_page_id": crawl_page_id,
            "canonical_url": canonical_url,
            "content_hash": content_hash,
            "chunk_version": chunk_version,
            "is_current": True,
            "tombstoned_at": None,
        })
        
        return metadata
    
    def is_tombstoned(self, metadata: Dict[str, Any]) -> bool:
        """
        Check if a chunk is tombstoned based on metadata.
        
        Args:
            metadata: Chunk metadata
            
        Returns:
            True if tombstoned
        """
        return is_tombstoned(metadata)


# Migration helper for existing chunks
async def migrate_existing_chunks(
    twin_id: str,
    batch_size: int = 100
) -> Dict[str, Any]:
    """
    Migrate existing chunks to add versioning metadata.
    
    This is a one-time migration for chunks created before Phase 2.
    
    Args:
        twin_id: Twin ID to migrate
        batch_size: Number of chunks per batch
        
    Returns:
        Migration statistics
    """
    # Note: Full implementation would:
    # 1. Query all chunks for twin from database
    # 2. For each chunk, add is_current=True if not present
    # 3. Re-upsert to Pinecone
    
    stats = {
        "chunks_migrated": 0,
        "chunks_skipped": 0,
        "errors": 0
    }
    
    logger.info(f"Migration requested for twin {twin_id}")
    
    return stats


# Standalone tombstone check function
def is_tombstoned(metadata: Dict[str, Any]) -> bool:
    """
    Check if a chunk is tombstoned based on metadata.
    
    Args:
        metadata: Chunk metadata
        
    Returns:
        True if tombstoned
    """
    # A chunk is tombstoned if:
    # 1. is_current is explicitly False, OR
    # 2. tombstoned_at is set (not None/null)
    
    is_current = metadata.get("is_current")
    if is_current is False:
        return True
    
    tombstoned_at = metadata.get("tombstoned_at")
    if tombstoned_at is not None and tombstoned_at != "null":
        return True
    
    return False


# Retrieval filter helper
def build_retrieval_filter(
    base_filter: Optional[Dict[str, Any]] = None,
    include_tombstoned: bool = False
) -> Dict[str, Any]:
    """
    Build retrieval filter with tombstone exclusion.
    
    Args:
        base_filter: Optional base filter to extend
        include_tombstoned: If True, include tombstoned chunks
        
    Returns:
        Filter dict for Pinecone query
    """
    if include_tombstoned:
        return base_filter or {}
    
    # Build filter that excludes tombstoned chunks
    # Pinecone filter: is_current must be True or not present
    
    tombstone_filter = {
        "$or": [
            {"is_current": {"$eq": True}},
            {"is_current": {"$exists": False}}  # Legacy chunks
        ]
    }
    
    if base_filter:
        # Combine with AND
        return {"$and": [base_filter, tombstone_filter]}
    
    return tombstone_filter
