"""
Tests for Chunk Version Manager (Phase 2.4)

Covers:
- Tombstone detection
- Version metadata building
- Retrieval filter construction
- Tombstone operations
"""

import pytest
from unittest.mock import Mock, patch

from modules.chunk_version_manager import (
    ChunkVersionManager,
    build_retrieval_filter,
    is_tombstoned
)


class TestIsTombstoned:
    """Test tombstone detection from metadata."""
    
    def test_is_tombstoned_explicit_false(self):
        """is_current=False indicates tombstoned."""
        metadata = {"is_current": False, "chunk_id": "chunk_123"}
        assert is_tombstoned(metadata) is True
    
    def test_is_tombstoned_by_timestamp(self):
        """tombstoned_at set indicates tombstoned."""
        metadata = {"is_current": True, "tombstoned_at": "2024-01-01T00:00:00Z"}
        assert is_tombstoned(metadata) is True
    
    def test_not_tombstoned_current(self):
        """is_current=True means not tombstoned."""
        metadata = {"is_current": True, "tombstoned_at": None}
        assert is_tombstoned(metadata) is False
    
    def test_not_tombstoned_no_field(self):
        """Missing is_current field means not tombstoned (legacy)."""
        metadata = {"chunk_id": "chunk_123", "text": "content"}
        assert is_tombstoned(metadata) is False
    
    def test_not_tombstoned_null_timestamp(self):
        """null tombstoned_at means not tombstoned."""
        metadata = {"is_current": True, "tombstoned_at": None}
        assert is_tombstoned(metadata) is False


class TestBuildRetrievalFilter:
    """Test retrieval filter construction."""
    
    def test_default_excludes_tombstoned(self):
        """Default filter excludes tombstoned chunks."""
        filter_dict = build_retrieval_filter()
        
        assert "$or" in filter_dict
        # Should include is_current=True OR is_current not exists
        or_conditions = filter_dict["$or"]
        assert any(cond.get("is_current") == {"$eq": True} for cond in or_conditions)
        assert any(cond.get("is_current") == {"$exists": False} for cond in or_conditions)
    
    def test_include_tombstoned(self):
        """include_tombstoned=True returns base filter only."""
        base = {"twin_id": {"$eq": "twin_123"}}
        filter_dict = build_retrieval_filter(base_filter=base, include_tombstoned=True)
        
        assert filter_dict == base
    
    def test_combines_with_base_filter(self):
        """Tombstone filter combines with base filter using AND."""
        base = {"twin_id": {"$eq": "twin_123"}}
        filter_dict = build_retrieval_filter(base_filter=base)
        
        assert "$and" in filter_dict
        and_conditions = filter_dict["$and"]
        assert base in and_conditions
        # One of the conditions should be tombstone filter
        assert any("$or" in cond for cond in and_conditions)


class TestChunkVersionManager:
    """Test ChunkVersionManager class."""
    
    def test_init(self):
        """Manager initializes correctly."""
        manager = ChunkVersionManager()
        assert manager._index is None
    
    def test_build_versioned_metadata(self):
        """Build metadata with versioning fields."""
        manager = ChunkVersionManager()
        base = {"text": "content", "source_id": "src_123"}
        
        result = manager.build_versioned_metadata(
            base_metadata=base,
            crawl_id="crawl_456",
            crawl_page_id="page_789",
            canonical_url="https://example.com",
            content_hash="abc123",
            chunk_version=2
        )
        
        assert result["text"] == "content"  # Preserved
        assert result["source_id"] == "src_123"  # Preserved
        assert result["crawl_id"] == "crawl_456"
        assert result["crawl_page_id"] == "page_789"
        assert result["canonical_url"] == "https://example.com"
        assert result["content_hash"] == "abc123"
        assert result["chunk_version"] == 2
        assert result["is_current"] is True
        assert result["tombstoned_at"] is None
    
    def test_build_versioned_metadata_defaults(self):
        """Build metadata with default version=1."""
        manager = ChunkVersionManager()
        base = {"text": "content"}
        
        result = manager.build_versioned_metadata(
            base_metadata=base,
            crawl_id="crawl_456",
            crawl_page_id="page_789",
            canonical_url="https://example.com",
            content_hash="abc123"
        )
        
        assert result["chunk_version"] == 1
    
    @pytest.mark.asyncio
    async def test_get_next_version_default(self):
        """Default next version is 2."""
        manager = ChunkVersionManager()
        version = await manager.get_next_version("previous_page_123")
        assert version == 2
    
    @pytest.mark.asyncio
    async def test_tombstone_previous_version(self):
        """Tombstone operation returns 0 (stub implementation)."""
        manager = ChunkVersionManager()
        count = await manager.tombstone_previous_version("page_123", "twin_456")
        assert count == 0  # Stub returns 0
    
    @pytest.mark.asyncio
    async def test_tombstone_removed_page(self):
        """Tombstone removed page returns 0 (stub implementation)."""
        manager = ChunkVersionManager()
        count = await manager.tombstone_removed_page("page_123", "twin_456")
        assert count == 0  # Stub returns 0
    
    @pytest.mark.asyncio
    async def test_get_current_chunks_returns_empty(self):
        """get_current_chunks returns empty list (stub)."""
        manager = ChunkVersionManager()
        chunks = await manager.get_current_chunks("page_123", "twin_456")
        assert chunks == []


class TestTombstoneFilterEdgeCases:
    """Test edge cases for tombstone filtering."""
    
    def test_empty_metadata(self):
        """Empty metadata is not tombstoned."""
        assert is_tombstoned({}) is False
    
    def test_null_is_current(self):
        """Null is_current should be treated as not tombstoned (current)."""
        # Actually, in Python None is falsy, so this might be ambiguous
        # The implementation treats None as "not explicitly False"
        metadata = {"is_current": None}
        # Implementation detail: None != False, so not tombstoned
        # This is acceptable because we only tombstone when explicitly False
        result = is_tombstoned(metadata)
        # The implementation checks: is_current is False
        assert result is False


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
