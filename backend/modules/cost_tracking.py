"""
Cost Optimization & Token Tracking

Track token usage and costs for optimization.
"""
import os
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# Token costs per 1K tokens (as of 2024)
TOKEN_COSTS = {
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "claude-3-opus": {"input": 0.015, "output": 0.075},
    "claude-3-sonnet": {"input": 0.003, "output": 0.015},
    "llama-3.3-70b": {"input": 0.0009, "output": 0.0009},  # Cerebras
}


@dataclass
class TokenUsage:
    """Token usage for a single request."""
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    timestamp: str


class CostTracker:
    """Track token usage and costs."""
    
    def __init__(self):
        self._langfuse_available = False
        self._init_langfuse()
    
    def _init_langfuse(self):
        """Initialize Langfuse client."""
        try:
            from langfuse import Langfuse
            
            public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
            secret_key = os.getenv("LANGFUSE_SECRET_KEY")
            
            if public_key and secret_key:
                self._client = Langfuse()
                self._langfuse_available = True
        except Exception:
            pass
    
    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost in USD for token usage."""
        costs = TOKEN_COSTS.get(model, TOKEN_COSTS["gpt-4o"])
        
        input_cost = (input_tokens / 1000) * costs["input"]
        output_cost = (output_tokens / 1000) * costs["output"]
        
        return input_cost + output_cost
    
    def track_usage(
        self,
        trace_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        metadata: Optional[Dict] = None
    ):
        """Track token usage for a request."""
        cost = self.calculate_cost(model, input_tokens, output_tokens)
        
        # Log to Langfuse
        if self._langfuse_available:
            try:
                self._client.score(
                    trace_id=trace_id,
                    name="input_tokens",
                    value=input_tokens,
                    data_type="NUMERIC"
                )
                self._client.score(
                    trace_id=trace_id,
                    name="output_tokens",
                    value=output_tokens,
                    data_type="NUMERIC"
                )
                self._client.score(
                    trace_id=trace_id,
                    name="cost_usd",
                    value=cost,
                    data_type="NUMERIC"
                )
                self._client.flush()
            except Exception as e:
                logger.debug(f"Failed to log cost to Langfuse: {e}")
        
        return TokenUsage(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            timestamp=datetime.utcnow().isoformat()
        )
    
    async def get_cost_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get cost summary for a time period."""
        if not self._langfuse_available:
            return {"error": "Langfuse not available"}
        
        try:
            from_time = datetime.utcnow() - timedelta(hours=hours)
            
            # Fetch traces
            traces = self._client.fetch_traces(
                from_timestamp=from_time.isoformat(),
                to_timestamp=datetime.utcnow().isoformat()
            )
            
            total_cost = 0.0
            total_input_tokens = 0
            total_output_tokens = 0
            model_breakdown = {}
            
            for trace in traces:
                # Get scores for this trace
                try:
                    scores = self._client.fetch_scores(trace_id=trace.id)
                    cost_score = next((s for s in scores if s.name == "cost_usd"), None)
                    input_score = next((s for s in scores if s.name == "input_tokens"), None)
                    output_score = next((s for s in scores if s.name == "output_tokens"), None)
                    
                    if cost_score:
                        total_cost += cost_score.value
                    if input_score:
                        total_input_tokens += int(input_score.value)
                    if output_score:
                        total_output_tokens += int(output_score.value)
                    
                    # Track by model
                    model = trace.metadata.get("model", "unknown")
                    if model not in model_breakdown:
                        model_breakdown[model] = {"cost": 0, "count": 0}
                    if cost_score:
                        model_breakdown[model]["cost"] += cost_score.value
                    model_breakdown[model]["count"] += 1
                    
                except Exception:
                    pass
            
            return {
                "time_range_hours": hours,
                "total_cost_usd": round(total_cost, 4),
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "total_tokens": total_input_tokens + total_output_tokens,
                "request_count": len(traces),
                "avg_cost_per_request": round(total_cost / len(traces), 4) if traces else 0,
                "model_breakdown": model_breakdown,
                "projected_monthly_cost": round(total_cost * (720 / hours), 2),  # 720 hours in 30 days
            }
            
        except Exception as e:
            logger.error(f"Failed to get cost summary: {e}")
            return {"error": str(e)}
    
    def get_optimization_suggestions(self, usage_data: Dict) -> List[str]:
        """Get cost optimization suggestions."""
        suggestions = []
        
        # Check if using expensive models
        model_breakdown = usage_data.get("model_breakdown", {})
        if "gpt-4" in model_breakdown and "gpt-4o-mini" not in model_breakdown:
            suggestions.append("Consider using gpt-4o-mini for non-critical tasks")
        
        # Check token efficiency
        total_tokens = usage_data.get("total_tokens", 0)
        request_count = usage_data.get("request_count", 0)
        if request_count > 0:
            avg_tokens = total_tokens / request_count
            if avg_tokens > 4000:
                suggestions.append("High average token count - consider prompt optimization")
        
        # Check cost per request
        avg_cost = usage_data.get("avg_cost_per_request", 0)
        if avg_cost > 0.05:
            suggestions.append("High cost per request - review model selection")
        
        return suggestions


# Singleton instance
_tracker: Optional[CostTracker] = None


def get_cost_tracker() -> CostTracker:
    """Get or create the singleton tracker."""
    global _tracker
    if _tracker is None:
        _tracker = CostTracker()
    return _tracker
