# backend/routers/regression_testing.py
"""Regression Testing API Endpoints

Admin endpoints for running regression tests and managing baselines.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Optional, List, Dict, Any
import logging

from modules.auth_guard import get_current_user, require_admin
from modules.regression_testing import (
    RegressionTestRunner,
    RegressionTestReport,
    get_regression_runner
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/regression", tags=["regression-testing"])


@router.post("/test", response_model=Dict[str, Any])
async def run_regression_test_endpoint(
    dataset_name: str,
    twin_id: str,
    sample_size: Optional[int] = None,
    baseline_tag: Optional[str] = None,
    background: bool = False,
    background_tasks: BackgroundTasks = None,
    user=Depends(require_admin)
):
    """
    Run a regression test against a dataset.
    
    Args:
        dataset_name: Name of the dataset to test (e.g., "high_quality_responses")
        twin_id: Twin ID to use for testing
        sample_size: Number of items to test (default: all)
        baseline_tag: Tag for baseline comparison (default: use item metadata)
        background: Run test in background (return immediately)
    
    Returns:
        Test report or job ID if running in background
    """
    try:
        runner = get_regression_runner()
        
        if background and background_tasks:
            # Run in background
            async def run_test():
                try:
                    report = await runner.run_test(
                        dataset_name=dataset_name,
                        twin_id=twin_id,
                        sample_size=sample_size,
                        baseline_tag=baseline_tag
                    )
                    logger.info(f"Background regression test completed: {report.test_id}")
                except Exception as e:
                    logger.error(f"Background regression test failed: {e}")
            
            background_tasks.add_task(run_test)
            
            return {
                "status": "started",
                "message": "Regression test started in background",
                "dataset_name": dataset_name,
                "twin_id": twin_id
            }
        else:
            # Run synchronously
            report = await runner.run_test(
                dataset_name=dataset_name,
                twin_id=twin_id,
                sample_size=sample_size,
                baseline_tag=baseline_tag
            )
            
            return _report_to_dict(report)
            
    except Exception as e:
        logger.error(f"Regression test endpoint failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/datasets", response_model=List[Dict[str, Any]])
async def list_regression_datasets(
    user=Depends(require_admin)
):
    """List available datasets for regression testing."""
    try:
        try:
            from langfuse import Langfuse
        except ImportError:
            raise HTTPException(status_code=503, detail="Langfuse not available")
        
        client = Langfuse()
        datasets = client.get_datasets()
        
        return [
            {
                "name": d.name,
                "item_count": len(list(d.items)),
                "created_at": getattr(d, 'created_at', None),
                "updated_at": getattr(d, 'updated_at', None)
            }
            for d in datasets
        ]
        
    except Exception as e:
        logger.error(f"Failed to list datasets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test/{test_id}", response_model=Dict[str, Any])
async def get_test_result(
    test_id: str,
    user=Depends(require_admin)
):
    """Get results of a specific regression test."""
    # In production, this would fetch from a database
    # For now, we search in Langfuse traces
    try:
        try:
            from langfuse import Langfuse
        except ImportError:
            raise HTTPException(status_code=503, detail="Langfuse not available")
        
        client = Langfuse()
        traces = client.fetch_traces(
            name="regression_test",
            metadata={"test_id": test_id}
        )
        
        for trace in traces:
            if trace.metadata.get("test_id") == test_id:
                return {
                    "test_id": test_id,
                    "found": True,
                    "trace_id": trace.id,
                    "metadata": trace.metadata
                }
        
        return {
            "test_id": test_id,
            "found": False,
            "message": "Test result not found (may have expired)"
        }
        
    except Exception as e:
        logger.error(f"Failed to get test result: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/baseline")
async def save_baseline(
    dataset_name: str,
    tag: str,
    user=Depends(require_admin)
):
    """
    Save current scores as baseline for future comparison.
    
    Args:
        dataset_name: Name of the dataset
        tag: Tag for this baseline (e.g., "v1.2.3")
    """
    try:
        try:
            from langfuse import Langfuse
        except ImportError:
            raise HTTPException(status_code=503, detail="Langfuse not available")
        
        runner = get_regression_runner()
        
        # Get current scores from dataset
        client = Langfuse()
        dataset = client.get_dataset(dataset_name)
        
        scores = {}
        for item in dataset.items:
            metadata = item.metadata or {}
            score = metadata.get("overall_score", 0.8)
            scores[item.id] = score
        
        # Save baseline
        runner.save_baseline(dataset_name, tag, scores)
        
        return {
            "status": "success",
            "dataset_name": dataset_name,
            "tag": tag,
            "item_count": len(scores)
        }
        
    except Exception as e:
        logger.error(f"Failed to save baseline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/baselines/{dataset_name}", response_model=List[str])
async def list_baselines(
    dataset_name: str,
    user=Depends(require_admin)
):
    """List available baseline tags for a dataset."""
    try:
        try:
            from langfuse import Langfuse
        except ImportError:
            raise HTTPException(status_code=503, detail="Langfuse not available")
        
        client = Langfuse()
        dataset = client.get_dataset(dataset_name)
        
        # Extract baseline tags from metadata
        tags = set()
        for item in dataset.items:
            metadata = item.metadata or {}
            for key in metadata.keys():
                if key.startswith("baseline_score_"):
                    tag = key.replace("baseline_score_", "")
                    tags.add(tag)
        
        return sorted(list(tags))
        
    except Exception as e:
        logger.error(f"Failed to list baselines: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _report_to_dict(report: RegressionTestReport) -> Dict[str, Any]:
    """Convert report to dict for JSON serialization."""
    return {
        "test_id": report.test_id,
        "dataset_name": report.dataset_name,
        "started_at": report.started_at,
        "completed_at": report.completed_at,
        "total_items": report.total_items,
        "passed": report.passed,
        "failed": report.failed,
        "warnings": report.warnings,
        "errors": report.errors,
        "summary": report.summary,
        "results": [
            {
                "dataset_item_id": r.dataset_item_id,
                "query": r.query,
                "status": r.status.value,
                "baseline_score": r.baseline_score,
                "new_score": r.new_score,
                "score_diff": r.score_diff,
                "diff_percent": r.diff_percent,
                "execution_time_ms": r.execution_time_ms
            }
            for r in report.results
        ]
    }
