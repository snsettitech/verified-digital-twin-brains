# backend/routers/alerts.py
"""Alerts API Endpoints

Manage alert rules and view alert history.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging

from modules.auth_guard import get_current_user, require_admin
from modules.alerting import (
    AlertManager,
    AlertRule,
    AlertRuleType,
    AlertSeverity,
    get_alert_manager,
    run_periodic_checks
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/alerts", tags=["alerts"])


# Background task control
_check_task = None


@router.get("/rules", response_model=List[Dict[str, Any]])
async def list_alert_rules(
    user=Depends(require_admin)
):
    """List all alert rules."""
    manager = get_alert_manager()
    rules = manager.get_rules()
    
    return [
        {
            "id": r.id,
            "name": r.name,
            "rule_type": r.rule_type.value,
            "threshold": r.threshold,
            "time_window_minutes": r.time_window_minutes,
            "severity": r.severity.value,
            "enabled": r.enabled,
            "cooldown_minutes": r.cooldown_minutes,
            "filters": r.filters
        }
        for r in rules
    ]


@router.post("/rules", response_model=Dict[str, Any])
async def create_alert_rule(
    rule_data: Dict[str, Any],
    user=Depends(require_admin)
):
    """Create a new alert rule."""
    try:
        rule = AlertRule(
            id=rule_data.get("id", f"rule_{datetime.utcnow().timestamp()}"),
            name=rule_data["name"],
            rule_type=AlertRuleType(rule_data["rule_type"]),
            threshold=rule_data["threshold"],
            time_window_minutes=rule_data["time_window_minutes"],
            severity=AlertSeverity(rule_data["severity"]),
            enabled=rule_data.get("enabled", True),
            cooldown_minutes=rule_data.get("cooldown_minutes", 30),
            filters=rule_data.get("filters")
        )
        
        manager = get_alert_manager()
        manager.add_rule(rule)
        
        return {
            "status": "success",
            "rule_id": rule.id,
            "message": f"Alert rule '{rule.name}' created"
        }
        
    except Exception as e:
        logger.error(f"Failed to create alert rule: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/rules/{rule_id}", response_model=Dict[str, Any])
async def update_alert_rule(
    rule_id: str,
    updates: Dict[str, Any],
    user=Depends(require_admin)
):
    """Update an alert rule."""
    manager = get_alert_manager()
    rule = manager.get_rule(rule_id)
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    # Convert enum strings to enums
    if "rule_type" in updates:
        updates["rule_type"] = AlertRuleType(updates["rule_type"])
    if "severity" in updates:
        updates["severity"] = AlertSeverity(updates["severity"])
    
    manager.update_rule(rule_id, updates)
    
    return {
        "status": "success",
        "rule_id": rule_id,
        "message": f"Alert rule '{rule.name}' updated"
    }


@router.delete("/rules/{rule_id}", response_model=Dict[str, Any])
async def delete_alert_rule(
    rule_id: str,
    user=Depends(require_admin)
):
    """Delete an alert rule."""
    manager = get_alert_manager()
    rule = manager.get_rule(rule_id)
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    manager.remove_rule(rule_id)
    
    return {
        "status": "success",
        "rule_id": rule_id,
        "message": f"Alert rule '{rule.name}' deleted"
    }


@router.post("/check", response_model=List[Dict[str, Any]])
async def run_alert_check(
    user=Depends(require_admin)
):
    """Run alert check manually."""
    try:
        manager = get_alert_manager()
        alerts = await manager.check_all_rules()
        
        return [
            {
                "rule_id": a.rule_id,
                "rule_name": a.rule_name,
                "severity": a.severity.value,
                "message": a.message,
                "timestamp": a.timestamp,
                "details": a.details
            }
            for a in alerts
        ]
        
    except Exception as e:
        logger.error(f"Alert check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=List[Dict[str, Any]])
async def get_alert_history(
    hours: Optional[int] = 24,
    severity: Optional[str] = None,
    limit: int = 100,
    user=Depends(require_admin)
):
    """
    Get alert history.
    
    Args:
        hours: Number of hours to look back
        severity: Filter by severity (info, warning, error, critical)
        limit: Maximum number of alerts to return
    """
    try:
        manager = get_alert_manager()
        
        from_time = datetime.utcnow() - timedelta(hours=hours) if hours else None
        severity_enum = AlertSeverity(severity) if severity else None
        
        alerts = manager.get_alert_history(from_time, severity_enum, limit)
        
        return [
            {
                "rule_id": a.rule_id,
                "rule_name": a.rule_name,
                "severity": a.severity.value,
                "message": a.message,
                "timestamp": a.timestamp,
                "details": a.details
            }
            for a in alerts
        ]
        
    except Exception as e:
        logger.error(f"Failed to get alert history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start-monitoring", response_model=Dict[str, Any])
async def start_monitoring(
    interval_minutes: int = 5,
    background_tasks: BackgroundTasks = None,
    user=Depends(require_admin)
):
    """
    Start background alert monitoring.
    
    Args:
        interval_minutes: How often to check rules (default: 5 minutes)
    """
    if _check_task is not None:
        return {
            "status": "already_running",
            "message": "Alert monitoring is already running"
        }
    
    # Start background task
    if background_tasks:
        background_tasks.add_task(run_periodic_checks, interval_minutes)
        
        return {
            "status": "started",
            "interval_minutes": interval_minutes,
            "message": "Alert monitoring started"
        }
    else:
        raise HTTPException(status_code=500, detail="Background tasks not available")


@router.get("/rule-types", response_model=List[Dict[str, str]])
async def get_rule_types(
    user=Depends(get_current_user)
):
    """Get available alert rule types."""
    return [
        {"type": t.value, "description": _get_rule_type_description(t)}
        for t in AlertRuleType
    ]


@router.get("/severities", response_model=List[Dict[str, str]])
async def get_severities(
    user=Depends(get_current_user)
):
    """Get available alert severities."""
    return [
        {"severity": s.value, "description": s.value.upper()}
        for s in AlertSeverity
    ]


def _get_rule_type_description(rule_type: AlertRuleType) -> str:
    """Get description for rule type."""
    descriptions = {
        AlertRuleType.ERROR_RATE: "Monitor error rate percentage",
        AlertRuleType.QUALITY_DROP: "Monitor average quality score",
        AlertRuleType.LATENCY_SPIKE: "Monitor P95 latency",
        AlertRuleType.COST_SPIKE: "Monitor token usage/cost",
        AlertRuleType.TRACE_VOLUME: "Monitor trace volume",
        AlertRuleType.SCORE_DROP: "Monitor specific score drop"
    }
    return descriptions.get(rule_type, rule_type.value)
