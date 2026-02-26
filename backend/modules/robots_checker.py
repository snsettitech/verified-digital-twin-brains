"""
robots_checker.py

Phase 1 Component: URL preflight checks for Mode C web fetch.
Ensures basic URL validity and optional crawlability checks.
"""

import os
import time
import hashlib
from typing import Optional, Set
from urllib.parse import urlparse
import httpx
from functools import lru_cache

# =============================================================================
# Configuration
# =============================================================================

ROBOTS_TXT_CACHE_TTL_SECONDS = int(os.getenv("ROBOTS_TXT_CACHE_TTL", "3600"))  # 1 hour
WEB_FETCH_RATE_LIMIT_SECONDS = float(os.getenv("WEB_FETCH_RATE_LIMIT", "2.0"))
LINK_FIRST_ALLOWLIST = os.getenv("LINK_FIRST_ALLOWLIST", "")
ALLOW_ALL_URLS = os.getenv("LINK_FIRST_ALLOW_ALL_URLS", "false").strip().lower() in {
    "1", "true", "yes", "on"
}

# Hard blocklist - these domains are NEVER crawled (use export upload instead)
BLOCKED_DOMAINS = {
    "linkedin.com",
    "www.linkedin.com",
    "mobile.linkedin.com",
    "twitter.com",
    "x.com",
    "www.twitter.com",
    "www.x.com",
    "mobile.twitter.com",
    "facebook.com",
    "www.facebook.com",
    "instagram.com",
    "www.instagram.com",
    "tiktok.com",
    "www.tiktok.com",
}

# Default allowlist for Mode C
DEFAULT_ALLOWLIST = {
    "github.com",
    "gist.github.com",
    "medium.com",
    "substack.com",
}

# In-memory cache for robots.txt content
_robots_cache: dict = {}
_last_fetch_time: float = 0.0


# =============================================================================
# Domain Allowlist Management
# =============================================================================

def get_allowlist() -> Set[str]:
    """Get the combined allowlist from env and defaults."""
    allowlist = DEFAULT_ALLOWLIST.copy()
    
    if LINK_FIRST_ALLOWLIST:
        custom_domains = {d.strip().lower() for d in LINK_FIRST_ALLOWLIST.split(",")}
        allowlist.update(custom_domains)
    
    return allowlist


