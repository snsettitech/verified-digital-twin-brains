"""
Crawl Manager Module (Phase 1B.2)

Orchestrates crawls with idempotency support using content hash comparison.

Classification Rules:
- NEW: No prior page with same canonical_url for this twin
- UNCHANGED: Prior page exists with same canonical_url AND same content_hash
- CHANGED: Prior page exists with same canonical_url BUT different content_hash
- FAILED_PRIOR: Prior page failed (no content_hash) - treated as NEW for safety

Edge Cases Handled:
- Twin-scoped matching (never compare across twins)
- Failed prior pages don't produce false "unchanged" classifications
- Whitespace-normalized content hashing
- In-run deduplication (same crawl run)
- Version chaining via previous_page_id
"""

import logging
import sys
from typing import Optional, Dict, Any, Tuple
from enum import Enum

from modules.crawl_repository import CrawlRepository
from modules.content_hasher import compute_secure_hash

# Keep module identity stable across both import paths:
# "modules.crawl_manager" and "backend.modules.crawl_manager".
if __name__.startswith("modules."):
    sys.modules.setdefault(f"backend.{__name__}", sys.modules[__name__])
elif __name__.startswith("backend.modules."):
    sys.modules.setdefault(__name__.replace("backend.", "", 1), sys.modules[__name__])

logger = logging.getLogger(__name__)


class PageClassification(str, Enum):
    """Classification of a page during recrawl."""
    NEW = "new"              # No prior page with this canonical_url
    UNCHANGED = "unchanged"  # Prior page exists, same content_hash
    CHANGED = "changed"      # Prior page exists, different content_hash
    FAILED_PRIOR = "failed_prior"  # Prior page failed, no content_hash to compare


