"""
Person Completeness Pipeline - Stage 1: Source Registry Builder

Builds the person_source_registry from existing sources and research runs.
Features:
- URL normalization
- Content hashing for deduplication
- Authority tier assignment
- Source type detection
"""

import hashlib
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

from modules.observability import supabase
from modules.person_completeness_config import SourceRegistryConfig

logger = logging.getLogger(__name__)


@dataclass
class SourceRegistryResult:
    """Result of source registry building."""
    success: bool
    sources_added: int = 0
    sources_updated: int = 0
    sources_deduped: int = 0
    error_message: Optional[str] = None

    @property
    def item_count(self) -> int:
        """Compatibility count for pipeline metrics."""
        return self.sources_added + self.sources_updated


class SourceRegistryBuilder:
    """Builds and maintains the person source registry."""
    
    # Domain authority tiers (1 = highest, 7 = lowest)
    AUTHORITY_TIERS = {
        1: ['.edu', '.gov', 'reuters.com', 'ap.org', 'bloomberg.com', 'nature.com', 'science.org'],
        2: ['linkedin.com', 'github.com', 'crunchbase.com', 'forbes.com', 'fortune.com', 
            'techcrunch.com', 'wired.com', 'economist.com', 'nytimes.com', 'wsj.com'],
        3: ['medium.com', 'substack.com', 'dev.to', 'hashnode.com', 'arxiv.org', 
            'researchgate.net', 'academia.edu'],
        4: [],  # Other professional sites
        5: ['twitter.com', 'x.com', 'threads.net'],
        6: ['facebook.com', 'instagram.com', 'tiktok.com', 'pinterest.com'],
        7: [],  # Unknown/personal sites
    }
    
    def __init__(self, config: Optional[SourceRegistryConfig] = None):
        self.config = config or SourceRegistryConfig()
    
    async def run(
        self,
        twin_id: str,
        research_run_id: Optional[str] = None,
    ) -> SourceRegistryResult:
        """
        Build source registry for a twin.
        
        Args:
            twin_id: The twin to process
            research_run_id: Optional research run for context
            
        Returns:
            SourceRegistryResult
        """
        import time
        start_time = time.time()
        
        try:
            logger.info(f"Building source registry for twin {twin_id}")
            
            # Collect sources from various places
            sources_added = 0
            sources_updated = 0
            sources_deduped = 0
            
            # 1. Get sources from research_run web evidence (if research_run_id provided)
            if research_run_id:
                web_sources = await self._collect_from_web_evidence(twin_id, research_run_id)
                added, updated, deduped = await self._upsert_sources(twin_id, web_sources)
                sources_added += added
                sources_updated += updated
                sources_deduped += deduped
            
            # 2. Get sources from existing sources table
            existing_sources = await self._collect_from_sources_table(twin_id)
            added, updated, deduped = await self._upsert_sources(twin_id, existing_sources)
            sources_added += added
            sources_updated += updated
            sources_deduped += deduped
            
            duration = time.time() - start_time
            logger.info(f"Source registry built in {duration:.2f}s: "
                       f"+{sources_added} added, ~{sources_updated} updated, "
                       f"{sources_deduped} deduped")
            
            return SourceRegistryResult(
                success=True,
                sources_added=sources_added,
                sources_updated=sources_updated,
                sources_deduped=sources_deduped
            )
        
        except Exception as e:
            logger.exception(f"Error building source registry: {e}")
            return SourceRegistryResult(
                success=False,
                error_message=str(e)
            )
    
    async def _collect_from_web_evidence(
        self,
        twin_id: str,
        research_run_id: str
    ) -> List[Dict[str, Any]]:
        """Collect sources from web verification evidence."""
        sources = []
        
        try:
            # Get web evidence from Phase 9 tables
            response = supabase.table("research_claim_web_evidence") \
                .select("*, verification:verification_id(twin_id, research_run_id)") \
                .execute()
            
            for item in response.data or []:
                # Filter by research_run_id if needed
                verification = item.get("verification", {})
                if verification.get("twin_id") != twin_id:
                    continue
                if verification.get("research_run_id") != research_run_id:
                    continue
                
                url = item.get("source_url", "")
                if not url:
                    continue
                
                source = {
                    "url": url,
                    "title": item.get("source_title", ""),
                    "source_type": self._detect_source_type(url),
                    "platform": self._extract_platform(url),
                    "authority_tier": item.get("domain_tier", self._calculate_authority_tier(url)),
                    "quality_score": 0.7 if item.get("content_quality") == "full" else 0.4,
                    "content_length_chars": len(item.get("extracted_quote", "")),
                    "raw_reference_json": {
                        "web_evidence_id": item.get("id"),
                        "evidence_type": item.get("evidence_type"),
                        "relevance_score": item.get("relevance_score"),
                    }
                }
                sources.append(source)
        
        except Exception as e:
            logger.warning(f"Error collecting from web evidence: {e}")
        
        return sources
    
    async def _collect_from_sources_table(
        self,
        twin_id: str
    ) -> List[Dict[str, Any]]:
        """Collect sources from existing sources table."""
        sources = []
        
        try:
            response = supabase.table("sources") \
                .select("*") \
                .eq("twin_id", twin_id) \
                .execute()
            
            for item in response.data or []:
                url = item.get("citation_url") or item.get("file_url", "")
                if not url:
                    # File upload without URL - use file_url as identifier
                    url = f"file://{item.get('filename', item.get('id'))}"
                
                content = item.get("content_text", "")
                content_hash = self._compute_content_hash(content) if content else None
                
                source = {
                    "url": url,
                    "title": item.get("filename", ""),
                    "source_type": self._detect_source_type(url),
                    "platform": self._extract_platform(url),
                    "content_hash": content_hash,
                    "content_length_chars": len(content) if content else 0,
                    "content_length_words": len(content.split()) if content else 0,
                    "authority_tier": self._calculate_authority_tier(url),
                    "quality_score": 0.8 if item.get("status") == "live" else 0.5,
                    "crawl_status": "completed" if item.get("status") == "live" else "discovered",
                    "raw_reference_json": {
                        "source_id": item.get("id"),
                        "status": item.get("status"),
                        "chunk_count": item.get("chunk_count"),
                    }
                }
                sources.append(source)
        
        except Exception as e:
            logger.warning(f"Error collecting from sources table: {e}")
        
        return sources
    
    async def _upsert_sources(
        self,
        twin_id: str,
        sources: List[Dict[str, Any]]
    ) -> tuple:
        """Upsert sources into registry. Returns (added, updated, deduped)."""
        added = 0
        updated = 0
        deduped = 0
        
        seen_urls: set = set()
        seen_hashes: set = set()
        
        for source in sources:
            url = source.get("url", "")
            normalized_url = self._normalize_url(url)
            
            # URL-based deduplication
            if normalized_url in seen_urls:
                deduped += 1
                continue
            seen_urls.add(normalized_url)
            
            # Content hash deduplication (if enabled)
            content_hash = source.get("content_hash")
            if self.config.enable_content_hash_dedup and content_hash:
                if content_hash in seen_hashes:
                    deduped += 1
                    continue
                seen_hashes.add(content_hash)
            
            # Check if source already exists
            existing = self._get_existing_source(twin_id, normalized_url)
            
            if existing:
                # Update existing
                self._update_source(existing["id"], source)
                updated += 1
            else:
                # Insert new
                self._insert_source(twin_id, normalized_url, source)
                added += 1
        
        return added, updated, deduped
    
    def _get_existing_source(self, twin_id: str, normalized_url: str) -> Optional[Dict]:
        """Check if source already exists in registry."""
        try:
            response = supabase.table("person_source_registry") \
                .select("id, updated_at") \
                .eq("twin_id", twin_id) \
                .eq("normalized_url", normalized_url) \
                .eq("is_active", True) \
                .single() \
                .execute()
            return response.data
        except Exception:
            return None
    
    def _insert_source(self, twin_id: str, normalized_url: str, source: Dict[str, Any]):
        """Insert new source into registry."""
        try:
            insert_data = {
                "twin_id": twin_id,
                "url": source.get("url", ""),
                "normalized_url": normalized_url,
                "source_type": source.get("source_type", "unknown"),
                "platform": source.get("platform"),
                "title": source.get("title"),
                "content_hash": source.get("content_hash"),
                "content_length_chars": source.get("content_length_chars", 0),
                "content_length_words": source.get("content_length_words", 0),
                "authority_tier": source.get("authority_tier", 7),
                "quality_score": source.get("quality_score", 0.5),
                "crawl_status": source.get("crawl_status", "discovered"),
                "raw_reference_json": source.get("raw_reference_json", {}),
            }
            
            supabase.table("person_source_registry").insert(insert_data).execute()
        except Exception as e:
            logger.warning(f"Error inserting source: {e}")
    
    def _update_source(self, source_id: str, source: Dict[str, Any]):
        """Update existing source in registry."""
        try:
            update_data = {
                "title": source.get("title"),
                "content_length_chars": source.get("content_length_chars", 0),
                "content_length_words": source.get("content_length_words", 0),
                "quality_score": source.get("quality_score", 0.5),
                "raw_reference_json": source.get("raw_reference_json", {}),
            }
            
            supabase.table("person_source_registry") \
                .update(update_data) \
                .eq("id", source_id) \
                .execute()
        except Exception as e:
            logger.warning(f"Error updating source: {e}")
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL for deduplication."""
        try:
            parsed = urlparse(url.lower().strip())
            # Remove www, trailing slashes, common tracking params
            netloc = parsed.netloc.replace("www.", "")
            path = parsed.path.rstrip("/")
            return f"{netloc}{path}"
        except Exception:
            return url.lower().strip()
    
    def _compute_content_hash(self, content: str) -> str:
        """Compute SHA-256 hash of content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    
    def _detect_source_type(self, url: str) -> str:
        """Detect source type from URL."""
        url_lower = url.lower()
        
        if "youtube.com" in url_lower or "youtu.be" in url_lower:
            return "youtube_video"
        elif "linkedin.com" in url_lower:
            return "linkedin_profile"
        elif "github.com" in url_lower:
            return "github"
        elif "twitter.com" in url_lower or "x.com" in url_lower:
            return "social_post"
        elif "medium.com" in url_lower or "substack.com" in url_lower:
            return "blog"
        elif ".pdf" in url_lower:
            return "uploaded_file"
        elif "podcast" in url_lower or "anchor.fm" in url_lower or "spotify.com/episode" in url_lower:
            return "podcast_episode"
        elif "arxiv.org" in url_lower:
            return "research_paper"
        elif url_lower.startswith("file://"):
            return "uploaded_file"
        else:
            return "website_page"
    
    def _extract_platform(self, url: str) -> Optional[str]:
        """Extract platform name from URL."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower().replace("www.", "")
            
            platform_map = {
                "linkedin.com": "LinkedIn",
                "twitter.com": "Twitter",
                "x.com": "Twitter",
                "github.com": "GitHub",
                "youtube.com": "YouTube",
                "medium.com": "Medium",
                "substack.com": "Substack",
            }
            
            for key, value in platform_map.items():
                if key in domain:
                    return value
            
            return domain.split(".")[0].capitalize()
        except Exception:
            return None
    
    def _calculate_authority_tier(self, url: str) -> int:
        """Calculate authority tier based on domain."""
        url_lower = url.lower()
        
        for tier, domains in self.AUTHORITY_TIERS.items():
            for domain in domains:
                if domain in url_lower:
                    return tier
        
        # Default tier based on TLD
        if ".edu" in url_lower or ".gov" in url_lower:
            return 2
        elif url_lower.startswith("file://"):
            return 3  # Uploaded files assumed trustworthy
        
        return 7  # Unknown
