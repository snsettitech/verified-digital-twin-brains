# backend/eval/runner.py
"""RAGAS Evaluation Runner

Runs evaluation against the GraphRAG Lite retrieval pipeline.
Measures faithfulness, context precision, and answer relevancy.
"""

import json
import os
import sys
import asyncio
from datetime import datetime
from typing import Dict, Any, List
import logging

# Add backend directory to path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load env vars
load_dotenv()


async def run_evaluation(
    twin_id: str,
    dataset_path: str = None,
    output_path: str = None
) -> Dict[str, Any]:
    """
    Run RAGAS evaluation on the dataset.
    
    Args:
        twin_id: Twin ID to evaluate
        dataset_path: Path to dataset.json
        output_path: Path to save results
    
    Returns:
        Evaluation results with metrics
    """
    # Default paths
    if dataset_path is None:
        dataset_path = os.path.join(os.path.dirname(__file__), "dataset.json")
    
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(os.path.dirname(__file__), f"results_{timestamp}.json")
    
    # Load dataset
    with open(dataset_path, 'r') as f:
        dataset = json.load(f)
    
    questions = dataset.get("questions", [])
    
    logger.info(f"Running evaluation on {len(questions)} questions for twin {twin_id}")
    
    results = []
    metrics = {
        "total_questions": len(questions),
        "answered": 0,
        "refused": 0,
        "errors": 0,
        "faithfulness_scores": [],
        "context_precision_scores": [],
        "answer_relevancy_scores": []
    }
    
    for q in questions:
        try:
            result = await evaluate_question(twin_id, q)
            results.append(result)
            
            if result.get("refused"):
                metrics["refused"] += 1
            elif result.get("error"):
                metrics["errors"] += 1
            else:
                metrics["answered"] += 1
                
                # Collect scores
                if result.get("faithfulness") is not None:
                    metrics["faithfulness_scores"].append(result["faithfulness"])
                if result.get("context_precision") is not None:
                    metrics["context_precision_scores"].append(result["context_precision"])
                if result.get("answer_relevancy") is not None:
                    metrics["answer_relevancy_scores"].append(result["answer_relevancy"])
                    
        except Exception as e:
            logger.error(f"Error evaluating question {q['id']}: {e}")
            metrics["errors"] += 1
            results.append({
                "question_id": q["id"],
                "error": str(e)
            })
    
    # Calculate averages
    summary = {
        "twin_id": twin_id,
        "timestamp": datetime.now().isoformat(),
        "total_questions": metrics["total_questions"],
        "answered": metrics["answered"],
        "refused": metrics["refused"],
        "errors": metrics["errors"],
        "avg_faithfulness": safe_avg(metrics["faithfulness_scores"]),
        "avg_context_precision": safe_avg(metrics["context_precision_scores"]),
        "avg_answer_relevancy": safe_avg(metrics["answer_relevancy_scores"]),
        "results": results
    }
    
    # Save results
    with open(output_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    logger.info(f"Evaluation complete. Results saved to {output_path}")
    logger.info(f"Faithfulness: {summary['avg_faithfulness']:.2f}")
    logger.info(f"Context Precision: {summary['avg_context_precision']:.2f}")
    logger.info(f"Answer Relevancy: {summary['avg_answer_relevancy']:.2f}")
    
    return summary


async def evaluate_question(twin_id: str, question: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluate a single question.
    
    Args:
        twin_id: Twin ID
        question: Question dict from dataset
    
    Returns:
        Evaluation result with scores
    """
    from modules.graph_context import get_graph_snapshot
    
    q_id = question["id"]
    q_text = question["question"]
    category = question.get("category", "unknown")
    context_needed = question.get("context_needed", [])
    
    # Get graph snapshot for context
    snapshot = await get_graph_snapshot(twin_id, query=q_text)
    
    nodes_used = snapshot.get("nodes", [])
    
    # Check if context is relevant
    context_precision = calculate_context_precision(nodes_used, context_needed)
    
    # For now, we don't have the full RAGAS pipeline
    # This is a simplified scorer that can be enhanced
    result = {
        "question_id": q_id,
        "question": q_text,
        "category": category,
        "context_retrieved": len(nodes_used) > 0,
        "nodes_retrieved": len(nodes_used),
        "context_precision": context_precision,
        "faithfulness": None,  # Requires LLM judge
        "answer_relevancy": None,  # Requires actual answer
        "refused": category in ("unknown", "edge_case") and len(nodes_used) == 0
    }
    
    return result


def calculate_context_precision(nodes: List[Dict], expected_types: List[str]) -> float:
    """
    Calculate context precision based on node types matching expected context.
    
    Args:
        nodes: Retrieved nodes
        expected_types: Expected context types
    
    Returns:
        Precision score 0.0 to 1.0
    """
    if not nodes or not expected_types:
        return 0.0
    
    # Count how many retrieved nodes match expected types
    matches = 0
    for node in nodes:
        node_type = (node.get("type") or "").lower()
        for expected in expected_types:
            if expected.lower() in node_type:
                matches += 1
                break
    
    return matches / len(nodes) if nodes else 0.0


def safe_avg(scores: List[float]) -> float:
    """Calculate average, returning 0.0 if empty."""
    return sum(scores) / len(scores) if scores else 0.0


def run_gate_check(results_path: str, thresholds: Dict[str, float] = None) -> bool:
    """
    Check if evaluation results pass the gate thresholds.
    
    Args:
        results_path: Path to results JSON
        thresholds: Dict of metric -> minimum value
    
    Returns:
        True if all thresholds met
    """
    if thresholds is None:
        thresholds = {
            "avg_faithfulness": 0.7,
            "avg_context_precision": 0.5,
            "avg_answer_relevancy": 0.6
        }
    
    with open(results_path, 'r') as f:
        results = json.load(f)
    
    passed = True
    for metric, threshold in thresholds.items():
        value = results.get(metric, 0.0)
        if value is None:
            continue
        if value < threshold:
            logger.warning(f"Gate FAILED: {metric} = {value:.2f} < {threshold:.2f}")
            passed = False
        else:
            logger.info(f"Gate PASSED: {metric} = {value:.2f} >= {threshold:.2f}")
    
    return passed


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python runner.py <twin_id> [dataset_path]")
        sys.exit(1)
    
    twin_id = sys.argv[1]
    dataset_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    asyncio.run(run_evaluation(twin_id, dataset_path))