class CrawlManager:
    """
    Manages crawl operations with idempotency and change detection.
    
    This is the main orchestrator for crawl classification and processing.
    """
    
    def __init__(self):
        self.repository = CrawlRepository()
    
    def classify_page(
        self,
        twin_id: str,
        crawl_id: str,
        canonical_url: str,
        content: Optional[str] = None,
    ) -> Tuple[PageClassification, Optional[Dict[str, Any]]]:
        """
        Classify a page during crawl based on prior crawl history.
        
        Args:
            twin_id: Twin ID (for scoping)
            crawl_id: Current crawl run ID (to exclude from lookup)
            canonical_url: Normalized canonical URL
            content: Page content (for hash computation if needed)
        
        Returns:
            Tuple of (classification, prior_page_record or None)
            
        Classification Logic:
        1. Look up latest prior page with same canonical_url for this twin
        2. If no prior page -> NEW
        3. If prior page has no content_hash (failed/blocked) -> FAILED_PRIOR
        4. Compute content hash of current content
        5. If content_hash matches prior -> UNCHANGED
        6. If content_hash differs -> CHANGED
        """
        # Find the most recent prior page with same canonical_url
        prior_page = self.repository.find_page_in_twin_history(
            twin_id=twin_id,
            canonical_url=canonical_url,
            exclude_crawl_id=crawl_id,
        )
        
        if not prior_page:
            logger.debug(f"No prior page found for {canonical_url}, classifying as NEW")
            return PageClassification.NEW, None
        
        # Check if prior page has content_hash (successful ingestion)
        prior_content_hash = prior_page.get("content_hash")
        prior_status = prior_page.get("status")
        
        if not prior_content_hash or prior_status in ("failed", "blocked", "error"):
            logger.debug(
                f"Prior page for {canonical_url} has no content_hash "
                f"(status: {prior_status}), classifying as FAILED_PRIOR"
            )
            return PageClassification.FAILED_PRIOR, prior_page
        
        # We have a prior page with content_hash - need to compare
        if content is None:
            # No content provided to compare - treat as CHANGED to be safe
            logger.warning(
                f"No content provided for comparison with {canonical_url}, "
                "classifying as CHANGED to be safe"
            )
            return PageClassification.CHANGED, prior_page
        
        # Compute content hash
        current_content_hash = compute_secure_hash(content)
        
        # Compare hashes
        if current_content_hash == prior_content_hash:
            logger.debug(
                f"Content hash match for {canonical_url}, classifying as UNCHANGED"
            )
            return PageClassification.UNCHANGED, prior_page
        else:
            logger.debug(
                f"Content hash differs for {canonical_url} "
                f"(prior: {prior_content_hash[:8]}..., current: {current_content_hash[:8]}...), "
                "classifying as CHANGED"
            )
            return PageClassification.CHANGED, prior_page
    
    def compute_content_hash(self, content: str) -> str:
        """
        Compute deterministic content hash with normalization.
        
        Uses content_hasher module for consistent hashing across the system.
        
        Args:
            content: Raw content string
        
        Returns:
            SHA-256 hash hex string
        """
        return compute_secure_hash(content)
    
    def should_skip_fetch(
        self,
        classification: PageClassification,
        prior_page: Optional[Dict[str, Any]],
    ) -> bool:
        """
        Determine if we can skip fetching content for this page.
        
        Args:
            classification: Page classification
            prior_page: Prior page record (if exists)
        
        Returns:
            True if fetch can be skipped
        """
        # Only skip if completely unchanged
        if classification == PageClassification.UNCHANGED and prior_page:
            # Additional check: prior page must have artifact paths
            if prior_page.get("normalized_artifact_path"):
                return True
        return False
    
    def prepare_page_record(
        self,
        classification: PageClassification,
        prior_page: Optional[Dict[str, Any]],
        url: str,
        canonical_url: str,
        content: Optional[str] = None,
        content_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Prepare page record metadata based on classification.
        
        Args:
            classification: Page classification
            prior_page: Prior page record (if exists)
            url: Original URL
            canonical_url: Normalized canonical URL
            content: Page content (optional)
            content_hash: Pre-computed content hash (optional)
        
        Returns:
            Page record dictionary
        """
        record = {
            "url": url,
            "canonical_url": canonical_url,
            "status": classification.value,
        }
        
        # Add content hash if available
        if content_hash:
            record["content_hash"] = content_hash
        elif content:
            record["content_hash"] = self.compute_content_hash(content)
        
        # Link to prior version for changed pages
        if classification == PageClassification.CHANGED and prior_page:
            record["previous_page_id"] = prior_page["id"]
            record["previous_content_hash"] = prior_page.get("content_hash")
        
        # For unchanged pages, reference prior artifacts
        if classification == PageClassification.UNCHANGED and prior_page:
            record["reference_page_id"] = prior_page["id"]
            # Optionally copy artifact paths to avoid lookups
            record["normalized_artifact_path"] = prior_page.get("normalized_artifact_path")
            record["raw_artifact_path"] = prior_page.get("raw_artifact_path")
        
        return record
    
    def update_crawl_counters(
        self,
        crawl_id: str,
        classification: PageClassification,
    ) -> None:
        """
        Update crawl run counters based on classification.
        
        Args:
            crawl_id: Crawl run ID
            classification: Page classification
        """
        # Get current stats
        crawl = self.repository.get_crawl_run(crawl_id)
        if not crawl:
            logger.error(f"Crawl run {crawl_id} not found for counter update")
            return
        
        # Update appropriate counter
        if classification == PageClassification.UNCHANGED:
            current = crawl.get("pages_unchanged", 0)
            self.repository.update_crawl_stats(
                crawl_id=crawl_id,
                pages_found=crawl.get("pages_found", 0),
                pages_ingested=crawl.get("pages_ingested", 0),
                pages_failed=crawl.get("pages_failed", 0),
                pages_unchanged=current + 1,
            )
        elif classification in (PageClassification.NEW, PageClassification.FAILED_PRIOR):
            # These count as "found" and potentially "ingested"
            pass  # Will be updated when page is actually ingested
        elif classification == PageClassification.CHANGED:
            # Changed pages count as found/ingested
            pass  # Will be updated when page is ingested


def classify_page_for_recrawl(
    twin_id: str,
    crawl_id: str,
    canonical_url: str,
    content: Optional[str] = None,
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Convenience function for page classification.
    
    Args:
        twin_id: Twin ID
        crawl_id: Current crawl ID
        canonical_url: Normalized URL
        content: Content for hash comparison
    
    Returns:
        Tuple of (classification_string, prior_page_or_none)
    """
    manager = CrawlManager()
    classification, prior = manager.classify_page(
        twin_id=twin_id,
        crawl_id=crawl_id,
        canonical_url=canonical_url,
        content=content,
    )
    return classification.value, prior
