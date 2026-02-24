"""
Tests for Fetch Safety Module
"""

import pytest
from modules.fetch_safety import (
    is_private_ip,
    is_ip_in_networks,
    validate_scheme,
    validate_hostname,
    validate_ip_safety,
    validate_url_safety,
    validate_content_safety,
    validate_redirect_safety,
    SafetyCheckResult,
    FailureType,
    FailureCategory,
    FetchSafetyValidator,
    is_safe_url,
    get_block_reason,
)
from modules.deep_research_config import FetchSafetyConfig


class TestIsPrivateIP:
    """Test private IP detection."""
    
    def test_private_class_a(self):
        """10.x.x.x should be private."""
        assert is_private_ip("10.0.0.1") is True
        assert is_private_ip("10.255.255.255") is True
    
    def test_private_class_b(self):
        """172.16-31.x.x should be private."""
        assert is_private_ip("172.16.0.1") is True
        assert is_private_ip("172.31.255.255") is True
        assert is_private_ip("172.15.0.1") is False  # Not in range
        assert is_private_ip("172.32.0.1") is False  # Not in range
    
    def test_private_class_c(self):
        """192.168.x.x should be private."""
        assert is_private_ip("192.168.0.1") is True
        assert is_private_ip("192.168.255.255") is True
    
    def test_loopback(self):
        """127.x.x.x should be private (loopback)."""
        assert is_private_ip("127.0.0.1") is True
        assert is_private_ip("127.255.255.255") is True
    
    def test_link_local(self):
        """169.254.x.x should be private (link-local)."""
        assert is_private_ip("169.254.0.1") is True
    
    def test_public_ip_not_private(self):
        """Public IPs should not be private."""
        assert is_private_ip("8.8.8.8") is False
        assert is_private_ip("1.1.1.1") is False
        assert is_private_ip("208.67.222.222") is False
    
    def test_invalid_ip(self):
        """Invalid IPs should return False."""
        assert is_private_ip("not-an-ip") is False
        assert is_private_ip("") is False


class TestIsIPInNetworks:
    """Test IP in network detection."""
    
    def test_ip_in_network(self):
        """IP in network should return True."""
        assert is_ip_in_networks("10.0.0.1", ["10.0.0.0/8"]) is True
        assert is_ip_in_networks("192.168.1.1", ["192.168.0.0/16"]) is True
    
    def test_ip_not_in_network(self):
        """IP not in network should return False."""
        assert is_ip_in_networks("8.8.8.8", ["10.0.0.0/8"]) is False
    
    def test_multiple_networks(self):
        """Should check all networks."""
        networks = ["10.0.0.0/8", "192.168.0.0/16"]
        assert is_ip_in_networks("10.0.0.1", networks) is True
        assert is_ip_in_networks("192.168.1.1", networks) is True
        assert is_ip_in_networks("8.8.8.8", networks) is False


class TestValidateScheme:
    """Test scheme validation."""
    
    def test_allowed_schemes(self):
        """HTTP and HTTPS should be allowed."""
        blocked = {"file", "ftp"}
        assert validate_scheme("http", blocked).allowed is True
        assert validate_scheme("https", blocked).allowed is True
        assert validate_scheme("HTTP", blocked).allowed is True  # Case insensitive
    
    def test_blocked_schemes(self):
        """Blocked schemes should not be allowed."""
        blocked = {"file", "ftp", "gopher"}
        result = validate_scheme("file", blocked)
        assert result.allowed is False
        assert result.category == FailureCategory.HARD_BLOCK
    
    def test_other_schemes_blocked(self):
        """Non-http/https schemes should be blocked."""
        blocked = set()
        result = validate_scheme("javascript", blocked)
        assert result.allowed is False
        result = validate_scheme("data", blocked)
        assert result.allowed is False


class TestValidateHostname:
    """Test hostname validation."""
    
    def test_valid_hostnames(self):
        """Valid hostnames should pass."""
        assert validate_hostname("example.com").allowed is True
        assert validate_hostname("sub.example.com").allowed is True
        assert validate_hostname("localhost").allowed is True
        assert validate_hostname("a").allowed is True  # Single char
    
    def test_empty_hostname(self):
        """Empty hostname should fail."""
        result = validate_hostname("")
        assert result.allowed is False
    
    def test_long_hostname(self):
        """Hostname exceeding max length should fail."""
        long_host = "a" * 300
        result = validate_hostname(long_host, max_length=253)
        assert result.allowed is False
    
    def test_custom_max_length(self):
        """Custom max length should be respected."""
        result = validate_hostname("example.com", max_length=5)
        assert result.allowed is False


