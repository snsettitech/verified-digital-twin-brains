# backend/modules/web_crawler.py
"""Web Crawler: Deep website scraping using Firecrawl.

Provides functions to crawl websites and extract content for Twin training.
Supports single-page scraping, deep crawling, and sitemap extraction.

Phase 3.0 Update: Integrated with production FirecrawlClient wrapper
for retry, circuit breaker, and honest quality reporting.
"""

import os
import re
import uuid
import logging
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse
from datetime import datetime

from modules.observability import supabase, log_ingestion_event
from modules.health_checks import calculate_content_hash
from modules.governance import AuditLogger

# Deep Research imports (Phase 1A.5+)
from modules.deep_research_config import get_config as get_dr_config
from modules.fetch_safety import (
    validate_url_safety,
    validate_content_safety,
    FetchSafetyValidator,
    FailureType,
    FailureCategory,
)
from modules.artifact_store import get_artifact_store, ArtifactStore
from modules.url_canonicalizer import canonicalize_url, get_url_hash, URLCanonicalizationRules
from modules.content_hasher import compute_secure_hash

# Phase 3.0: New FirecrawlClient with retry/circuit breaker
from modules.firecrawl_client import (
    get_firecrawl_client as get_firecrawl_client_v3,
    ContentQuality,
    FirecrawlResult,
)

logger = logging.getLogger(__name__)

# Legacy Firecrawl client singleton (maintained for backward compatibility)
_firecrawl_client = None


def get_firecrawl_client():
    """Get or create singleton Firecrawl client (legacy compatibility).
    
    Phase 3.0: This now delegates to the new FirecrawlClient wrapper
    which provides retry, circuit breaker, and quality reporting.
    
    Returns:
        Legacy FirecrawlApp instance or None
    """
    global _firecrawl_client
    if _firecrawl_client is None:
        api_key = os.getenv("FIRECRAWL_API_KEY")
        if not api_key:
            logger.warning("FIRECRAWL_API_KEY not found. Web crawling features disabled.")
            return None
        try:
            from firecrawl import FirecrawlApp
            _firecrawl_client = FirecrawlApp(api_key=api_key)
        except ImportError:
            logger.warning("firecrawl-py package not installed. Run: pip install firecrawl-py")
            return None
        except Exception as e:
            logger.error(f"Error initializing Firecrawl client: {e}")
            return None
    return _firecrawl_client


def get_firecrawl_client_v3_wrapper():
    """Get the Phase 3.0 FirecrawlClient wrapper.
    
    Returns:
        FirecrawlClient instance with retry/circuit breaker support, or None
    """
    return get_firecrawl_client_v3()


def validate_url(url: str) -> bool:
    """Validate that a URL is properly formatted and accessible."""
    try:
        result = urlparse(url)
        return all([result.scheme in ('http', 'https'), result.netloc])
    except Exception:
        return False


def extract_domain(url: str) -> str:
    """Extract the domain from a URL."""
    try:
        parsed = urlparse(url)
        return parsed.netloc
    except Exception:
        return ""


async def scrape_single_page(
    url: str,
    formats: List[str] = None,
    include_links: bool = False
) -> Dict[str, Any]:
    """
    Scrape a single page and return its content.
    
    Args:
        url: URL to scrape
        formats: Output formats ('markdown', 'html', 'links', 'screenshot')
        include_links: Whether to extract all links from the page
    
    Returns:
        Dict with 'success', 'content', 'metadata', 'links' (if requested)
    """
    if not validate_url(url):
        return {"success": False, "error": "Invalid URL format"}
    
    client = get_firecrawl_client()
    if not client:
        return {"success": False, "error": "Firecrawl client not available"}
    
    if formats is None:
        formats = ["markdown"]
    
    try:
        # Firecrawl scrape options
        scrape_options = {
            "formats": formats
        }
        
        if include_links:
            if "links" not in formats:
                scrape_options["formats"].append("links")
        
        result = client.scrape_url(url, params=scrape_options)
        
        # Extract content based on format
        content = ""
        if "markdown" in result:
            content = result["markdown"]
        elif "html" in result:
            content = result["html"]
        
        # Extract metadata
        metadata = result.get("metadata", {})
        
        # Extract links if requested
        links = []
        if include_links and "links" in result:
            links = result["links"]
        
        return {
            "success": True,
            "content": content,
            "content_length": len(content),
            "metadata": {
                "title": metadata.get("title", ""),
                "description": metadata.get("description", ""),
                "language": metadata.get("language", "en"),
                "sourceURL": metadata.get("sourceURL", url),
                "ogImage": metadata.get("ogImage", ""),
            },
            "links": links
        }
        
    except Exception as e:
        logger.error(f"Error scraping {url}: {e}")
        return {"success": False, "error": str(e)}


