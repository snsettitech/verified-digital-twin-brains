"""
Graph Memory Core

Production-ready Graphiti client with:
- scope_id isolation (single-profile boundary: {tenant_id}__{creator_id})
- Constraint detection at startup
- Timeout handling
- Circuit breaker integration
- Fallback to Supabase + Pinecone
"""

import asyncio
import os
import time
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from concurrent.futures import ProcessPoolExecutor


from modules.graph_memory_config import (
    get_graph_memory_config, 
    GraphMemoryConfig,
    is_single_profile_enabled
)
from modules.graph_circuit_breaker import get_circuit_breaker
from modules.graph_outbox import get_graph_outbox, GraphOperationType

# Import Neo4j at module level to avoid import overhead on each search
try:
    from neo4j import AsyncGraphDatabase
    from neo4j.exceptions import ServiceUnavailable
    _NEO4J_AVAILABLE = True
except ImportError:
    _NEO4J_AVAILABLE = False
    AsyncGraphDatabase = None
    ServiceUnavailable = Exception

# Persistent driver pool (shared across instances)
_driver_pool: Dict[str, Any] = {}


def _get_pooled_driver(uri: str, user: str, password: str) -> Optional[Any]:
    """Get or create persistent Neo4j driver."""
    global _driver_pool
    key = f"{uri}@{user}"
    
    if key not in _driver_pool or _driver_pool[key] is None:
        if not _NEO4J_AVAILABLE:
            return None
        try:
            _driver_pool[key] = AsyncGraphDatabase.driver(
                uri,
                auth=(user or "neo4j", password)
            )
        except Exception:
            return None
    
    return _driver_pool[key]


async def _close_all_drivers():
    """Close all pooled drivers (for shutdown)."""
    global _driver_pool
    for key, driver in list(_driver_pool.items()):
        if driver:
            try:
                await driver.close()
            except Exception:
                pass
        _driver_pool[key] = None
    _driver_pool.clear()

logger = logging.getLogger(__name__)

# Global process pool for Graphiti operations (created lazily)
_process_pool: Optional[ProcessPoolExecutor] = None

def _get_process_pool() -> ProcessPoolExecutor:
    """Get or create global process pool for isolated Graphiti operations."""
    global _process_pool
    if _process_pool is None:
        _process_pool = ProcessPoolExecutor(max_workers=2)
    return _process_pool


# Module-level function for process pool execution (must be picklable)
def _search_in_process(query: str, num_results: int, group_id: str, neo4j_uri: str, neo4j_user: str, neo4j_password: str, openai_key: str):
    """
    Execute Graphiti search in separate process.
    This allows true timeout enforcement via process termination.
    """
    import os
    os.environ["OPENAI_API_KEY"] = openai_key
    
    from graphiti_core import Graphiti
    from graphiti_core.llm_client.openai_client import OpenAIClient
    from graphiti_core.llm_client.client import LLMConfig
    import asyncio as aio
    
    if not neo4j_uri or not neo4j_password:
        return []
    
    # Create fresh Graphiti instance in this process
    llm_config = LLMConfig(
        api_key=openai_key,
        model="gpt-4o-mini",
        temperature=0.1,
        max_tokens=2000
    )
    llm_client = OpenAIClient(config=llm_config)
    
    loop = aio.new_event_loop()
    try:
        graphiti = Graphiti(
            uri=neo4j_uri,
            user=neo4j_user or "neo4j",
            password=neo4j_password,
            llm_client=llm_client
        )
        
        results = loop.run_until_complete(graphiti.search(
            query=query, 
            num_results=num_results,
            group_ids=[group_id]
        ))
        return results or []
    except Exception as e:
        # Don't log here - just return empty on any error
        return []
    finally:
        loop.close()


@dataclass
class ConstraintCapabilities:
    """Detected Neo4j constraint capabilities."""
    supports_unique_constraints: bool = False
    supports_node_key_constraints: bool = False
    supports_exists_constraints: bool = False
    active_strategy: str = "none"
    detected_at: float = 0.0


class GraphMemoryUnavailable(Exception):
    """Raised when graph memory is unavailable (circuit open, timeout, etc)."""
    pass


