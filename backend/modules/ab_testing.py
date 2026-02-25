"""
A/B Testing Framework for Digital Twin

Systematically compare prompts, models, or configurations.
"""
import os
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ABTestStatus(Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    PAUSED = "paused"


@dataclass
class ABTestVariant:
    """A single variant in an A/B test."""
    name: str
    config: Dict[str, Any]  # prompt_name, model, temperature, etc.
    traffic_percentage: float  # 0.0 to 1.0


@dataclass
class ABTestResult:
    """Results for a single variant."""
    variant_name: str
    sample_size: int
    avg_quality_score: float
    avg_latency_ms: float
    error_rate: float
    conversion_rate: Optional[float] = None  # For conversion tracking


class ABTestingFramework:
    """Framework for running A/B tests."""
    
    def __init__(self):
        self._tests: Dict[str, Dict] = {}  # In-memory storage
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
                logger.info("A/B Testing Framework initialized")
        except Exception as e:
            logger.warning(f"Langfuse not available for A/B testing: {e}")
    
    def create_test(
        self,
        name: str,
        description: str,
        variants: List[ABTestVariant],
        success_metric: str = "overall_quality",
        min_sample_size: int = 100
    ) -> str:
        """
        Create a new A/B test.
        
        Args:
            name: Test name
            description: Test description
            variants: List of variants to test
            success_metric: Metric to determine winner
            min_sample_size: Minimum samples before declaring winner
        
        Returns:
            Test ID
        """
        test_id = f"abtest_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{name}"
        
        # Validate traffic percentages sum to 1.0
        total_traffic = sum(v.traffic_percentage for v in variants)
        if abs(total_traffic - 1.0) > 0.01:
            raise ValueError(f"Traffic percentages must sum to 1.0, got {total_traffic}")
        
        test = {
            "id": test_id,
            "name": name,
            "description": description,
            "variants": [
                {
                    "name": v.name,
                    "config": v.config,
                    "traffic_percentage": v.traffic_percentage,
                }
                for v in variants
            ],
            "success_metric": success_metric,
            "min_sample_size": min_sample_size,
            "status": ABTestStatus.RUNNING.value,
            "created_at": datetime.utcnow().isoformat(),
            "results": {v.name: {"sample_size": 0, "scores": [], "latencies": [], "errors": 0} for v in variants},
        }
        
        self._tests[test_id] = test
        logger.info(f"Created A/B test: {test_id}")
        
        return test_id
    
    def get_variant_for_request(self, test_id: str, user_id: Optional[str] = None) -> Optional[str]:
        """
        Determine which variant to use for a request.
        
        Uses consistent hashing if user_id provided for sticky assignments.
        """
        if test_id not in self._tests:
            return None
        
        test = self._tests[test_id]
        if test["status"] != ABTestStatus.RUNNING.value:
            return None
        
        import random
        
        # If user_id provided, use consistent hashing
        if user_id:
            import hashlib
            hash_val = int(hashlib.md5(f"{test_id}:{user_id}".encode()).hexdigest(), 16)
            random_val = (hash_val % 1000) / 1000.0
        else:
            random_val = random.random()
        
        # Select variant based on traffic percentage
        cumulative = 0.0
        for variant in test["variants"]:
            cumulative += variant["traffic_percentage"]
            if random_val <= cumulative:
                return variant["name"]
        
        return test["variants"][-1]["name"]  # Default to last variant
    
    def record_result(
        self,
        test_id: str,
        variant_name: str,
        quality_score: float,
        latency_ms: int,
        error: bool = False
    ):
        """Record a result for a variant."""
        if test_id not in self._tests:
            return
        
        test = self._tests[test_id]
        if variant_name not in test["results"]:
            return
        
        result = test["results"][variant_name]
        result["sample_size"] += 1
        result["scores"].append(quality_score)
        result["latencies"].append(latency_ms)
        if error:
            result["errors"] += 1
        
        logger.debug(f"Recorded result for {test_id}/{variant_name}")
    
    def get_test_results(self, test_id: str) -> Optional[Dict]:
        """Get current results for a test."""
        if test_id not in self._tests:
            return None
        
        test = self._tests[test_id].copy()
        
        # Calculate aggregate stats
        for variant_name, result in test["results"].items():
            if result["sample_size"] > 0:
                result["avg_score"] = sum(result["scores"]) / len(result["scores"])
                result["avg_latency"] = sum(result["latencies"]) / len(result["latencies"])
                result["error_rate"] = result["errors"] / result["sample_size"]
            else:
                result["avg_score"] = 0
                result["avg_latency"] = 0
                result["error_rate"] = 0
        
        return test
    
    def determine_winner(self, test_id: str) -> Optional[str]:
        """Determine the winning variant based on success metric."""
        test = self.get_test_results(test_id)
        if not test:
            return None
        
        # Check if we have enough samples
        for variant in test["variants"]:
            result = test["results"][variant["name"]]
            if result["sample_size"] < test["min_sample_size"]:
                logger.info(f"Test {test_id} needs more samples")
                return None
        
        # Find winner based on success metric
        metric = test["success_metric"]
        
        if metric == "overall_quality":
            winner = max(
                test["variants"],
                key=lambda v: test["results"][v["name"]]["avg_score"]
            )
        elif metric == "latency":
            winner = min(
                test["variants"],
                key=lambda v: test["results"][v["name"]]["avg_latency"]
            )
        elif metric == "error_rate":
            winner = min(
                test["variants"],
                key=lambda v: test["results"][v["name"]]["error_rate"]
            )
        else:
            return None
        
        return winner["name"]
    
    def stop_test(self, test_id: str):
        """Stop an A/B test."""
        if test_id in self._tests:
            self._tests[test_id]["status"] = ABTestStatus.COMPLETED.value
            self._tests[test_id]["completed_at"] = datetime.utcnow().isoformat()
            
            # Determine winner
            winner = self.determine_winner(test_id)
            self._tests[test_id]["winner"] = winner
            
            logger.info(f"Stopped A/B test {test_id}, winner: {winner}")
    
    def list_tests(self) -> List[Dict]:
        """List all A/B tests."""
        return [
            {
                "id": tid,
                "name": t["name"],
                "status": t["status"],
                "created_at": t["created_at"],
                "winner": t.get("winner"),
            }
            for tid, t in self._tests.items()
        ]


# Singleton instance
_framework: Optional[ABTestingFramework] = None


def get_ab_testing_framework() -> ABTestingFramework:
    """Get or create the singleton framework."""
    global _framework
    if _framework is None:
        _framework = ABTestingFramework()
    return _framework