async def scrape_single_page_v3(
    url: str,
    formats: List[str] = None,
    use_retry: bool = True
) -> Dict[str, Any]:
    """
    Scrape a single page using Phase 3.0 FirecrawlClient with retry/circuit breaker.
    
    Args:
        url: URL to scrape
        formats: Output formats ('markdown', 'html', etc.)
        use_retry: Whether to use retry logic (default: True)
    
    Returns:
        Dict with 'success', 'content', 'metadata', 'quality', 'attempts'
    """
    if not validate_url(url):
        return {"success": False, "error": "Invalid URL format"}
    
    client = get_firecrawl_client_v3_wrapper()
    if not client:
        # Fall back to legacy client
        return await scrape_single_page(url, formats)
    
    formats = formats or ["markdown"]
    max_retries = 3 if use_retry else 0
    
    try:
        result = await client.scrape_with_retry(url, formats=formats, max_retries=max_retries)
        
        return {
            "success": result.success,
            "content": result.content,
            "content_length": len(result.content),
            "metadata": result.metadata,
            "quality": result.quality.value,
            "quality_reason": result.quality_reason,
            "attempts": result.attempts,
            "duration_ms": result.duration_ms,
            "error": result.error.get("detail") if result.error else None,
        }
    except Exception as e:
        logger.error(f"Error in v3 scrape for {url}: {e}")
        # Fall back to legacy behavior
        return await scrape_single_page(url, formats)


async def crawl_website(
    url: str,
    twin_id: str,
    max_pages: int = 10,
    max_depth: int = 2,
    include_patterns: List[str] = None,
    exclude_patterns: List[str] = None,
    source_id: str = None
) -> Dict[str, Any]:
    """
    Deep crawl a website and ingest all pages.
    
    Args:
        url: Starting URL
        twin_id: Twin ID to associate content with
        max_pages: Maximum number of pages to crawl
        max_depth: Maximum crawl depth from starting URL
        include_patterns: URL patterns to include (glob format)
        exclude_patterns: URL patterns to exclude (glob format)
        source_id: Optional source ID (will be generated if not provided)
    
    Returns:
        Dict with crawl results and statistics
    """
    if not validate_url(url):
        return {"success": False, "error": "Invalid URL format"}
    
    client = get_firecrawl_client()
    if not client:
        return {"success": False, "error": "Firecrawl client not available"}
    
    # Generate source ID if not provided
    if not source_id:
        source_id = str(uuid.uuid4())
    
    domain = extract_domain(url)
    
    try:
        # Create source record
        supabase.table("sources").insert({
            "id": source_id,
            "twin_id": twin_id,
            "filename": f"Website: {domain}",
            "file_size": 0,
            "content_text": "",
            "status": "processing",
            "staging_status": "staged"
        }).execute()
        
        log_ingestion_event(source_id, twin_id, "info", f"Starting crawl of {url}")
        
        # Firecrawl crawl options
        crawl_options = {
            "limit": max_pages,
            "maxDepth": max_depth,
            "scrapeOptions": {
                "formats": ["markdown"]
            }
        }
        
        if include_patterns:
            crawl_options["includePaths"] = include_patterns
        if exclude_patterns:
            crawl_options["excludePaths"] = exclude_patterns
        
        # Start crawl (this is async in Firecrawl)
        crawl_result = client.crawl_url(url, params=crawl_options, poll_interval=5)
        
        # Process results
        pages_crawled = 0
        total_content = []
        page_metadata = []
        
        if crawl_result and crawl_result.get("data"):
            for page in crawl_result["data"]:
                pages_crawled += 1
                content = page.get("markdown", "")
                metadata = page.get("metadata", {})
                
                if content:
                    total_content.append(f"## {metadata.get('title', 'Page')}\n\n{content}")
                    page_metadata.append({
                        "url": metadata.get("sourceURL", ""),
                        "title": metadata.get("title", ""),
                        "length": len(content)
                    })
        
        # Combine all content
        combined_content = "\n\n---\n\n".join(total_content)
        content_hash = calculate_content_hash(combined_content)
        
        # Update source record
        supabase.table("sources").update({
            "content_text": combined_content,
            "content_hash": content_hash,
            "file_size": len(combined_content),
            "status": "indexed",
            "staging_status": "live",
            "extracted_text_length": len(combined_content)
        }).eq("id", source_id).execute()
        
        log_ingestion_event(
            source_id, twin_id, "info",
            f"Crawl complete: {pages_crawled} pages, {len(combined_content)} chars"
        )
        
        # Index the content
        from modules.ingestion import process_and_index_text
        num_chunks = await process_and_index_text(
            source_id, twin_id, combined_content,
            metadata_override={
                "filename": f"Website: {domain}",
                "type": "website",
                "domain": domain,
                "pages_crawled": pages_crawled
            }
        )
        
        # Fetch tenant_id
        tenant_id = None
        try:
            res = supabase.table("twins").select("tenant_id").eq("id", twin_id).single().execute()
            tenant_id = res.data.get("tenant_id") if res.data else None
        except Exception:
            pass

        # Audit log
        AuditLogger.log(
            tenant_id=tenant_id,
            twin_id=twin_id, 
            event_type="KNOWLEDGE_UPDATE", 
            action="SOURCE_INDEXED",
            metadata={
                "source_id": source_id,
                "filename": f"Website: {domain}",
                "type": "website",
                "chunks": num_chunks,
                "pages": pages_crawled
            }
        )

        
        return {
            "success": True,
            "source_id": source_id,
            "domain": domain,
            "pages_crawled": pages_crawled,
            "total_content_length": len(combined_content),
            "chunks_indexed": num_chunks,
            "page_details": page_metadata
        }
        
    except Exception as e:
        logger.error(f"Error crawling {url}: {e}")
        
        # Update source status
        try:
            supabase.table("sources").update({
                "status": "error",
                "health_status": "failed"
            }).eq("id", source_id).execute()
            
            log_ingestion_event(source_id, twin_id, "error", f"Crawl failed: {e}")
        except Exception:
            pass
        
        return {"success": False, "error": str(e), "source_id": source_id}


