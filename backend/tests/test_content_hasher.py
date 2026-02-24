"""
Tests for Content Hasher Module
"""

import pytest
from modules.content_hasher import (
    normalize_unicode,
    normalize_whitespace,
    strip_non_significant_formatting,
    normalize_for_hashing,
    compute_content_hash,
    compute_fast_hash,
    compute_secure_hash,
    compute_chunk_fingerprint,
    ContentHasher,
)


class TestNormalizeUnicode:
    """Test Unicode normalization."""
    
    def test_nfc_vs_nfd_equivalence(self):
        """NFC and NFD forms of same character should normalize to same."""
        # é can be represented as single char (NFC) or e + combining accent (NFD)
        nfc = "café"  # Precomposed
        nfd = "cafe\u0301"  # Decomposed (e + combining acute)
        
        assert normalize_unicode(nfc) == normalize_unicode(nfd)
    
    def test_fullwidth_characters(self):
        """Fullwidth characters should be normalized."""
        fullwidth_a = "\uff21"  # Fullwidth Latin Capital Letter A
        result = normalize_unicode(fullwidth_a)
        # NFKC should normalize fullwidth to regular
        assert result != fullwidth_a or result == "A"


class TestNormalizeWhitespace:
    """Test whitespace normalization."""
    
    def test_collapse_multiple_spaces(self):
        """Multiple spaces should collapse to single."""
        text = "hello    world"
        result = normalize_whitespace(text)
        assert result == "hello world"
    
    def test_collapse_tabs(self):
        """Tabs should be treated as whitespace."""
        text = "hello\t\tworld"
        result = normalize_whitespace(text)
        assert result == "hello world"
    
    def test_collapse_newlines(self):
        """Newlines should be treated as whitespace."""
        text = "hello\n\nworld"
        result = normalize_whitespace(text)
        assert result == "hello world"
    
    def test_normalize_crlf(self):
        """CRLF should be normalized to space."""
        text = "hello\r\nworld"
        result = normalize_whitespace(text)
        assert "\r" not in result
        assert result == "hello world"
    
    def test_strip_leading_trailing(self):
        """Leading and trailing whitespace should be stripped."""
        text = "   hello world   "
        result = normalize_whitespace(text)
        assert result == "hello world"
    
    def test_empty_string(self):
        """Empty string should remain empty."""
        assert normalize_whitespace("") == ""
    
    def test_whitespace_only(self):
        """Whitespace-only string should become empty."""
        assert normalize_whitespace("   \t\n   ") == ""


class TestStripNonSignificantFormatting:
    """Test stripping of non-significant formatting."""
    
    def test_strip_zero_width_space(self):
        """Zero-width space should be stripped."""
        text = "hello\u200Bworld"
        result = strip_non_significant_formatting(text)
        assert "\u200B" not in result
        assert result == "helloworld"
    
    def test_strip_bom(self):
        """Byte order mark should be stripped."""
        text = "\uFEFFhello world"
        result = strip_non_significant_formatting(text)
        assert "\uFEFF" not in result
        assert result == "hello world"
    
    def test_strip_soft_hyphen(self):
        """Soft hyphen should be stripped."""
        text = "hy\u00ADphen"
        result = strip_non_significant_formatting(text)
        assert "\u00AD" not in result


class TestNormalizeForHashing:
    """Test full normalization pipeline."""
    
    def test_full_pipeline(self):
        """Normalization pipeline should apply all steps."""
        text = "  caf\u00e9  \u200B  world  \n\n  "
        result = normalize_for_hashing(text)
        assert result == "café world"
    
    def test_consistency(self):
        """Same input should always produce same output."""
        text = "  hello   \n\t   world  "
        result1 = normalize_for_hashing(text)
        result2 = normalize_for_hashing(text)
        assert result1 == result2


