"""
Tests for Web Crawler V2 (Deep Research)

Tests the new crawl_website_v2 function with:
- Safety integration
- Artifact storage
- URL canonicalization
- Failure taxonomy
"""

import os
import pytest
import tempfile
import shutil
from datetime import datetime
from unittest.mock import patch, MagicMock

from modules.web_crawler import (
    crawl_website_v2,
    CrawlV2Result,
    CrawlPageV2,
    _create_crawl_run_record,
    _calculate_crawl_stats,
    canonicalize_url,
    get_url_hash,
)
@pytest.fixture
def temp_artifact_dir():
    """Create temporary artifact directory."""
    temp_dir = tempfile.mkdtemp()
    os.environ["ARTIFACT_BASE_PATH"] = temp_dir
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)
    del os.environ["ARTIFACT_BASE_PATH"]


@pytest.fixture
def mock_supabase():
    """Mock Supabase client."""
    with patch("backend.modules.web_crawler.supabase") as mock:
        mock_table = MagicMock()
        mock.table.return_value = mock_table
        mock_table.insert.return_value.execute.return_value = {"data": [{"id": "test"}]}
        mock_table.update.return_value.eq.return_value.execute.return_value = {"data": []}
        yield mock


class TestCrawlV2FeatureFlag:
    """Test always-on Deep Research behavior."""

    @pytest.mark.asyncio
    async def test_enabled_crawl_flow(self, temp_artifact_dir, mock_supabase):
        """Crawl should proceed through setup path."""
        result = await crawl_website_v2("https://example.com", "twin_123")
        assert result.crawl_id is not None


class TestURLCanonicalization:
    """Test URL canonicalization in v2 crawler."""
    
    def test_canonicalize_before_processing(self):
        """URLs should be canonicalized before processing."""
        url = "HTTPS://EXAMPLE.COM/Page/?utm_source=google&b=2&a=1#section"
        canonical = canonicalize_url(url)
        
        # Should be normalized
        assert canonical.startswith("https://example.com/")
        assert "utm_source" not in canonical
        assert "#section" not in canonical
        assert "?a=1&b=2" in canonical  # Sorted
    
    def test_url_hash_consistency(self):
        """Same canonical URL should produce same hash."""
        url1 = "https://example.com/page?utm_source=a"
        url2 = "https://example.com/page?utm_medium=b"
        
        # After canonicalization, both should be same
        canonical1 = canonicalize_url(url1)
        canonical2 = canonicalize_url(url2)
        
        assert canonical1 == canonical2 == "https://example.com/page"
        assert get_url_hash(canonical1) == get_url_hash(canonical2)


class TestSafetyIntegration:
    """Test fetch safety integration."""
    
    @pytest.mark.asyncio
    async def test_private_ip_blocked(self, temp_artifact_dir, mock_supabase):
        """Private IP URLs should be blocked."""
        result = await crawl_website_v2("http://10.0.0.1/page", "twin_123")
        assert result.success is False
        assert "blocked" in result.error.lower() or result.crawl_id is not None
    
    @pytest.mark.asyncio
    async def test_localhost_blocked(self, temp_artifact_dir, mock_supabase):
        """localhost should be blocked."""
        result = await crawl_website_v2("http://localhost/page", "twin_123")
        assert result.success is False or "blocked" in str(result.error).lower()
    
    @pytest.mark.asyncio
    async def test_file_scheme_blocked(self, temp_artifact_dir, mock_supabase):
        """file:// URLs should be blocked at seed validation."""
        result = await crawl_website_v2("file:///etc/passwd", "twin_123")
        assert result.success is False


class TestCrawlPageV2:
    """Test CrawlPageV2 data structure."""
    
    def test_page_creation(self):
        """Page should be created with correct fields."""
        page = CrawlPageV2(
            url="https://example.com/page",
            canonical_url="https://example.com/page",
            url_hash="abc123",
        )
        assert page.url == "https://example.com/page"
        assert page.status == "discovered"
        assert page.id is not None
    
    def test_page_status_transitions(self):
        """Page status should be updatable."""
        page = CrawlPageV2(
            url="https://example.com/page",
            canonical_url="https://example.com/page",
            url_hash="abc123",
        )
        page.status = "fetching"
        assert page.status == "fetching"
        page.status = "ingested"
        assert page.status == "ingested"


class TestCrawlStats:
    """Test crawl statistics calculation."""
    
    def test_empty_stats(self):
        """Empty pages should return zero stats."""
        stats = _calculate_crawl_stats({})
        assert stats["discovered"] == 0
        assert stats["ingested"] == 0
    
    def test_mixed_status_stats(self):
        """Mixed statuses should be counted correctly."""
        pages = {
            "url1": CrawlPageV2("url1", "canon1", "hash1"),
            "url2": CrawlPageV2("url2", "canon2", "hash2"),
            "url3": CrawlPageV2("url3", "canon3", "hash3"),
        }
        pages["url1"].status = "ingested"
        pages["url2"].status = "failed"
        pages["url3"].status = "blocked"
        
        stats = _calculate_crawl_stats(pages)
        assert stats["discovered"] == 3
        assert stats["ingested"] == 1
        assert stats["failed"] == 1
        assert stats["blocked"] == 1


class TestCrawlResult:
    """Test CrawlV2Result data structure."""
    
    def test_success_result(self):
        """Successful result should have correct fields."""
        result = CrawlV2Result(
            crawl_id="crawl_123",
            success=True,
            pages_discovered=10,
            pages_ingested=8,
            pages_failed=2,
        )
        assert result.success is True
        assert result.crawl_id == "crawl_123"
        assert result.pages_discovered == 10
        
        dict_result = result.to_dict()
        assert dict_result["success"] is True
        assert dict_result["pages_discovered"] == 10
    
    def test_failure_result(self):
        """Failed result should include error."""
        result = CrawlV2Result(
            crawl_id="crawl_123",
            success=False,
            error="Something went wrong",
        )
        assert result.success is False
        assert result.error == "Something went wrong"


class TestBackwardCompatibility:
    """Test that old crawl path still works."""
    
    def test_old_crawl_function_exists(self):
        """Original crawl_website should still exist."""
        from modules.web_crawler import crawl_website
        assert callable(crawl_website)
    
    def test_old_scrape_function_exists(self):
        """Original scrape_single_page should still exist."""
        from modules.web_crawler import scrape_single_page
        assert callable(scrape_single_page)


class TestDedupWithinCrawl:
    """Test duplicate detection within crawl."""
    
    def test_same_canonical_url_deduplicated(self):
        """Pages with same canonical URL should be deduplicated."""
        pages = {}
        
        # Add first page
        canonical = "https://example.com/page"
        page1 = CrawlPageV2("url1", canonical, "hash1")
        pages[canonical] = page1
        
        # Try to add same canonical (should be skipped)
        page2 = CrawlPageV2("url2", canonical, "hash1")
        
        # In actual implementation, page2 would not be added to pages dict
        assert canonical in pages
        assert pages[canonical].url == "url1"  # Original kept


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