async def extract_sitemap_urls(url: str, max_urls: int = 100) -> List[str]:
    """
    Extract URLs from a website's sitemap.
    
    Args:
        url: Base URL or sitemap URL
        max_urls: Maximum number of URLs to return
    
    Returns:
        List of URLs found in the sitemap
    """
    if not validate_url(url):
        return []
    
    # Try common sitemap locations
    base_url = url.rstrip('/')
    sitemap_urls = [
        f"{base_url}/sitemap.xml",
        f"{base_url}/sitemap_index.xml",
        f"{base_url}/sitemap-index.xml",
    ]
    
    # If URL already points to a sitemap, use it directly
    if url.endswith('.xml'):
        sitemap_urls.insert(0, url)
    
    import httpx
    
    urls_found = []
    
    for sitemap_url in sitemap_urls:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(sitemap_url, timeout=10)
                if response.status_code == 200:
                    content = response.text
                    
                    # Parse sitemap XML
                    # Simple regex extraction (for robustness)
                    loc_matches = re.findall(r'<loc>(.*?)</loc>', content)
                    
                    for loc in loc_matches:
                        # Skip other sitemaps
                        if loc.endswith('.xml') and 'sitemap' in loc.lower():
                            # Recursively get URLs from sub-sitemaps
                            sub_urls = await extract_sitemap_urls(loc, max_urls - len(urls_found))
                            urls_found.extend(sub_urls)
                        else:
                            urls_found.append(loc)
                        
                        if len(urls_found) >= max_urls:
                            break
                    
                    if urls_found:
                        break
                        
        except Exception as e:
            logger.warning(f"Error fetching sitemap {sitemap_url}: {e}")
            continue
    
    return urls_found[:max_urls]


async def get_page_links(url: str) -> List[str]:
    """
    Get all links from a page without full content scraping.
    Useful for mapping a website structure.
    """
    result = await scrape_single_page(url, formats=["links"], include_links=True)
    if result.get("success"):
        return result.get("links", [])
    return []


# ============================================================================
# Phase 1A.5: Deep Research - Crawl Website V2
# ============================================================================
# New crawler implementation with:
# - Fetch safety integration (SSRF protection, content-type, size limits)
# - Artifact-based storage (content in files, not DB)
# - URL canonicalization and deduplication
# - Structured failure taxonomy
# - Metadata-only DB storage
# 
# Phase 1B.1: Added crawl_repository integration for idempotency
# ============================================================================

import asyncio
from collections import defaultdict

from modules.crawl_repository import CrawlRepository
from modules.crawl_manager import CrawlManager, PageClassification
from modules.crawl_failure_taxonomy import (
    classify_failure,
    create_failure_artifact,
    create_failure_summary,
    FailureStage,
)


