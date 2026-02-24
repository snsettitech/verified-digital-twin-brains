"""
Fetch Safety Module

Provides security controls for web fetching to prevent SSRF attacks,
enforce content policies, and ensure safe crawling.

Implements:
- SSRF protection (private IP blocking)
- Content-type allowlisting
- Size and timeout limits
- Redirect safety
- DNS rebinding protection
"""

import ipaddress
import re
import socket
from typing import Optional, List, Tuple, Set
from urllib.parse import urlparse
from enum import Enum

from modules.deep_research_config import FetchSafetyConfig, get_config


class SafetyCheckResult:
    """Result of a safety check."""
    
    def __init__(
        self,
        allowed: bool,
        reason: Optional[str] = None,
        category: Optional[str] = None,
        details: Optional[dict] = None
    ):
        self.allowed = allowed
        self.reason = reason or ""
        self.category = category or ""  # 'hard_block' or 'soft_fail'
        self.details = details or {}
    
    @classmethod
    def allowed(cls) -> "SafetyCheckResult":
        """Create an allowed result."""
        return cls(allowed=True, reason="OK", category="allowed")
    
    @classmethod
    def blocked(
        cls,
        reason: str,
        category: str = "hard_block",
        details: Optional[dict] = None
    ) -> "SafetyCheckResult":
        """Create a blocked result."""
        return cls(allowed=False, reason=reason, category=category, details=details)
    
    def __bool__(self) -> bool:
        """Allow using result in boolean context."""
        return self.allowed
    
    def __repr__(self) -> str:
        status = "ALLOWED" if self.allowed else f"BLOCKED({self.category})"
        return f"<SafetyCheckResult: {status} - {self.reason}>"


class FailureCategory(str, Enum):
    """Failure taxonomy categories."""
    HARD_BLOCK = "hard_block"
    SOFT_FAIL = "soft_fail"


class FailureType(str, Enum):
    """Detailed failure taxonomy."""
    # Hard blocks (never retry)
    SSRF_BLOCKED = "ssrf_blocked"
    PRIVATE_IP_BLOCKED = "private_ip_blocked"
    CONTENT_TYPE_BLOCKED = "content_type_blocked"
    SIZE_EXCEEDED = "size_exceeded"
    TOO_MANY_REDIRECTS = "too_many_redirects"
    INVALID_HOSTNAME = "invalid_hostname"
    SCHEME_BLOCKED = "scheme_blocked"
    
    # Soft fails (may retry)
    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    GATING = "gating"
    UNAVAILABLE = "unavailable"
    NETWORK = "network"
    TIMEOUT = "timeout"
    PARSER_FAIL = "parser_fail"


def is_private_ip(ip_str: str) -> bool:
    """
    Check if an IP address is in a private range.
    
    Args:
        ip_str: IP address string (IPv4 or IPv6)
    
    Returns:
        True if IP is private/reserved
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
    except ValueError:
        return False


def is_ip_in_networks(ip_str: str, networks: List[str]) -> bool:
    """
    Check if IP is in any of the specified networks.
    
    Args:
        ip_str: IP address string
        networks: List of CIDR network strings
    
    Returns:
        True if IP is in any network
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        for network_str in networks:
            try:
                network = ipaddress.ip_network(network_str, strict=False)
                if ip in network:
                    return True
            except ValueError:
                continue
        return False
    except ValueError:
        return False


def resolve_hostname(hostname: str) -> Optional[str]:
    """
    Resolve hostname to IP address.
    
    Args:
        hostname: Hostname to resolve
    
    Returns:
        IP address string or None if resolution fails
    """
    try:
        return socket.gethostbyname(hostname)
    except socket.gaierror:
        return None


