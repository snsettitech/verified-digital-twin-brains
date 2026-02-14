"""
Dashboard API - Unified endpoint for dashboard data
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from datetime import datetime, timedelta
import logging

from modules.auth_guard import get_current_user
from modules.metrics_collector import get_metrics_collector
from modules.langfuse_client import is_langfuse_available

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview")
async def get_overview(
    hours: int = 24,
    user=Depends(get_current_user)
):
    """Get dashboard overview data."""
    try:
        collector = get_metrics_collector()
        
        to_time = datetime.utcnow()
        from_time = to_time - timedelta(hours=hours)
        
        # Fetch all metrics in parallel
        quality = await collector.get_quality_metrics(from_time, to_time, interval="hour")
        latency = await collector.get_latency_metrics(from_time, to_time)
        errors = await collector.get_error_metrics(from_time, to_time)
        persona = await collector.get_persona_metrics(from_time, to_time)
        datasets = await collector.get_dataset_stats()
        
        # Calculate trends
        current_quality = quality[-1]["avg_score"] if quality else 0
        prev_quality = quality[0]["avg_score"] if len(quality) > 1 else current_quality
        quality_trend = current_quality - prev_quality
        
        return {
            "time_range": {"hours": hours, "from": from_time.isoformat(), "to": to_time.isoformat()},
            "health": {
                "status": "healthy" if errors.get("error_rate", 0) < 5 else "degraded",
                "error_rate": errors.get("error_rate", 0),
                "total_requests": errors.get("total_traces", 0),
            },
            "quality": {
                "current_score": round(current_quality, 2),
                "trend": round(quality_trend, 3),
                "history": quality,
            },
            "latency": latency,
            "errors": errors,
            "persona": persona,
            "datasets": datasets,
            "langfuse_connected": is_langfuse_available(),
        }
    except Exception as e:
        logger.error(f"Dashboard overview failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/traces/recent")
async def get_recent_traces(
    limit: int = 20,
    status: Optional[str] = None,
    user=Depends(get_current_user)
):
    """Get recent traces for dashboard."""
    try:
        try:
            from langfuse import Langfuse
        except ImportError:
            return {"traces": [], "count": 0, "error": "Langfuse not available"}
        
        client = Langfuse()
        from_time = datetime.utcnow() - timedelta(hours=24)
        
        traces = client.fetch_traces(
            from_timestamp=from_time.isoformat(),
            to_timestamp=datetime.utcnow().isoformat(),
            limit=limit * 2  # Fetch more for filtering
        )
        
        results = []
        for trace in traces:
            # Apply status filter
            has_error = trace.metadata.get("error", False)
            if status == "success" and has_error:
                continue
            if status == "error" and not has_error:
                continue
            
            results.append({
                "id": trace.id,
                "name": trace.name,
                "timestamp": trace.timestamp,
                "latency_ms": getattr(trace, 'latency', 0),
                "error": has_error,
                "user_id": trace.metadata.get("user_id"),
                "session_id": trace.metadata.get("session_id"),
            })
            
            if len(results) >= limit:
                break
        
        return {"traces": results, "count": len(results)}
        
    except Exception as e:
        logger.error(f"Failed to get recent traces: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/active")
async def get_active_alerts(
    user=Depends(get_current_user)
):
    """Get currently active alerts."""
    try:
        from modules.alerting import get_alert_manager
        
        manager = get_alert_manager()
        recent_alerts = manager.get_alert_history(
            from_time=datetime.utcnow() - timedelta(hours=24),
            limit=10
        )
        
        return {
            "alerts": [
                {
                    "rule_id": a.rule_id,
                    "rule_name": a.rule_name,
                    "severity": a.severity.value,
                    "message": a.message,
                    "timestamp": a.timestamp,
                }
                for a in recent_alerts
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get active alerts: {e}")
        return {"alerts": []}
