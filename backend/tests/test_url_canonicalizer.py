"""
Tests for URL Canonicalizer Module
"""

import pytest
from modules.url_canonicalizer import (
    canonicalize_url,
    get_url_hash,
    extract_domain,
    is_same_domain,
    normalize_for_comparison,
    URLCanonicalizationRules,
    URLCanonicalizer,
)


class TestCanonicalizeURL:
    """Test URL canonicalization."""
    
    def test_basic_url_unchanged(self):
        """Basic HTTPS URL should be normalized but structurally similar."""
        url = "https://example.com/page"
        result = canonicalize_url(url)
        assert result == "https://example.com/page"
    
    def test_lowercase_scheme_and_host(self):
        """Scheme and host should be lowercased."""
        url = "HTTPS://EXAMPLE.COM/Page"
        result = canonicalize_url(url)
        assert result.startswith("https://example.com/")
    
    def test_strip_utm_parameters(self):
        """Google Analytics UTM parameters should be stripped."""
        url = "https://example.com/page?utm_source=google&utm_medium=email"
        result = canonicalize_url(url)
        assert "utm_source" not in result
        assert "utm_medium" not in result
        assert result == "https://example.com/page"
    
    def test_strip_fbclid(self):
        """Facebook click ID should be stripped."""
        url = "https://example.com/page?fbclid=IwAR123abc"
        result = canonicalize_url(url)
        assert "fbclid" not in result
    
    def test_strip_multiple_tracking_params(self):
        """Multiple tracking parameters should be stripped."""
        url = "https://example.com/page?utm_source=google&fbclid=abc&real_param=value"
        result = canonicalize_url(url)
        assert "utm_source" not in result
        assert "fbclid" not in result
        assert "real_param=value" in result
    
    def test_sort_query_params(self):
        """Query parameters should be sorted alphabetically."""
        url = "https://example.com/page?z=last&a=first&m=middle"
        result = canonicalize_url(url)
        # After sorting: a, m, z
        assert result == "https://example.com/page?a=first&m=middle&z=last"
    
    def test_remove_trailing_slash(self):
        """Trailing slash should be removed (except for root)."""
        url = "https://example.com/page/"
        result = canonicalize_url(url)
        assert result == "https://example.com/page"
    
    def test_keep_root_slash(self):
        """Root slash should be kept."""
        url = "https://example.com/"
        result = canonicalize_url(url)
        assert result == "https://example.com/"
    
    def test_remove_fragment(self):
        """Fragment should be removed by default."""
        url = "https://example.com/page#section"
        result = canonicalize_url(url)
        assert "#section" not in result
        assert result == "https://example.com/page"
    
    def test_keep_fragment_when_configured(self):
        """Fragment should be kept when configured."""
        rules = URLCanonicalizationRules(remove_fragment=False)
        url = "https://example.com/page#section"
        result = canonicalize_url(url, rules)
        assert "#section" in result
    
    def test_strip_default_http_port(self):
        """Default HTTP port should be stripped."""
        url = "http://example.com:80/page"
        result = canonicalize_url(url)
        assert ":80" not in result
    
    def test_strip_default_https_port(self):
        """Default HTTPS port should be stripped."""
        url = "https://example.com:443/page"
        result = canonicalize_url(url)
        assert ":443" not in result
    
    def test_keep_non_default_port(self):
        """Non-default ports should be kept."""
        url = "https://example.com:8080/page"
        result = canonicalize_url(url)
        assert ":8080" in result
    
    def test_empty_url_raises_error(self):
        """Empty URL should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            canonicalize_url("")
    
    def test_invalid_url_raises_error(self):
        """Invalid URL should raise ValueError."""
        with pytest.raises(ValueError):
            canonicalize_url("not-a-url")
    
    def test_url_too_long_raises_error(self):
        """URL exceeding max length should raise ValueError."""
        rules = URLCanonicalizationRules(max_url_length=10)
        with pytest.raises(ValueError, match="exceeds maximum"):
            canonicalize_url("https://example.com/page", rules)
    
    def test_complex_url_all_transformations(self):
        """Complex URL with multiple transformations."""
        url = "HTTPS://EXAMPLE.COM:443/Page/?utm_source=google&b=2&a=1#section"
        result = canonicalize_url(url)
        # Should be: https://example.com/page?a=1&b=2
        assert result == "https://example.com/page?a=1&b=2"
    
    def test_url_with_encoded_characters(self):
        """URL with encoded characters should be handled."""
        url = "https://example.com/page?q=hello%20world"
        result = canonicalize_url(url)
        assert result == "https://example.com/page?q=hello+world"


class TestGetURLHash:
    """Test URL hashing."""
    
    def test_hash_deterministic(self):
        """Same URL should produce same hash."""
        url = "https://example.com/page"
        hash1 = get_url_hash(url)
        hash2 = get_url_hash(url)
        assert hash1 == hash2
    
    def test_different_urls_different_hashes(self):
        """Different URLs should produce different hashes."""
        hash1 = get_url_hash("https://example.com/page1")
        hash2 = get_url_hash("https://example.com/page2")
        assert hash1 != hash2
    
    def test_hash_length(self):
        """SHA-256 hash should be 64 characters."""
        url = "https://example.com/page"
        hash_val = get_url_hash(url)
        assert len(hash_val) == 64
    
    def test_hash_is_hex(self):
        """Hash should be hexadecimal."""
        url = "https://example.com/page"
        hash_val = get_url_hash(url)
        int(hash_val, 16)  # Should not raise


class TestExtractDomain:
    """Test domain extraction."""
    
    def test_extract_domain_simple(self):
        """Simple domain extraction."""
        url = "https://example.com/page"
        assert extract_domain(url) == "example.com"
    
    def test_extract_domain_with_www(self):
        """Domain with www prefix."""
        url = "https://www.example.com/page"
        assert extract_domain(url) == "www.example.com"
    
    def test_extract_domain_lowercase(self):
        """Domain should be lowercased."""
        url = "https://EXAMPLE.COM/page"
        assert extract_domain(url) == "example.com"
    
    def test_extract_domain_with_port(self):
        """Domain with port."""
        url = "https://example.com:8080/page"
        assert extract_domain(url) == "example.com:8080"


class TestIsSameDomain:
    """Test same domain check."""
    
    def test_same_domain_true(self):
        """Same domain should return True."""
        url1 = "https://example.com/page1"
        url2 = "https://example.com/page2"
        assert is_same_domain(url1, url2) is True
    
    def test_same_domain_different_paths(self):
        """Same domain, different paths should return True."""
        url1 = "https://example.com/a/b/c"
        url2 = "https://example.com/x/y/z"
        assert is_same_domain(url1, url2) is True
    
    def test_different_domains(self):
        """Different domains should return False."""
        url1 = "https://example.com/page"
        url2 = "https://other.com/page"
        assert is_same_domain(url1, url2) is False
    
    def test_case_insensitive(self):
        """Domain comparison should be case-insensitive."""
        url1 = "https://EXAMPLE.COM/page"
        url2 = "https://example.com/page"
        assert is_same_domain(url1, url2) is True


class TestNormalizeForComparison:
    """Test aggressive normalization for comparison."""
    
    def test_remove_www(self):
        """www prefix should be removed."""
        url = "https://www.example.com/page"
        result = normalize_for_comparison(url)
        assert "www." not in result
        assert "example.com" in result
    
    def test_remove_index_html(self):
        """index.html should be normalized to root."""
        url = "https://example.com/index.html"
        result = normalize_for_comparison(url)
        assert result.endswith("/")
        assert "index.html" not in result


class TestURLCanonicalizer:
    """Test the stateful URLCanonicalizer class."""
    
    def test_canonicalize_with_cache(self):
        """Canonicalizer should cache results."""
        canonicalizer = URLCanonicalizer()
        url = "https://example.com/page"
        
        result1 = canonicalizer.canonicalize(url)
        result2 = canonicalizer.canonicalize(url)
        
        assert result1 == result2
        assert url in canonicalizer._cache
    
    def test_get_hash(self):
        """get_hash should return hash of canonical URL."""
        canonicalizer = URLCanonicalizer()
        url = "https://example.com/page"
        
        hash_val = canonicalizer.get_hash(url)
        expected_hash = get_url_hash(canonicalize_url(url))
        
        assert hash_val == expected_hash
    
    def test_clear_cache(self):
        """clear_cache should empty the cache."""
        canonicalizer = URLCanonicalizer()
        url = "https://example.com/page"
        
        canonicalizer.canonicalize(url)
        assert len(canonicalizer._cache) > 0
        
        canonicalizer.clear_cache()
        assert len(canonicalizer._cache) == 0


class TestURLCanonicalizationRules:
    """Test URLCanonicalizationRules class."""
    
    def test_default_rules(self):
        """Default rules should be reasonable."""
        rules = URLCanonicalizationRules.default()
        assert rules.strip_tracking_params is True
        assert rules.sort_query_params is True
        assert rules.normalize_case is True
        assert rules.remove_trailing_slash is True
        assert rules.remove_fragment is True
    
    def test_from_dict(self):
        """Rules can be created from dictionary."""
        data = {
            "strip_tracking_params": False,
            "sort_query_params": False,
            "max_url_length": 1024,
        }
        rules = URLCanonicalizationRules.from_dict(data)
        assert rules.strip_tracking_params is False
        assert rules.sort_query_params is False
        assert rules.max_url_length == 1024
        # Defaults for unspecified fields
        assert rules.normalize_case is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
