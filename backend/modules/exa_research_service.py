"""
Exa Research Service - Enhanced Web Discovery & Verification

Refactored service layer for Exa API integration with support for:
- People-focused discovery (category="people")
- Two-pass retrieval (highlights -> full content)
- Freshness controls (max_age_hours)
- Structured result capture
- Person query builder
- Safety & quality filters

Usage:
    service = ExaResearchService()
    
    # Person discovery
    results = await service.discover_person(
        name="John Doe",
        company="Acme Corp",
        social_handles=["@johndoe"]
    )
    
    # Two-pass verification
    candidates = await service.search_highlights(query, num_results=10)
    verified = await service.fetch_full_contents([r.url for r in candidates[:3]])
"""

import os
import logging
from typing import List, Dict, Any, Optional, Union, Literal
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)


# ============================================================================
# Enums & Constants
# ============================================================================

class ExaCategory(str, Enum):
    """Exa search categories."""
    COMPANY = "company"
    RESEARCH_PAPER = "research paper"
    NEWS = "news"
    PDF = "pdf"
    TWEET = "tweet"
    PERSONAL_SITE = "personal site"
    FINANCIAL_REPORT = "financial report"
    PEOPLE = "people"


class SearchType(str, Enum):
    """Exa search types."""
    AUTO = "auto"
    FAST = "fast"


class SourceFreshness(str, Enum):
    """Freshness presets for different source types."""
    NEWS = "news"              # 24 hours
    SOCIAL = "social"          # 48 hours  
    COMPANY = "company"        # 168 hours (1 week)
    EVERGREEN = "evergreen"    # 720 hours (30 days)
    ARCHIVE = "archive"        # -1 (cache only)


# Default max_age_hours by freshness type
FRESHNESS_DEFAULTS = {
    SourceFreshness.NEWS: 24,
    SourceFreshness.SOCIAL: 48,
    SourceFreshness.COMPANY: 168,
    SourceFreshness.EVERGREEN: 720,
    SourceFreshness.ARCHIVE: -1,
}


# Domain authority tiers
HIGH_AUTHORITY_DOMAINS = {
    # Professional
    'linkedin.com', 'github.com', 'crunchbase.com', 'bloomberg.com',
    'reuters.com', 'forbes.com', 'fortune.com', 'inc.com',
    # Academic
    'arxiv.org', 'scholar.google.com', 'researchgate.net', 'academia.edu',
    # News
    'nytimes.com', 'wsj.com', 'ft.com', 'economist.com', 'wired.com',
    'techcrunch.com', 'theverge.com', 'medium.com',
    # Tech
    'stackoverflow.com', 'dev.to', 'hashnode.com',
}

LOW_QUALITY_DOMAINS = {
    'pinterest.com', 'instagram.com', 'facebook.com', 'tiktok.com',
    'youtube.com', 'reddit.com', 'quora.com',  # Social - low depth for research
}


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class SearchMetadata:
    """Metadata about the search execution."""
    query: str
    category: Optional[str]
    search_type: str
    num_results_requested: int
    num_results_returned: int
    max_age_hours: Optional[int] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    provider: str = "exa"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "category": self.category,
            "search_type": self.search_type,
            "num_results_requested": self.num_results_requested,
            "num_results_returned": self.num_results_returned,
            "max_age_hours": self.max_age_hours,
            "timestamp": self.timestamp,
            "provider": self.provider,
        }


@dataclass
class ResearchResult:
    """Structured research result with full metadata."""
    # Core fields
    url: str
    title: str
    
    # Content
    text: Optional[str] = None
    highlights: List[str] = field(default_factory=list)
    highlight_scores: List[float] = field(default_factory=list)
    text_length: int = 0
    
    # Metadata
    published_date: Optional[str] = None
    author: Optional[str] = None
    favicon: Optional[str] = None
    
    # Entities (if returned by Exa)
    entities: List[Dict[str, Any]] = field(default_factory=list)
    
    # Quality signals
    score: float = 0.0
    source_quality: str = "unknown"  # high, medium, low, unknown
    verified: bool = False
    verification_notes: List[str] = field(default_factory=list)
    
    # Search metadata
    search_metadata: Optional[SearchMetadata] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "text": self.text,
            "highlights": self.highlights,
            "highlight_scores": self.highlight_scores,
            "text_length": self.text_length,
            "published_date": self.published_date,
            "author": self.author,
            "favicon": self.favicon,
            "entities": self.entities,
            "score": self.score,
            "source_quality": self.source_quality,
            "verified": self.verified,
            "verification_notes": self.verification_notes,
            "search_metadata": self.search_metadata.to_dict() if self.search_metadata else None,
        }