class TestValidateIPSafety:
    """Test IP safety validation."""
    
    def test_private_ip_blocked(self):
        """Private IPs should be blocked."""
        config = FetchSafetyConfig()
        result = validate_ip_safety("10.0.0.1", config.blocked_private_ip_ranges, config)
        assert result.allowed is False
        assert result.category == FailureCategory.HARD_BLOCK
    
    def test_public_ip_allowed(self):
        """Public IPs should be allowed."""
        config = FetchSafetyConfig()
        result = validate_ip_safety("8.8.8.8", config.blocked_private_ip_ranges, config)
        assert result.allowed is True
    
    def test_blocked_network(self):
        """IPs in blocked networks should be blocked."""
        config = FetchSafetyConfig()
        blocked = ["1.2.3.0/24"]
        result = validate_ip_safety("1.2.3.4", blocked, config)
        assert result.allowed is False
    
    def test_invalid_ip(self):
        """Invalid IPs should be blocked."""
        config = FetchSafetyConfig()
        result = validate_ip_safety("not-an-ip", [], config)
        assert result.allowed is False


class TestValidateURLSafety:
    """Test URL safety validation."""
    
    def test_http_url_allowed(self):
        """Regular HTTP URL should be allowed."""
        result = validate_url_safety("http://example.com/page")
        assert result.allowed is True
    
    def test_https_url_allowed(self):
        """Regular HTTPS URL should be allowed."""
        result = validate_url_safety("https://example.com/page")
        assert result.allowed is True
    
    def test_private_ip_url_blocked(self):
        """URL with private IP should be blocked."""
        result = validate_url_safety("http://10.0.0.1/page")
        assert result.allowed is False
        assert result.category == FailureCategory.HARD_BLOCK
    
    def test_localhost_blocked(self):
        """localhost should be blocked."""
        result = validate_url_safety("http://localhost/page")
        assert result.allowed is False
    
    def test_127_0_0_1_blocked(self):
        """127.0.0.1 should be blocked."""
        result = validate_url_safety("http://127.0.0.1/page")
        assert result.allowed is False
    
    def test_file_scheme_blocked(self):
        """file:// should be blocked."""
        result = validate_url_safety("file:///etc/passwd")
        assert result.allowed is False
    
    def test_ftp_scheme_blocked(self):
        """ftp:// should be blocked."""
        result = validate_url_safety("ftp://ftp.example.com/file")
        assert result.allowed is False
    
    def test_invalid_url_blocked(self):
        """Invalid URL should be blocked."""
        result = validate_url_safety("not-a-valid-url")
        assert result.allowed is False
    
    def test_empty_url_blocked(self):
        """Empty URL should be blocked."""
        result = validate_url_safety("")
        assert result.allowed is False


class TestValidateContentSafety:
    """Test content safety validation."""
    
    def test_allowed_content_type(self):
        """Allowed content type should pass."""
        config = FetchSafetyConfig(allowed_content_types=["text/html", "text/plain"])
        result = validate_content_safety("text/html", 1000, config)
        assert result.allowed is True
    
    def test_blocked_content_type(self):
        """Blocked content type should fail."""
        config = FetchSafetyConfig(allowed_content_types=["text/html"])
        result = validate_content_safety("application/pdf", 1000, config)
        assert result.allowed is False
        assert result.details["failure_type"] == FailureType.CONTENT_TYPE_BLOCKED
    
    def test_content_type_with_charset(self):
        """Content type with charset should be handled."""
        config = FetchSafetyConfig(allowed_content_types=["text/html"])
        result = validate_content_safety("text/html; charset=utf-8", 1000, config)
        assert result.allowed is True
    
    def test_size_within_limit(self):
        """Content within size limit should pass."""
        config = FetchSafetyConfig(max_content_size_mb=10)
        result = validate_content_safety("text/html", 5 * 1024 * 1024, config)  # 5 MB
        assert result.allowed is True
    
    def test_size_exceeds_limit(self):
        """Content exceeding size limit should fail."""
        config = FetchSafetyConfig(max_content_size_mb=1)
        result = validate_content_safety("text/html", 2 * 1024 * 1024, config)  # 2 MB
        assert result.allowed is False
        assert result.details["failure_type"] == FailureType.SIZE_EXCEEDED


