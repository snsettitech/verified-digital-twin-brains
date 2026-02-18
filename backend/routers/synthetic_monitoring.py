"""
Synthetic Monitoring API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import List, Optional
import logging

from modules.auth_guard import require_admin
from modules.synthetic_monitoring import (
    SyntheticMonitor,
    SyntheticCheck,
    get_synthetic_monitor
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/monitoring", tags=["synthetic-monitoring"])

_monitor_task = None


@router.get("/status")
async def get_monitoring_status(
    user=Depends(require_admin)
):
    """Get current synthetic monitoring status."""
    monitor = get_synthetic_monitor()
    return monitor.get_health_status()


@router.post("/run-checks")
async def run_checks(
    user=Depends(require_admin)
):
    """Run all synthetic checks immediately."""
    try:
        monitor = get_synthetic_monitor()
        results = await monitor.run_all_checks()
        
        return {
            "checks_run": len(results),
            "results": [
                {
                    "check_id": r.check_id,
                    "status": r.status.value,
                    "latency_ms": r.latency_ms,
                    "error": r.error,
                    "timestamp": r.timestamp,
                }
                for r in results
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to run checks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start")
async def start_monitoring(
    interval_seconds: int = 60,
    background_tasks: BackgroundTasks = None,
    user=Depends(require_admin)
):
    """Start continuous synthetic monitoring."""
    if _monitor_task is not None:
        return {"status": "already_running", "message": "Monitoring is already running"}
    
    if background_tasks:
        monitor = get_synthetic_monitor()
        background_tasks.add_task(monitor.start_monitoring, interval_seconds)
        
        return {
            "status": "started",
            "interval_seconds": interval_seconds,
            "message": "Synthetic monitoring started"
        }
    else:
        raise HTTPException(status_code=500, detail="Background tasks not available")


@router.post("/stop")
async def stop_monitoring(
    user=Depends(require_admin)
):
    """Stop continuous synthetic monitoring."""
    global _monitor_task
    
    monitor = get_synthetic_monitor()
    monitor.stop_monitoring()
    _monitor_task = None
    
    return {"status": "stopped", "message": "Synthetic monitoring stopped"}


@router.get("/checks")
async def list_checks(
    user=Depends(require_admin)
):
    """List all synthetic checks."""
    monitor = get_synthetic_monitor()
    
    return {
        "checks": [
            {
                "id": c.id,
                "name": c.name,
                "query": c.query,
                "expected_keywords": c.expected_keywords,
                "max_latency_ms": c.max_latency_ms,
                "twin_id": c.twin_id,
            }
            for c in monitor.checks.values()
        ]
    }


@router.post("/checks")
async def add_check(
    id: str,
    name: str,
    query: str,
    expected_keywords: Optional[List[str]] = None,
    max_latency_ms: int = 5000,
    twin_id: str = "default",
    user=Depends(require_admin)
):
    """Add a new synthetic check."""
    monitor = get_synthetic_monitor()
    
    check = SyntheticCheck(
        id=id,
        name=name,
        query=query,
        expected_keywords=expected_keywords or [],
        max_latency_ms=max_latency_ms,
        twin_id=twin_id
    )
    
    monitor.add_check(check)
    
    return {"status": "added", "check_id": id}


@router.delete("/checks/{check_id}")
async def remove_check(
    check_id: str,
    user=Depends(require_admin)
):
    """Remove a synthetic check."""
    monitor = get_synthetic_monitor()
    monitor.remove_check(check_id)
    
    return {"status": "removed", "check_id": check_id}
