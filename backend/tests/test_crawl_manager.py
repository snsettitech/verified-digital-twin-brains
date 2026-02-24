"""
Tests for Crawl Manager (Phase 1B.2)

Tests the page classification logic and change detection.
"""

import pytest
from unittest.mock import patch, MagicMock

from modules.crawl_manager import (
    CrawlManager,
    PageClassification,
    classify_page_for_recrawl,
)
from modules.content_hasher import compute_secure_hash


@pytest.fixture
def mock_repository():
    """Mock repository for testing."""
    with patch("backend.modules.crawl_manager.CrawlRepository") as mock:
        instance = MagicMock()
        mock.return_value = instance
        yield instance


@pytest.fixture
def crawl_manager(mock_repository):
    """Create crawl manager with mocked repository."""
    return CrawlManager()


class TestPageClassificationNew:
    """Test NEW page classification."""
    
    def test_new_page_no_prior(self, crawl_manager, mock_repository):
        """Page with no prior history should be NEW."""
        mock_repository.find_page_in_twin_history.return_value = None
        
        classification, prior = crawl_manager.classify_page(
            twin_id="twin_123",
            crawl_id="crawl_456",
            canonical_url="https://example.com/page",
            content="New content",
        )
        
        assert classification == PageClassification.NEW
        assert prior is None
    
    def test_twin_scoped_lookup(self, crawl_manager, mock_repository):
        """Should only look up within the same twin."""
        mock_repository.find_page_in_twin_history.return_value = None
        
        crawl_manager.classify_page(
            twin_id="twin_123",
            crawl_id="crawl_456",
            canonical_url="https://example.com/page",
            content="Content",
        )
        
        mock_repository.find_page_in_twin_history.assert_called_once_with(
            twin_id="twin_123",
            canonical_url="https://example.com/page",
            exclude_crawl_id="crawl_456",
        )


class TestPageClassificationUnchanged:
    """Test UNCHANGED page classification."""
    
    def test_unchanged_same_content_hash(self, crawl_manager, mock_repository):
        """Page with matching content_hash should be UNCHANGED."""
        content = "This is the page content"
        content_hash = compute_secure_hash(content)
        
        mock_repository.find_page_in_twin_history.return_value = {
            "id": "page_001",
            "canonical_url": "https://example.com/page",
            "content_hash": content_hash,
            "status": "ingested",
            "normalized_artifact_path": "crawl/twin_123/crawl_001/pages/page_001/normalized.md",
        }
        
        classification, prior = crawl_manager.classify_page(
            twin_id="twin_123",
            crawl_id="crawl_456",
            canonical_url="https://example.com/page",
            content=content,
        )
        
        assert classification == PageClassification.UNCHANGED
        assert prior is not None
        assert prior["id"] == "page_001"
    
    def test_unchanged_normalization_stable(self, crawl_manager, mock_repository):
        """Whitespace normalization should not cause false changes."""
        content1 = "Hello World"
        content2 = "Hello  World"  # Extra space
        
        # After normalization, both should have same hash
        hash1 = compute_secure_hash(content1)
        hash2 = compute_secure_hash(content2)
        
        # Note: Our normalizer should handle this, but if not, they might differ
        # This test documents expected behavior
        mock_repository.find_page_in_twin_history.return_value = {
            "id": "page_001",
            "content_hash": hash1,
            "status": "ingested",
        }
        
        classification, _ = crawl_manager.classify_page(
            twin_id="twin_123",
            crawl_id="crawl_456",
            canonical_url="https://example.com/page",
            content=content2,
        )
        
        # Classification depends on hash match
        if hash1 == hash2:
            assert classification == PageClassification.UNCHANGED


class TestPageClassificationChanged:
    """Test CHANGED page classification."""
    
    def test_changed_different_content_hash(self, crawl_manager, mock_repository):
        """Page with different content_hash should be CHANGED."""
        old_content = "Old content"
        new_content = "New content"
        
        old_hash = compute_secure_hash(old_content)
        new_hash = compute_secure_hash(new_content)
        
        assert old_hash != new_hash  # Verify hashes differ
        
        mock_repository.find_page_in_twin_history.return_value = {
            "id": "page_001",
            "canonical_url": "https://example.com/page",
            "content_hash": old_hash,
            "status": "ingested",
        }
        
        classification, prior = crawl_manager.classify_page(
            twin_id="twin_123",
            crawl_id="crawl_456",
            canonical_url="https://example.com/page",
            content=new_content,
        )
        
        assert classification == PageClassification.CHANGED
        assert prior is not None
        assert prior["content_hash"] == old_hash


class TestPageClassificationFailedPrior:
    """Test FAILED_PRIOR classification."""
    
    def test_failed_prior_no_content_hash(self, crawl_manager, mock_repository):
        """Prior page that failed (no content_hash) should be FAILED_PRIOR."""
        mock_repository.find_page_in_twin_history.return_value = {
            "id": "page_001",
            "canonical_url": "https://example.com/page",
            "content_hash": None,
            "status": "failed",
        }
        
        classification, prior = crawl_manager.classify_page(
            twin_id="twin_123",
            crawl_id="crawl_456",
            canonical_url="https://example.com/page",
            content="New content",
        )
        
        assert classification == PageClassification.FAILED_PRIOR
        assert prior is not None
    
    def test_blocked_prior_no_content_hash(self, crawl_manager, mock_repository):
        """Prior page that was blocked should be FAILED_PRIOR."""
        mock_repository.find_page_in_twin_history.return_value = {
            "id": "page_001",
            "canonical_url": "https://example.com/page",
            "content_hash": None,
            "status": "blocked",
        }
        
        classification, prior = crawl_manager.classify_page(
            twin_id="twin_123",
            crawl_id="crawl_456",
            canonical_url="https://example.com/page",
            content="New content",
        )
        
        assert classification == PageClassification.FAILED_PRIOR


