"""
Metrics Collection Module

Collects and stores performance metrics for observability:
- Request latency (retrieval, LLM, total)
- Token usage per request
- Error counts
- Service health
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from contextlib import contextmanager
import time
from modules.observability import supabase


class MetricsCollector:
    """
    Collect and store metrics for observability dashboard.
    
    Usage:
        collector = MetricsCollector(twin_id="...", user_id="...")
        
        with collector.measure("retrieval"):
            # do retrieval
            pass
        
        collector.record_tokens(prompt=100, completion=50)
        collector.flush()
    """
    
    def __init__(self, twin_id: Optional[str] = None, user_id: Optional[str] = None):
        self.twin_id = twin_id
        self.user_id = user_id
        self.metrics_buffer = []
        self.timings = {}
        self.start_time = time.time()
    
    @contextmanager
    def measure(self, operation: str):
        """Context manager to measure operation duration."""
        start = time.time()
        try:
            yield
        finally:
            duration_ms = (time.time() - start) * 1000
            self.timings[operation] = duration_ms
            self._add_metric(f"{operation}_latency_ms", duration_ms)
    
    def record_latency(self, operation: str, duration_ms: float):
        """Record a latency measurement directly."""
        self.timings[operation] = duration_ms
        self._add_metric(f"{operation}_latency_ms", duration_ms)
    
    def record_tokens(self, prompt: int = 0, completion: int = 0, total: Optional[int] = None):
        """Record token usage."""
        if total is None:
            total = prompt + completion
        
        if prompt > 0:
            self._add_metric("tokens_prompt", prompt)
        if completion > 0:
            self._add_metric("tokens_completion", completion)
        if total > 0:
            self._add_metric("tokens_total", total)
    
    def record_error(self, error_type: str = "general"):
        """Record an error occurrence."""
        self._add_metric("error_count", 1, {"error_type": error_type})
    
    def record_request(self):
        """Record a request count."""
        self._add_metric("request_count", 1)
    
    def _add_metric(self, metric_type: str, value: float, metadata: Optional[Dict] = None):
        """Add metric to buffer."""
        self.metrics_buffer.append({
            "twin_id": self.twin_id,
            "user_id": self.user_id,
            "metric_type": metric_type,
            "value": value,
            "metadata": metadata or {},
            "created_at": datetime.utcnow().isoformat()
        })
    
    def flush(self):
        """Flush all buffered metrics to database."""
        if not self.metrics_buffer:
            return
        
        # Add total latency
        total_ms = (time.time() - self.start_time) * 1000
        self._add_metric("total_latency_ms", total_ms)
        
        try:
            # Batch insert all metrics
            supabase.table("metrics").insert(self.metrics_buffer).execute()
        except Exception as e:
            print(f"Error flushing metrics: {e}")
        finally:
            self.metrics_buffer = []
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of collected metrics."""
        return {
            "twin_id": self.twin_id,
            "timings": self.timings,
            "total_elapsed_ms": (time.time() - self.start_time) * 1000
        }


def get_metrics_summary(twin_id: Optional[str] = None, days: int = 7) -> Dict[str, Any]:
    """
    Get metrics summary for a twin or all twins.
    
    Returns aggregated metrics for the specified time period.
    """
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    
    try:
        query = supabase.table("metrics").select("*").gte("created_at", since)
        
        if twin_id:
            query = query.eq("twin_id", twin_id)
        
        result = query.execute()
        
        if not result.data:
            return {"total_requests": 0, "metrics": {}}
        
        # Aggregate by metric type
        aggregates = {}
        for row in result.data:
            metric_type = row["metric_type"]
            value = row["value"]
            
            if metric_type not in aggregates:
                aggregates[metric_type] = {
                    "count": 0,
                    "sum": 0,
                    "min": float("inf"),
                    "max": float("-inf")
                }
            
            agg = aggregates[metric_type]
            agg["count"] += 1
            agg["sum"] += value
            agg["min"] = min(agg["min"], value)
            agg["max"] = max(agg["max"], value)
        
        # Calculate averages
        for metric_type, agg in aggregates.items():
            agg["avg"] = agg["sum"] / agg["count"] if agg["count"] > 0 else 0
        
        # Extract key metrics
        request_count = aggregates.get("request_count", {}).get("sum", 0)
        token_total = aggregates.get("tokens_total", {}).get("sum", 0)
        avg_latency = aggregates.get("total_latency_ms", {}).get("avg", 0)
        error_count = aggregates.get("error_count", {}).get("sum", 0)
        
        return {
            "total_requests": int(request_count),
            "total_tokens": int(token_total),
            "avg_latency_ms": round(avg_latency, 2),
            "error_count": int(error_count),
            "error_rate": round(error_count / request_count * 100, 2) if request_count > 0 else 0,
            "metrics": aggregates,
            "period_days": days
        }
        
    except Exception as e:
        print(f"Error getting metrics summary: {e}")
        return {"error": str(e), "total_requests": 0}