class CrawlV2Result:
    """Result of a V2 crawl operation."""
    
    def __init__(
        self,
        crawl_id: str,
        success: bool,
        pages_discovered: int = 0,
        pages_ingested: int = 0,
        pages_failed: int = 0,
        pages_skipped: int = 0,
        pages_unchanged: int = 0,
        pages_changed: int = 0,
        error: Optional[str] = None,
        artifact_path: Optional[str] = None,
    ):
        self.crawl_id = crawl_id
        self.success = success
        self.pages_discovered = pages_discovered
        self.pages_ingested = pages_ingested
        self.pages_failed = pages_failed
        self.pages_skipped = pages_skipped
        self.pages_unchanged = pages_unchanged
        self.pages_changed = pages_changed
        self.error = error
        self.artifact_path = artifact_path
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "crawl_id": self.crawl_id,
            "success": self.success,
            "pages_discovered": self.pages_discovered,
            "pages_ingested": self.pages_ingested,
            "pages_failed": self.pages_failed,
            "pages_skipped": self.pages_skipped,
            "pages_unchanged": self.pages_unchanged,
            "pages_changed": self.pages_changed,
            "error": self.error,
            "artifact_path": self.artifact_path,
        }


class CrawlPageV2:
    """Represents a page in a V2 crawl (in-memory only, DB record created separately)."""
    
    def __init__(
        self,
        url: str,
        canonical_url: str,
        url_hash: str,
        status: str = "discovered",
    ):
        self.id = str(uuid.uuid4())
        self.url = url
        self.canonical_url = canonical_url
        self.url_hash = url_hash
        self.status = status
        self.content_hash: Optional[str] = None
        self.content_length: int = 0
        self.snippet: str = ""
        self.normalized_artifact_path: Optional[str] = None
        self.raw_artifact_path: Optional[str] = None
        self.metadata: Dict[str, Any] = {}
        self.fetched_at: Optional[datetime] = None
        self.error_category: Optional[str] = None
        self.error_detail: Optional[str] = None
        self.retry_count: int = 0


