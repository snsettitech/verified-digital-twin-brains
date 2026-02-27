"""
Graph Memory Metrics

Prometheus-style metrics for observability during single-profile rollout.

Metrics:
- graph_outbox_dedup_hits_total{scope_id}
- graph_outbox_submits_total{operation, scope}
- graph_outbox_depth{status, scope}
- graph_outbox_processing_latency_ms*
- graph_scope_resolution_total{mode, fallback}
- graph_scope_mismatch_total
- graph_circuit_breaker_state{scope_id}
- graph_snapshot_hit_total{scope_id}
"""

import time
import logging
from typing import Dict, Optional, Callable
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class MetricCounter:
    """Simple counter metric."""
    name: str
    description: str
    labels: list = field(default_factory=list)
    _values: Dict[tuple, int] = field(default_factory=lambda: defaultdict(int))
    
    def inc(self, value: int = 1, **labels):
        """Increment counter with labels."""
        label_key = tuple(labels.get(k, "") for k in self.labels)
        self._values[label_key] += value
    
    def get(self, **labels) -> int:
        """Get counter value for labels."""
        label_key = tuple(labels.get(k, "") for k in self.labels)
        return self._values.get(label_key, 0)
    
    def reset(self):
        """Reset all values."""
        self._values.clear()


@dataclass
class MetricGauge:
    """Simple gauge metric."""
    name: str
    description: str
    labels: list = field(default_factory=list)
    _values: Dict[tuple, float] = field(default_factory=dict)
    
    def set(self, value: float, **labels):
        """Set gauge value."""
        label_key = tuple(labels.get(k, "") for k in self.labels)
        self._values[label_key] = value
    
    def get(self, **labels) -> float:
        """Get gauge value."""
        label_key = tuple(labels.get(k, "") for k in self.labels)
        return self._values.get(label_key, 0.0)


@dataclass
class MetricHistogram:
    """Simple histogram metric (tracks p50, p95, p99)."""
    name: str
    description: str
    labels: list = field(default_factory=list)
    buckets: list = field(default_factory=lambda: [10, 50, 100, 250, 500, 1000, 2500, 5000])
    _values: Dict[tuple, list] = field(default_factory=lambda: defaultdict(list))
    
    def observe(self, value: float, **labels):
        """Observe a value."""
        label_key = tuple(labels.get(k, "") for k in self.labels)
        self._values[label_key].append(value)
        # Keep last 1000 values for memory efficiency
        if len(self._values[label_key]) > 1000:
            self._values[label_key] = self._values[label_key][-1000:]
    
    def get_percentile(self, p: float, **labels) -> float:
        """Get percentile value."""
        label_key = tuple(labels.get(k, "") for k in self.labels)
        values = sorted(self._values.get(label_key, []))
        if not values:
            return 0.0
        idx = int(len(values) * p / 100)
        return values[min(idx, len(values) - 1)]
    
    def get_stats(self, **labels) -> Dict[str, float]:
        """Get all stats."""
        return {
            "p50": self.get_percentile(50, **labels),
            "p95": self.get_percentile(95, **labels),
            "p99": self.get_percentile(99, **labels),
            "count": len(self._values.get(tuple(labels.get(k, "") for k in self.labels), []))
        }