def get_usage_by_twin(days: int = 7) -> list:
    """Get token usage breakdown by twin."""
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    
    try:
        result = supabase.table("metrics").select(
            "twin_id, value"
        ).eq("metric_type", "tokens_total").gte("created_at", since).execute()
        
        if not result.data:
            return []
        
        # Aggregate by twin
        by_twin = {}
        for row in result.data:
            twin_id = row["twin_id"]
            if twin_id not in by_twin:
                by_twin[twin_id] = 0
            by_twin[twin_id] += row["value"]
        
        # Sort by usage
        return sorted(
            [{"twin_id": k, "tokens": int(v)} for k, v in by_twin.items()],
            key=lambda x: x["tokens"],
            reverse=True
        )
        
    except Exception as e:
        print(f"Error getting usage by twin: {e}")
        return []


def check_quota(tenant_id: str, quota_type: str = "daily_tokens", increment: int = 0) -> Dict[str, Any]:
    """
    Check if tenant has quota available and optionally increment usage.
    
    Returns: {"allowed": bool, "current_usage": int, "limit": int}
    """
    try:
        result = supabase.rpc("increment_quota_usage", {
            "p_tenant_id": tenant_id,
            "p_quota_type": quota_type,
            "p_increment": increment
        }).execute()
        
        if result.data and len(result.data) > 0:
            row = result.data[0]
            return {
                "allowed": row["allowed"],
                "current_usage": row["current_usage"],
                "limit": row["limit_value"],
                "remaining": row["limit_value"] - row["current_usage"]
            }
        
        # Fallback if no result
        return {"allowed": True, "current_usage": 0, "limit": 100000, "remaining": 100000}
        
    except Exception as e:
        print(f"Error checking quota: {e}")
        # On error, allow the request (fail open for beta)
        return {"allowed": True, "current_usage": 0, "limit": 100000, "remaining": 100000, "error": str(e)}


def log_service_health(service_name: str, status: str, response_time_ms: Optional[float] = None, 
                       error_message: Optional[str] = None):
    """Log a service health check result."""
    try:
        supabase.table("service_health_logs").insert({
            "service_name": service_name,
            "status": status,
            "response_time_ms": response_time_ms,
            "error_message": error_message,
            "created_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        print(f"Error logging health: {e}")


def get_recent_health(hours: int = 24) -> Dict[str, Any]:
    """Get recent health status for all services."""
    since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    
    try:
        result = supabase.table("service_health_logs").select(
            "service_name, status, response_time_ms, created_at"
        ).gte("created_at", since).order("created_at", desc=True).limit(100).execute()
        
        if not result.data:
            return {"services": {}}
        
        # Get latest status per service
        services = {}
        for row in result.data:
            svc = row["service_name"]
            if svc not in services:
                services[svc] = {
                    "status": row["status"],
                    "last_check": row["created_at"],
                    "avg_response_ms": row["response_time_ms"]
                }
        
        return {"services": services, "period_hours": hours}
        
    except Exception as e:
        print(f"Error getting health: {e}")
        return {"error": str(e), "services": {}}