async def crawl_website_v2(
    url: str,
    twin_id: str,
    max_pages: int = 10,
    max_depth: int = 2,
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
    crawl_run_id: Optional[str] = None,
) -> CrawlV2Result:
    """
    V2 crawl with safety, artifacts, and metadata-only storage.
    
    This is the new Deep Research crawler that:
    - Validates all URLs through fetch_safety before fetching
    - Stores content in artifacts, not DB
    - Canonicalizes URLs and deduplicates within crawl
    - Records structured failure taxonomy
    
    Args:
        url: Starting URL
        twin_id: Twin ID
        max_pages: Maximum pages to crawl
        max_depth: Maximum crawl depth
        include_patterns: URL patterns to include
        exclude_patterns: URL patterns to exclude
        crawl_run_id: Optional existing crawl run ID (creates new if None)
    
    Returns:
        CrawlV2Result with crawl statistics
    """
    # Check if Deep Research is enabled
    dr_config = get_dr_config()
    if not dr_config.is_enabled():
        return CrawlV2Result(
            crawl_id="",
            success=False,
            error="Deep Research feature is not enabled",
        )
    
    # Validate initial URL
    if not validate_url(url):
        return CrawlV2Result(
            crawl_id="",
            success=False,
            error="Invalid URL format",
        )
    
    # Check URL safety for seed URL
    safety_result = validate_url_safety(url)
    if not safety_result:
        return CrawlV2Result(
            crawl_id="",
            success=False,
            error=f"Seed URL blocked by safety policy: {safety_result.reason}",
        )
    
    # Get or create crawl run
    crawl_id = crawl_run_id or str(uuid.uuid4())
    
    try:
        # Create crawl run record
        _create_crawl_run_record(
            crawl_id=crawl_id,
            twin_id=twin_id,
            seed_urls=[url],
            max_pages=max_pages,
            max_depth=max_depth,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
        )
    except Exception as e:
        logger.error(f"Failed to create crawl run record: {e}")
        return CrawlV2Result(
            crawl_id=crawl_id,
            success=False,
            error=f"Failed to create crawl run: {e}",
        )
    
    # Initialize components
    artifact_store = get_artifact_store()
    safety_validator = FetchSafetyValidator()
    canonicalization_rules = URLCanonicalizationRules.default()
    crawl_manager = CrawlManager()
    
    # Track pages by canonical URL (for deduplication)
    pages_by_canonical: Dict[str, CrawlPageV2] = {}
    discovered_urls: List[str] = [url]
    processed_count = 0
    unchanged_count = 0
    
    try:
        # Update crawl run status to running
        _update_crawl_run_status(crawl_id, "running")
        
        # Process discovered URLs
        while discovered_urls and processed_count < max_pages:
            current_url = discovered_urls.pop(0)
            processed_count += 1
            
            # Canonicalize URL
            try:
                canonical_url = canonicalize_url(current_url, canonicalization_rules)
                url_hash = get_url_hash(canonical_url)
            except ValueError as e:
                logger.warning(f"Failed to canonicalize URL {current_url}: {e}")
                continue
            
            # Check for duplicates within this crawl
            if canonical_url in pages_by_canonical:
                logger.debug(f"Skipping duplicate URL: {current_url}")
                continue
            
            # Create page record with canonical URL and hash
            page = CrawlPageV2(
                url=current_url,
                canonical_url=canonical_url,
                url_hash=url_hash,
            )
            pages_by_canonical[canonical_url] = page
            
            # Persist initial page record (canonical_url + url_hash)
            CrawlRepository.create_crawl_page(
                page_id=page.id,
                crawl_id=crawl_id,
                url=page.url,
                canonical_url=page.canonical_url,
                status="discovered",
            )
            
            # Validate URL safety
            safety_result = safety_validator.validate_url(current_url)
            if not safety_result:
                _mark_page_blocked(page, safety_result, artifact_store, crawl_id, twin_id)
                continue
            
            # Fetch the page (mocked for now - actual Firecrawl integration in later phase)
            fetch_result = await _fetch_page_with_safety(
                url=current_url,
                page=page,
                safety_validator=safety_validator,
                artifact_store=artifact_store,
                crawl_id=crawl_id,
                twin_id=twin_id,
            )
            
            if not fetch_result["success"]:
                _mark_page_failed(
                    page=page,
                    error=fetch_result.get("error", "Unknown error"),
                    error_category=fetch_result.get("error_category"),
                    artifact_store=artifact_store,
                    crawl_id=crawl_id,
                    twin_id=twin_id,
                )
                continue
            
            # Get content from fetch result
            content = fetch_result.get("content", "")
            content_hash = fetch_result.get("content_hash")
            
            # Classify page (new/unchanged/changed)
            classification, prior_page = crawl_manager.classify_page(
                twin_id=twin_id,
                crawl_id=crawl_id,
                canonical_url=canonical_url,
                content=content,
            )
            
            # Handle based on classification
            if classification == PageClassification.UNCHANGED:
                # Page unchanged - update status and reference prior artifacts
                page.status = "unchanged"
                page.content_hash = prior_page.get("content_hash") if prior_page else content_hash
                unchanged_count += 1
                
                # Reference prior artifacts to avoid duplication
                if prior_page:
                    page.normalized_artifact_path = prior_page.get("normalized_artifact_path")
                    page.raw_artifact_path = prior_page.get("raw_artifact_path")
                    page.reference_page_id = prior_page.get("id")
                
                logger.info(f"Page {canonical_url} classified as UNCHANGED, skipping artifact write")
                
            elif classification == PageClassification.CHANGED:
                # Page changed - write new artifacts and link to prior version
                page.status = "changed"
                page.content_hash = content_hash or crawl_manager.compute_content_hash(content)
                
                # Link to prior version
                if prior_page:
                    page.previous_page_id = prior_page.get("id")
                    page.previous_content_hash = prior_page.get("content_hash")
                
                # Write artifacts for changed content
                _write_page_artifacts(
                    page=page,
                    content=content,
                    raw_content=fetch_result.get("raw_content"),
                    metadata=fetch_result.get("metadata", {}),
                    artifact_store=artifact_store,
                    crawl_id=crawl_id,
                    twin_id=twin_id,
                )
                logger.info(f"Page {canonical_url} classified as CHANGED, new version created")
                
            else:  # NEW or FAILED_PRIOR
                # New page - write artifacts normally
                page.status = "ingested"
                page.content_hash = content_hash or crawl_manager.compute_content_hash(content)
                
                # Write artifacts
                _write_page_artifacts(
                    page=page,
                    content=content,
                    raw_content=fetch_result.get("raw_content"),
                    metadata=fetch_result.get("metadata", {}),
                    artifact_store=artifact_store,
                    crawl_id=crawl_id,
                    twin_id=twin_id,
                )
                logger.info(f"Page {canonical_url} classified as {classification.value}")
            
            page.ingested_at = datetime.utcnow()
            
            # Persist page metadata to DB with classification
            _persist_page_metadata_with_classification(
                page=page,
                crawl_id=crawl_id,
                classification=classification,
            )
        
        # Write crawl manifest to artifacts
        manifest_path = _write_crawl_manifest(
            crawl_id=crawl_id,
            twin_id=twin_id,
            pages=pages_by_canonical,
            artifact_store=artifact_store,
        )
        
        # Write failure summary if there were failures
        _write_failure_summary(
            crawl_id=crawl_id,
            twin_id=twin_id,
            pages=pages_by_canonical,
            artifact_store=artifact_store,
        )
        
        # Update crawl run status to completed
        stats = _calculate_crawl_stats(pages_by_canonical)
        _update_crawl_run_completed(crawl_id, stats, manifest_path)
        
        return CrawlV2Result(
            crawl_id=crawl_id,
            success=True,
            pages_discovered=len(pages_by_canonical),
            pages_ingested=stats["ingested"],
            pages_failed=stats["failed"],
            pages_skipped=stats["skipped"],
            pages_unchanged=stats["unchanged"],
            pages_changed=stats["changed"],
            artifact_path=manifest_path,
        )
        
    except Exception as e:
        logger.error(f"Crawl v2 failed: {e}")
        _update_crawl_run_status(crawl_id, "failed", error=str(e))
        return CrawlV2Result(
            crawl_id=crawl_id,
            success=False,
            error=str(e),
        )