class TestValidateRedirectSafety:
    """Test redirect safety validation."""
    
    def test_redirect_within_limit(self):
        """Redirect within limit should be allowed."""
        config = FetchSafetyConfig(max_redirects=5)
        result = validate_redirect_safety("https://example.com", 2, config)
        assert result.allowed is True
    
    def test_too_many_redirects(self):
        """Too many redirects should fail."""
        config = FetchSafetyConfig(max_redirects=5)
        result = validate_redirect_safety("https://example.com", 5, config)
        assert result.allowed is False
        assert result.details["failure_type"] == FailureType.TOO_MANY_REDIRECTS
    
    def test_redirect_to_private_ip_blocked(self):
        """Redirect to private IP should be blocked."""
        config = FetchSafetyConfig()
        result = validate_redirect_safety("http://10.0.0.1/page", 1, config)
        assert result.allowed is False


class TestFetchSafetyValidator:
    """Test the FetchSafetyValidator class."""
    
    def test_validator_creation(self):
        """Validator should be creatable."""
        config = FetchSafetyConfig()
        validator = FetchSafetyValidator(config)
        assert validator.config == config
    
    def test_validate_url_method(self):
        """validate_url should work."""
        validator = FetchSafetyValidator()
        result = validator.validate_url("https://example.com")
        assert result.allowed is True
    
    def test_validate_content_method(self):
        """validate_content should work."""
        config = FetchSafetyConfig(allowed_content_types=["text/html"])
        validator = FetchSafetyValidator(config)
        result = validator.validate_content("text/html", 1000)
        assert result.allowed is True
    
    def test_is_retryable_hard_blocks(self):
        """Hard block failures should not be retryable."""
        validator = FetchSafetyValidator()
        assert validator.is_retryable(FailureType.SSRF_BLOCKED) is False
        assert validator.is_retryable(FailureType.PRIVATE_IP_BLOCKED) is False
        assert validator.is_retryable(FailureType.CONTENT_TYPE_BLOCKED) is False
        assert validator.is_retryable(FailureType.SIZE_EXCEEDED) is False
    
    def test_is_retryable_soft_fails(self):
        """Soft fail failures should be retryable."""
        validator = FetchSafetyValidator()
        assert validator.is_retryable(FailureType.NETWORK) is True
        assert validator.is_retryable(FailureType.TIMEOUT) is True
        assert validator.is_retryable(FailureType.RATE_LIMIT) is True
        assert validator.is_retryable(FailureType.UNAVAILABLE) is True
    
    def test_classify_failure_status_codes(self):
        """Failure classification from status codes."""
        validator = FetchSafetyValidator()
        
        ft, _ = validator.classify_failure(401, None)
        assert ft == FailureType.AUTH
        
        ft, _ = validator.classify_failure(429, None)
        assert ft == FailureType.RATE_LIMIT
        
        ft, _ = validator.classify_failure(503, None)
        assert ft == FailureType.UNAVAILABLE
    
    def test_classify_failure_errors(self):
        """Failure classification from error messages."""
        validator = FetchSafetyValidator()
        
        ft, _ = validator.classify_failure(None, "Connection timeout")
        assert ft == FailureType.TIMEOUT
        
        ft, _ = validator.classify_failure(None, "DNS resolution failed")
        assert ft == FailureType.NETWORK
        
        ft, _ = validator.classify_failure(None, "Cloudflare protection")
        assert ft == FailureType.GATING


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_is_safe_url_true(self):
        """is_safe_url should return True for safe URLs."""
        assert is_safe_url("https://example.com") is True
    
    def test_is_safe_url_false(self):
        """is_safe_url should return False for unsafe URLs."""
        assert is_safe_url("http://10.0.0.1") is False
    
    def test_get_block_reason_none(self):
        """get_block_reason should return None for safe URLs."""
        assert get_block_reason("https://example.com") is None
    
    def test_get_block_reason_string(self):
        """get_block_reason should return reason for unsafe URLs."""
        reason = get_block_reason("http://10.0.0.1")
        assert reason is not None
        assert "private" in reason.lower()


class TestSafetyCheckResult:
    """Test SafetyCheckResult class."""
    
    def test_allowed_result(self):
        """Allowed result should be truthy."""
        result = SafetyCheckResult.allowed()
        assert result.allowed is True
        assert bool(result) is True
    
    def test_blocked_result(self):
        """Blocked result should be falsy."""
        result = SafetyCheckResult.blocked("Test reason")
        assert result.allowed is False
        assert bool(result) is False
    
    def test_blocked_with_category(self):
        """Blocked result should have category."""
        result = SafetyCheckResult.blocked("Test", category="hard_block")
        assert result.category == "hard_block"
    
    def test_blocked_with_details(self):
        """Blocked result should have details."""
        result = SafetyCheckResult.blocked("Test", details={"key": "value"})
        assert result.details["key"] == "value"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
