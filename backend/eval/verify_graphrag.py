#!/usr/bin/env python3
"""
GraphRAG Eval Harness

Compares RAG-lite baseline vs GraphRAG enabled mode.
Tests that GraphRAG returns non-empty context for at least N of 20 questions.
"""

import argparse
import sys
import os
import asyncio
import json
from typing import Dict, Any, List

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from modules.graph_context import get_graph_snapshot
from modules.retrieval import retrieve_context_vectors


async def test_rag_lite(twin_id: str, questions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Test RAG-lite baseline (vector retrieval only)."""
    results = {
        "mode": "rag_lite",
        "total": len(questions),
        "successful": 0,
        "errors": 0,
        "empty_contexts": 0,
        "results": []
    }
    
    for question in questions:
        q_id = question["id"]
        q_text = question["question"]
        
        try:
            contexts = await retrieve_context_vectors(q_text, twin_id, top_k=5)
            
            has_context = len(contexts) > 0
            context_count = len(contexts)
            
            if has_context:
                results["successful"] += 1
            else:
                results["empty_contexts"] += 1
            
            results["results"].append({
                "question_id": q_id,
                "question": q_text,
                "context_count": context_count,
                "has_context": has_context,
                "error": None
            })
        except Exception as e:
            results["errors"] += 1
            results["results"].append({
                "question_id": q_id,
                "question": q_text,
                "context_count": 0,
                "has_context": False,
                "error": str(e)
            })
    
    return results


async def test_graphrag(twin_id: str, questions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Test GraphRAG mode (graph snapshot retrieval)."""
    results = {
        "mode": "graphrag",
        "total": len(questions),
        "successful": 0,
        "errors": 0,
        "empty_contexts": 0,
        "results": []
    }
    
    for question in questions:
        q_id = question["id"]
        q_text = question["question"]
        
        try:
            snapshot = await get_graph_snapshot(twin_id, query=q_text)
            
            context_text = snapshot.get("context_text", "")
            node_count = snapshot.get("node_count", 0)
            edge_count = snapshot.get("edge_count", 0)
            has_context = bool(context_text) and node_count > 0
            
            if has_context:
                results["successful"] += 1
            else:
                results["empty_contexts"] += 1
            
            results["results"].append({
                "question_id": q_id,
                "question": q_text,
                "node_count": node_count,
                "edge_count": edge_count,
                "context_length": len(context_text),
                "has_context": has_context,
                "error": snapshot.get("error")
            })
        except Exception as e:
            results["errors"] += 1
            results["results"].append({
                "question_id": q_id,
                "question": q_text,
                "node_count": 0,
                "edge_count": 0,
                "context_length": 0,
                "has_context": False,
                "error": str(e)
            })
    
    return results


async def run_evaluation(twin_id: str, dataset_path: str = None) -> Dict[str, Any]:
    """Run evaluation comparing RAG-lite vs GraphRAG."""
    
    # Load dataset
    if dataset_path is None:
        dataset_path = os.path.join(os.path.dirname(__file__), "graph_rag_smoke.json")
    
    with open(dataset_path, 'r') as f:
        dataset = json.load(f)
    
    questions = dataset.get("questions", [])
    
    print(f"Evaluating {len(questions)} questions for twin: {twin_id}\n")
    
    # Test RAG-lite baseline
    print("Testing RAG-lite baseline...")
    rag_lite_results = await test_rag_lite(twin_id, questions)
    print(f"  Successful: {rag_lite_results['successful']}/{rag_lite_results['total']}")
    print(f"  Empty contexts: {rag_lite_results['empty_contexts']}")
    print(f"  Errors: {rag_lite_results['errors']}\n")
    
    # Test GraphRAG
    print("Testing GraphRAG...")
    graphrag_results = await test_graphrag(twin_id, questions)
    print(f"  Successful: {graphrag_results['successful']}/{graphrag_results['total']}")
    print(f"  Empty contexts: {graphrag_results['empty_contexts']}")
    print(f"  Errors: {graphrag_results['errors']}\n")
    
    # Calculate metrics
    rag_lite_success_rate = rag_lite_results["successful"] / rag_lite_results["total"] if rag_lite_results["total"] > 0 else 0
    graphrag_success_rate = graphrag_results["successful"] / graphrag_results["total"] if graphrag_results["total"] > 0 else 0
    
    # Pass criteria: GraphRAG must return non-empty context for at least 50% (10 of 20)
    min_successful = max(1, int(rag_lite_results["total"] * 0.5))
    graphrag_passes = graphrag_results["successful"] >= min_successful and graphrag_results["errors"] == 0
    
    summary = {
        "twin_id": twin_id,
        "dataset": dataset.get("name", "unknown"),
        "total_questions": len(questions),
        "rag_lite": {
            "successful": rag_lite_results["successful"],
            "success_rate": rag_lite_success_rate,
            "empty_contexts": rag_lite_results["empty_contexts"],
            "errors": rag_lite_results["errors"]
        },
        "graphrag": {
            "successful": graphrag_results["successful"],
            "success_rate": graphrag_success_rate,
            "empty_contexts": graphrag_results["empty_contexts"],
            "errors": graphrag_results["errors"]
        },
        "pass_criteria": {
            "min_successful": min_successful,
            "graphrag_passes": graphrag_passes,
            "no_errors_required": True
        },
        "results": {
            "rag_lite": rag_lite_results,
            "graphrag": graphrag_results
        }
    }
    
    print("="*60)
    print("EVALUATION SUMMARY")
    print("="*60)
    print(f"RAG-lite success rate: {rag_lite_success_rate:.1%}")
    print(f"GraphRAG success rate: {graphrag_success_rate:.1%}")
    print(f"Pass criteria: {min_successful} successful, 0 errors")
    print(f"GraphRAG passes: {'✅ PASS' if graphrag_passes else '❌ FAIL'}")
    print("="*60)
    
    return summary


async def main():
    parser = argparse.ArgumentParser(description="Test GraphRAG vs RAG-lite")
    parser.add_argument("--twin-id", required=True, help="Twin ID to test")
    parser.add_argument("--dataset", help="Path to dataset JSON file (default: graph_rag_smoke.json)")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    
    args = parser.parse_args()
    
    summary = await run_evaluation(args.twin_id, args.dataset)
    
    if args.json:
        print(json.dumps(summary, indent=2))
    
    # Exit with error code if GraphRAG fails
    if not summary["pass_criteria"]["graphrag_passes"]:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

