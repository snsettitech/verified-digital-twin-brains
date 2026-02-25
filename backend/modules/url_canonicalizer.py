"""
URL Canonicalizer Module

Normalizes URLs for deduplication and consistent indexing.
Implements URL canonicalization rules for web crawling.
"""

import hashlib
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse


# Default tracking parameters to strip
DEFAULT_STRIP_PARAMS = {
    # Google Analytics
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_source_platform", "utm_creative_format", "utm_marketing_tactic",
    # Facebook
    "fbclid", "fb_action_ids", "fb_action_types", "fb_source",
    # Twitter/X
    "twclid", "twitter_id",
    # LinkedIn
    "li_fat_id",
    # Microsoft
    "msclkid",
    # Pinterest
    "epik", "pin_id",
    # Reddit
    "rdt_cid",
    # TikTok
    "ttclid",
    # General tracking
    "ref", "referrer", "source", "campaign", "medium", "term", "content",
    "gclid", "dclid", "wickedid", "yclid", "mc_cid", "mc_eid",
    # Session/junk params
    "sessionid", "jsessionid", "phpsessid", "aspsessionid",
}

# Default patterns to strip from path
DEFAULT_PATH_STRIP_PATTERNS = [
    r'/+$',  # Trailing slashes (handled separately)
]


class URLCanonicalizationRules:
    """Rules for URL canonicalization."""
    
    def __init__(
        self,
        strip_tracking_params: bool = True,
        strip_params: Optional[set] = None,
        sort_query_params: bool = True,
        normalize_case: bool = True,
        remove_trailing_slash: bool = True,
        remove_fragment: bool = True,
        keep_fragment_for_paths: Optional[List[str]] = None,
        max_url_length: int = 2048,
    ):
        self.strip_tracking_params = strip_tracking_params
        self.strip_params = strip_params or DEFAULT_STRIP_PARAMS
        self.sort_query_params = sort_query_params
        self.normalize_case = normalize_case
        self.remove_trailing_slash = remove_trailing_slash
        self.remove_fragment = remove_fragment
        self.keep_fragment_for_paths = keep_fragment_for_paths or []
        self.max_url_length = max_url_length
    
    @classmethod
    def default(cls) -> "URLCanonicalizationRules":
        """Get default rules."""
        return cls()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "URLCanonicalizationRules":
        """Create rules from dictionary configuration."""
        return cls(
            strip_tracking_params=data.get("strip_tracking_params", True),
            strip_params=set(data.get("strip_params", [])) if data.get("strip_params") else None,
            sort_query_params=data.get("sort_query_params", True),
            normalize_case=data.get("normalize_case", True),
            remove_trailing_slash=data.get("remove_trailing_slash", True),
            remove_fragment=data.get("remove_fragment", True),
            keep_fragment_for_paths=data.get("keep_fragment_for_paths", []),
            max_url_length=data.get("max_url_length", 2048),
        )


