"""
Trace Comparison API - Compare two traces side-by-side
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any
import logging

from modules.auth_guard import require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/traces/compare", tags=["trace-compare"])


@router.get("/{trace_id_1}/{trace_id_2}")
async def compare_traces(
    trace_id_1: str,
    trace_id_2: str,
    user=Depends(require_admin)
):
    """
    Compare two traces side-by-side.
    
    Returns detailed comparison of:
    - Latency differences
    - Score differences
    - Metadata differences
    - Error comparison
    """
    try:
        try:
            from langfuse import Langfuse
        except ImportError:
            raise HTTPException(status_code=503, detail="Langfuse not available")
        
        client = Langfuse()
        
        # Fetch both traces
        trace1 = client.fetch_trace(trace_id_1)
        trace2 = client.fetch_trace(trace_id_2)
        
        if not trace1 or not trace2:
            raise HTTPException(status_code=404, detail="One or both traces not found")
        
        # Fetch scores for both
        scores1 = client.fetch_scores(trace_id=trace_id_1)
        scores2 = client.fetch_scores(trace_id=trace_id_2)
        
        # Build comparison
        comparison = {
            "trace_1": {
                "id": trace_id_1,
                "name": trace1.name,
                "timestamp": trace1.timestamp,
                "latency_ms": getattr(trace1, 'latency', 0),
                "error": trace1.metadata.get("error", False),
                "metadata": trace1.metadata,
                "scores": {s.name: s.value for s in scores1},
            },
            "trace_2": {
                "id": trace_id_2,
                "name": trace2.name,
                "timestamp": trace2.timestamp,
                "latency_ms": getattr(trace2, 'latency', 0),
                "error": trace2.metadata.get("error", False),
                "metadata": trace2.metadata,
                "scores": {s.name: s.value for s in scores2},
            },
            "differences": _calculate_differences(trace1, trace2, scores1, scores2),
        }
        
        return comparison
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Trace comparison failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _calculate_differences(trace1, trace2, scores1, scores2):
    """Calculate differences between two traces."""
    diffs = {
        "latency_ms": getattr(trace2, 'latency', 0) - getattr(trace1, 'latency', 0),
    }
    
    # Compare scores
    scores1_dict = {s.name: s.value for s in scores1}
    scores2_dict = {s.name: s.value for s in scores2}
    
    all_score_names = set(scores1_dict.keys()) | set(scores2_dict.keys())
    score_diffs = {}
    
    for name in all_score_names:
        s1 = scores1_dict.get(name, 0)
        s2 = scores2_dict.get(name, 0)
        score_diffs[name] = round(s2 - s1, 3)
    
    diffs["scores"] = score_diffs
    
    # Error comparison
    err1 = trace1.metadata.get("error", False)
    err2 = trace2.metadata.get("error", False)
    diffs["error_changed"] = err1 != err2
    diffs["regression"] = not err1 and err2  # Was ok, now has error
    
    return diffs


@router.post("/batch")
async def compare_batch(
    trace_ids: List[str],
    user=Depends(require_admin)
):
    """
    Compare multiple traces in a batch.
    Returns summary statistics across all traces.
    """
    try:
        try:
            from langfuse import Langfuse
        except ImportError:
            raise HTTPException(status_code=503, detail="Langfuse not available")
        
        client = Langfuse()
        
        traces = []
        for tid in trace_ids:
            try:
                trace = client.fetch_trace(tid)
                if trace:
                    traces.append({
                        "id": tid,
                        "name": trace.name,
                        "latency_ms": getattr(trace, 'latency', 0),
                        "error": trace.metadata.get("error", False),
                    })
            except Exception:
                pass
        
        if not traces:
            return {"error": "No valid traces found"}
        
        # Calculate statistics
        latencies = [t["latency_ms"] for t in traces]
        errors = sum(1 for t in traces if t["error"])
        
        return {
            "count": len(traces),
            "latency_stats": {
                "avg": sum(latencies) / len(latencies),
                "min": min(latencies),
                "max": max(latencies),
            },
            "error_count": errors,
            "error_rate": errors / len(traces),
            "traces": traces,
        }
        
    except Exception as e:
        logger.error(f"Batch comparison failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
