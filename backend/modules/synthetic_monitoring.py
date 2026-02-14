"""
Synthetic Monitoring

Run continuous test queries to monitor system health.
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class CheckStatus(Enum):
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"


@dataclass
class SyntheticCheck:
    """A synthetic monitoring check."""
    id: str
    name: str
    query: str
    expected_keywords: List[str]
    max_latency_ms: int
    twin_id: str


@dataclass
class CheckResult:
    """Result of a synthetic check."""
    check_id: str
    status: CheckStatus
    latency_ms: int
    response: str
    error: Optional[str] = None
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()


class SyntheticMonitor:
    """Synthetic monitoring for continuous health checks."""
    
    DEFAULT_CHECKS = [
        SyntheticCheck(
            id="health_basic_qa",
            name="Basic Q&A Response",
            query="What is the capital of France?",
            expected_keywords=["Paris"],
            max_latency_ms=5000,
            twin_id="default"
        ),
        SyntheticCheck(
            id="health_citation_check",
            name="Citation Check",
            query="What is our company's mission?",
            expected_keywords=[],
            max_latency_ms=8000,
            twin_id="default"
        ),
        SyntheticCheck(
            id="health_smalltalk",
            name="Smalltalk Response",
            query="Hello, how are you?",
            expected_keywords=[],
            max_latency_ms=3000,
            twin_id="default"
        ),
    ]
    
    def __init__(self):
        self.checks: Dict[str, SyntheticCheck] = {}
        self.results: List[CheckResult] = []
        self._running = False
        self._load_default_checks()
    
    def _load_default_checks(self):
        """Load default checks."""
        for check in self.DEFAULT_CHECKS:
            self.checks[check.id] = check
    
    def add_check(self, check: SyntheticCheck):
        """Add a synthetic check."""
        self.checks[check.id] = check
        logger.info(f"Added synthetic check: {check.id}")
    
    def remove_check(self, check_id: str):
        """Remove a synthetic check."""
        if check_id in self.checks:
            del self.checks[check_id]
    
    async def run_check(self, check: SyntheticCheck) -> CheckResult:
        """Run a single synthetic check."""
        import time
        
        start_time = time.time()
        
        try:
            # Call the chat endpoint
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                # This would need to be configured with actual endpoint
                url = f"http://localhost:8000/chat/{check.twin_id}"
                
                async with session.post(
                    url,
                    json={"query": check.query},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    latency_ms = int((time.time() - start_time) * 1000)
                    
                    if response.status != 200:
                        return CheckResult(
                            check_id=check.id,
                            status=CheckStatus.FAIL,
                            latency_ms=latency_ms,
                            response="",
                            error=f"HTTP {response.status}"
                        )
                    
                    data = await response.json()
                    response_text = data.get("response", "")
                    
                    # Check expected keywords
                    missing_keywords = [
                        kw for kw in check.expected_keywords
                        if kw.lower() not in response_text.lower()
                    ]
                    
                    # Determine status
                    if latency_ms > check.max_latency_ms:
                        status = CheckStatus.WARNING
                    elif missing_keywords:
                        status = CheckStatus.WARNING
                    else:
                        status = CheckStatus.PASS
                    
                    return CheckResult(
                        check_id=check.id,
                        status=status,
                        latency_ms=latency_ms,
                        response=response_text[:200],
                    )
                    
        except asyncio.TimeoutError:
            latency_ms = int((time.time() - start_time) * 1000)
            return CheckResult(
                check_id=check.id,
                status=CheckStatus.FAIL,
                latency_ms=latency_ms,
                response="",
                error="Timeout"
            )
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return CheckResult(
                check_id=check.id,
                status=CheckStatus.FAIL,
                latency_ms=latency_ms,
                response="",
                error=str(e)
            )
    
    async def run_all_checks(self) -> List[CheckResult]:
        """Run all synthetic checks."""
        results = []
        
        for check in self.checks.values():
            result = await self.run_check(check)
            results.append(result)
            self.results.append(result)
        
        # Keep only last 1000 results
        self.results = self.results[-1000:]
        
        return results
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status from recent results."""
        if not self.results:
            return {"status": "unknown", "checks": []}
        
        # Get last result for each check
        latest = {}
        for result in reversed(self.results):
            if result.check_id not in latest:
                latest[result.check_id] = result
        
        check_statuses = [
            {
                "id": r.check_id,
                "status": r.status.value,
                "latency_ms": r.latency_ms,
                "error": r.error,
                "timestamp": r.timestamp,
            }
            for r in latest.values()
        ]
        
        # Overall status
        any_fail = any(s["status"] == "fail" for s in check_statuses)
        any_warning = any(s["status"] == "warning" for s in check_statuses)
        
        if any_fail:
            overall_status = "degraded"
        elif any_warning:
            overall_status = "warning"
        else:
            overall_status = "healthy"
        
        return {
            "status": overall_status,
            "checks": check_statuses,
            "last_check_time": max(r.timestamp for r in latest.values()) if latest else None,
        }
    
    async def start_monitoring(self, interval_seconds: int = 60):
        """Start continuous monitoring."""
        self._running = True
        logger.info(f"Starting synthetic monitoring (interval: {interval_seconds}s)")
        
        while self._running:
            try:
                await self.run_all_checks()
                logger.debug("Completed synthetic check cycle")
            except Exception as e:
                logger.error(f"Synthetic monitoring error: {e}")
            
            await asyncio.sleep(interval_seconds)
    
    def stop_monitoring(self):
        """Stop continuous monitoring."""
        self._running = False
        logger.info("Stopped synthetic monitoring")


# Singleton instance
_monitor: Optional[SyntheticMonitor] = None


def get_synthetic_monitor() -> SyntheticMonitor:
    """Get or create the singleton monitor."""
    global _monitor
    if _monitor is None:
        _monitor = SyntheticMonitor()
    return _monitor