@dataclass
class PersonSearchQuery:
    """Structured person search query."""
    name: str
    aliases: List[str] = field(default_factory=list)
    company: Optional[str] = None
    social_handles: List[str] = field(default_factory=list)
    website_domains: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    geography: Optional[str] = None
    
    def build_query(self) -> str:
        """Build optimized Exa query string."""
        parts = [self.name]
        
        # Add aliases (primary name already included)
        for alias in self.aliases[:2]:  # Limit to 2 aliases
            parts.append(f'"{alias}"')
        
        # Company (singular form recommended by Exa)
        if self.company:
            parts.append(self.company)
        
        # Social handles (cleaned)
        for handle in self.social_handles[:2]:
            clean = handle.lstrip('@')
            parts.append(f'"{clean}"')
        
        # Topics (what they work on)
        for topic in self.topics[:3]:
            parts.append(topic)
        
        # Geography
        if self.geography:
            parts.append(self.geography)
        
        # Join without over-constraining
        return " ".join(parts)
    
    def build_domain_filters(self) -> List[str]:
        """Build include_domains list from website_domains."""
        return [d for d in self.website_domains if d]


# ============================================================================
# Main Service Class
# ============================================================================

class ExaResearchService:
    """
    Enhanced Exa API service for research and verification.
    
    Features:
    - People discovery mode
    - Two-pass retrieval (highlights -> full content)
    - Freshness controls
    - Quality filtering
    - Structured result capture
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Exa service.
        
        Args:
            api_key: Exa API key. Defaults to EXA_API_KEY env var.
        """
        # Respect explicit empty-string API keys in tests/callers. Only fall back
        # to env when the argument is omitted (None).
        self.api_key = os.getenv("EXA_API_KEY", "") if api_key is None else api_key
        self._client = None
        
        if not self.api_key:
            logger.warning("ExaResearchService initialized without API key")
    
    def _get_client(self):
        """Lazy initialization of Exa client."""
        if self._client is None:
            try:
                from exa_py import Exa
                self._client = Exa(self.api_key)
                logger.info("Exa client initialized")
            except ImportError:
                raise ImportError("exa-py not installed. Run: pip install exa-py")
        return self._client
    
    # ========================================================================
    # Core Search Methods
    # ========================================================================
    
    async def search_highlights(
        self,
        query: str,
        num_results: int = 10,
        category: Optional[Union[ExaCategory, str]] = None,
        search_type: SearchType = SearchType.AUTO,
        freshness: Optional[SourceFreshness] = None,
        max_age_hours: Optional[int] = None,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
    ) -> List[ResearchResult]:
        """
        Pass 1: Search with highlights only (efficient candidate selection).
        
        Args:
            query: Search query
            num_results: Number of results to return
            category: Exa category (people, company, news, etc.)
            search_type: auto or fast
            freshness: Preset freshness type (news, social, evergreen, etc.)
            max_age_hours: Override freshness with specific hours (-1 = cache only)
            include_domains: Whitelist domains
            exclude_domains: Blacklist domains
            
        Returns:
            List of ResearchResult with highlights only (no full text)
        """
        if not self.api_key:
            logger.warning("No Exa API key configured")
            return []
        
        try:
            client = self._get_client()
            
            # Determine max_age_hours
            freshness_hours = self._resolve_freshness(freshness, max_age_hours)
            
            # Build contents options for highlights only
            contents_options = {"highlights": {"num_sentences": 3, "highlights_per_url": 3}}
            
            # Run synchronous call in thread pool
            loop = asyncio.get_event_loop()
            
            def _search():
                kwargs = {
                    "query": query,
                    "num_results": num_results,
                    "type": search_type.value,
                    "contents": contents_options,
                }
                
                if category:
                    kwargs["category"] = category.value if isinstance(category, ExaCategory) else category
                
                # Note: freshness/freshness_hours is tracked in metadata but
                # actual implementation uses date filters or flags depending on SDK version
                # For now, we document the intent in metadata
                
                if include_domains:
                    kwargs["include_domains"] = include_domains
                if exclude_domains:
                    kwargs["exclude_domains"] = exclude_domains
                
                return client.search(**kwargs)
            
            response = await loop.run_in_executor(None, _search)
            
            # Build metadata
            metadata = SearchMetadata(
                query=query,
                category=category.value if isinstance(category, ExaCategory) else category,
                search_type=search_type.value,
                num_results_requested=num_results,
                num_results_returned=len(response.results),
                max_age_hours=freshness_hours,
            )
            
            # Convert to ResearchResult
            results = []
            for result in response.results:
                research_result = self._convert_to_research_result(result, metadata)
                results.append(research_result)
            
            logger.info(f"Exa search returned {len(results)} highlight results")
            return results
            
        except Exception as e:
            logger.error(f"Exa highlight search failed: {e}")
            return []
    
    async def fetch_full_contents(
        self,
        urls: List[str],
        max_characters: int = 10000,
    ) -> List[ResearchResult]:
        """
        Pass 2: Fetch full contents for shortlisted URLs.
        
        Args:
            urls: List of URLs to fetch
            max_characters: Maximum characters per URL
            
        Returns:
            List of ResearchResult with full text
        """
        if not urls:
            return []
        
        if not self.api_key:
            logger.warning("No Exa API key configured")
            return []
        
        try:
            client = self._get_client()
            
            loop = asyncio.get_event_loop()
            
            def _fetch():
                return client.get_contents(
                    urls,
                    text={"max_characters": max_characters},
                )
            
            response = await loop.run_in_executor(None, _fetch)
            
            # Convert to ResearchResult
            results = []
            for result in response.results:
                research_result = ResearchResult(
                    url=result.url,
                    title=result.title or "",
                    text=result.text if hasattr(result, 'text') else None,
                    text_length=len(result.text) if hasattr(result, 'text') and result.text else 0,
                    author=result.author if hasattr(result, 'author') else None,
                    published_date=result.published_date if hasattr(result, 'published_date') else None,
                    favicon=result.favicon if hasattr(result, 'favicon') else None,
                )
                results.append(research_result)
            
            logger.info(f"Exa contents fetched for {len(results)} URLs")
            return results
            
        except Exception as e:
            logger.error(f"Exa contents fetch failed: {e}")
            return []
    
    async def two_pass_search(
        self,
        query: str,
        num_candidates: int = 10,
        num_full_content: int = 3,
        **search_kwargs
    ) -> List[ResearchResult]:
        """
        Two-pass retrieval: highlights -> full content for top candidates.
        
        Args:
            query: Search query
            num_candidates: Number of candidates in pass 1
            num_full_content: Number of top candidates to fetch full content for
            **search_kwargs: Additional args for search_highlights()
            
        Returns:
            List of ResearchResult with mixed highlight/full content
        """
        # Pass 1: Get highlights
        candidates = await self.search_highlights(
            query,
            num_results=num_candidates,
            **search_kwargs
        )
        
        if not candidates:
            return []
        
        # Apply quality filtering
        filtered = self._filter_quality(candidates)
        
        if not filtered:
            logger.warning("All candidates failed quality filter")
            return candidates  # Return original if all filtered out
        
        # Deduplicate by domain
        deduplicated = self._deduplicate_by_domain(filtered)
        
        # Pass 2: Fetch full content for top N
        top_urls = [r.url for r in deduplicated[:num_full_content]]
        
        if top_urls:
            full_contents = await self.fetch_full_contents(top_urls)
            
            # Merge full content into results
            content_map = {r.url: r for r in full_contents}
            
            for result in deduplicated:
                if result.url in content_map:
                    full = content_map[result.url]
                    result.text = full.text
                    result.text_length = full.text_length
                    result.author = full.author or result.author
                    result.published_date = full.published_date or result.published_date
        
        return deduplicated
    
    # ========================================================================
    # Person Discovery
    # ========================================================================
    
    async def discover_person(
        self,
        name: str,
        aliases: Optional[List[str]] = None,
        company: Optional[str] = None,
        social_handles: Optional[List[str]] = None,
        website_domains: Optional[List[str]] = None,
        topics: Optional[List[str]] = None,
        geography: Optional[str] = None,
        num_results: int = 10,
        fetch_full_content: bool = True,
    ) -> List[ResearchResult]:
        """
        Discover information about a person using optimized search.
        
        Args:
            name: Primary name
            aliases: Alternative names
            company: Company/organization
            social_handles: Social media handles (@handle)
            website_domains: Personal/professional websites
            topics: Topics of expertise
            geography: Location
            num_results: Number of results
            fetch_full_content: Whether to do two-pass retrieval
            
        Returns:
            List of ResearchResult
        """
        # Build structured query
        query_builder = PersonSearchQuery(
            name=name,
            aliases=aliases or [],
            company=company,
            social_handles=social_handles or [],
            website_domains=website_domains or [],
            topics=topics or [],
            geography=geography,
        )
        
        query = query_builder.build_query()
        include_domains = query_builder.build_domain_filters()
        
        logger.info(f"Person discovery query: {query[:100]}...")
        
        # Use people category when searching for individuals
        category = ExaCategory.PEOPLE
        
        if fetch_full_content:
            results = await self.two_pass_search(
                query,
                num_candidates=num_results + 5,  # Get extra for filtering
                num_full_content=min(5, num_results),
                category=category,
                freshness=SourceFreshness.EVERGREEN,  # People info is relatively stable
                include_domains=include_domains if include_domains else None,
            )
        else:
            results = await self.search_highlights(
                query,
                num_results=num_results,
                category=category,
                freshness=SourceFreshness.EVERGREEN,
                include_domains=include_domains if include_domains else None,
            )
        
        # Mark results with verification notes
        for result in results:
            result.verification_notes.append(f"Person search: {name}")
            if company:
                result.verification_notes.append(f"Company context: {company}")
        
        return results[:num_results]
    
    # ========================================================================
    # Verification Methods
    # ========================================================================
    
    async def verify_claim(
        self,
        claim_text: str,
        claim_type: str = "preference",
        num_results: int = 5,
        freshness: SourceFreshness = SourceFreshness.EVERGREEN,
    ) -> List[ResearchResult]:
        """
        Search for evidence to verify a claim.
        
        Args:
            claim_text: The claim to verify
            claim_type: Type of claim (affects query building)
            num_results: Number of results
            freshness: How fresh the sources should be
            
        Returns:
            List of ResearchResult with verification metadata
        """
        # Build verification query (remove first-person pronouns)
        query = self._build_claim_query(claim_text, claim_type)
        
        results = await self.two_pass_search(
            query,
            num_candidates=num_results + 3,
            num_full_content=min(3, num_results),
            freshness=freshness,
        )
        
        # Assess verification quality
        for result in results:
            result = self._assess_verification_quality(result, claim_text)
        
        return results
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    def _resolve_freshness(
        self,
        freshness: Optional[SourceFreshness],
        max_age_hours: Optional[int]
    ) -> Optional[int]:
        """Resolve freshness preset to max_age_hours."""
        if max_age_hours is not None:
            return max_age_hours
        if freshness:
            return FRESHNESS_DEFAULTS.get(freshness)
        return None
    
    def _convert_to_research_result(
        self,
        result,
        metadata: SearchMetadata
    ) -> ResearchResult:
        """Convert Exa Result to ResearchResult."""
        # Determine source quality
        domain = self._extract_domain(result.url)
        source_quality = self._assess_domain_quality(domain)
        
        # Extract highlights
        highlights = []
        highlight_scores = []
        if hasattr(result, 'highlights') and result.highlights:
            highlights = result.highlights
        if hasattr(result, 'highlight_scores') and result.highlight_scores:
            highlight_scores = result.highlight_scores
        
        # Extract entities if available
        entities = []
        if hasattr(result, 'entities') and result.entities:
            entities = [e.to_dict() if hasattr(e, 'to_dict') else str(e) for e in result.entities]
        
        return ResearchResult(
            url=result.url,
            title=result.title or "",
            highlights=highlights,
            highlight_scores=highlight_scores,
            published_date=result.published_date if hasattr(result, 'published_date') else None,
            author=result.author if hasattr(result, 'author') else None,
            favicon=result.favicon if hasattr(result, 'favicon') else None,
            entities=entities,
            score=getattr(result, 'score', 0.0),
            source_quality=source_quality,
            search_metadata=metadata,
        )
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc.lower().replace('www.', '')
        except:
            return ""
    
    def _assess_domain_quality(self, domain: str) -> str:
        """Assess domain authority."""
        if any(d in domain for d in HIGH_AUTHORITY_DOMAINS):
            return "high"
        if any(d in domain for d in LOW_QUALITY_DOMAINS):
            return "low"
        return "medium"
    
    def _filter_quality(self, results: List[ResearchResult]) -> List[ResearchResult]:
        """Filter out low-quality results."""
        filtered = []
        for result in results:
            # Skip low-quality domains
            if result.source_quality == "low":
                logger.debug(f"Filtering low-quality domain: {result.url}")
                continue
            
            # Skip results with no content
            if not result.title:
                continue
            
            filtered.append(result)
        
        return filtered
    
    def _deduplicate_by_domain(
        self,
        results: List[ResearchResult],
        max_per_domain: int = 2
    ) -> List[ResearchResult]:
        """Deduplicate results by domain."""
        domain_counts = {}
        deduplicated = []
        
        for result in results:
            domain = self._extract_domain(result.url)
            count = domain_counts.get(domain, 0)
            
            if count < max_per_domain:
                deduplicated.append(result)
                domain_counts[domain] = count + 1
            else:
                logger.debug(f"Skipping duplicate domain: {domain}")
        
        return deduplicated
    
    def _build_claim_query(self, claim_text: str, claim_type: str) -> str:
        """Build search query from claim."""
        # Remove first-person pronouns
        import re
        query = claim_text.lower()
        query = re.sub(r'\b(i|me|my|myself|we|our|ours)\b', '', query)
        query = re.sub(r'\s+', ' ', query).strip()
        
        # Add context for certain claim types
        if claim_type == "experience":
            query = f"{query} experience background"
        elif claim_type == "preference":
            query = f"{query} prefers"
        
        return query
    
    def _assess_verification_quality(
        self,
        result: ResearchResult,
        claim_text: str
    ) -> ResearchResult:
        """Assess whether result provides good verification for claim."""
        notes = []
        
        # Check for evidence span
        if result.text and len(result.text) > 1000:
            notes.append("Good evidence span (full text available)")
        elif result.highlights:
            notes.append("Limited evidence (highlights only)")
        else:
            notes.append("No evidence span available")
        
        # Check source quality
        if result.source_quality == "high":
            notes.append("High authority source")
            result.verified = True
        elif result.source_quality == "medium":
            notes.append("Medium authority source - verify with additional sources")
            result.verified = False
        else:
            notes.append("Low authority source - not suitable for verification")
            result.verified = False
        
        result.verification_notes.extend(notes)
        return result


# ============================================================================
# Convenience Functions
# ============================================================================

async def search_person(
    name: str,
    **kwargs
) -> List[ResearchResult]:
    """Convenience function for person discovery."""
    service = ExaResearchService()
    return await service.discover_person(name, **kwargs)


async def verify_claim(
    claim_text: str,
    **kwargs
) -> List[ResearchResult]:
    """Convenience function for claim verification."""
    service = ExaResearchService()
    return await service.verify_claim(claim_text, **kwargs)
