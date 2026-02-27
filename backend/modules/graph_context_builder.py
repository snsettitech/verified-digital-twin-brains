"""
Graph Context Builder for Chat Integration (Phase 3)

Provides best-effort graph context retrieval for agent state.
Uses materialized snapshots for fast reads (Phase 3).
Falls back to direct graph query if snapshot unavailable.
"""

import asyncio
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from modules.graph_memory_core import GraphMemoryCore
from modules.graph_memory_config import get_graph_memory_config
from modules.graph_snapshot_manager import GraphSnapshotManager


@dataclass
class GraphContextResult:
    """Result of graph context retrieval with metadata for debugging."""
    context: Optional[str]  # Formatted context string or None
    latency_ms: float
    source: str  # 'snapshot', 'graph', 'timeout', 'unavailable', 'disabled'
    episode_count: int = 0
    claim_count: int = 0
    scope_id: Optional[str] = None


class GraphContextBuilder:
    """
    Builds graph context for chat agent with soft budget enforcement.
    
    Usage:
        builder = GraphContextBuilder(tenant_id, twin_id, correlation_id)
        result = await builder.build_context(
            query="user question",
            soft_budget_ms=500  # Optional override
        )
        
        if result.context:
            agent_state["graph_context"] = result.context
    """
    
    def __init__(
        self,
        tenant_id: str,
        twin_id: str,
        correlation_id: Optional[str] = None,
        creator_id: Optional[str] = None,
        scope_id: Optional[str] = None,
    ):
        self.tenant_id = tenant_id
        self.twin_id = twin_id
        self.correlation_id = correlation_id or "no-correlation"
        self.creator_id = creator_id
        self.scope_id = scope_id
        self.config = get_graph_memory_config()
        self._client: Optional[GraphMemoryCore] = None
        self._resolved_scope_id: Optional[str] = None
    
    def _get_client(self, scope_id: Optional[str] = None) -> Optional[GraphMemoryCore]:
        """Lazy initialize GraphMemoryCore client."""
        if self._client is not None:
            return self._client
        
        if not self.config.is_read_allowed():
            return None
        
        self._client = GraphMemoryCore(
            tenant_id=self.tenant_id,
            twin_id=self.twin_id,
            scope_id=scope_id,
            correlation_id=self.correlation_id
        )
        return self._client

    async def _resolve_scope_id(self) -> Optional[str]:
        """Resolve canonical scope_id for chat retrieval."""
        if self._resolved_scope_id:
            return self._resolved_scope_id

        if self.scope_id:
            self._resolved_scope_id = self.scope_id
            return self._resolved_scope_id

        if self.creator_id:
            self._resolved_scope_id = self.config.make_scope_id(self.tenant_id, self.creator_id)
            return self._resolved_scope_id

        # Single-profile default creator convention: tenant_{tenant_id}.
        # This avoids an extra DB hop in the chat critical path.
        default_creator_id = f"tenant_{self.tenant_id}"
        self._resolved_scope_id = self.config.make_scope_id(self.tenant_id, default_creator_id)
        return self._resolved_scope_id

        return None
    
    async def build_context(
        self,
        query: str,
        soft_budget_ms: Optional[int] = None,
        num_episodes: int = 5
    ) -> GraphContextResult:
        """
        Build graph context with soft budget enforcement.
        
        Phase 3: Uses materialized snapshots for instant reads.
        Falls back to direct graph query if snapshot unavailable.
        
        Args:
            query: User query to search for relevant episodes
            soft_budget_ms: Override default soft budget
            num_episodes: Max episodes to include in context
            
        Returns:
            GraphContextResult with context (or None if unavailable/timeout)
        """
        t_start = time.perf_counter()

        # Check if graph reads enabled
        if not self.config.is_read_allowed():
            return GraphContextResult(
                context=None,
                latency_ms=(time.perf_counter() - t_start) * 1000,
                source='disabled'
            )

        raw_budget = soft_budget_ms if soft_budget_ms is not None else getattr(self.config, "chat_soft_budget_ms", 500)
        try:
            budget = float(raw_budget)
        except Exception:
            budget = 500.0
        budget_seconds = max(0.001, budget / 1000.0)

        resolved_scope = None
        try:
            resolve_timeout = min(0.05, budget_seconds / 2.0)
            resolved_scope = await asyncio.wait_for(self._resolve_scope_id(), timeout=resolve_timeout)
        except Exception:
            resolved_scope = None
        
        # Phase 3: Try materialized snapshot first (instant read from Supabase)
        try:
            manager = GraphSnapshotManager()
            # Snapshot is the preferred read path. Allocate most of the budget to it.
            snapshot_timeout = min(max(budget_seconds - 0.05, 0.1), budget_seconds)
            snapshot = None

            if resolved_scope:
                snapshot = await asyncio.wait_for(
                    manager.get_snapshot_by_scope(
                        scope_id=resolved_scope,
                        max_age_seconds=300,
                    ),
                    timeout=snapshot_timeout,
                )
            else:
                snapshot = await asyncio.wait_for(
                    manager.get_snapshot(
                        tenant_id=self.tenant_id,
                        twin_id=self.twin_id,
                        max_age_seconds=300,
                    ),
                    timeout=snapshot_timeout,
                )

            if snapshot:
                context_str = manager._format_snapshot(snapshot, query)
                latency_ms = (time.perf_counter() - t_start) * 1000
                return GraphContextResult(
                    context=context_str,
                    latency_ms=latency_ms,
                    source='snapshot',
                    episode_count=snapshot.episode_count,
                    claim_count=snapshot.claim_count,
                    scope_id=snapshot.scope_id or resolved_scope,
                )
        except asyncio.TimeoutError:
            # Snapshot took too long, fall through to direct query
            pass
        except Exception:
            # Snapshot unavailable, fall through to direct query
            pass

        elapsed = time.perf_counter() - t_start
        remaining_budget = budget_seconds - elapsed
        if remaining_budget <= 0:
            return GraphContextResult(
                context=None,
                latency_ms=(time.perf_counter() - t_start) * 1000,
                source="timeout",
                scope_id=resolved_scope,
            )
        
        # Fallback: Direct graph query (with soft budget)
        client = self._get_client(scope_id=resolved_scope)
        if not client:
            return GraphContextResult(
                context=None,
                latency_ms=(time.perf_counter() - t_start) * 1000,
                source='unavailable',
                scope_id=resolved_scope,
            )
        
        try:
            context_data = await asyncio.wait_for(
                self._fetch_and_format_context(client, query, num_episodes),
                timeout=remaining_budget
            )
            
            latency_ms = (time.perf_counter() - t_start) * 1000
            
            if context_data.get('episodes'):
                context_str = self._format_context(context_data['episodes'])
                return GraphContextResult(
                    context=context_str,
                    latency_ms=latency_ms,
                    source='graph',
                    episode_count=len(context_data['episodes']),
                    claim_count=context_data.get('claim_count', 0),
                    scope_id=resolved_scope,
                )
            else:
                return GraphContextResult(
                    context=None,
                    latency_ms=latency_ms,
                    source='graph',
                    episode_count=0,
                    claim_count=0,
                    scope_id=resolved_scope,
                )
                
        except asyncio.TimeoutError:
            latency_ms = (time.perf_counter() - t_start) * 1000
            return GraphContextResult(
                context=None,
                latency_ms=latency_ms,
                source='timeout',
                scope_id=resolved_scope,
            )
        except Exception:
            latency_ms = (time.perf_counter() - t_start) * 1000
            return GraphContextResult(
                context=None,
                latency_ms=latency_ms,
                source='unavailable',
                scope_id=resolved_scope,
            )
    
    async def _fetch_and_format_context(
        self,
        client: GraphMemoryCore,
        query: str,
        num_episodes: int
    ) -> Dict[str, Any]:
        """Fetch episodes from graph and extract claims."""
        # Search for relevant episodes
        episodes = await client.search(query, num_results=num_episodes)
        
        if not episodes:
            return {'episodes': [], 'claim_count': 0}
        
        # TODO: Phase 2.5+ - Extract claims from episodes
        # For now, return episodes as context
        return {
            'episodes': episodes,
            'claim_count': 0  # Will be populated when claim extraction implemented
        }
    
    def _format_context(self, episodes: List[Dict[str, Any]]) -> str:
        """Format episodes into context string for agent."""
        if not episodes:
            return ""
        
        context_parts = ["## Graph Memory Context"]
        
        for i, ep in enumerate(episodes, 1):
            name = ep.get('name', 'Unnamed Episode')
            content = ep.get('content', '')
            if content:
                context_parts.append(f"\n### {i}. {name}")
                context_parts.append(content[:500])  # Truncate long content
        
        return "\n".join(context_parts)
    
    def get_debug_headers(self, result: GraphContextResult) -> Dict[str, str]:
        """Get debug headers if GRAPH_MEMORY_DEBUG_HEADERS enabled."""
        if not self.config.debug_headers:
            return {}
        
        return {
            'X-Graph-Context-Source': result.source,
            'X-Graph-Context-Latency-Ms': str(int(result.latency_ms)),
            'X-Graph-Context-Episodes': str(result.episode_count),
            'X-Graph-Context-Claims': str(result.claim_count),
            'X-Graph-Scope-Id': result.scope_id or "",
            'X-Correlation-Id': self.correlation_id,
        }


async def get_graph_context_for_chat(
    tenant_id: str,
    twin_id: str,
    query: str,
    correlation_id: Optional[str] = None,
    soft_budget_ms: Optional[int] = None,
    creator_id: Optional[str] = None,
    scope_id: Optional[str] = None,
) -> GraphContextResult:
    """
    Convenience function for chat integration.
    
    Runs graph context retrieval with soft budget.
    Safe to call in parallel with Pinecone retrieval.
    """
    builder = GraphContextBuilder(
        tenant_id=tenant_id,
        twin_id=twin_id,
        correlation_id=correlation_id,
        creator_id=creator_id,
        scope_id=scope_id,
    )
    return await builder.build_context(
        query=query,
        soft_budget_ms=soft_budget_ms
    )