def canonicalize_url(url: str, rules: Optional[URLCanonicalizationRules] = None) -> str:
    """
    Normalize URL for deduplication.
    
    Steps:
    1. Parse URL
    2. Normalize scheme and netloc (lowercase)
    3. Strip tracking parameters from query
    4. Sort query parameters alphabetically
    5. Normalize path (remove trailing slash unless root)
    6. Remove fragment (unless configured to keep)
    7. Reconstruct URL
    
    Args:
        url: Raw URL to canonicalize
        rules: Canonicalization rules (uses defaults if None)
    
    Returns:
        Canonicalized URL string
    
    Raises:
        ValueError: If URL is invalid or exceeds max length
    """
    if not url:
        raise ValueError("URL cannot be empty")
    
    rules = rules or URLCanonicalizationRules.default()
    
    if len(url) > rules.max_url_length:
        raise ValueError(f"URL exceeds maximum length of {rules.max_url_length}")
    
    # Parse URL
    parsed = urlparse(url)
    
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid URL: missing scheme or netloc: {url}")
    
    # 1. Normalize scheme and netloc (lowercase)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    
    # Remove default ports
    if scheme == "http" and netloc.endswith(":80"):
        netloc = netloc[:-3]
    elif scheme == "https" and netloc.endswith(":443"):
        netloc = netloc[:-4]
    
    # 2. Normalize path
    path = parsed.path
    if rules.normalize_case:
        # Only lowercase path, not query (which may be case-sensitive)
        path = path.lower()
    
    # Remove trailing slash (but keep root slash)
    if rules.remove_trailing_slash and path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    
    # 3. Normalize query parameters
    query = parsed.query
    if query:
        params = parse_qs(query, keep_blank_values=True)
        
        # Strip tracking parameters
        if rules.strip_tracking_params:
            params = {
                k: v for k, v in params.items()
                if k.lower() not in rules.strip_params
            }
        
        # Sort parameters alphabetically
        if rules.sort_query_params:
            sorted_params = sorted(params.items())
        else:
            sorted_params = list(params.items())
        
        # Rebuild query string
        # Use doseq=True to handle multiple values for same key
        query = urlencode(sorted_params, doseq=True)
    
    # 4. Handle fragment
    fragment = parsed.fragment
    if rules.remove_fragment:
        # Check if we should keep fragment for this path
        keep_fragment = False
        for path_pattern in rules.keep_fragment_for_paths:
            if path_pattern in path:
                keep_fragment = True
                break
        if not keep_fragment:
            fragment = ""
    
    # Reconstruct URL
    canonical = urlunparse((scheme, netloc, path, parsed.params, query, fragment))
    
    return canonical


def get_url_hash(canonical_url: str) -> str:
    """
    Return SHA-256 hash of canonical URL for indexing.
    
    Args:
        canonical_url: Canonicalized URL string
    
    Returns:
        Hexadecimal hash string (64 characters)
    """
    return hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()


def extract_domain(url: str) -> str:
    """
    Extract domain from URL.
    
    Args:
        url: URL string
    
    Returns:
        Domain (netloc) part of URL
    """
    parsed = urlparse(url)
    return parsed.netloc.lower()


def is_same_domain(url1: str, url2: str) -> bool:
    """
    Check if two URLs are from the same domain.
    
    Args:
        url1: First URL
        url2: Second URL
    
    Returns:
        True if domains match
    """
    return extract_domain(url1) == extract_domain(url2)


def normalize_for_comparison(url: str) -> str:
    """
    Normalize URL for comparison purposes (more aggressive than canonicalization).
    
    This removes www prefix and normalizes more aggressively for
    finding near-duplicate URLs.
    
    Args:
        url: URL to normalize
    
    Returns:
        Aggressively normalized URL
    """
    canonical = canonicalize_url(url)
    parsed = urlparse(canonical)
    
    # Remove www prefix
    netloc = parsed.netloc
    if netloc.startswith("www."):
        netloc = netloc[4:]
    
    # Remove common index pages
    path = parsed.path
    if path in ["/index.html", "/index.php", "/home", "/default"]:
        path = "/"
    
    return urlunparse((parsed.scheme, netloc, path, parsed.params, parsed.query, ""))


class URLCanonicalizer:
    """Stateful URL canonicalizer with caching."""
    
    def __init__(self, rules: Optional[URLCanonicalizationRules] = None):
        self.rules = rules or URLCanonicalizationRules.default()
        self._cache: Dict[str, str] = {}
    
    def canonicalize(self, url: str) -> str:
        """Canonicalize URL with caching."""
        if url in self._cache:
            return self._cache[url]
        
        canonical = canonicalize_url(url, self.rules)
        self._cache[url] = canonical
        return canonical
    
    def get_hash(self, url: str) -> str:
        """Get hash of canonical URL."""
        canonical = self.canonicalize(url)
        return get_url_hash(canonical)
    
    def clear_cache(self) -> None:
        """Clear the canonicalization cache."""
        self._cache.clear()
