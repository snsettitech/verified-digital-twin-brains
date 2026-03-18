"""
Deep Research Configuration Module

Feature flags, limits, and configuration for the Deep Research system.
All settings are loaded from environment variables with sensible defaults.
"""

import os
from typing import List, Dict, Any
from pydantic import BaseModel, Field


class FetchSafetyConfig(BaseModel):
    """Safety configuration for web fetching/crawling."""
    max_content_size_mb: int = Field(default=10, description="Max content size in MB")
    request_timeout_seconds: int = Field(default=30, description="Request timeout in seconds")
    max_redirects: int = Field(default=5, description="Maximum redirects to follow")
    allowed_content_types: List[str] = Field(
        default=["text/html", "text/plain", "text/markdown", "application/json", "application/xml"],
        description="Allowed content types for fetching"
    )
    blocked_private_ip_ranges: List[str] = Field(
        default=[
            "10.0.0.0/8",      # RFC1918 - Private
            "172.16.0.0/12",   # RFC1918 - Private
            "192.168.0.0/16",  # RFC1918 - Private
            "127.0.0.0/8",     # Loopback
            "169.254.0.0/16",  # Link-local
            "0.0.0.0/8",       # Current network
            "::1/128",         # IPv6 loopback
            "fc00::/7",        # IPv6 unique local
            "fe80::/10",       # IPv6 link-local
        ],
        description="Private IP ranges to block (SSRF protection)"
    )
    blocked_schemes: List[str] = Field(
        default=["file", "ftp", "gopher", "ldap", "javascript", "data"],
        description="URL schemes to block"
    )
    dns_rebinding_protection: bool = Field(
        default=True,
        description="Re-resolve DNS after redirects to prevent rebinding"
    )
    max_hostname_length: int = Field(default=253, description="Maximum hostname length")

    @classmethod
    def from_env(cls) -> "FetchSafetyConfig":
        """Load configuration from environment variables."""
        return cls(
            max_content_size_mb=int(os.getenv("CRAWL_MAX_CONTENT_SIZE_MB", "10")),
            request_timeout_seconds=int(os.getenv("CRAWL_REQUEST_TIMEOUT_SECONDS", "30")),
            max_redirects=int(os.getenv("CRAWL_MAX_REDIRECTS", "5")),
            allowed_content_types=os.getenv(
                "CRAWL_ALLOWED_CONTENT_TYPES",
                "text/html,text/plain,text/markdown,application/json,application/xml"
            ).split(","),
            dns_rebinding_protection=os.getenv("CRAWL_DNS_REBINDING_PROTECTION", "true").lower() == "true",
            max_hostname_length=int(os.getenv("CRAWL_MAX_HOSTNAME_LENGTH", "253")),
        )


class ResearchLimitsConfig(BaseModel):
    """Limits for research runs."""
    max_subquestions: int = Field(default=10, description="Maximum subquestions per research run")
    max_claims_per_subquestion: int = Field(default=50, description="Maximum claims per subquestion")
    max_web_searches: int = Field(default=20, description="Maximum web searches per research run")
    max_web_fetches: int = Field(default=50, description="Maximum web fetches per research run")
    max_run_duration_minutes: int = Field(default=10, description="Maximum research run duration")
    max_depth: int = Field(default=3, description="Maximum research depth")
    
    # Global limits
    concurrent_runs_per_twin: int = Field(default=2, description="Max concurrent runs per twin")
    concurrent_runs_per_user: int = Field(default=3, description="Max concurrent runs per user")
    max_global_concurrent_research_jobs: int = Field(default=50, description="Global max concurrent jobs")
    
    # Idempotency
    dedupe_window_minutes: int = Field(default=5, description="Window for request deduplication")

    @classmethod
    def from_env(cls) -> "ResearchLimitsConfig":
        """Load configuration from environment variables."""
        return cls(
            max_subquestions=int(os.getenv("RESEARCH_MAX_SUBQUESTIONS", "10")),
            max_claims_per_subquestion=int(os.getenv("RESEARCH_MAX_CLAIMS_PER_SUBQ", "50")),
            max_web_searches=int(os.getenv("RESEARCH_MAX_WEB_SEARCHES", "20")),
            max_web_fetches=int(os.getenv("RESEARCH_MAX_WEB_FETCHES", "50")),
            max_run_duration_minutes=int(os.getenv("RESEARCH_MAX_RUN_DURATION_MINUTES", "10")),
            max_depth=int(os.getenv("RESEARCH_MAX_DEPTH", "3")),
            concurrent_runs_per_twin=int(os.getenv("RESEARCH_CONCURRENT_PER_TWIN", "2")),
            concurrent_runs_per_user=int(os.getenv("RESEARCH_CONCURRENT_PER_USER", "3")),
            max_global_concurrent_research_jobs=int(os.getenv("RESEARCH_GLOBAL_MAX_JOBS", "50")),
            dedupe_window_minutes=int(os.getenv("RESEARCH_DEDUPE_WINDOW_MINUTES", "5")),
        )