class GraphMemoryCore:
    """
    Core Graphiti client with production safety features.
    
    Single-Profile Scope Migration:
    - scope_id: "{tenant_id}__{creator_id}" (single-profile boundary)
    - group_id: Same as scope_id for Graphiti compatibility
    - All isolation uses scope_id for deduplication and queries
    """
    
    _constraint_cache: Optional[ConstraintCapabilities] = None
    _graphiti_available: Optional[bool] = None
    
    def __init__(
        self,
        tenant_id: str,
        twin_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        creator_id: Optional[str] = None,
        scope_id: Optional[str] = None
    ):
        """
        Initialize GraphMemoryCore with scope isolation.
        
        Single-Profile Mode (recommended):
            GraphMemoryCore(tenant_id, creator_id="user_123")
            or: GraphMemoryCore(tenant_id, scope_id="tenant_abc__user_123")
        
        Legacy Mode (backward compatibility):
            GraphMemoryCore(tenant_id, twin_id="twin_456")
        
        Args:
            tenant_id: The tenant identifier (required)
            twin_id: Legacy twin identifier (optional, for backward compat)
            correlation_id: Tracing correlation ID (optional)
            creator_id: Creator identifier for single-profile scope (optional)
            scope_id: Pre-computed scope identifier (optional, takes precedence)
        """
        self.tenant_id = tenant_id
        self.twin_id = twin_id  # Kept for backward compatibility
        self.correlation_id = correlation_id or "no-correlation"
        self.config = get_graph_memory_config()
        
        # Determine scope_id (single-profile boundary)
        if scope_id:
            # Explicit scope_id provided (highest priority)
            self.scope_id = scope_id
            self.group_id = scope_id  # Graphiti uses group_id
        elif creator_id:
            # Single-profile mode with creator_id
            self.scope_id = self.config.make_scope_id(tenant_id, creator_id)
            self.group_id = self.scope_id
            self.creator_id = creator_id
        elif twin_id:
            # Backward-compatible fallback: if creator_id is unavailable,
            # still scope by twin_id (never collapse to tenant__default).
            self.scope_id = self.config.make_group_id(tenant_id, twin_id)
            self.group_id = self.scope_id
            self.creator_id = None
        else:
            # Fallback: use tenant_id alone (degraded but safe)
            self.scope_id = f"{tenant_id}__default"
            self.group_id = self.scope_id
            self.creator_id = None
            logger.warning(
                f"[GraphMemoryCore] No scope identifier provided, using fallback: {self.scope_id}"
            )
        
        # Circuit breaker uses scope_id for isolation
        self.circuit_breaker = get_circuit_breaker(self.scope_id)
        self.outbox = get_graph_outbox()
        self._graphiti: Optional[Any] = None
    
    @classmethod
    def detect_constraints(cls, neo4j_driver) -> ConstraintCapabilities:
        """
        Detect Neo4j constraint capabilities at startup.
        Cached for performance.
        """
        if cls._constraint_cache is not None:
            return cls._constraint_cache
        
        capabilities = ConstraintCapabilities(detected_at=time.time())
        
        try:
            # Check Neo4j version and edition
            with neo4j_driver.session() as session:
                result = session.run("CALL dbms.components() YIELD name, versions, edition RETURN edition")
                record = result.single()
                edition = record["edition"] if record else "community"
                
                # Check existing constraints
                result = session.run("SHOW CONSTRAINTS")
                constraints = list(result)
                
                capabilities.supports_unique_constraints = True  # Basic unique constraints
                
                # Node key constraints require enterprise
                if edition.lower() == "enterprise":
                    capabilities.supports_node_key_constraints = True
                
                # Determine active strategy
                if capabilities.supports_node_key_constraints:
                    capabilities.active_strategy = "node_key"
                elif capabilities.supports_unique_constraints:
                    capabilities.active_strategy = "unique"
                else:
                    capabilities.active_strategy = "index_only"
                
                logger.info(
                    f"[GraphMemoryCore] Neo4j constraint detection: "
                    f"edition={edition}, strategy={capabilities.active_strategy}, "
                    f"existing_constraints={len(constraints)}"
                )
        except Exception as e:
            logger.warning(f"[GraphMemoryCore] Constraint detection failed: {e}")
            capabilities.active_strategy = "unknown"
        
        cls._constraint_cache = capabilities
        return capabilities
    
    @classmethod
    def check_graphiti_available(cls) -> bool:
        """Check if Graphiti is available (cached)."""
        if cls._graphiti_available is not None:
            return cls._graphiti_available
        
        try:
            from graphiti_core import Graphiti
            cls._graphiti_available = True
            return True
        except ImportError:
            logger.warning("[GraphMemoryCore] Graphiti not available")
            cls._graphiti_available = False
            return False
    
    def _get_graphiti(self) -> Optional[Any]:
        """Lazy initialize Graphiti client with LLM configuration."""
        if self._graphiti is not None:
            return self._graphiti
        
        if not self.config.enabled:
            return None
        
        if not self.check_graphiti_available():
            return None
        
        if not self.config.neo4j_uri or not self.config.neo4j_password:
            logger.warning("[GraphMemoryCore] Neo4j credentials not configured")
            return None
        
        try:
            from graphiti_core import Graphiti
            from graphiti_core.llm_client.openai_client import OpenAIClient
            from graphiti_core.llm_client.client import LLMConfig
            
            # Configure LLM with GPT-4o-mini for fast extraction
            llm_config = LLMConfig(
                api_key=os.getenv("OPENAI_API_KEY"),
                model="gpt-4o-mini",  # Fast and cost-effective
                temperature=0.1,  # Low temperature for consistent extraction
                max_tokens=2000
            )
            llm_client = OpenAIClient(config=llm_config)
            
            self._graphiti = Graphiti(
                uri=self.config.neo4j_uri,
                user=self.config.neo4j_user or "neo4j",
                password=self.config.neo4j_password,
                llm_client=llm_client  # Required for entity extraction
            )
            
            logger.info(f"[GraphMemoryCore] Graphiti initialized with GPT-4o-mini for {self.scope_id}")
            return self._graphiti
            
        except Exception as e:
            logger.error(f"[GraphMemoryCore] Failed to initialize Graphiti: {e}")
            return None
    
    async def _execute_with_timeout(
        self, 
        operation_name: str, 
        coro_or_func, 
        timeout_ms: Optional[int] = None,
        use_executor: bool = False
    ):
        """
        Execute with timeout enforcement.
        
        Args:
            operation_name: Name for logging
            coro_or_func: Coroutine or callable to execute
            timeout_ms: Timeout in milliseconds
            use_executor: If True, runs in thread pool (for blocking ops)
        """
        timeout = (timeout_ms or self.config.read_timeout_ms) / 1000.0
        
        try:
            if use_executor:
                # Run blocking function in thread pool
                loop = asyncio.get_event_loop()
                return await asyncio.wait_for(
                    loop.run_in_executor(None, coro_or_func),
                    timeout=timeout
                )
            else:
                # Direct coroutine execution
                return await asyncio.wait_for(coro_or_func, timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(
                f"[GraphMemoryCore] Timeout after {timeout}s for {operation_name} "
                f"corr={self.correlation_id}"
            )
            raise GraphMemoryUnavailable(f"Timeout: {operation_name}")
    
    async def create_episode(
        self,
        name: str,
        body: str,
        source_type: str,
        source_ref: str,
        timestamp: Optional[str] = None,
        async_write: bool = True
    ) -> Optional[str]:
        """
        Create episode in graph.
        
        Args:
            name: Episode name
            body: Episode content
            source_type: Type of source (escalation, interview, etc)
            source_ref: Reference ID
            timestamp: Optional timestamp
            async_write: If True, uses outbox; if False, synchronous
        
        Returns:
            Episode ID or None if disabled/failed
        """
        if not self.config.is_write_allowed():
            logger.debug("[GraphMemoryCore] Write disabled, skipping episode creation")
            return None
        
        # Check circuit breaker
        if self.circuit_breaker.is_open():
            logger.warning(f"[GraphMemoryCore] Circuit open for {self.scope_id}")
            # Still submit to outbox for retry
            async_write = True
        
        # Generate idempotency key with scope_id for proper isolation
        idempotency_key = self.config.make_idempotency_key(
            tenant_id=self.tenant_id,
            twin_id=self.twin_id or "default",
            source_type=source_type,
            source_ref=source_ref,
            content=body,
            scope_id=self.scope_id  # Critical: ensures scope-isolated deduplication
        )
        
        if async_write:
            # Submit to outbox with scope_id
            job_id = self.outbox.submit(
                tenant_id=self.tenant_id,
                twin_id=self.twin_id or "default",
                scope_id=self.scope_id,
                creator_id=getattr(self, 'creator_id', None),
                operation=GraphOperationType.CREATE_EPISODE,
                idempotency_key=idempotency_key,
                payload={
                    "name": name,
                    "body": body,
                    "source_type": source_type,
                    "source_ref": source_ref,
                    "timestamp": timestamp or time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "scope_id": self.scope_id,
                    "group_id": self.group_id
                },
                correlation_id=self.correlation_id
            )
            logger.info(
                f"[GraphMemoryCore] Episode queued: job={job_id} "
                f"scope={self.scope_id} corr={self.correlation_id}"
            )
            return job_id
        
        # Synchronous write with timeout
        async def _do_create():
            graphiti = self._get_graphiti()
            if not graphiti:
                raise GraphMemoryUnavailable("Graphiti not available")
            
            from datetime import datetime
            
            # Graphiti.add_episode is async - await it directly
            result = await graphiti.add_episode(
                name=name,
                episode_body=body,
                source_description=f"{source_type}:{source_ref}",
                reference_time=datetime.now(),
                group_id=self.group_id  # Uses scope_id for isolation
            )
            return result
        
        try:
            result = await self._execute_with_timeout(
                "create_episode", 
                _do_create(),
                timeout_ms=self.config.extraction_timeout_ms
            )
            
            self.circuit_breaker.record_success()
            
            # Extract episode ID from AddEpisodeResults object
            episode_id = None
            if result:
                if hasattr(result, 'episode'):
                    episode_id = result.episode.uuid if hasattr(result.episode, 'uuid') else str(result.episode)
                elif hasattr(result, 'uuid'):
                    episode_id = result.uuid
                else:
                    episode_id = str(result)
            logger.info(
                f"[GraphMemoryCore] Episode created: {episode_id} "
                f"scope={self.scope_id} corr={self.correlation_id}"
            )
            return episode_id
            
        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error(
                f"[GraphMemoryCore] Episode creation failed: {e} "
                f"scope={self.scope_id} corr={self.correlation_id}"
            )
            raise GraphMemoryUnavailable(f"Failed to create episode: {e}")
    
    async def _search_episodes_direct(
        self, query: str, num_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Fast direct Neo4j query with persistent driver and latency metrics."""
        import time
        t_start = time.time()
        
        if not _NEO4J_AVAILABLE:
            return []
        
        timeout_secs = self.config.read_timeout_ms / 1000.0
        
        # Use persistent driver (avoids ~1000ms connection overhead)
        driver = _get_pooled_driver(
            self.config.neo4j_uri,
            self.config.neo4j_user or "neo4j",
            self.config.neo4j_password
        )
        
        if not driver:
            raise GraphMemoryUnavailable("Neo4j driver not available")
        
        async def execute_query():
            cypher = """
            MATCH (e:Episode)
            WHERE e.group_id = $gid
              AND (e.content CONTAINS $q OR e.name CONTAINS $q)
            RETURN e.content as content, e.name as name 
            LIMIT $lim
            """
            
            async with driver.session() as session:
                result = await session.run(cypher, gid=self.group_id, q=query, lim=num_results)
                records = []
                async for record in result:
                    records.append({"content": record.get("content", "")})
                return records
        
        try:
            # Hard cap enforcement with timeout
            results = await asyncio.wait_for(execute_query(), timeout=timeout_secs)
            
            # Record latency metric
            latency_ms = (time.time() - t_start) * 1000
            self._record_latency_metric(latency_ms, success=True)
            
            return results
            
        except asyncio.TimeoutError:
            latency_ms = (time.time() - t_start) * 1000
            self._record_latency_metric(latency_ms, success=False, error="timeout")
            raise GraphMemoryUnavailable(f"Graph memory search timed out after {latency_ms:.0f}ms")
        except ServiceUnavailable:
            latency_ms = (time.time() - t_start) * 1000
            self._record_latency_metric(latency_ms, success=False, error="unavailable")
            raise GraphMemoryUnavailable("Neo4j unavailable")
        except Exception as e:
            latency_ms = (time.time() - t_start) * 1000
            self._record_latency_metric(latency_ms, success=False, error=type(e).__name__)
            raise GraphMemoryUnavailable(f"Search error: {type(e).__name__}")
    
    def _record_latency_metric(self, latency_ms: float, success: bool, error: str = None):
        """Record latency metric for observability (p95/p99 tracking)."""
        status = "success" if success else f"error:{error}"
        logger.debug(
            f"[GraphMemoryCore] latency_ms={latency_ms:.1f} status={status} "
            f"scope={self.scope_id} corr={self.correlation_id}"
        )
    
    async def search(
        self,
        query: str,
        num_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search graph for relevant episodes/facts.
        
        Uses direct Neo4j queries for timeout enforceability.
        Respects timeout and circuit breaker.
        """
        if not self.config.is_read_allowed():
            logger.debug("[GraphMemoryCore] Read disabled, returning empty")
            return []
        
        if self.circuit_breaker.is_open():
            logger.warning(f"[GraphMemoryCore] Circuit open, skipping search")
            return []
        
        try:
            # Route through timeout wrapper so timeout config is centrally enforced
            # and test instrumentation can validate timeout propagation.
            results = await self._execute_with_timeout(
                "search",
                self._search_episodes_direct(query, num_results),
                timeout_ms=self.config.read_timeout_ms
            )
            
            logger.debug(
                f"[GraphMemoryCore] Search returned {len(results)} results "
                f"scope={self.scope_id} corr={self.correlation_id}"
            )
            return results
            
        except GraphMemoryUnavailable:
            # Timeout or unavailable - return empty for graceful fallback
            logger.debug(
                f"[GraphMemoryCore] Graph unavailable, returning empty "
                f"scope={self.scope_id} corr={self.correlation_id}"
            )
            return []
        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error(
                f"[GraphMemoryCore] Search failed: {e} "
                f"scope={self.scope_id} corr={self.correlation_id}"
            )
            return []
    
    async def delete_scope_graph(self) -> bool:
        """
        Delete all graph data for this scope.
        Uses scope_id (group_id) for targeted deletion.
        """
        if not self.config.is_write_allowed():
            return False
        
        try:
            # Submit to outbox for async processing
            idempotency_key = f"delete:{self.scope_id}:{time.time()}"
            job_id = self.outbox.submit(
                tenant_id=self.tenant_id,
                twin_id=self.twin_id or "default",
                scope_id=self.scope_id,
                creator_id=getattr(self, 'creator_id', None),
                operation=GraphOperationType.DELETE_TWIN_GRAPH,
                idempotency_key=idempotency_key,
                payload={
                    "scope_id": self.scope_id,
                    "group_id": self.group_id
                },
                correlation_id=self.correlation_id
            )
            
            logger.info(
                f"[GraphMemoryCore] Scope graph deletion queued: job={job_id} "
                f"scope={self.scope_id}"
            )
            return True
            
        except Exception as e:
            logger.error(f"[GraphMemoryCore] Delete failed: {e}")
            return False
    
    # Backward compatibility alias
    delete_twin_graph = delete_scope_graph
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status for debugging."""
        return {
            "enabled": self.config.enabled,
            "read_allowed": self.config.is_read_allowed(),
            "write_allowed": self.config.is_write_allowed(),
            "circuit_status": self.circuit_breaker.get_status(),
            "scope_id": self.scope_id,
            "group_id": self.group_id,
            "twin_id": self.twin_id,  # For backward compat
            "graphiti_initialized": self._graphiti is not None,
            "correlation_id": self.correlation_id,
            "single_profile_enabled": is_single_profile_enabled()
        }


class GraphMemoryCoreFactory:
    """Factory for creating GraphMemoryCore instances."""
    
    @staticmethod
    def create(
        tenant_id: str,
        twin_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        creator_id: Optional[str] = None,
        scope_id: Optional[str] = None
    ) -> GraphMemoryCore:
        """
        Create GraphMemoryCore with appropriate scope.
        
        Single-Profile Mode:
            factory.create(tenant_id, creator_id="user_123")
            
        Legacy Mode:
            factory.create(tenant_id, twin_id="twin_456")
        """
        return GraphMemoryCore(
            tenant_id=tenant_id,
            twin_id=twin_id,
            correlation_id=correlation_id,
            creator_id=creator_id,
            scope_id=scope_id
        )