class GraphMemoryMetrics:
    """
    Centralized metrics collection for Graph Memory.
    
    Usage:
        from modules.graph_memory_metrics import get_metrics
        
        metrics = get_metrics()
        metrics.outbox_dedup_hits.inc(scope_id="tenant_123__creator_456")
        metrics.outbox_latency.observe(150.0, operation="create_episode")
    """
    
    def __init__(self):
        # Outbox metrics
        self.outbox_dedup_hits = MetricCounter(
            "graph_outbox_dedup_hits_total",
            "Total outbox deduplication hits",
            ["scope_id"]
        )
        self.outbox_submits = MetricCounter(
            "graph_outbox_submits_total",
            "Total outbox job submissions",
            ["operation", "scope"]
        )
        self.outbox_depth = MetricGauge(
            "graph_outbox_depth",
            "Current outbox depth by status",
            ["status", "scope"]
        )
        self.outbox_latency = MetricHistogram(
            "graph_outbox_processing_latency_ms",
            "Outbox job processing latency in milliseconds",
            ["operation"],
            buckets=[10, 50, 100, 250, 500, 1000, 2500, 5000, 10000]
        )
        
        # Scope resolution metrics
        self.scope_resolution = MetricCounter(
            "graph_scope_resolution_total",
            "Total scope resolutions by mode",
            ["mode", "fallback"]
        )
        self.scope_mismatch = MetricCounter(
            "graph_scope_mismatch_total",
            "Total scope mismatches (data quality issue)",
            ["type"]
        )
        
        # Circuit breaker metrics
        self.circuit_breaker_state = MetricGauge(
            "graph_circuit_breaker_state",
            "Circuit breaker state (0=closed, 1=half_open, 2=open)",
            ["scope_id"]
        )
        self.circuit_breaker_trips = MetricCounter(
            "graph_circuit_breaker_trips_total",
            "Total circuit breaker trips",
            ["scope_id"]
        )
        
        # Snapshot metrics
        self.snapshot_hits = MetricCounter(
            "graph_snapshot_hit_total",
            "Total snapshot cache hits",
            ["scope_id", "hit_type"]  # hit_type: fresh, stale, miss
        )
        self.snapshot_latency = MetricHistogram(
            "graph_snapshot_read_latency_ms",
            "Snapshot read latency",
            ["source"]  # source: cache, neo4j
        )
        
        # Graph operation metrics
        self.graph_operations = MetricCounter(
            "graph_operations_total",
            "Total graph operations",
            ["operation", "status", "scope_id"]
        )
        self.graph_operation_latency = MetricHistogram(
            "graph_operation_latency_ms",
            "Graph operation latency",
            ["operation"]
        )
    
    def record_outbox_submit(
        self,
        operation: str,
        scope_id: Optional[str] = None,
        deduped: bool = False
    ):
        """Record outbox submission."""
        scope_label = "single_profile" if scope_id else "legacy"
        self.outbox_submits.inc(operation=operation, scope=scope_label)
        
        if deduped and scope_id:
            self.outbox_dedup_hits.inc(scope_id=scope_id[:50])  # Truncate for label
    
    def record_outbox_depth(self, status: str, count: int, scope_id: Optional[str] = None):
        """Record outbox depth."""
        scope_label = "single_profile" if scope_id else "legacy"
        self.outbox_depth.set(float(count), status=status, scope=scope_label)
    
    def record_scope_resolution(
        self,
        mode: str,  # "legacy" or "single_profile"
        fallback: bool = False
    ):
        """Record scope resolution event."""
        fallback_label = "true" if fallback else "false"
        self.scope_resolution.inc(mode=mode, fallback=fallback_label)
    
    def record_scope_mismatch(self, mismatch_type: str):
        """
        Record scope mismatch (data quality issue).
        
        Types:
        - missing_scope_id: Row has twin_id but no scope_id
        - missing_twin_id: Row has scope_id but no twin_id
        - inconsistent_ids: scope_id doesn't match twin_id derivation
        """
        self.scope_mismatch.inc(type=mismatch_type)
    
    def record_circuit_breaker_state(self, scope_id: str, state: str):
        """
        Record circuit breaker state.
        
        State values:
        - closed: 0
        - half_open: 1
        - open: 2
        """
        state_map = {"closed": 0, "half_open": 1, "open": 2}
        state_value = state_map.get(state, 0)
        self.circuit_breaker_state.set(float(state_value), scope_id=scope_id[:50])
    
    def record_circuit_breaker_trip(self, scope_id: str):
        """Record circuit breaker trip."""
        self.circuit_breaker_trips.inc(scope_id=scope_id[:50])
    
    def record_snapshot_hit(
        self,
        scope_id: str,
        hit_type: str  # "fresh", "stale", "miss"
    ):
        """Record snapshot hit/miss."""
        self.snapshot_hits.inc(scope_id=scope_id[:50], hit_type=hit_type)
    
    def record_graph_operation(
        self,
        operation: str,
        status: str,  # "success", "failure", "timeout"
        scope_id: Optional[str] = None,
        latency_ms: Optional[float] = None
    ):
        """Record graph operation."""
        scope_label = scope_id[:50] if scope_id else "legacy"
        self.graph_operations.inc(
            operation=operation,
            status=status,
            scope_id=scope_label
        )
        
        if latency_ms is not None:
            self.graph_operation_latency.observe(latency_ms, operation=operation)
    
    def get_prometheus_format(self) -> str:
        """Export metrics in Prometheus exposition format."""
        lines = []
        
        # Counters
        for metric in [self.outbox_dedup_hits, self.outbox_submits, 
                       self.scope_resolution, self.scope_mismatch,
                       self.circuit_breaker_trips, self.snapshot_hits,
                       self.graph_operations]:
            lines.append(f"# HELP {metric.name} {metric.description}")
            lines.append(f"# TYPE {metric.name} counter")
            for (label_values,), value in metric._values.items():
                label_str = ",".join(
                    f'{k}="{v}"' for k, v in zip(metric.labels, label_values)
                )
                lines.append(f'{metric.name}{{{label_str}}} {value}')
            lines.append("")
        
        # Gauges
        for metric in [self.outbox_depth, self.circuit_breaker_state]:
            lines.append(f"# HELP {metric.name} {metric.description}")
            lines.append(f"# TYPE {metric.name} gauge")
            for label_values, value in metric._values.items():
                label_str = ",".join(
                    f'{k}="{v}"' for k, v in zip(metric.labels, label_values)
                )
                lines.append(f'{metric.name}{{{label_str}}} {value}')
            lines.append("")
        
        return "\n".join(lines)
    
    def get_health_report(self) -> Dict:
        """Get health report for monitoring dashboards."""
        return {
            "outbox": {
                "submits_total": sum(self.outbox_submits._values.values()),
                "dedup_hits_total": sum(self.outbox_dedup_hits._values.values()),
                "current_depth": {
                    status: self.outbox_depth.get(status=status, scope="single_profile") +
                             self.outbox_depth.get(status=status, scope="legacy")
                    for status in ["pending", "processing", "completed", "failed"]
                }
            },
            "scope_migration": {
                "single_profile_resolutions": self.scope_resolution.get(
                    mode="single_profile", fallback="false"
                ),
                "legacy_resolutions": self.scope_resolution.get(
                    mode="legacy", fallback="false"
                ),
                "fallback_count": (
                    self.scope_resolution.get(mode="single_profile", fallback="true") +
                    self.scope_resolution.get(mode="legacy", fallback="true")
                ),
                "mismatch_count": sum(self.scope_mismatch._values.values())
            },
            "circuit_breakers": {
                "total_trips": sum(self.circuit_breaker_trips._values.values()),
                "open_count": sum(
                    1 for v in self.circuit_breaker_state._values.values() if v == 2
                )
            },
            "snapshots": {
                "hits": self.snapshot_hits.get(hit_type="fresh"),
                "stale": self.snapshot_hits.get(hit_type="stale"),
                "misses": self.snapshot_hits.get(hit_type="miss")
            }
        }


# Global metrics instance
_metrics_instance: Optional[GraphMemoryMetrics] = None


def get_metrics() -> GraphMemoryMetrics:
    """Get or create global metrics instance."""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = GraphMemoryMetrics()
    return _metrics_instance


def reset_metrics():
    """Reset all metrics (for testing)."""
    global _metrics_instance
    _metrics_instance = None


# Convenience functions for common metrics

def record_outbox_dedup(scope_id: str):
    """Record outbox deduplication hit."""
    get_metrics().outbox_dedup_hits.inc(scope_id=scope_id[:50])


def record_scope_resolution(mode: str, fallback: bool = False):
    """Record scope resolution."""
    get_metrics().record_scope_resolution(mode, fallback)


def record_scope_mismatch(mismatch_type: str):
    """Record scope mismatch."""
    get_metrics().record_scope_mismatch(mismatch_type)