def is_domain_allowed(url: str) -> tuple[bool, str]:
    """
    Check URL/domain validity.

    Returns:
        (allowed, reason)
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False, "Invalid URL. Use an absolute http(s) URL."

    if ALLOW_ALL_URLS:
        return True, "Allow-all mode enabled"

    domain = parsed.netloc.lower()
    
    # Remove www. prefix for comparison
    if domain.startswith("www."):
        domain = domain[4:]
    
    # Check blocklist first
    if domain in BLOCKED_DOMAINS or f"www.{domain}" in BLOCKED_DOMAINS:
        return False, f"Domain {domain} is blocked. Use export upload (Mode A)."
    
    # Check allowlist
    allowlist = get_allowlist()
    
    # Check exact match
    if domain in allowlist:
        return True, "Domain in allowlist"
    
    # Check wildcard subdomains
    for allowed in allowlist:
        if allowed.startswith("*."):
            suffix = allowed[2:]  # Remove *.
            if domain.endswith(suffix):
                return True, f"Domain matches allowlist pattern {allowed}"
    
    return False, f"Domain {domain} not in allowlist. Add to LINK_FIRST_ALLOWLIST."


# =============================================================================
# robots.txt Checking
# =============================================================================

class RobotsChecker:
    """Checks robots.txt compliance for URLs."""
    
    def __init__(self, user_agent: str = "DigitalTwinBot/1.0"):
        self.user_agent = user_agent
        self.cache_ttl = ROBOTS_TXT_CACHE_TTL_SECONDS
    
    def _get_cache_key(self, domain: str) -> str:
        """Generate cache key for domain."""
        return hashlib.sha256(domain.encode()).hexdigest()[:16]
    
    def _get_cached_robots(self, domain: str) -> Optional[str]:
        """Get cached robots.txt content if valid."""
        cache_key = self._get_cache_key(domain)
        cached = _robots_cache.get(cache_key)
        
        if cached:
            age = time.time() - cached.get("timestamp", 0)
            if age < self.cache_ttl:
                return cached.get("content")
        
        return None
    
    def _cache_robots(self, domain: str, content: str):
        """Cache robots.txt content."""
        cache_key = self._get_cache_key(domain)
        _robots_cache[cache_key] = {
            "content": content,
            "timestamp": time.time(),
        }
    
    async def fetch_robots_txt(self, domain: str) -> Optional[str]:
        """Fetch robots.txt for a domain."""
        # Check cache first
        cached = self._get_cached_robots(domain)
        if cached is not None:
            return cached
        
        # Fetch robots.txt
        robots_url = f"https://{domain}/robots.txt"
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(robots_url)
                
                if response.status_code == 200:
                    content = response.text
                    self._cache_robots(domain, content)
                    return content
                elif response.status_code == 404:
                    # No robots.txt means allow all
                    self._cache_robots(domain, "")
                    return ""
                else:
                    # On error, cache empty and allow (fail open for safety)
                    self._cache_robots(domain, "")
                    return ""
                    
        except Exception as e:
            print(f"[RobotsChecker] Error fetching robots.txt for {domain}: {e}")
            # Fail open - allow if we can't fetch
            self._cache_robots(domain, "")
            return ""
    
    def _parse_robots_txt(self, content: str) -> dict:
        """Parse robots.txt content into rules."""
        rules = {
            "disallow": [],
            "allow": [],
            "crawl_delay": None,
        }
        
        if not content:
            return rules
        
        lines = content.split("\n")
        user_agent_relevant = False
        
        for line in lines:
            line = line.strip()
            
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue
            
            # Parse directives
            if ":" in line:
                directive, value = line.split(":", 1)
                directive = directive.strip().lower()
                value = value.strip()
                
                if directive == "user-agent":
                    # Check if this applies to us
                    user_agent_relevant = (
                        value == "*" or 
                        self.user_agent.lower() in value.lower()
                    )
                
                elif user_agent_relevant:
                    if directive == "disallow":
                        rules["disallow"].append(value)
                    elif directive == "allow":
                        rules["allow"].append(value)
                    elif directive == "crawl-delay":
                        try:
                            rules["crawl_delay"] = float(value)
                        except ValueError:
                            pass
        
        return rules
    
    def _is_path_allowed(self, path: str, rules: dict) -> bool:
        """Check if a path is allowed by robots rules."""
        # Check explicit allows first
        for allow_path in rules["allow"]:
            if path.startswith(allow_path):
                return True
        
        # Check disallows
        for disallow_path in rules["disallow"]:
            if path.startswith(disallow_path):
                return False
        
        return True
    
    async def can_fetch(self, url: str) -> tuple[bool, str]:
        """
        Check if we can fetch a URL according to robots.txt.
        
        Returns:
            (allowed, reason)
        """
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        path = parsed.path or "/"
        
        # Fetch and parse robots.txt
        robots_content = await self.fetch_robots_txt(domain)
        rules = self._parse_robots_txt(robots_content)
        
        # Check path
        if self._is_path_allowed(path, rules):
            return True, "robots.txt allows"
        else:
            return False, f"robots.txt disallows path {path}"
    
    def get_crawl_delay(self, domain: str) -> float:
        """Get crawl delay for a domain (seconds)."""
        cache_key = self._get_cache_key(domain)
        cached = _robots_cache.get(cache_key)
        
        if cached:
            rules = self._parse_robots_txt(cached.get("content", ""))
            if rules["crawl_delay"]:
                return max(rules["crawl_delay"], WEB_FETCH_RATE_LIMIT_SECONDS)
        
        return WEB_FETCH_RATE_LIMIT_SECONDS


# =============================================================================
# Rate Limiting
# =============================================================================

async def check_rate_limit() -> tuple[bool, float]:
    """
    Check global rate limit for web fetch.
    
    Returns:
        (allowed, wait_seconds)
    """
    global _last_fetch_time
    
    now = time.time()
    elapsed = now - _last_fetch_time
    
    if elapsed >= WEB_FETCH_RATE_LIMIT_SECONDS:
        _last_fetch_time = now
        return True, 0.0
    else:
        wait = WEB_FETCH_RATE_LIMIT_SECONDS - elapsed
        return False, wait


def reset_rate_limit():
    """Reset rate limit (for testing)."""
    global _last_fetch_time
    _last_fetch_time = 0.0


# =============================================================================
# Main Check Function
# =============================================================================

async def check_url_fetchable(url: str) -> dict:
    """
    Complete URL fetchability check for Mode C.
    
    Returns:
        {
            "allowed": bool,
            "reason": str,
            "error_code": str | None,
            "crawl_delay": float,
        }
    """
    # Check basic URL/domain validity
    domain_allowed, domain_reason = is_domain_allowed(url)
    
    if not domain_allowed:
        return {
            "allowed": False,
            "reason": domain_reason,
            "error_code": "LINK_INVALID_URL" if "invalid url" in domain_reason.lower() else "LINK_DOMAIN_NOT_ALLOWED",
            "crawl_delay": 0.0,
        }

    # Allow-all policy: do not hard-block by domain, robots, or preflight rate limit.
    # Real fetch/auth failures are handled by ingestion.
    if ALLOW_ALL_URLS:
        return {
            "allowed": True,
            "reason": "URL accepted (allow-all mode). Actual fetch may still fail at ingestion time.",
            "error_code": None,
            "crawl_delay": 0.0,
        }
    
    # Check rate limit
    rate_ok, wait_time = await check_rate_limit()
    
    if not rate_ok:
        return {
            "allowed": False,
            "reason": f"Rate limit hit. Wait {wait_time:.1f} seconds.",
            "error_code": "LINK_RATE_LIMITED",
            "crawl_delay": wait_time,
        }
    
    # Check robots.txt
    checker = RobotsChecker()
    robots_allowed, robots_reason = await checker.can_fetch(url)
    
    if not robots_allowed:
        return {
            "allowed": False,
            "reason": robots_reason,
            "error_code": "LINK_CRAWL_BLOCKED",
            "crawl_delay": 0.0,
        }
    
    # Get crawl delay
    parsed = urlparse(url)
    crawl_delay = checker.get_crawl_delay(parsed.netloc.lower())
    
    return {
        "allowed": True,
        "reason": "All checks passed",
        "error_code": None,
        "crawl_delay": crawl_delay,
    }
