"""
Graph Extraction Cache

Durable caching for claim extraction results.
Redis = hot cache (fast, TTL)
Supabase = durable cache (persistent, survives Redis restart)

Single-Profile Scope Migration:
- Cache key uses scope_id when single-profile is enabled
- scope_id format: "{tenant_id}__{creator_id}"
- Backward compatible: falls back to legacy format during rollout
"""

import time
import hashlib
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from modules.graph_memory_config import get_graph_memory_config, is_single_profile_enabled
from modules.observability import supabase

logger = logging.getLogger(__name__)


class GraphExtractionCache:
    """
    Two-tier caching for extraction results:
    1. Redis (hot) - fast access with TTL
    2. Supabase (durable) - survives Redis restarts
    """
    
    def __init__(self):
        self.config = get_graph_memory_config()
        self._single_profile_enabled = is_single_profile_enabled()
    
    def _get_redis_client(self):
        """Get Redis client from job_queue module."""
        try:
            from modules.job_queue import get_redis_client
            return get_redis_client()
        except Exception:
            return None
    
    def _make_cache_key(
        self,
        tenant_id: str,
        twin_id: str,
        source_ref: str,
        content: str,
        extractor_version: str,
        scope_id: Optional[str] = None
    ) -> str:
        """
        Generate cache key from content and metadata.
        
        Uses scope_id format when single-profile is enabled:
            "extract:{scope_id}:{source_ref}:{content_hash}:{extractor_version}"
        Falls back to legacy format for backward compatibility:
            "extract:{tenant_id}:{twin_id}:{source_ref}:{content_hash}:{extractor_version}"
        """
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:32]
        
        if self._single_profile_enabled and scope_id:
            # New single-profile format
            return f"extract:{scope_id}:{source_ref}:{content_hash}:{extractor_version}"
        else:
            # Legacy format for backward compatibility
            return f"extract:{tenant_id}:{twin_id}:{source_ref}:{content_hash}:{extractor_version}"
    
    def _make_lookup_key(
        self,
        tenant_id: str,
        twin_id: str,
        source_ref: str,
        content_hash: str,
        extractor_version: str,
        scope_id: Optional[str] = None
    ) -> str:
        """
        Generate cache key from pre-computed hash.
        
        Uses scope_id format when single-profile is enabled.
        """
        if self._single_profile_enabled and scope_id:
            # New single-profile format
            return f"extract:{scope_id}:{source_ref}:{content_hash}:{extractor_version}"
        else:
            # Legacy format for backward compatibility
            return f"extract:{tenant_id}:{twin_id}:{source_ref}:{content_hash}:{extractor_version}"
    
    async def get(
        self,
        tenant_id: str,
        twin_id: str,
        source_ref: str,
        content: str,
        extractor_version: Optional[str] = None,
        scope_id: Optional[str] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached extraction result.
        Try Redis first, then Supabase.
        
        Args:
            tenant_id: Tenant identifier
            twin_id: Twin identifier (legacy, used when scope_id not provided)
            source_ref: Source reference
            content: Content to look up
            extractor_version: Optional extractor version override
            scope_id: Optional scope_id for single-profile mode ("{tenant_id}__{creator_id}")
        """
        version = extractor_version or self.config.extractor_version
        cache_key = self._make_cache_key(
            tenant_id, twin_id, source_ref, content, version, scope_id
        )
        
        # Try Redis first (hot cache)
        client = self._get_redis_client()
        if client:
            try:
                cached = client.get(cache_key)
                if cached:
                    logger.debug(f"[ExtractionCache] Redis hit for {cache_key[:50]}...")
                    return json.loads(cached)
            except Exception as e:
                logger.warning(f"[ExtractionCache] Redis read failed: {e}")
        
        # Try Supabase (durable cache)
        try:
            content_hash = hashlib.sha256(content.encode()).hexdigest()[:32]
            
            if self._single_profile_enabled and scope_id:
                # Single-profile mode: use scope_id column (when available)
                # For now, fall back to tenant_id + twin_id query with scope check
                # This maintains compatibility during schema migration
                query = supabase.table("graph_extraction_cache").select("*").eq(
                    "tenant_id", tenant_id
                ).eq("twin_id", twin_id).eq(
                    "source_ref", source_ref
                ).eq("content_hash", content_hash).eq(
                    "extractor_version", version
                )
            else:
                # Legacy mode
                query = supabase.table("graph_extraction_cache").select("*").eq(
                    "tenant_id", tenant_id
                ).eq("twin_id", twin_id).eq(
                    "source_ref", source_ref
                ).eq("content_hash", content_hash).eq(
                    "extractor_version", version
                )
            
            result = query.single().execute()
            
            if result.data:
                logger.debug(f"[ExtractionCache] Supabase hit for {cache_key[:50]}...")
                claims = result.data.get("claims", [])
                
                # Backfill Redis for next time
                if client:
                    try:
                        client.setex(
                            cache_key,
                            self.config.extraction_cache_ttl,
                            json.dumps(claims)
                        )
                    except Exception as e:
                        logger.warning(f"[ExtractionCache] Redis backfill failed: {e}")
                
                return claims
                
        except Exception as e:
            logger.warning(f"[ExtractionCache] Supabase read failed: {e}")
        
        logger.debug(f"[ExtractionCache] Miss for {cache_key[:50]}...")
        return None
    
    async def set(
        self,
        tenant_id: str,
        twin_id: str,
        source_ref: str,
        content: str,
        claims: List[Dict[str, Any]],
        extractor_version: Optional[str] = None,
        scope_id: Optional[str] = None
    ):
        """
        Store extraction result in both caches.
        
        Args:
            tenant_id: Tenant identifier
            twin_id: Twin identifier (legacy)
            source_ref: Source reference
            content: Content that was processed
            claims: Extracted claims to cache
            extractor_version: Optional extractor version override
            scope_id: Optional scope_id for single-profile mode ("{tenant_id}__{creator_id}")
        """
        version = extractor_version or self.config.extractor_version
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:32]
        cache_key = self._make_cache_key(
            tenant_id, twin_id, source_ref, content, version, scope_id
        )
        
        # Store in Redis (hot cache)
        client = self._get_redis_client()
        if client:
            try:
                client.setex(
                    cache_key,
                    self.config.extraction_cache_ttl,
                    json.dumps(claims)
                )
                logger.debug(f"[ExtractionCache] Stored in Redis: {cache_key[:50]}...")
            except Exception as e:
                logger.warning(f"[ExtractionCache] Redis write failed: {e}")
        
        # Store in Supabase (durable cache)
        try:
            data = {
                "tenant_id": tenant_id,
                "twin_id": twin_id,
                "source_ref": source_ref,
                "content_hash": content_hash,
                "extractor_version": version,
                "claims": claims,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # Include scope_id in data when single-profile is enabled
            if self._single_profile_enabled and scope_id:
                data["scope_id"] = scope_id
            
            supabase.table("graph_extraction_cache").upsert(
                data,
                on_conflict="tenant_id,twin_id,source_ref,content_hash,extractor_version"
            ).execute()
            logger.debug(f"[ExtractionCache] Stored in Supabase: {cache_key[:50]}...")
        except Exception as e:
            logger.warning(f"[ExtractionCache] Supabase write failed: {e}")
    
    async def invalidate(
        self,
        tenant_id: str,
        twin_id: str,
        source_ref: Optional[str] = None,
        scope_id: Optional[str] = None
    ):
        """
        Invalidate cache entries.
        If source_ref is None, invalidates all for tenant-twin.
        
        Args:
            tenant_id: Tenant identifier
            twin_id: Twin identifier (legacy)
            source_ref: Optional specific source to invalidate
            scope_id: Optional scope_id for single-profile mode
        """
        # Invalidate in Redis
        client = self._get_redis_client()
        if client:
            try:
                if self._single_profile_enabled and scope_id:
                    # Single-profile pattern
                    pattern = f"extract:{scope_id}:{source_ref or '*'}*"
                else:
                    # Legacy pattern
                    pattern = f"extract:{tenant_id}:{twin_id}:{source_ref or '*'}*"
                
                keys = client.keys(pattern)
                if keys:
                    client.delete(*keys)
                    logger.info(f"[ExtractionCache] Invalidated {len(keys)} Redis keys")
            except Exception as e:
                logger.warning(f"[ExtractionCache] Redis invalidate failed: {e}")
        
        # Invalidate in Supabase
        try:
            query = supabase.table("graph_extraction_cache").delete().eq(
                "tenant_id", tenant_id
            ).eq("twin_id", twin_id)
            
            if source_ref:
                query = query.eq("source_ref", source_ref)
            
            result = query.execute()
            logger.info(f"[ExtractionCache] Invalidated Supabase entries for {tenant_id}:{twin_id}")
        except Exception as e:
            logger.warning(f"[ExtractionCache] Supabase invalidate failed: {e}")


# Global cache instance
_cache_instance: Optional[GraphExtractionCache] = None


def get_extraction_cache() -> GraphExtractionCache:
    """Get or create global cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = GraphExtractionCache()
    return _cache_instance


def reset_cache():
    """Reset cache (for testing)."""
    global _cache_instance
    _cache_instance = None
