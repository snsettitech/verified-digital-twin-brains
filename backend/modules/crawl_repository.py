"""
Crawl Repository Module (Phase 1B.1)

Data access layer for crawl operations with idempotency support.
Provides methods for persisting and querying crawl data with canonical URL tracking.
"""

from typing import Optional, Dict, List, Any
from datetime import datetime

from modules.observability import supabase
from modules.url_canonicalizer import get_url_hash


class CrawlRepository:
    """Repository for crawl-related database operations."""
    
    @staticmethod
    def create_crawl_run(
        crawl_id: str,
        twin_id: str,
        seed_urls: List[str],
        max_pages: int,
        max_depth: int,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        previous_crawl_id: Optional[str] = None,
    ) -> None:
        """
        Create a new crawl run record.
        
        Args:
            crawl_id: Unique crawl run ID
            twin_id: Twin ID
            seed_urls: List of starting URLs
            max_pages: Maximum pages to crawl
            max_depth: Maximum crawl depth
            include_patterns: URL patterns to include
            exclude_patterns: URL patterns to exclude
            previous_crawl_id: ID of previous crawl (for incremental recrawls)
        """
        from backend.modules.deep_research_config import get_config as get_dr_config
        
        config = get_dr_config()
        
        supabase.table("crawl_runs").insert({
            "id": crawl_id,
            "twin_id": twin_id,
            "status": "queued",
            "seed_urls": seed_urls,
            "max_pages": max_pages,
            "max_depth": max_depth,
            "include_patterns": include_patterns or [],
            "exclude_patterns": exclude_patterns or [],
            "safety_config": config.safety.model_dump(),
            "previous_crawl_id": previous_crawl_id,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }).execute()
    
    @staticmethod
    def create_crawl_page(
        page_id: str,
        crawl_id: str,
        url: str,
        canonical_url: str,
        status: str = "discovered",
        previous_page_id: Optional[str] = None,
    ) -> None:
        """
        Create a crawl page record with canonical URL and hash.
        
        Args:
            page_id: Unique page ID
            crawl_id: Parent crawl run ID
            url: Original URL
            canonical_url: Normalized canonical URL
            status: Page status
            previous_page_id: ID of previous version (for recrawls)
        """
        url_hash = get_url_hash(canonical_url)
        
        supabase.table("crawl_pages").insert({
            "id": page_id,
            "crawl_id": crawl_id,
            "url": url,
            "canonical_url": canonical_url,
            "url_hash": url_hash,
            "status": status,
            "previous_page_id": previous_page_id,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }).execute()
    
    @staticmethod
    def update_page_after_fetch(
        page_id: str,
        content_hash: Optional[str] = None,
        content_length: int = 0,
        snippet: str = "",
        normalized_artifact_path: Optional[str] = None,
        raw_artifact_path: Optional[str] = None,
        metadata: Optional[Dict] = None,
        status: str = "ingested",
    ) -> None:
        """
        Update page record after successful fetch.
        
        Args:
            page_id: Page ID
            content_hash: Hash of normalized content
            content_length: Content length in bytes
            snippet: Content preview (first 500 chars)
            normalized_artifact_path: Path to normalized content artifact
            raw_artifact_path: Path to raw content artifact
            metadata: Extracted metadata (title, description, etc.)
            status: New status (default: ingested)
        """
        update_data = {
            "status": status,
            "content_hash": content_hash,
            "content_length": content_length,
            "snippet": snippet[:500] if snippet else None,
            "normalized_artifact_path": normalized_artifact_path,
            "raw_artifact_path": raw_artifact_path,
            "metadata": metadata or {},
            "fetched_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        # Remove None values
        update_data = {k: v for k, v in update_data.items() if v is not None}
        
        supabase.table("crawl_pages").update(update_data).eq("id", page_id).execute()
    
    @staticmethod
    def mark_page_failed(
        page_id: str,
        error_category: str,
        error_detail: str,
    ) -> None:
        """
        Mark page as failed with error information.
        
        Args:
            page_id: Page ID
            error_category: Failure taxonomy category
            error_detail: Detailed error message
        """
        supabase.table("crawl_pages").update({
            "status": "failed",
            "error_category": error_category,
            "error_detail": error_detail,
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("id", page_id).execute()
    
    @staticmethod
    def mark_page_blocked(
        page_id: str,
        error_category: str,
        error_detail: str,
    ) -> None:
        """
        Mark page as blocked by safety policy.
        
        Args:
            page_id: Page ID
            error_category: Failure taxonomy category (e.g., 'ssrf_blocked')
            error_detail: Detailed reason
        """
        supabase.table("crawl_pages").update({
            "status": "blocked",
            "error_category": error_category,
            "error_detail": error_detail,
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("id", page_id).execute()
    
    @staticmethod
    def find_page_by_canonical_url(
        crawl_id: str,
        canonical_url: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Find a page in a crawl by its canonical URL.
        
        Args:
            crawl_id: Crawl run ID
            canonical_url: Canonical URL to look up
        
        Returns:
            Page record or None
        """
        response = (
            supabase.table("crawl_pages")
            .select("*")
            .eq("crawl_id", crawl_id)
            .eq("canonical_url", canonical_url)
            .maybe_single()
            .execute()
        )
        
        return response.data
    
    @staticmethod
    def find_page_by_url_hash(
        crawl_id: str,
        url_hash: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Find a page in a crawl by its URL hash.
        
        Args:
            crawl_id: Crawl run ID
            url_hash: URL hash to look up
        
        Returns:
            Page record or None
        """
        response = (
            supabase.table("crawl_pages")
            .select("*")
            .eq("crawl_id", crawl_id)
            .eq("url_hash", url_hash)
            .maybe_single()
            .execute()
        )
        
        return response.data
    
    @staticmethod
    def find_page_in_twin_history(
        twin_id: str,
        canonical_url: str,
        exclude_crawl_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Find the most recent page with given canonical URL across all crawls for a twin.
        
        Used for cross-crawl deduplication and change detection.
        
        Args:
            twin_id: Twin ID
            canonical_url: Canonical URL to look up
            exclude_crawl_id: Optional crawl ID to exclude (e.g., current crawl)
        
        Returns:
            Most recent page record or None
        """
        query = (
            supabase.table("crawl_pages")
            .select("*, crawl_runs!inner(twin_id)")
            .eq("crawl_runs.twin_id", twin_id)
            .eq("canonical_url", canonical_url)
            .order("created_at", desc=True)
            .limit(1)
        )
        
        if exclude_crawl_id:
            query = query.neq("crawl_id", exclude_crawl_id)
        
        response = query.maybe_single().execute()
        return response.data
    
    @staticmethod
    def get_pages_by_crawl(crawl_id: str) -> List[Dict[str, Any]]:
        """
        Get all pages for a crawl run.
        
        Args:
            crawl_id: Crawl run ID
        
        Returns:
            List of page records
        """
        response = (
            supabase.table("crawl_pages")
            .select("*")
            .eq("crawl_id", crawl_id)
            .order("created_at")
            .execute()
        )
        
        return response.data or []
    
    @staticmethod
    def get_crawl_run(crawl_id: str) -> Optional[Dict[str, Any]]:
        """
        Get crawl run by ID.
        
        Args:
            crawl_id: Crawl run ID
        
        Returns:
            Crawl run record or None
        """
        response = (
            supabase.table("crawl_runs")
            .select("*")
            .eq("id", crawl_id)
            .maybe_single()
            .execute()
        )
        
        return response.data
    
    @staticmethod
    def update_crawl_status(
        crawl_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Update crawl run status.
        
        Args:
            crawl_id: Crawl run ID
            status: New status
            error_message: Optional error message
        """
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        if error_message:
            update_data["error_message"] = error_message
        
        if status == "running":
            update_data["started_at"] = datetime.utcnow().isoformat()
        elif status in ("completed", "failed", "cancelled"):
            update_data["completed_at"] = datetime.utcnow().isoformat()
        
        supabase.table("crawl_runs").update(update_data).eq("id", crawl_id).execute()
    
    @staticmethod
    def update_crawl_stats(
        crawl_id: str,
        pages_found: int,
        pages_ingested: int,
        pages_failed: int,
        pages_unchanged: int = 0,
    ) -> None:
        """
        Update crawl run statistics.
        
        Args:
            crawl_id: Crawl run ID
            pages_found: Total pages found
            pages_ingested: Pages successfully ingested
            pages_failed: Pages that failed
            pages_unchanged: Pages skipped due to unchanged content
        """
        supabase.table("crawl_runs").update({
            "pages_found": pages_found,
            "pages_ingested": pages_ingested,
            "pages_failed": pages_failed,
            "pages_unchanged": pages_unchanged,
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("id", crawl_id).execute()
    
    @staticmethod
    def get_previous_crawl_pages(
        previous_crawl_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Get all pages from a previous crawl for comparison.
        
        Used during recrawl to detect changes.
        
        Args:
            previous_crawl_id: Previous crawl run ID
        
        Returns:
            List of page records
        """
        response = (
            supabase.table("crawl_pages")
            .select("*")
            .eq("crawl_id", previous_crawl_id)
            .execute()
        )
        
        return response.data or []
