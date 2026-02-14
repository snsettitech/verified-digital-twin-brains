# backend/modules/metrics_collector.py
"""Metrics Collector for Langfuse Data

Collects and aggregates metrics from Langfuse for dashboard APIs.
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TimeRangeMetrics:
    """Metrics for a time range."""
    start_time: str
    end_time: str
    total_traces: int
    error_count: int
    error_rate: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    avg_quality_score: float
    total_tokens: int


class MetricsCollector:
    """Collects metrics from Langfuse."""
    
    def __init__(self, twin_id: Optional[str] = None):
        # Backward-compatible optional scope hint used by callers.
        self._twin_id = twin_id
        self._langfuse_available = False
        self._request_count = 0
        self._latency_ms: List[float] = []
        self._init_langfuse()

    def record_request(self) -> None:
        """Record a request event (lightweight, backward-compatible)."""
        self._request_count += 1

    def record_latency(self, phase: str, latency_ms: float) -> None:
        """Record latency metric for a phase."""
        try:
            self._latency_ms.append(float(latency_ms))
        except Exception:
            return

    def flush(self) -> None:
        """Flush collected metrics to Langfuse when available."""
        if not self._langfuse_available:
            return
        try:
            if self._request_count:
                self._client.score(
                    name="requests_count",
                    value=self._request_count,
                    data_type="NUMERIC",
                )
            if self._latency_ms:
                avg_latency = sum(self._latency_ms) / len(self._latency_ms)
                self._client.score(
                    name="agent_latency_ms",
                    value=avg_latency,
                    data_type="NUMERIC",
                )
            self._client.flush()
        except Exception as e:
            logger.debug(f"Failed to flush metrics collector data: {e}")
    
    def _init_langfuse(self):
        """Initialize Langfuse client."""
        try:
            from langfuse import Langfuse
            
            public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
            secret_key = os.getenv("LANGFUSE_SECRET_KEY")
            host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
            
            if public_key and secret_key:
                self._client = Langfuse(
                    public_key=public_key,
                    secret_key=secret_key,
                    host=host,
                )
                self._langfuse_available = True
                logger.info("Metrics Collector initialized")
        except Exception as e:
            logger.warning(f"Langfuse not available for metrics: {e}")
    
    async def get_quality_metrics(
        self,
        from_time: datetime,
        to_time: datetime,
        interval: str = "hour"  # "hour", "day"
    ) -> List[Dict[str, Any]]:
        """
        Get quality metrics over time.
        
        Args:
            from_time: Start time
            to_time: End time
            interval: Aggregation interval
        
        Returns:
            List of metric points
        """
        if not self._langfuse_available:
            return []
        
        try:
            # Fetch overall_quality scores
            scores = self._client.fetch_scores(
                name="overall_quality",
                from_timestamp=from_time.isoformat(),
                to_timestamp=to_time.isoformat()
            )
            
            # Group by interval
            buckets = {}
            for score in scores:
                timestamp = datetime.fromisoformat(score.timestamp.replace('Z', '+00:00'))
                
                if interval == "hour":
                    bucket_key = timestamp.strftime("%Y-%m-%d %H:00")
                else:
                    bucket_key = timestamp.strftime("%Y-%m-%d")
                
                if bucket_key not in buckets:
                    buckets[bucket_key] = []
                buckets[bucket_key].append(score.value)
            
            # Calculate averages per bucket
            results = []
            for bucket_key, values in sorted(buckets.items()):
                results.append({
                    "timestamp": bucket_key,
                    "avg_score": round(sum(values) / len(values), 3),
                    "min_score": round(min(values), 3),
                    "max_score": round(max(values), 3),
                    "count": len(values)
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get quality metrics: {e}")
            return []
    
    async def get_latency_metrics(
        self,
        from_time: datetime,
        to_time: datetime
    ) -> Dict[str, Any]:
        """Get latency metrics for a time range."""
        if not self._langfuse_available:
            return {}
        
        try:
            traces = self._client.fetch_traces(
                from_timestamp=from_time.isoformat(),
                to_timestamp=to_time.isoformat()
            )
            
            latencies = [t.latency for t in traces if hasattr(t, 'latency') and t.latency]
            
            if not latencies:
                return {}
            
            latencies.sort()
            n = len(latencies)
            
            return {
                "count": n,
                "avg_ms": round(sum(latencies) / n, 2),
                "p50_ms": latencies[int(n * 0.5)],
                "p95_ms": latencies[int(n * 0.95)],
                "p99_ms": latencies[int(n * 0.99)],
                "min_ms": latencies[0],
                "max_ms": latencies[-1]
            }
            
        except Exception as e:
            logger.error(f"Failed to get latency metrics: {e}")
            return {}
    
    async def get_error_metrics(
        self,
        from_time: datetime,
        to_time: datetime
    ) -> Dict[str, Any]:
        """Get error metrics for a time range."""
        if not self._langfuse_available:
            return {}
        
        try:
            traces = self._client.fetch_traces(
                from_timestamp=from_time.isoformat(),
                to_timestamp=to_time.isoformat()
            )
            
            total = len(traces)
            errors = sum(1 for t in traces if t.metadata.get("error", False))
            
            # Group by error type
            error_types = {}
            for t in traces:
                if t.metadata.get("error"):
                    error_type = t.metadata.get("error_type", "unknown")
                    error_types[error_type] = error_types.get(error_type, 0) + 1
            
            return {
                "total_traces": total,
                "error_count": errors,
                "error_rate": round(errors / total * 100, 2) if total > 0 else 0,
                "error_types": error_types
            }
            
        except Exception as e:
            logger.error(f"Failed to get error metrics: {e}")
            return {}
    
    async def get_persona_metrics(
        self,
        from_time: datetime,
        to_time: datetime
    ) -> Dict[str, Any]:
        """Get persona compliance metrics."""
        if not self._langfuse_available:
            return {}
        
        try:
            scores = {}
            for score_name in ["persona_overall", "persona_structure_policy", "persona_voice_fidelity"]:
                try:
                    score_data = self._client.fetch_scores(
                        name=score_name,
                        from_timestamp=from_time.isoformat(),
                        to_timestamp=to_time.isoformat()
                    )
                    if score_data:
                        values = [s.value for s in score_data]
                        scores[score_name] = {
                            "avg": round(sum(values) / len(values), 3),
                            "count": len(values)
                        }
                except Exception:
                    pass
            
            # Count rewrites
            try:
                rewrite_scores = self._client.fetch_scores(
                    name="persona_rewrite_applied",
                    from_timestamp=from_time.isoformat(),
                    to_timestamp=to_time.isoformat()
                )
                rewrite_count = sum(1 for s in rewrite_scores if s.value)
                scores["rewrite_count"] = rewrite_count
            except Exception:
                pass
            
            return scores
            
        except Exception as e:
            logger.error(f"Failed to get persona metrics: {e}")
            return {}
    
    async def get_dataset_stats(self) -> Dict[str, Any]:
        """Get dataset statistics."""
        if not self._langfuse_available:
            return {}
        
        try:
            stats = {}
            for dataset_name in ["high_quality_responses", "needs_improvement"]:
                try:
                    dataset = self._client.get_dataset(dataset_name)
                    items = list(dataset.items)
                    
                    # Calculate average score
                    scores = [item.metadata.get("overall_score", 0) for item in items if item.metadata]
                    avg_score = sum(scores) / len(scores) if scores else 0
                    
                    stats[dataset_name] = {
                        "item_count": len(items),
                        "avg_score": round(avg_score, 3)
                    }
                except Exception:
                    stats[dataset_name] = {"item_count": 0, "avg_score": 0}
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get dataset stats: {e}")
            return {}
    
    async def get_full_dashboard_metrics(
        self,
        hours: int = 24
    ) -> Dict[str, Any]:
        """Get all metrics for dashboard in one call."""
        to_time = datetime.utcnow()
        from_time = to_time - timedelta(hours=hours)
        
        quality = await self.get_quality_metrics(from_time, to_time, interval="hour")
        latency = await self.get_latency_metrics(from_time, to_time)
        errors = await self.get_error_metrics(from_time, to_time)
        persona = await self.get_persona_metrics(from_time, to_time)
        datasets = await self.get_dataset_stats()
        
        return {
            "time_range": {
                "from": from_time.isoformat(),
                "to": to_time.isoformat(),
                "hours": hours
            },
            "quality": quality,
            "latency": latency,
            "errors": errors,
            "persona": persona,
            "datasets": datasets
        }


# Singleton instance
_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create the singleton collector."""
    global _collector
    if _collector is None:
        _collector = MetricsCollector()
    return _collector