class SearchProviderConfig(BaseModel):
    """Configuration for search providers."""
    provider: str = Field(default="exa", description="Search provider: exa, brave, or serper")
    api_key: str = Field(default="", description="API key for search provider")
    
    @classmethod
    def from_env(cls) -> "SearchProviderConfig":
        """Load configuration from environment variables."""
        provider = os.getenv("SEARCH_PROVIDER", "exa").lower()
        
        # Get API key based on provider
        api_key = ""
        if provider == "exa":
            api_key = os.getenv("EXA_API_KEY", "")
        elif provider == "brave":
            api_key = os.getenv("BRAVE_API_KEY", "")
        elif provider == "serper":
            api_key = os.getenv("SERPER_API_KEY", "")
        
        return cls(provider=provider, api_key=api_key)


class ArtifactStorageConfig(BaseModel):
    """Configuration for artifact storage."""
    backend: str = Field(default="filesystem", description="Storage backend: filesystem or s3")
    base_path: str = Field(default="artifacts", description="Base path for filesystem storage")
    
    # S3 settings (for future use)
    s3_bucket: str = Field(default="", description="S3 bucket name")
    s3_region: str = Field(default="", description="S3 region")
    s3_prefix: str = Field(default="artifacts", description="S3 key prefix")
    
    @classmethod
    def from_env(cls) -> "ArtifactStorageConfig":
        """Load configuration from environment variables."""
        return cls(
            backend=os.getenv("ARTIFACT_STORAGE_BACKEND", "filesystem"),
            base_path=os.getenv("ARTIFACT_BASE_PATH", "artifacts"),
            s3_bucket=os.getenv("ARTIFACT_S3_BUCKET", ""),
            s3_region=os.getenv("ARTIFACT_S3_REGION", ""),
            s3_prefix=os.getenv("ARTIFACT_S3_PREFIX", "artifacts"),
        )


class FirecrawlConfig(BaseModel):
    """Configuration for Firecrawl API (Phase 3.0)."""
    api_key: str = Field(default="", description="Firecrawl API key")
    base_url: str = Field(default="https://api.firecrawl.dev", description="Firecrawl API base URL")
    
    # Retry and resilience settings
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_backoff_base: float = Field(default=2.0, description="Exponential backoff base")
    timeout_seconds: int = Field(default=60, description="Request timeout in seconds")
    max_concurrent: int = Field(default=5, description="Max concurrent requests")
    
    # Circuit breaker settings
    circuit_failure_threshold: int = Field(default=5, description="Failures before opening circuit")
    circuit_recovery_timeout: int = Field(default=30, description="Seconds before half-open test")
    
    # Crawl defaults
    website_crawl_limit: int = Field(default=50, description="Default max pages per crawl")
    website_max_depth: int = Field(default=3, description="Default max crawl depth")
    scrape_formats: List[str] = Field(default_factory=lambda: ["markdown"], description="Output formats")
    
    @classmethod
    def from_env(cls) -> "FirecrawlConfig":
        """Load configuration from environment variables."""
        return cls(
            api_key=os.getenv("FIRECRAWL_API_KEY", ""),
            base_url=os.getenv("FIRECRAWL_BASE_URL", "https://api.firecrawl.dev"),
            max_retries=int(os.getenv("FIRECRAWL_MAX_RETRIES", "3")),
            retry_backoff_base=float(os.getenv("FIRECRAWL_RETRY_BACKOFF_BASE", "2.0")),
            timeout_seconds=int(os.getenv("FIRECRAWL_TIMEOUT_SECONDS", "60")),
            max_concurrent=int(os.getenv("FIRECRAWL_MAX_CONCURRENT", "5")),
            circuit_failure_threshold=int(os.getenv("FIRECRAWL_CIRCUIT_FAILURE_THRESHOLD", "5")),
            circuit_recovery_timeout=int(os.getenv("FIRECRAWL_CIRCUIT_RECOVERY_TIMEOUT", "30")),
            website_crawl_limit=int(os.getenv("FIRECRAWL_WEBSITE_CRAWL_LIMIT", "50")),
            website_max_depth=int(os.getenv("FIRECRAWL_WEBSITE_MAX_DEPTH", "3")),
            scrape_formats=os.getenv("FIRECRAWL_SCRAPE_FORMATS", "markdown").split(","),
        )
    
    def is_configured(self) -> bool:
        """Check if Firecrawl is properly configured."""
        try:
            from firecrawl import FirecrawlApp
            return bool(self.api_key)
        except ImportError:
            return False