def _create_crawl_run_record(
    crawl_id: str,
    twin_id: str,
    seed_urls: List[str],
    max_pages: int,
    max_depth: int,
    include_patterns: Optional[List[str]],
    exclude_patterns: Optional[List[str]],
    previous_crawl_id: Optional[str] = None,
) -> None:
    """Create initial crawl run record in DB using repository."""
    CrawlRepository.create_crawl_run(
        crawl_id=crawl_id,
        twin_id=twin_id,
        seed_urls=seed_urls,
        max_pages=max_pages,
        max_depth=max_depth,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
        previous_crawl_id=previous_crawl_id,
    )


def _update_crawl_run_status(crawl_id: str, status: str, error: Optional[str] = None) -> None:
    """Update crawl run status using repository."""
    CrawlRepository.update_crawl_status(
        crawl_id=crawl_id,
        status=status,
        error_message=error,
    )


def _update_crawl_run_completed(
    crawl_id: str,
    stats: Dict[str, int],
    manifest_path: str,
) -> None:
    """Mark crawl run as completed with stats using repository."""
    CrawlRepository.update_crawl_status(crawl_id, "completed")
    CrawlRepository.update_crawl_stats(
        crawl_id=crawl_id,
        pages_found=stats["discovered"],
        pages_ingested=stats["ingested"],
        pages_failed=stats["failed"],
        pages_unchanged=stats.get("unchanged", 0),
    )


def _mark_page_blocked(
    page: CrawlPageV2,
    safety_result: Any,
    artifact_store: ArtifactStore,
    crawl_id: str,
    twin_id: str,
) -> None:
    """Mark page as blocked due to safety policy using repository and failure taxonomy."""
    # Classify the failure using taxonomy
    failure_type = classify_failure(
        status_code=None,
        error=safety_result.reason,
        stage=FailureStage.SAFETY_CHECK,
    )
    
    page.status = "blocked"
    page.error_category = failure_type.value
    page.error_detail = safety_result.reason
    
    # Create standardized failure artifact
    failure_artifact = create_failure_artifact(
        url=page.url,
        canonical_url=page.canonical_url,
        crawl_id=crawl_id,
        crawl_page_id=page.id,
        failure_type=failure_type,
        error_detail=safety_result.reason,
        stage=FailureStage.SAFETY_CHECK,
        metadata=safety_result.details,
    )
    
    artifact_store.write_json(
        "crawl", twin_id, crawl_id,
        f"failures/{page.id}.json",
        failure_artifact,
    )
    
    # Create page record first, then mark as blocked
    CrawlRepository.create_crawl_page(
        page_id=page.id,
        crawl_id=crawl_id,
        url=page.url,
        canonical_url=page.canonical_url,
        status="blocked",
    )
    
    CrawlRepository.mark_page_blocked(
        page_id=page.id,
        error_category=page.error_category,
        error_detail=page.error_detail,
    )