def validate_scheme(scheme: str, blocked_schemes: Set[str]) -> SafetyCheckResult:
    """
    Validate URL scheme.
    
    Args:
        scheme: URL scheme
        blocked_schemes: Set of blocked schemes
    
    Returns:
        Safety check result
    """
    scheme_lower = scheme.lower()
    
    if scheme_lower in blocked_schemes:
        return SafetyCheckResult.blocked(
            reason=f"Scheme '{scheme}' is not allowed",
            category=FailureCategory.HARD_BLOCK,
            details={"scheme": scheme, "blocked_schemes": list(blocked_schemes)}
        )
    
    if scheme_lower not in ("http", "https"):
        return SafetyCheckResult.blocked(
            reason=f"Scheme '{scheme}' is not supported",
            category=FailureCategory.HARD_BLOCK,
            details={"scheme": scheme}
        )
    
    return SafetyCheckResult.allowed()


def validate_hostname(hostname: str, max_length: int = 253) -> SafetyCheckResult:
    """
    Validate hostname.
    
    Args:
        hostname: Hostname to validate
        max_length: Maximum allowed length
    
    Returns:
        Safety check result
    """
    if not hostname:
        return SafetyCheckResult.blocked(
            reason="Hostname is empty",
            category=FailureCategory.HARD_BLOCK
        )
    
    if len(hostname) > max_length:
        return SafetyCheckResult.blocked(
            reason=f"Hostname exceeds maximum length of {max_length}",
            category=FailureCategory.HARD_BLOCK,
            details={"hostname_length": len(hostname), "max_length": max_length}
        )
    
    # Check for valid hostname characters
    # Allow alphanumeric, hyphens, dots (for subdomains)
    if not re.match(r'^[a-zA-Z0-9][-a-zA-Z0-9.]*[a-zA-Z0-9]$', hostname):
        # Allow single alphanumeric (for localhost testing)
        if not re.match(r'^[a-zA-Z0-9]$', hostname):
            return SafetyCheckResult.blocked(
                reason="Hostname contains invalid characters",
                category=FailureCategory.HARD_BLOCK,
                details={"hostname": hostname}
            )
    
    return SafetyCheckResult.allowed()


def validate_ip_safety(
    ip_str: str,
    blocked_networks: List[str],
    config: FetchSafetyConfig
) -> SafetyCheckResult:
    """
    Validate IP address for SSRF protection.
    
    Args:
        ip_str: IP address string
        blocked_networks: List of blocked CIDR networks
        config: Safety configuration
    
    Returns:
        Safety check result
    """
    # Check if it's a valid IP
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return SafetyCheckResult.blocked(
            reason=f"Invalid IP address: {ip_str}",
            category=FailureCategory.HARD_BLOCK
        )
    
    # Check private IP ranges
    if is_private_ip(ip_str):
        return SafetyCheckResult.blocked(
            reason=f"IP {ip_str} is in a private/reserved range",
            category=FailureCategory.HARD_BLOCK,
            details={
                "ip": ip_str,
                "type": "private/reserved",
                "is_private": ip.is_private,
                "is_loopback": ip.is_loopback,
                "is_link_local": ip.is_link_local
            }
        )
    
    # Check explicitly blocked networks
    if is_ip_in_networks(ip_str, blocked_networks):
        return SafetyCheckResult.blocked(
            reason=f"IP {ip_str} is in a blocked network",
            category=FailureCategory.HARD_BLOCK,
            details={"ip": ip_str, "blocked_networks": blocked_networks}
        )
    
    return SafetyCheckResult.allowed()