class DeepResearchConfig(BaseModel):
    """Main Deep Research configuration."""
    enabled: bool = Field(default=True, description="Deep Research is always enabled")
    crawl_safety_enabled: bool = Field(default=True, description="Enable crawl safety controls")
    name_only_deep_research_enabled: bool = Field(
        default=True,
        description="Enable name-only deep research flow (/deep-research/runs)",
    )
    phase_12_suppress_unresolved_by_default: bool = Field(default=True, description="Suppress unresolved claims from runtime")
    phase_12_auto_publish: bool = Field(default=False, description="Auto-publish without manual review")
    
    # Sub-configs
    safety: FetchSafetyConfig = Field(default_factory=FetchSafetyConfig.from_env)
    limits: ResearchLimitsConfig = Field(default_factory=ResearchLimitsConfig.from_env)
    search: SearchProviderConfig = Field(default_factory=SearchProviderConfig.from_env)
    artifacts: ArtifactStorageConfig = Field(default_factory=ArtifactStorageConfig.from_env)
    firecrawl: FirecrawlConfig = Field(default_factory=FirecrawlConfig.from_env)
    
    @classmethod
    def from_env(cls) -> "DeepResearchConfig":
        """Load full configuration from environment variables."""
        return cls(
            enabled=True,
            crawl_safety_enabled=os.getenv("CRAWL_SAFETY_ENABLED", "true").lower() == "true",
            name_only_deep_research_enabled=os.getenv("NAME_ONLY_DEEP_RESEARCH_ENABLED", "true").lower() == "true",
            phase_12_suppress_unresolved_by_default=os.getenv("DR_PHASE_12_SUPPRESS_UNRESOLVED", "true").lower() == "true",
            phase_12_auto_publish=os.getenv("DR_PHASE_12_AUTO_PUBLISH", "false").lower() == "true",
        )
    
    def is_enabled(self) -> bool:
        """Deep Research is always enabled."""
        return True
    
    def is_firecrawl_configured(self) -> bool:
        """Check if Firecrawl is properly configured."""
        return self.firecrawl.is_configured()


# Global configuration instance (lazy-loaded)
_config: DeepResearchConfig | None = None


def get_config() -> DeepResearchConfig:
    """Get the global Deep Research configuration."""
    global _config
    if _config is None:
        _config = DeepResearchConfig.from_env()
    return _config


def reset_config() -> None:
    """Reset the global configuration (useful for testing)."""
    global _config
    _config = None


# Claim class taxonomy (as documented in plan)
CLAIM_CLASS_TAXONOMY = {
    "public_fact": {
        "description": "Verifiable objective facts",
        "web_verify": "always",
        "examples": ["Earth's population is 8B", "Company founded in 2010"],
    },
    "private_fact": {
        "description": "Twin owner's private information",
        "web_verify": "never",
        "examples": ["Owner's home address", "Unpublished revenue figures"],
    },
    "owner_stance": {
        "description": "Owner's documented position",
        "web_verify": "never",
        "examples": ["I believe AI alignment is critical", "My investment thesis"],
    },
    "procedural": {
        "description": "How-to/process questions",
        "web_verify": "optional",
        "examples": ["How to apply for funding", "Evaluation criteria"],
    },
    "opinion": {
        "description": "Subjective assessments",
        "web_verify": "never",
        "examples": ["Best startup in 2024", "Most promising technology"],
    },
    "freshness_sensitive": {
        "description": "Time-dependent facts",
        "web_verify": "always",
        "examples": ["Current stock price", "Latest funding round"],
    },
}

# Web verification eligibility by claim class
def is_web_verification_eligible(claim_class: str, policy: str = "eligible_only") -> bool:
    """
    Determine if a claim class is eligible for web verification.
    
    Args:
        claim_class: The class of the claim
        policy: Verification policy - "eligible_only", "all", or "none"
    
    Returns:
        True if web verification should be performed
    """
    if policy == "none":
        return False
    if policy == "all":
        return True
    
    # eligible_only - check taxonomy
    taxonomy = CLAIM_CLASS_TAXONOMY.get(claim_class, {})
    web_verify = taxonomy.get("web_verify", "never")
    return web_verify in ("always", "optional")


# Source tier definitions (will be extended with DB table in Phase 5)
SOURCE_TIER_DEFINITIONS = {
    1: {
        "name": "Tier 1 - Authoritative",
        "description": "Academic, government, major news organizations",
        "domain_patterns": [".edu", ".gov", "reuters.com", "ap.org", "bloomberg.com"],
        "trust_score_range": (0.8, 1.0),
    },
    2: {
        "name": "Tier 2 - Established",
        "description": "Established blogs, industry publications, company press releases",
        "domain_patterns": ["medium.com", "substack.com", "techcrunch.com", "forbes.com"],
        "trust_score_range": (0.5, 0.8),
    },
    3: {
        "name": "Tier 3 - User-Generated",
        "description": "Social media, forums, user-generated content, unknown domains",
        "domain_patterns": [],  # Catch-all for non-matching domains
        "trust_score_range": (0.0, 0.5),
    },
}