def _mark_page_failed(
    page: CrawlPageV2,
    error: str,
    error_category: Optional[str],
    artifact_store: ArtifactStore,
    crawl_id: str,
    twin_id: str,
) -> None:
    """Mark page as failed with error details using repository and failure taxonomy."""
    # Classify the failure using taxonomy
    failure_type = classify_failure(
        status_code=None,
        error=error,
        stage=FailureStage.FETCH,
    )
    
    page.status = "failed"
    page.error_category = failure_type.value
    page.error_detail = error
    
    # Create standardized failure artifact
    failure_artifact = create_failure_artifact(
        url=page.url,
        canonical_url=page.canonical_url,
        crawl_id=crawl_id,
        crawl_page_id=page.id,
        failure_type=failure_type,
        error_detail=error,
        stage=FailureStage.FETCH,
    )
    
    artifact_store.write_json(
        "crawl", twin_id, crawl_id,
        f"failures/{page.id}.json",
        failure_artifact,
    )
    
    # Create page record first, then mark as failed
    CrawlRepository.create_crawl_page(
        page_id=page.id,
        crawl_id=crawl_id,
        url=page.url,
        canonical_url=page.canonical_url,
        status="failed",
    )
    
    CrawlRepository.mark_page_failed(
        page_id=page.id,
        error_category=page.error_category,
        error_detail=page.error_detail,
    )


async def _fetch_page_with_safety(
    url: str,
    page: CrawlPageV2,
    safety_validator: FetchSafetyValidator,
    artifact_store: ArtifactStore,
    crawl_id: str,
    twin_id: str,
) -> Dict[str, Any]:
    """
    Fetch a single page with safety checks.
    
    NOTE: This is a skeleton implementation. Full Firecrawl integration
    will be completed in Phase 1B or later sub-phase.
    """
    # TODO: Implement actual Firecrawl integration with safety checks
    # For now, return a placeholder that indicates the structure
    
    page.status = "fetching"
    page.fetched_at = datetime.utcnow()
    
    # Placeholder: In full implementation, this would:
    # 1. Call Firecrawl to fetch the page
    # 2. Check content-type and size safety
    # 3. Normalize content
    # 4. Write to artifacts
    # 5. Return success/failure
    
    return {
        "success": False,
        "error": "Fetch not yet implemented - skeleton only",
        "error_category": "network",
    }


def _persist_page_metadata(page: CrawlPageV2, crawl_id: str) -> None:
    """Persist page metadata to DB using repository (content is in artifacts only)."""
    try:
        # Check if page already exists (for idempotency)
        existing = CrawlRepository.find_page_by_canonical_url(
            crawl_id=crawl_id,
            canonical_url=page.canonical_url,
        )
        
        if existing:
            # Update existing page
            CrawlRepository.update_page_after_fetch(
                page_id=page.id,
                content_hash=page.content_hash,
                content_length=page.content_length,
                snippet=page.snippet,
                normalized_artifact_path=page.normalized_artifact_path,
                raw_artifact_path=page.raw_artifact_path,
                metadata=page.metadata,
                status=page.status,
            )
        else:
            # Create new page record with canonical URL and hash
            CrawlRepository.create_crawl_page(
                page_id=page.id,
                crawl_id=crawl_id,
                url=page.url,
                canonical_url=page.canonical_url,
                status=page.status,
            )
            # Update with fetch results if available
            if page.fetched_at:
                CrawlRepository.update_page_after_fetch(
                    page_id=page.id,
                    content_hash=page.content_hash,
                    content_length=page.content_length,
                    snippet=page.snippet,
                    normalized_artifact_path=page.normalized_artifact_path,
                    raw_artifact_path=page.raw_artifact_path,
                    metadata=page.metadata,
                    status=page.status,
                )
    except Exception as e:
        logger.error(f"Failed to persist page metadata: {e}")
        raise


def _write_page_artifacts(
    page: CrawlPageV2,
    content: str,
    raw_content: Optional[str],
    metadata: Dict[str, Any],
    artifact_store: ArtifactStore,
    crawl_id: str,
    twin_id: str,
) -> None:
    """
    Write page content to artifacts.
    
    Args:
        page: Crawl page object
        content: Normalized content
        raw_content: Raw response content
        metadata: Extracted metadata
        artifact_store: Artifact store instance
        crawl_id: Crawl run ID
        twin_id: Twin ID
    """
    # Write normalized content
    normalized_path = artifact_store.write_artifact(
        "crawl", twin_id, crawl_id,
        f"pages/{page.id}/normalized.md",
        content,
        "text/markdown",
    )
    page.normalized_artifact_path = normalized_path
    
    # Write raw content if available
    if raw_content:
        raw_path = artifact_store.write_artifact(
            "crawl", twin_id, crawl_id,
            f"pages/{page.id}/raw.json",
            raw_content,
            "application/json",
        )
        page.raw_artifact_path = raw_path
    
    # Write metadata
    artifact_store.write_json(
        "crawl", twin_id, crawl_id,
        f"pages/{page.id}/metadata.json",
        metadata,
    )
    
    # Update page metadata
    page.metadata = metadata
    page.content_length = len(content)
    page.snippet = content[:500] if content else ""


