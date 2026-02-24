"""
Content Hasher Module

Computes deterministic hashes for content deduplication and versioning.
"""

import hashlib
import re
import unicodedata
from typing import Optional


def normalize_unicode(text: str) -> str:
    """
    Normalize Unicode to NFKC form for consistent hashing.
    
    NFKC (Normalization Form KC) provides:
    - Canonical decomposition
    - Compatibility composition
    
    This ensures that different Unicode representations of the same
    character are normalized to a single form.
    
    Args:
        text: Input text
    
    Returns:
        Unicode normalized text
    """
    return unicodedata.normalize("NFKC", text)


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace in text.
    
    - Collapse multiple whitespace characters to single space
    - Strip leading/trailing whitespace
    - Normalize line endings to \n
    
    Args:
        text: Input text
    
    Returns:
        Whitespace-normalized text
    """
    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    
    # Collapse whitespace (including newlines) to single space
    text = re.sub(r'\s+', ' ', text)
    
    # Strip leading/trailing
    return text.strip()


def strip_non_significant_formatting(text: str) -> str:
    """
    Strip non-significant formatting that shouldn't affect content hash.
    
    - Zero-width spaces and joiners
    - Byte order marks
    - Soft hyphens
    
    Args:
        text: Input text
    
    Returns:
        Text with non-significant formatting removed
    """
    # Characters to remove
    # \u200B: Zero-width space
    # \u200C: Zero-width non-joiner
    # \u200D: Zero-width joiner
    # \uFEFF: Byte order mark
    # \u00AD: Soft hyphen
    # \u2060: Word joiner
    chars_to_remove = '\u200B\u200C\u200D\uFEFF\u00AD\u2060'
    
    for char in chars_to_remove:
        text = text.replace(char, '')
    
    return text


def normalize_for_hashing(text: str) -> str:
    """
    Full normalization pipeline for content hashing.
    
    Steps:
    1. Unicode normalization (NFKC)
    2. Strip non-significant formatting
    3. Whitespace normalization
    
    Args:
        text: Input text
    
    Returns:
        Normalized text ready for hashing
    """
    text = normalize_unicode(text)
    text = strip_non_significant_formatting(text)
    text = normalize_whitespace(text)
    return text


def compute_content_hash(text: str, algorithm: str = "sha256") -> str:
    """
    Compute deterministic hash of normalized content.
    
    Args:
        text: Content to hash
        algorithm: Hash algorithm (sha256, sha512, md5)
    
    Returns:
        Hexadecimal hash string
    
    Raises:
        ValueError: If unsupported algorithm specified
    """
    # Normalize text
    normalized = normalize_for_hashing(text)
    
    # Encode to bytes
    data = normalized.encode("utf-8")
    
    # Compute hash
    if algorithm == "sha256":
        return hashlib.sha256(data).hexdigest()
    elif algorithm == "sha512":
        return hashlib.sha512(data).hexdigest()
    elif algorithm == "md5":
        return hashlib.md5(data).hexdigest()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")


def compute_fast_hash(text: str) -> str:
    """
    Compute fast (MD5) hash for non-cryptographic use.
    
    Use this for quick comparison when collision resistance
    is not critical (e.g., cache keys).
    
    Args:
        text: Content to hash
    
    Returns:
        MD5 hash hex string (32 characters)
    """
    return compute_content_hash(text, algorithm="md5")


def compute_secure_hash(text: str) -> str:
    """
    Compute secure (SHA-256) hash for content versioning.
    
    Use this for content deduplication and versioning where
    collision resistance is important.
    
    Args:
        text: Content to hash
    
    Returns:
        SHA-256 hash hex string (64 characters)
    """
    return compute_content_hash(text, algorithm="sha256")


class ContentHasher:
    """Stateful content hasher with caching."""
    
    def __init__(self, algorithm: str = "sha256"):
        self.algorithm = algorithm
        self._cache: dict = {}
    
    def hash(self, text: str) -> str:
        """
        Compute hash with caching.
        
        Args:
            text: Content to hash
        
        Returns:
            Hash hex string
        """
        # Use fast cache key (content length + first/last 100 chars)
        cache_key = f"{len(text)}:{text[:100]}:{text[-100:]}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        result = compute_content_hash(text, self.algorithm)
        self._cache[cache_key] = result
        return result
    
    def clear_cache(self) -> None:
        """Clear the hash cache."""
        self._cache.clear()
    
    def are_equal(self, text1: str, text2: str) -> bool:
        """
        Check if two texts have the same hash.
        
        Args:
            text1: First text
            text2: Second text
        
        Returns:
            True if hashes match
        """
        return self.hash(text1) == self.hash(text2)


def compute_chunk_fingerprint(
    text: str,
    source_url: Optional[str] = None,
    chunk_index: Optional[int] = None
) -> str:
    """
    Compute a fingerprint for a chunk that includes metadata.
    
    This creates a hash that changes if either the content or
    key metadata changes.
    
    Args:
        text: Chunk text content
        source_url: Source URL (optional)
        chunk_index: Chunk index (optional)
    
    Returns:
        Fingerprint hash
    """
    components = [text]
    
    if source_url:
        components.append(source_url)
    if chunk_index is not None:
        components.append(str(chunk_index))
    
    combined = "|".join(components)
    return compute_secure_hash(combined)