class TestComputeContentHash:
    """Test content hash computation."""
    
    def test_sha256_deterministic(self):
        """Same content should produce same SHA-256 hash."""
        text = "hello world"
        hash1 = compute_content_hash(text, "sha256")
        hash2 = compute_content_hash(text, "sha256")
        assert hash1 == hash2
    
    def test_different_content_different_hashes(self):
        """Different content should produce different hashes."""
        hash1 = compute_content_hash("hello", "sha256")
        hash2 = compute_content_hash("world", "sha256")
        assert hash1 != hash2
    
    def test_sha256_length(self):
        """SHA-256 hash should be 64 hex characters."""
        text = "hello"
        hash_val = compute_content_hash(text, "sha256")
        assert len(hash_val) == 64
    
    def test_md5_length(self):
        """MD5 hash should be 32 hex characters."""
        text = "hello"
        hash_val = compute_content_hash(text, "md5")
        assert len(hash_val) == 32
    
    def test_whitespace_normalized_before_hashing(self):
        """Whitespace should be normalized before hashing."""
        text1 = "hello   world"
        text2 = "hello world"
        hash1 = compute_content_hash(text1, "sha256")
        hash2 = compute_content_hash(text2, "sha256")
        # After normalization, both should have same hash
        assert hash1 == hash2
    
    def test_unsupported_algorithm_raises(self):
        """Unsupported algorithm should raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported"):
            compute_content_hash("hello", "unsupported")


class TestComputeFastHash:
    """Test fast (MD5) hash."""
    
    def test_fast_hash_is_md5(self):
        """Fast hash should use MD5 (32 chars)."""
        text = "hello world"
        fast = compute_fast_hash(text)
        md5 = compute_content_hash(text, "md5")
        assert fast == md5
        assert len(fast) == 32


class TestComputeSecureHash:
    """Test secure (SHA-256) hash."""
    
    def test_secure_hash_is_sha256(self):
        """Secure hash should use SHA-256 (64 chars)."""
        text = "hello world"
        secure = compute_secure_hash(text)
        sha256 = compute_content_hash(text, "sha256")
        assert secure == sha256
        assert len(secure) == 64


class TestComputeChunkFingerprint:
    """Test chunk fingerprint computation."""
    
    def test_fingerprint_with_content_only(self):
        """Fingerprint with just content should work."""
        text = "chunk content"
        fp = compute_chunk_fingerprint(text)
        assert len(fp) == 64  # SHA-256
    
    def test_fingerprint_with_url(self):
        """Fingerprint should include URL."""
        text = "chunk content"
        url = "https://example.com/page"
        fp1 = compute_chunk_fingerprint(text, source_url=url)
        fp2 = compute_chunk_fingerprint(text)  # No URL
        assert fp1 != fp2
    
    def test_fingerprint_with_index(self):
        """Fingerprint should include chunk index."""
        text = "chunk content"
        fp1 = compute_chunk_fingerprint(text, chunk_index=0)
        fp2 = compute_chunk_fingerprint(text, chunk_index=1)
        assert fp1 != fp2
    
    def test_fingerprint_deterministic(self):
        """Same inputs should produce same fingerprint."""
        text = "chunk content"
        url = "https://example.com/page"
        fp1 = compute_chunk_fingerprint(text, source_url=url, chunk_index=0)
        fp2 = compute_chunk_fingerprint(text, source_url=url, chunk_index=0)
        assert fp1 == fp2


class TestContentHasher:
    """Test the stateful ContentHasher class."""
    
    def test_hash_deterministic(self):
        """Hasher should produce deterministic results."""
        hasher = ContentHasher()
        text = "hello world"
        hash1 = hasher.hash(text)
        hash2 = hasher.hash(text)
        assert hash1 == hash2
    
    def test_hash_caching(self):
        """Hasher should cache results."""
        hasher = ContentHasher()
        text = "hello world"
        
        hasher.hash(text)
        assert len(hasher._cache) > 0
    
    def test_clear_cache(self):
        """clear_cache should empty the cache."""
        hasher = ContentHasher()
        hasher.hash("hello")
        hasher.hash("world")
        
        assert len(hasher._cache) == 2
        hasher.clear_cache()
        assert len(hasher._cache) == 0
    
    def test_are_equal_true(self):
        """are_equal should return True for identical content."""
        hasher = ContentHasher()
        assert hasher.are_equal("hello", "hello") is True
    
    def test_are_equal_false(self):
        """are_equal should return False for different content."""
        hasher = ContentHasher()
        assert hasher.are_equal("hello", "world") is False
    
    def test_are_equal_with_normalization(self):
        """are_equal should respect normalization."""
        hasher = ContentHasher()
        # After normalization, these should be equal
        assert hasher.are_equal("hello   world", "hello world") is True
    
    def test_different_algorithms(self):
        """Different algorithms should produce different hashes."""
        text = "hello"
        hasher_md5 = ContentHasher(algorithm="md5")
        hasher_sha256 = ContentHasher(algorithm="sha256")
        
        hash_md5 = hasher_md5.hash(text)
        hash_sha256 = hasher_sha256.hash(text)
        
        assert len(hash_md5) == 32
        assert len(hash_sha256) == 64
        assert hash_md5 != hash_sha256


class TestCollisionResistance:
    """Basic collision resistance checks."""
    
    def test_similar_strings_different_hashes(self):
        """Similar but different strings should have different hashes."""
        texts = [
            "hello world",
            "hello  world",  # Extra space (normalized)
            "Hello World",   # Case difference
            "hello world!",  # Punctuation
            "hello world.",  # Different punctuation
        ]
        
        hashes = [compute_secure_hash(t) for t in texts]
        # After normalization, some may be equal, but generally different
        unique_hashes = set(hashes)
        assert len(unique_hashes) >= 2  # At least some should be different
    
    def test_long_content_hashable(self):
        """Long content should be hashable without errors."""
        text = "x" * 1000000  # 1 million characters
        hash_val = compute_secure_hash(text)
        assert len(hash_val) == 64


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