def validate_url_safety(
    url: str,
    config: Optional[FetchSafetyConfig] = None,
    check_dns: bool = True
) -> SafetyCheckResult:
    """
    Validate URL safety for fetching.
    
    Performs SSRF protection checks:
    1. Scheme validation
    2. Hostname validation
    3. IP-based checks (literal IP or resolved hostname)
    
    Args:
        url: URL to validate
        config: Safety configuration (uses default if None)
        check_dns: Whether to resolve hostname for DNS rebinding protection
    
    Returns:
        Safety check result
    """
    config = config or get_config().safety
    
    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        return SafetyCheckResult.blocked(
            reason=f"Failed to parse URL: {e}",
            category=FailureCategory.HARD_BLOCK
        )
    
    # 1. Validate scheme
    blocked_schemes = set(config.blocked_schemes)
    scheme_result = validate_scheme(parsed.scheme, blocked_schemes)
    if not scheme_result:
        scheme_result.details["failure_type"] = FailureType.SCHEME_BLOCKED
        return scheme_result
    
    # 2. Validate hostname
    hostname = parsed.hostname
    if not hostname:
        return SafetyCheckResult.blocked(
            reason="URL has no hostname",
            category=FailureCategory.HARD_BLOCK,
            details={"failure_type": FailureType.INVALID_HOSTNAME}
        )
    
    hostname_result = validate_hostname(hostname, config.max_hostname_length)
    if not hostname_result:
        hostname_result.details["failure_type"] = FailureType.INVALID_HOSTNAME
        return hostname_result
    
    # 3. IP-based validation
    blocked_networks = config.blocked_private_ip_ranges
    
    # Check if hostname is already an IP address
    try:
        ip = ipaddress.ip_address(hostname)
        # It's a literal IP
        ip_result = validate_ip_safety(hostname, blocked_networks, config)
        if not ip_result:
            ip_result.details["failure_type"] = FailureType.PRIVATE_IP_BLOCKED
            return ip_result
    except ValueError:
        # It's a hostname, resolve it
        if check_dns:
            resolved_ip = resolve_hostname(hostname)
            if resolved_ip:
                ip_result = validate_ip_safety(resolved_ip, blocked_networks, config)
                if not ip_result:
                    ip_result.details["failure_type"] = FailureType.PRIVATE_IP_BLOCKED
                    ip_result.details["hostname"] = hostname
                    ip_result.details["resolved_ip"] = resolved_ip
                    return ip_result
    
    return SafetyCheckResult.allowed()


def validate_content_safety(
    content_type: str,
    content_length: int,
    config: Optional[FetchSafetyConfig] = None
) -> SafetyCheckResult:
    """
    Validate content headers for safety.
    
    Args:
        content_type: Content-Type header value
        content_length: Content-Length header value
        config: Safety configuration
    
    Returns:
        Safety check result
    """
    config = config or get_config().safety
    
    # Check content type
    if content_type:
        # Extract main type (ignore charset, etc.)
        main_type = content_type.split(";")[0].strip().lower()
        
        allowed_types = [t.lower() for t in config.allowed_content_types]
        
        # Check exact match or wildcard match (e.g., text/*)
        type_allowed = False
        for allowed in allowed_types:
            if allowed == main_type:
                type_allowed = True
                break
            if allowed.endswith("/*"):
                prefix = allowed[:-1]
                if main_type.startswith(prefix):
                    type_allowed = True
                    break
        
        if not type_allowed:
            return SafetyCheckResult.blocked(
                reason=f"Content type '{content_type}' is not allowed",
                category=FailureCategory.HARD_BLOCK,
                details={
                    "failure_type": FailureType.CONTENT_TYPE_BLOCKED,
                    "content_type": content_type,
                    "allowed_types": config.allowed_content_types
                }
            )
    
    # Check content length
    max_size_bytes = config.max_content_size_mb * 1024 * 1024
    if content_length > max_size_bytes:
        return SafetyCheckResult.blocked(
            reason=f"Content size {content_length} exceeds maximum of {max_size_bytes} bytes",
            category=FailureCategory.HARD_BLOCK,
            details={
                "failure_type": FailureType.SIZE_EXCEEDED,
                "content_length": content_length,
                "max_size_bytes": max_size_bytes,
                "max_size_mb": config.max_content_size_mb
            }
        )
    
    return SafetyCheckResult.allowed()


