# backend/modules/web_crawler.py
"""Web Crawler: Deep website scraping using Firecrawl.

Provides functions to crawl websites and extract content for Twin training.
Supports single-page scraping, deep crawling, and sitemap extraction.
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

logger = logging.getLogger(__name__)

# Firecrawl client singleton
_firecrawl_client = None


def get_firecrawl_client():
    """Get or create singleton Firecrawl client."""
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
            "staging_status": "processing"
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
            "staging_status": "approved",
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
        
        # Audit log
        AuditLogger.log(
            twin_id, "KNOWLEDGE_UPDATE", "SOURCE_INDEXED",
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