def _persist_page_metadata_with_classification(
    page: CrawlPageV2,
    crawl_id: str,
    classification: Any,
) -> None:
    """
    Persist page metadata with classification info.
    
    Args:
        page: Crawl page object
        crawl_id: Crawl run ID
        classification: PageClassification enum value
    """
    try:
        # Update the page record with classification status
        CrawlRepository.update_page_after_fetch(
            page_id=page.id,
            content_hash=page.content_hash,
            content_length=page.content_length,
            snippet=page.snippet,
            normalized_artifact_path=page.normalized_artifact_path,
            raw_artifact_path=page.raw_artifact_path,
            metadata={
                **page.metadata,
                "classification": classification.value,
                "previous_page_id": page.previous_page_id,
                "reference_page_id": getattr(page, "reference_page_id", None),
            },
            status=page.status,
        )
    except Exception as e:
        logger.error(f"Failed to persist page metadata with classification: {e}")
        raise


def _write_crawl_manifest(
    crawl_id: str,
    twin_id: str,
    pages: Dict[str, CrawlPageV2],
    artifact_store: ArtifactStore,
) -> str:
    """Write crawl manifest to artifacts."""
    manifest = {
        "crawl_id": crawl_id,
        "twin_id": twin_id,
        "created_at": datetime.utcnow().isoformat(),
        "pages": [
            {
                "id": p.id,
                "url": p.url,
                "canonical_url": p.canonical_url,
                "url_hash": p.url_hash,
                "status": p.status,
                "content_hash": p.content_hash,
                "error_category": p.error_category,
            }
            for p in pages.values()
        ],
    }
    
    path = artifact_store.write_json(
        "crawl", twin_id, crawl_id,
        "manifest.json",
        manifest,
    )
    return path


def _calculate_crawl_stats(pages: Dict[str, CrawlPageV2]) -> Dict[str, int]:
    """Calculate crawl statistics including classification."""
    stats = {
        "discovered": len(pages),
        "ingested": 0,
        "unchanged": 0,
        "changed": 0,
        "failed": 0,
        "blocked": 0,
        "skipped": 0,
    }
    
    for page in pages.values():
        if page.status == "unchanged":
            stats["unchanged"] += 1
        elif page.status == "changed":
            stats["changed"] += 1
        elif page.status == "ingested":
            stats["ingested"] += 1
        elif page.status == "failed":
            stats["failed"] += 1
        elif page.status == "blocked":
            stats["blocked"] += 1
        else:
            stats["skipped"] += 1
    
    return stats


def _write_failure_summary(
    crawl_id: str,
    twin_id: str,
    pages: Dict[str, CrawlPageV2],
    artifact_store: ArtifactStore,
) -> Optional[str]:
    """
    Write failure summary artifact if there are failed/blocked pages.
    
    Args:
        crawl_id: Crawl run ID
        twin_id: Twin ID
        pages: Dictionary of pages
        artifact_store: Artifact store instance
    
    Returns:
        Path to summary artifact or None if no failures
    """
    # Collect failure artifacts
    failures = []
    for page in pages.values():
        if page.status in ("failed", "blocked") and page.error_category:
            # Reconstruct failure artifact from page data
            failure_type = classify_failure(
                status_code=None,
                error=page.error_detail or "Unknown error",
                stage=FailureStage.FETCH if page.status == "failed" else FailureStage.SAFETY_CHECK,
            )
            
            failure_artifact = create_failure_artifact(
                url=page.url,
                canonical_url=page.canonical_url,
                crawl_id=crawl_id,
                crawl_page_id=page.id,
                failure_type=failure_type,
                error_detail=page.error_detail or "Unknown error",
                stage=FailureStage.FETCH if page.status == "failed" else FailureStage.SAFETY_CHECK,
            )
            failures.append(failure_artifact)
    
    if not failures:
        return None
    
    # Create and write summary
    summary = create_failure_summary(crawl_id, failures)
    
    path = artifact_store.write_json(
        "crawl", twin_id, crawl_id,
        "failures/summary.json",
        summary,
    )
    
    logger.info(f"Wrote failure summary for {len(failures)} failures to {path}")
    return path


# ============================================================================
# End of Phase 1B.2
# ============================================================================
