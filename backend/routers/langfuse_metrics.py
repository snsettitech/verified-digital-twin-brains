# backend/routers/langfuse_metrics.py
"""Langfuse Metrics API Endpoints

Provides metrics and analytics for dashboards.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from datetime import datetime, timedelta
import logging

from modules.auth_guard import get_current_user, require_admin
from modules.metrics_collector import get_metrics_collector

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/dashboard")
async def get_dashboard_metrics(
    hours: int = Query(default=24, ge=1, le=168),
    user=Depends(get_current_user)
):
    """
    Get full dashboard metrics.
    
    Args:
        hours: Time range in hours (default: 24, max: 168/7 days)
    
    Returns:
        Complete metrics for dashboard
    """
    try:
        collector = get_metrics_collector()
        metrics = await collector.get_full_dashboard_metrics(hours)
        return metrics
    except Exception as e:
        logger.error(f"Failed to get dashboard metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quality")
async def get_quality_metrics(
    hours: int = Query(default=24, ge=1, le=168),
    interval: str = Query(default="hour", regex="^(hour|day)$"),
    user=Depends(get_current_user)
):
    """
    Get quality score metrics over time.
    
    Args:
        hours: Time range in hours
        interval: Aggregation interval ("hour" or "day")
    
    Returns:
        Quality metrics time series
    """
    try:
        collector = get_metrics_collector()
        to_time = datetime.utcnow()
        from_time = to_time - timedelta(hours=hours)
        
        metrics = await collector.get_quality_metrics(from_time, to_time, interval)
        return {
            "time_range": {"from": from_time.isoformat(), "to": to_time.isoformat()},
            "interval": interval,
            "data": metrics
        }
    except Exception as e:
        logger.error(f"Failed to get quality metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/latency")
async def get_latency_metrics(
    hours: int = Query(default=24, ge=1, le=168),
    user=Depends(get_current_user)
):
    """
    Get latency statistics.
    
    Args:
        hours: Time range in hours
    
    Returns:
        Latency percentiles and stats
    """
    try:
        collector = get_metrics_collector()
        to_time = datetime.utcnow()
        from_time = to_time - timedelta(hours=hours)
        
        metrics = await collector.get_latency_metrics(from_time, to_time)
        return {
            "time_range": {"from": from_time.isoformat(), "to": to_time.isoformat()},
            "data": metrics
        }
    except Exception as e:
        logger.error(f"Failed to get latency metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/errors")
async def get_error_metrics(
    hours: int = Query(default=24, ge=1, le=168),
    user=Depends(get_current_user)
):
    """
    Get error statistics.
    
    Args:
        hours: Time range in hours
    
    Returns:
        Error count, rate, and breakdown by type
    """
    try:
        collector = get_metrics_collector()
        to_time = datetime.utcnow()
        from_time = to_time - timedelta(hours=hours)
        
        metrics = await collector.get_error_metrics(from_time, to_time)
        return {
            "time_range": {"from": from_time.isoformat(), "to": to_time.isoformat()},
            "data": metrics
        }
    except Exception as e:
        logger.error(f"Failed to get error metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/persona")
async def get_persona_metrics(
    hours: int = Query(default=24, ge=1, le=168),
    user=Depends(get_current_user)
):
    """
    Get persona compliance metrics.
    
    Args:
        hours: Time range in hours
    
    Returns:
        Persona audit scores and rewrite counts
    """
    try:
        collector = get_metrics_collector()
        to_time = datetime.utcnow()
        from_time = to_time - timedelta(hours=hours)
        
        metrics = await collector.get_persona_metrics(from_time, to_time)
        return {
            "time_range": {"from": from_time.isoformat(), "to": to_time.isoformat()},
            "data": metrics
        }
    except Exception as e:
        logger.error(f"Failed to get persona metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dataset")
async def get_dataset_stats(
    user=Depends(get_current_user)
):
    """Get dataset statistics."""
    try:
        collector = get_metrics_collector()
        stats = await collector.get_dataset_stats()
        return {"data": stats}
    except Exception as e:
        logger.error(f"Failed to get dataset stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/traces/search")
async def search_traces(
    query: Optional[str] = None,
    status: Optional[str] = Query(default=None, regex="^(success|error)$"),
    from_hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=50, ge=1, le=100),
    user=Depends(require_admin)
):
    """
    Search traces with filters.
    
    Args:
        query: Search query string
        status: Filter by status (success/error)
        from_hours: Time range in hours
        limit: Max results
    
    Returns:
        Matching traces
    """
    try:
        try:
            from langfuse import Langfuse
        except ImportError:
            raise HTTPException(status_code=503, detail="Langfuse not available")
        
        client = Langfuse()
        from_time = datetime.utcnow() - timedelta(hours=from_hours)
        
        traces = client.fetch_traces(
            from_timestamp=from_time.isoformat(),
            to_timestamp=datetime.utcnow().isoformat(),
            limit=limit
        )
        
        # Apply filters
        results = []
        for trace in traces:
            if status == "success" and trace.metadata.get("error"):
                continue
            if status == "error" and not trace.metadata.get("error"):
                continue
            if query and query.lower() not in str(trace.metadata).lower():
                continue
            
            results.append({
                "id": trace.id,
                "name": trace.name,
                "timestamp": trace.timestamp,
                "latency_ms": trace.latency,
                "error": trace.metadata.get("error", False),
                "metadata": trace.metadata
            })
        
        return {
            "count": len(results),
            "traces": results
        }
        
    except Exception as e:
        logger.error(f"Failed to search traces: {e}")
        raise HTTPException(status_code=500, detail=str(e))
