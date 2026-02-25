# backend/modules/alerting.py
"""Langfuse Alerting System

Monitors metrics and sends alerts when thresholds are breached.
"""

import os
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertRuleType(Enum):
    ERROR_RATE = "error_rate"
    QUALITY_DROP = "quality_drop"
    LATENCY_SPIKE = "latency_spike"
    COST_SPIKE = "cost_spike"
    TRACE_VOLUME = "trace_volume"
    SCORE_DROP = "score_drop"


@dataclass
class AlertRule:
    """An alert rule configuration."""
    id: str
    name: str
    rule_type: AlertRuleType
    threshold: float
    time_window_minutes: int
    severity: AlertSeverity
    enabled: bool = True
    filters: Optional[Dict[str, Any]] = None
    cooldown_minutes: int = 30


@dataclass
class Alert:
    """An triggered alert."""
    rule_id: str
    rule_name: str
    severity: AlertSeverity
    message: str
    timestamp: str
    details: Dict[str, Any]
    trace_ids: Optional[List[str]] = None


class AlertManager:
    """Manages alert rules and checks for violations."""
    
    def __init__(self):
        self._rules: Dict[str, AlertRule] = {}
        self._alert_history: List[Alert] = []
        self._last_alert_time: Dict[str, datetime] = {}
        self._langfuse_available = False
        self._webhook_url: Optional[str] = os.getenv("ALERT_WEBHOOK_URL")
        self._init_langfuse()
        self._load_default_rules()
    
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
                logger.info("Alert Manager initialized")
        except Exception as e:
            logger.warning(f"Langfuse not available for alerting: {e}")
    
    def _load_default_rules(self):
        """Load default alert rules."""
        default_rules = [
            AlertRule(
                id="error_rate_high",
                name="High Error Rate",
                rule_type=AlertRuleType.ERROR_RATE,
                threshold=0.1,  # 10% error rate
                time_window_minutes=5,
                severity=AlertSeverity.ERROR
            ),
            AlertRule(
                id="quality_drop",
                name="Quality Score Drop",
                rule_type=AlertRuleType.QUALITY_DROP,
                threshold=0.7,  # Below 0.7 average
                time_window_minutes=10,
                severity=AlertSeverity.WARNING
            ),
            AlertRule(
                id="latency_p95_high",
                name="High P95 Latency",
                rule_type=AlertRuleType.LATENCY_SPIKE,
                threshold=5000,  # 5 seconds
                time_window_minutes=10,
                severity=AlertSeverity.WARNING
            ),
            AlertRule(
                id="cost_spike",
                name="Cost Spike",
                rule_type=AlertRuleType.COST_SPIKE,
                threshold=2.0,  # 2x normal
                time_window_minutes=30,
                severity=AlertSeverity.WARNING
            ),
            AlertRule(
                id="faithfulness_drop",
                name="Faithfulness Score Drop",
                rule_type=AlertRuleType.SCORE_DROP,
                threshold=0.6,
                time_window_minutes=10,
                severity=AlertSeverity.ERROR,
                filters={"score_name": "faithfulness"}
            )
        ]
        
        for rule in default_rules:
            self._rules[rule.id] = rule
    
    def add_rule(self, rule: AlertRule):
        """Add a new alert rule."""
        self._rules[rule.id] = rule
        logger.info(f"Added alert rule: {rule.name}")
    
    def remove_rule(self, rule_id: str):
        """Remove an alert rule."""
        if rule_id in self._rules:
            del self._rules[rule_id]
            logger.info(f"Removed alert rule: {rule_id}")
    
    def update_rule(self, rule_id: str, updates: Dict[str, Any]):
        """Update an alert rule."""
        if rule_id in self._rules:
            rule = self._rules[rule_id]
            for key, value in updates.items():
                if hasattr(rule, key):
                    setattr(rule, key, value)
            logger.info(f"Updated alert rule: {rule_id}")
    
    def get_rules(self) -> List[AlertRule]:
        """Get all alert rules."""
        return list(self._rules.values())
    
    def get_rule(self, rule_id: str) -> Optional[AlertRule]:
        """Get a specific alert rule."""
        return self._rules.get(rule_id)
    
    async def check_all_rules(self) -> List[Alert]:
        """Check all enabled rules and return triggered alerts."""
        if not self._langfuse_available:
            return []
        
        alerts = []
        
        for rule in self._rules.values():
            if not rule.enabled:
                continue
            
            # Check cooldown
            if self._is_in_cooldown(rule.id):
                continue
            
            try:
                alert = await self._check_rule(rule)
                if alert:
                    alerts.append(alert)
                    self._last_alert_time[rule.id] = datetime.utcnow()
            except Exception as e:
                logger.error(f"Failed to check rule {rule.id}: {e}")
        
        # Send notifications
        for alert in alerts:
            await self._send_notification(alert)
        
        self._alert_history.extend(alerts)
        return alerts
    
    def _is_in_cooldown(self, rule_id: str) -> bool:
        """Check if rule is in cooldown period."""
        if rule_id not in self._last_alert_time:
            return False
        
        rule = self._rules.get(rule_id)
        if not rule:
            return False
        
        cooldown_end = self._last_alert_time[rule_id] + timedelta(minutes=rule.cooldown_minutes)
        return datetime.utcnow() < cooldown_end
    
    async def _check_rule(self, rule: AlertRule) -> Optional[Alert]:
        """Check a single rule and return alert if triggered."""
        if rule.rule_type == AlertRuleType.ERROR_RATE:
            return await self._check_error_rate(rule)
        elif rule.rule_type == AlertRuleType.QUALITY_DROP:
            return await self._check_quality_drop(rule)
        elif rule.rule_type == AlertRuleType.LATENCY_SPIKE:
            return await self._check_latency_spike(rule)
        elif rule.rule_type == AlertRuleType.SCORE_DROP:
            return await self._check_score_drop(rule)
        # Add more check types as needed
        return None
    
    async def _check_error_rate(self, rule: AlertRule) -> Optional[Alert]:
        """Check error rate in time window."""
        from_time = datetime.utcnow() - timedelta(minutes=rule.time_window_minutes)
        
        # Query Langfuse for traces with errors
        traces = self._client.fetch_traces(
            from_timestamp=from_time.isoformat(),
            to_timestamp=datetime.utcnow().isoformat()
        )
        
        total = len(traces)
        if total == 0:
            return None
        
        errors = sum(1 for t in traces if t.metadata.get("error", False))
        error_rate = errors / total
        
        if error_rate > rule.threshold:
            return Alert(
                rule_id=rule.id,
                rule_name=rule.name,
                severity=rule.severity,
                message=f"Error rate is {error_rate:.1%} (threshold: {rule.threshold:.1%})",
                timestamp=datetime.utcnow().isoformat(),
                details={
                    "error_rate": error_rate,
                    "total_traces": total,
                    "error_count": errors,
                    "time_window_minutes": rule.time_window_minutes
                }
            )
        return None
    
    async def _check_quality_drop(self, rule: AlertRule) -> Optional[Alert]:
        """Check average quality score in time window."""
        from_time = datetime.utcnow() - timedelta(minutes=rule.time_window_minutes)
        
        # Query Langfuse for overall_quality scores
        scores = self._client.fetch_scores(
            name="overall_quality",
            from_timestamp=from_time.isoformat(),
            to_timestamp=datetime.utcnow().isoformat()
        )
        
        if not scores:
            return None
        
        avg_score = sum(s.value for s in scores) / len(scores)
        
        if avg_score < rule.threshold:
            return Alert(
                rule_id=rule.id,
                rule_name=rule.name,
                severity=rule.severity,
                message=f"Average quality score is {avg_score:.2f} (threshold: {rule.threshold:.2f})",
                timestamp=datetime.utcnow().isoformat(),
                details={
                    "avg_score": avg_score,
                    "score_count": len(scores),
                    "time_window_minutes": rule.time_window_minutes
                }
            )
        return None
    
    async def _check_latency_spike(self, rule: AlertRule) -> Optional[Alert]:
        """Check P95 latency in time window."""
        from_time = datetime.utcnow() - timedelta(minutes=rule.time_window_minutes)
        
        traces = self._client.fetch_traces(
            from_timestamp=from_time.isoformat(),
            to_timestamp=datetime.utcnow().isoformat()
        )
        
        if not traces:
            return None
        
        latencies = [t.latency for t in traces if hasattr(t, 'latency') and t.latency]
        if not latencies:
            return None
        
        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]
        
        if p95 > rule.threshold:
            return Alert(
                rule_id=rule.id,
                rule_name=rule.name,
                severity=rule.severity,
                message=f"P95 latency is {p95:.0f}ms (threshold: {rule.threshold:.0f}ms)",
                timestamp=datetime.utcnow().isoformat(),
                details={
                    "p95_latency_ms": p95,
                    "trace_count": len(traces),
                    "time_window_minutes": rule.time_window_minutes
                }
            )
        return None
    
    async def _check_score_drop(self, rule: AlertRule) -> Optional[Alert]:
        """Check specific score drop in time window."""
        score_name = rule.filters.get("score_name", "overall_quality") if rule.filters else "overall_quality"
        from_time = datetime.utcnow() - timedelta(minutes=rule.time_window_minutes)
        
        scores = self._client.fetch_scores(
            name=score_name,
            from_timestamp=from_time.isoformat(),
            to_timestamp=datetime.utcnow().isoformat()
        )
        
        if not scores:
            return None
        
        avg_score = sum(s.value for s in scores) / len(scores)
        
        if avg_score < rule.threshold:
            return Alert(
                rule_id=rule.id,
                rule_name=rule.name,
                severity=rule.severity,
                message=f"{score_name} score is {avg_score:.2f} (threshold: {rule.threshold:.2f})",
                timestamp=datetime.utcnow().isoformat(),
                details={
                    "score_name": score_name,
                    "avg_score": avg_score,
                    "score_count": len(scores),
                    "time_window_minutes": rule.time_window_minutes
                }
            )
        return None
    
    async def _send_notification(self, alert: Alert):
        """Send alert notification via webhook."""
        if not self._webhook_url:
            logger.info(f"Alert triggered (no webhook): {alert.message}")
            return
        
        try:
            import aiohttp
            
            payload = {
                "alert_id": f"{alert.rule_id}_{alert.timestamp}",
                "rule_name": alert.rule_name,
                "severity": alert.severity.value,
                "message": alert.message,
                "timestamp": alert.timestamp,
                "details": alert.details
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status >= 400:
                        logger.error(f"Failed to send alert: {response.status}")
                    else:
                        logger.info(f"Alert sent: {alert.message}")
                        
        except Exception as e:
            logger.error(f"Failed to send alert notification: {e}")
    
    def get_alert_history(
        self,
        from_time: Optional[datetime] = None,
        severity: Optional[AlertSeverity] = None,
        limit: int = 100
    ) -> List[Alert]:
        """Get alert history with filters."""
        alerts = self._alert_history
        
        if from_time:
            alerts = [a for a in alerts if datetime.fromisoformat(a.timestamp) >= from_time]
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        return alerts[-limit:]


# Singleton instance
_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Get or create the singleton alert manager."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


# Background task for periodic checks
async def run_periodic_checks(interval_minutes: int = 5):
    """Run alert checks periodically."""
    manager = get_alert_manager()
    
    while True:
        try:
            alerts = await manager.check_all_rules()
            if alerts:
                logger.info(f"Triggered {len(alerts)} alerts")
        except Exception as e:
            logger.error(f"Periodic alert check failed: {e}")
        
        await asyncio.sleep(interval_minutes * 60)
