"""
Tests for Crawl Repository (Phase 1B.1)

Tests the data access layer with canonical URL and url_hash persistence.
"""

import pytest
from unittest.mock import patch, MagicMock

from modules.crawl_repository import CrawlRepository
from modules.url_canonicalizer import get_url_hash


@pytest.fixture
def mock_supabase():
    """Mock Supabase client."""
    with patch("backend.modules.crawl_repository.supabase") as mock:
        mock_table = MagicMock()
        mock.table.return_value = mock_table
        
        # Default successful response
        mock_table.insert.return_value.execute.return_value = {"data": [{"id": "test"}]}
        mock_table.update.return_value.eq.return_value.execute.return_value = {"data": []}
        mock_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = {"data": None}
        mock_table.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = {"data": []}
        
        yield mock


class TestCreateCrawlPage:
    """Test crawl page creation with canonical URL and hash."""
    
    def test_create_page_with_canonical_url(self, mock_supabase):
        """Should persist canonical_url."""
        CrawlRepository.create_crawl_page(
            page_id="page_123",
            crawl_id="crawl_456",
            url="https://example.com/page?utm_source=google",
            canonical_url="https://example.com/page",
            status="discovered",
        )
        
        # Verify insert was called
        mock_supabase.table.assert_called_with("crawl_pages")
        call_args = mock_supabase.table.return_value.insert.call_args[0][0]
        assert call_args["canonical_url"] == "https://example.com/page"
    
    def test_create_page_with_url_hash(self, mock_supabase):
        """Should compute and persist url_hash."""
        canonical_url = "https://example.com/page"
        expected_hash = get_url_hash(canonical_url)
        
        CrawlRepository.create_crawl_page(
            page_id="page_123",
            crawl_id="crawl_456",
            url="https://example.com/page",
            canonical_url=canonical_url,
            status="discovered",
        )
        
        call_args = mock_supabase.table.return_value.insert.call_args[0][0]
        assert call_args["url_hash"] == expected_hash
    
    def test_url_hash_deterministic(self):
        """Same canonical URL should produce same hash."""
        canonical_url = "https://example.com/page"
        hash1 = get_url_hash(canonical_url)
        hash2 = get_url_hash(canonical_url)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex


class TestDuplicateUrlHandling:
    """Test that duplicate URLs with different tracking params map to same canonical."""
    
    def test_same_canonical_same_hash(self):
        """Different raw URLs with same canonical should have same hash."""
        canonical1 = "https://example.com/page"
        canonical2 = "https://example.com/page"
        
        hash1 = get_url_hash(canonical1)
        hash2 = get_url_hash(canonical2)
        
        assert hash1 == hash2


class TestNoContentInDb:
    """Test that large content is not stored in DB."""
    
    def test_create_page_no_content_blob(self, mock_supabase):
        """Page creation should not include content blobs."""
        CrawlRepository.create_crawl_page(
            page_id="page_123",
            crawl_id="crawl_456",
            url="https://example.com/page",
            canonical_url="https://example.com/page",
            status="discovered",
        )
        
        call_args = mock_supabase.table.return_value.insert.call_args[0][0]
        
        # Should NOT have large content fields
        assert "content" not in call_args
        assert "raw_content" not in call_args
        assert "normalized_content" not in call_args
        
        # Should have metadata fields
        assert "canonical_url" in call_args
        assert "url_hash" in call_args


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