def validate_redirect_safety(
    redirect_url: str,
    redirect_count: int,
    config: Optional[FetchSafetyConfig] = None
) -> SafetyCheckResult:
    """
    Validate redirect for safety.
    
    Args:
        redirect_url: URL being redirected to
        redirect_count: Current redirect count
        config: Safety configuration
    
    Returns:
        Safety check result
    """
    config = config or get_config().safety
    
    # Check redirect limit
    if redirect_count >= config.max_redirects:
        return SafetyCheckResult.blocked(
            reason=f"Too many redirects ({redirect_count} >= {config.max_redirects})",
            category=FailureCategory.HARD_BLOCK,
            details={
                "failure_type": FailureType.TOO_MANY_REDIRECTS,
                "redirect_count": redirect_count,
                "max_redirects": config.max_redirects
            }
        )
    
    # Validate the redirect URL
    url_result = validate_url_safety(redirect_url, config, check_dns=config.dns_rebinding_protection)
    if not url_result:
        return url_result
    
    return SafetyCheckResult.allowed()


class FetchSafetyValidator:
    """Stateful fetch safety validator."""
    
    def __init__(self, config: Optional[FetchSafetyConfig] = None):
        self.config = config or get_config().safety
        self._dns_cache: dict = {}
    
    def validate_url(self, url: str) -> SafetyCheckResult:
        """Validate URL safety."""
        return validate_url_safety(url, self.config)
    
    def validate_content(self, content_type: str, content_length: int) -> SafetyCheckResult:
        """Validate content safety."""
        return validate_content_safety(content_type, content_length, self.config)
    
    def validate_redirect(self, redirect_url: str, redirect_count: int) -> SafetyCheckResult:
        """Validate redirect safety."""
        return validate_redirect_safety(redirect_url, redirect_count, self.config)
    
    def is_retryable(self, failure_type: FailureType) -> bool:
        """
        Determine if a failure type is retryable.
        
        Args:
            failure_type: Type of failure
        
        Returns:
            True if the failure is retryable
        """
        hard_block_types = {
            FailureType.SSRF_BLOCKED,
            FailureType.PRIVATE_IP_BLOCKED,
            FailureType.CONTENT_TYPE_BLOCKED,
            FailureType.SIZE_EXCEEDED,
            FailureType.TOO_MANY_REDIRECTS,
            FailureType.INVALID_HOSTNAME,
            FailureType.SCHEME_BLOCKED,
        }
        return failure_type not in hard_block_types
    
    def classify_failure(self, status_code: Optional[int], error: Optional[str]) -> Tuple[FailureType, str]:
        """
        Classify an HTTP error or exception into failure taxonomy.
        
        Args:
            status_code: HTTP status code (if available)
            error: Error message or exception string
        
        Returns:
            Tuple of (failure_type, description)
        """
        error_lower = (error or "").lower()
        
        # Status code based classification
        if status_code:
            if status_code == 401 or status_code == 403:
                return FailureType.AUTH, f"Authentication required ({status_code})"
            if status_code == 429:
                return FailureType.RATE_LIMIT, "Rate limit exceeded"
            if status_code >= 500:
                return FailureType.UNAVAILABLE, f"Server error ({status_code})"
        
        # Error message based classification
        if any(x in error_lower for x in ["timeout", "timed out"]):
            return FailureType.TIMEOUT, "Request timeout"
        if any(x in error_lower for x in ["connection", "network", "dns"]):
            return FailureType.NETWORK, "Network error"
        if any(x in error_lower for x in ["ssl", "certificate", "tls"]):
            return FailureType.NETWORK, "TLS/SSL error"
        if any(x in error_lower for x in ["cloudflare", "captcha", "bot"]):
            return FailureType.GATING, "Bot protection/gating"
        if any(x in error_lower for x in ["parse", "decode", "encoding"]):
            return FailureType.PARSER_FAIL, "Content parsing failed"
        
        return FailureType.NETWORK, error or "Unknown error"


# Convenience functions for common use cases
def is_safe_url(url: str) -> bool:
    """Quick check if URL is safe to fetch."""
    result = validate_url_safety(url)
    return bool(result)


def get_block_reason(url: str) -> Optional[str]:
    """Get reason why URL is blocked (or None if allowed)."""
    result = validate_url_safety(url)
    if result.allowed:
        return None
    return result.reason