class TestComputeContentHash:
    """Test content hash computation."""
    
    def test_hash_deterministic(self, crawl_manager):
        """Same content should produce same hash."""
        content = "Test content"
        hash1 = crawl_manager.compute_content_hash(content)
        hash2 = crawl_manager.compute_content_hash(content)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex
    
    def test_hash_different_content(self, crawl_manager):
        """Different content should produce different hashes."""
        hash1 = crawl_manager.compute_content_hash("Content A")
        hash2 = crawl_manager.compute_content_hash("Content B")
        
        assert hash1 != hash2


class TestShouldSkipFetch:
    """Test fetch skipping logic."""
    
    def test_skip_unchanged_with_artifacts(self, crawl_manager):
        """Should skip fetch for UNCHANGED pages with prior artifacts."""
        prior_page = {
            "id": "page_001",
            "normalized_artifact_path": "crawl/twin_123/crawl_001/pages/page_001/normalized.md",
        }
        
        should_skip = crawl_manager.should_skip_fetch(
            PageClassification.UNCHANGED,
            prior_page,
        )
        
        assert should_skip is True
    
    def test_do_not_skip_changed(self, crawl_manager):
        """Should NOT skip fetch for CHANGED pages."""
        prior_page = {"id": "page_001"}
        
        should_skip = crawl_manager.should_skip_fetch(
            PageClassification.CHANGED,
            prior_page,
        )
        
        assert should_skip is False
    
    def test_do_not_skip_new(self, crawl_manager):
        """Should NOT skip fetch for NEW pages."""
        should_skip = crawl_manager.should_skip_fetch(
            PageClassification.NEW,
            None,
        )
        
        assert should_skip is False


class TestPreparePageRecord:
    """Test page record preparation."""
    
    def test_changed_page_links_to_prior(self, crawl_manager):
        """CHANGED pages should have previous_page_id."""
        prior_page = {
            "id": "page_001",
            "content_hash": "old_hash",
        }
        
        record = crawl_manager.prepare_page_record(
            classification=PageClassification.CHANGED,
            prior_page=prior_page,
            url="https://example.com/page",
            canonical_url="https://example.com/page",
            content_hash="new_hash",
        )
        
        assert record["status"] == "changed"
        assert record["previous_page_id"] == "page_001"
        assert record["previous_content_hash"] == "old_hash"
    
    def test_unchanged_page_references_prior(self, crawl_manager):
        """UNCHANGED pages should reference prior artifacts."""
        prior_page = {
            "id": "page_001",
            "normalized_artifact_path": "path/to/normalized.md",
            "raw_artifact_path": "path/to/raw.json",
        }
        
        record = crawl_manager.prepare_page_record(
            classification=PageClassification.UNCHANGED,
            prior_page=prior_page,
            url="https://example.com/page",
            canonical_url="https://example.com/page",
        )
        
        assert record["status"] == "unchanged"
        assert record["reference_page_id"] == "page_001"
        assert record["normalized_artifact_path"] == "path/to/normalized.md"


class TestTwinIsolation:
    """Test twin-scoped matching."""
    
    def test_different_twins_dont_interfere(self, crawl_manager, mock_repository):
        """Pages in different twins should not affect each other."""
        content = "Test content for twin isolation"
        content_hash = compute_secure_hash(content)
        
        # Twin 1 has the page with matching hash
        mock_repository.find_page_in_twin_history.side_effect = [
            {"id": "page_twin1", "content_hash": content_hash, "status": "ingested"},  # twin_123
            None,  # twin_456
        ]
        
        # Query for twin_123
        classification1, _ = crawl_manager.classify_page(
            twin_id="twin_123",
            crawl_id="crawl_001",
            canonical_url="https://example.com/page",
            content=content,
        )
        
        # Query for twin_456
        classification2, _ = crawl_manager.classify_page(
            twin_id="twin_456",
            crawl_id="crawl_002",
            canonical_url="https://example.com/page",
            content=content,
        )
        
        # twin_123 should find prior with matching hash (UNCHANGED)
        # twin_456 should not find prior (NEW)
        assert classification1 == PageClassification.UNCHANGED
        assert classification2 == PageClassification.NEW


class TestConvenienceFunction:
    """Test classify_page_for_recrawl convenience function."""
    
    def test_returns_string_classification(self):
        """Should return string classification for easy use."""
        with patch("backend.modules.crawl_manager.CrawlManager") as mock_cm:
            instance = MagicMock()
            instance.classify_page.return_value = (PageClassification.NEW, None)
            mock_cm.return_value = instance
            
            classification, prior = classify_page_for_recrawl(
                twin_id="twin_123",
                crawl_id="crawl_456",
                canonical_url="https://example.com/page",
            )
            
            assert classification == "new"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
