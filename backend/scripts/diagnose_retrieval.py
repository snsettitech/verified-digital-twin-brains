#!/usr/bin/env python3
"""
Retrieval System Diagnostic Script

Run this script to diagnose chat retrieval issues.
Generates a comprehensive report of the retrieval system health.

Usage:
    python diagnose_retrieval.py <twin_id>
    
Example:
    python diagnose_retrieval.py sainath.no.1_coach
"""

import asyncio
import sys
import os
import json
from datetime import datetime
from typing import Dict, Any, List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Colors:
    """Terminal colors for output."""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_section(title: str):
    """Print a section header."""
    print(f"\n{Colors.BOLD}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{title}{Colors.RESET}")
    print(f"{Colors.BOLD}{'=' * 60}{Colors.RESET}")


def print_status(label: str, status: str, details: str = ""):
    """Print a status line with color coding."""
    color = Colors.GREEN if status == "OK" else Colors.YELLOW if status == "WARN" else Colors.RED
    print(f"  {label}: {color}{status}{Colors.RESET}", end="")
    if details:
        print(f" - {details}")
    else:
        print()


async def check_environment() -> Dict[str, Any]:
    """Check environment variables."""
    print_section("1. Environment Variables")
    
    required_vars = [
        'PINECONE_API_KEY',
        'PINECONE_HOST',
        'OPENAI_API_KEY'
    ]
    
    optional_vars = [
        'PINECONE_INDEX_NAME',
        'CREATOR_NAMESPACE_DUAL_READ',
        'EMBEDDING_PROVIDER'
    ]
    
    results = {
        "required": {},
        "optional": {},
        "missing_required": []
    }
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            masked = value[:10] + "..." if len(value) > 10 else value
            print_status(var, "OK", f"Set ({masked})")
            results["required"][var] = "set"
        else:
            print_status(var, "FAIL", "Not set!")
            results["missing_required"].append(var)
            results["required"][var] = "missing"
    
    print()
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            print_status(var, "OK", f"Set to: {value}")
            results["optional"][var] = value
        else:
            print_status(var, "WARN", "Not set (using default)")
            results["optional"][var] = None
    
    return results


async def check_pinecone() -> Dict[str, Any]:
    """Check Pinecone connection and stats."""
    print_section("2. Pinecone Connection")
    
    try:
        from modules.clients import get_pinecone_index
        index = get_pinecone_index()
        stats = index.describe_index_stats()
        
        print_status("Connection", "OK")
        print(f"  Total vectors: {stats.total_vector_count:,}")
        print(f"  Dimension: {stats.dimension}")
        print(f"  Index fullness: {stats.index_fullness:.2%}")
        
        namespaces = stats.namespaces
        print(f"\n  Namespaces ({len(namespaces)} total):")
        
        # Show top 10 namespaces by vector count
        sorted_ns = sorted(
            namespaces.items(),
            key=lambda x: x[1].vector_count,
            reverse=True
        )[:10]
        
        for ns_name, ns_stats in sorted_ns:
            print(f"    - {ns_name}: {ns_stats.vector_count:,} vectors")
        
        return {
            "connected": True,
            "total_vectors": stats.total_vector_count,
            "dimension": stats.dimension,
            "namespaces": {k: v.vector_count for k, v in namespaces.items()}
        }
        
    except Exception as e:
        print_status("Connection", "FAIL", str(e))
        return {
            "connected": False,
            "error": str(e)
        }


async def check_embeddings() -> Dict[str, Any]:
    """Check embedding generation."""
    print_section("3. Embedding Generation")
    
    try:
        from modules.embeddings import get_embedding
        import time
        
        test_text = "This is a test query for diagnostic purposes."
        start = time.time()
        emb = get_embedding(test_text)
        elapsed = time.time() - start
        
        print_status("Generation", "OK")
        print(f"  Dimension: {len(emb)}")
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Sample values: [{emb[0]:.4f}, {emb[1]:.4f}, {emb[2]:.4f}, ...]")
        
        return {
            "working": True,
            "dimension": len(emb),
            "time_seconds": elapsed
        }
        
    except Exception as e:
        print_status("Generation", "FAIL", str(e))
        return {
            "working": False,
            "error": str(e)
        }


async def check_namespace_resolution(twin_id: str) -> Dict[str, Any]:
    """Check namespace resolution for a twin."""
    print_section(f"4. Namespace Resolution (Twin: {twin_id})")
    
    try:
        from modules.twin_namespace import (
            resolve_creator_id_for_twin,
            get_namespace_candidates_for_twin,
            get_primary_namespace_for_twin
        )
        
        # Clear cache for fresh lookup
        from modules.twin_namespace import clear_creator_namespace_cache
        clear_creator_namespace_cache()
        
        creator_id = resolve_creator_id_for_twin(twin_id, _bypass_cache=True)
        print(f"  Creator ID: {creator_id or 'Not found (will use legacy format)'}")
        
        primary_ns = get_primary_namespace_for_twin(twin_id)
        print(f"  Primary namespace: {primary_ns}")
        
        candidates = get_namespace_candidates_for_twin(twin_id, include_legacy=True)
        print(f"\n  Namespace candidates:")
        for ns in candidates:
            print(f"    - {ns}")
        
        return {
            "creator_id": creator_id,
            "primary_namespace": primary_ns,
            "candidates": candidates
        }
        
    except Exception as e:
        print_status("Resolution", "FAIL", str(e))
        import traceback
        traceback.print_exc()
        return {
            "error": str(e)
        }


async def check_vector_counts(twin_id: str, pinecone_stats: Dict) -> Dict[str, Any]:
    """Check vector counts for twin namespaces."""
    print_section("5. Vector Counts for Twin")
    
    try:
        from modules.twin_namespace import get_namespace_candidates_for_twin
        
        candidates = get_namespace_candidates_for_twin(twin_id, include_legacy=True)
        namespaces = pinecone_stats.get("namespaces", {})
        
        results = {}
        total_vectors = 0
        
        print(f"  Checking {len(candidates)} namespaces:")
        for ns in candidates:
            count = namespaces.get(ns, 0)
            total_vectors += count
            status = "OK" if count > 0 else "EMPTY"
            print_status(ns, status, f"{count:,} vectors")
            results[ns] = count
        
        print(f"\n  Total vectors for twin: {total_vectors:,}")
        
        if total_vectors == 0:
            print(f"\n  {Colors.YELLOW}WARNING: No vectors found for this twin!{Colors.RESET}")
            print("  Possible causes:")
            print("  - Twin has no documents uploaded")
            print("  - Documents not yet processed/indexed")
            print("  - Wrong namespace format (check CREATOR_NAMESPACE_DUAL_READ)")
            print("  - Vectors in different namespace")
        
        return {
            "namespace_counts": results,
            "total_vectors": total_vectors
        }
        
    except Exception as e:
        print_status("Check", "FAIL", str(e))
        return {"error": str(e)}


async def test_retrieval(twin_id: str) -> Dict[str, Any]:
    """Test actual retrieval for a twin."""
    print_section("6. Retrieval Test")
    
    try:
        from modules.retrieval import retrieve_context
        import time
        
        test_queries = [
            "What can you help me with?",
            "Tell me about your expertise.",
            "What topics do you know about?"
        ]
        
        results = []
        
        for query in test_queries:
            print(f"\n  Query: \"{query}\"")
            start = time.time()
            contexts = await retrieve_context(query, twin_id, top_k=3)
            elapsed = time.time() - start
            
            print(f"  Time: {elapsed:.2f}s")
            print(f"  Contexts retrieved: {len(contexts)}")
            
            if contexts:
                print(f"  Top results:")
                for i, ctx in enumerate(contexts[:2]):
                    text_preview = ctx.get('text', '')[:60] + "..."
                    score = ctx.get('score', 0)
                    source = ctx.get('source_id', 'unknown')
                    print(f"    [{i+1}] Score: {score:.3f} | Source: {source}")
                    print(f"        Text: {text_preview}")
            else:
                print(f"  {Colors.YELLOW}No contexts found!{Colors.RESET}")
            
            results.append({
                "query": query,
                "contexts_found": len(contexts),
                "time_seconds": elapsed
            })
        
        return {
            "tests": results,
            "average_contexts": sum(r["contexts_found"] for r in results) / len(results)
        }
        
    except Exception as e:
        print_status("Retrieval", "FAIL", str(e))
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


async def check_health_status(twin_id: str) -> Dict[str, Any]:
    """Check health status endpoint."""
    print_section("7. Health Status Check")
    
    try:
        from modules.retrieval import get_retrieval_health_status
        
        status = await get_retrieval_health_status(twin_id)
        
        overall = "OK" if status["healthy"] else "FAIL"
        print_status("Overall", overall)
        
        print(f"\n  Components:")
        for component, details in status.get("components", {}).items():
            if isinstance(details, dict):
                if "connected" in details:
                    comp_status = "OK" if details["connected"] else "FAIL"
                elif "working" in details:
                    comp_status = "OK" if details["working"] else "FAIL"
                else:
                    comp_status = "OK"
                print_status(f"  {component}", comp_status)
        
        if status.get("warnings"):
            print(f"\n  {Colors.YELLOW}Warnings:{Colors.RESET}")
            for warning in status["warnings"]:
                print(f"    - {warning}")
        
        if status.get("errors"):
            print(f"\n  {Colors.RED}Errors:{Colors.RESET}")
            for error in status["errors"]:
                print(f"    - {error}")
        
        return status
        
    except Exception as e:
        print_status("Health Check", "FAIL", str(e))
        return {"error": str(e)}


async def generate_report(twin_id: str, results: Dict) -> str:
    """Generate a JSON report."""
    report = {
        "timestamp": datetime.now().isoformat(),
        "twin_id": twin_id,
        "summary": {
            "healthy": True,
            "issues": []
        },
        "details": results
    }
    
    # Determine overall health
    if results.get("environment", {}).get("missing_required"):
        report["summary"]["healthy"] = False
        report["summary"]["issues"].append("Missing required environment variables")
    
    if not results.get("pinecone", {}).get("connected"):
        report["summary"]["healthy"] = False
        report["summary"]["issues"].append("Pinecone connection failed")
    
    if not results.get("embeddings", {}).get("working"):
        report["summary"]["healthy"] = False
        report["summary"]["issues"].append("Embedding generation failed")
    
    vector_total = results.get("vector_counts", {}).get("total_vectors", 0)
    if vector_total == 0:
        report["summary"]["issues"].append("No vectors found for twin")
    
    avg_contexts = results.get("retrieval_test", {}).get("average_contexts", 0)
    if avg_contexts == 0:
        report["summary"]["issues"].append("Retrieval returning empty results")
    
    return json.dumps(report, indent=2)


async def main():
    """Main diagnostic routine."""
    if len(sys.argv) < 2:
        print("Usage: python diagnose_retrieval.py <twin_id>")
        print("\nExample:")
        print("  python diagnose_retrieval.py sainath.no.1_coach")
        sys.exit(1)
    
    twin_id = sys.argv[1]
    
    print(f"{Colors.BLUE}{Colors.BOLD}")
    print("╔══════════════════════════════════════════════════════════╗")
    print("║     CHAT RETRIEVAL SYSTEM DIAGNOSTIC TOOL               ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"{Colors.RESET}")
    print(f"Twin ID: {twin_id}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {}
    
    try:
        # Run all checks
        results["environment"] = await check_environment()
        results["pinecone"] = await check_pinecone()
        results["embeddings"] = await check_embeddings()
        results["namespace_resolution"] = await check_namespace_resolution(twin_id)
        results["vector_counts"] = await check_vector_counts(twin_id, results["pinecone"])
        results["retrieval_test"] = await test_retrieval(twin_id)
        results["health_status"] = await check_health_status(twin_id)
        
        # Generate summary
        print_section("SUMMARY")
        
        healthy = True
        issues = []
        
        if results["environment"].get("missing_required"):
            healthy = False
            issues.append(f"Missing env vars: {results['environment']['missing_required']}")
        
        if not results["pinecone"].get("connected"):
            healthy = False
            issues.append("Pinecone connection failed")
        
        if not results["embeddings"].get("working"):
            healthy = False
            issues.append("Embedding generation failed")
        
        if results["vector_counts"].get("total_vectors", 0) == 0:
            issues.append("No vectors found for twin")
        
        if results["retrieval_test"].get("average_contexts", 0) == 0:
            healthy = False
            issues.append("Retrieval returning empty results")
        
        if healthy and not issues:
            print(f"{Colors.GREEN}{Colors.BOLD}✓ Retrieval system is healthy{Colors.RESET}")
        elif healthy and issues:
            print(f"{Colors.YELLOW}{Colors.BOLD}⚠ Retrieval system functional but with warnings:{Colors.RESET}")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print(f"{Colors.RED}{Colors.BOLD}✗ Retrieval system has issues:{Colors.RESET}")
            for issue in issues:
                print(f"  - {issue}")
        
        # Save report
        report_json = await generate_report(twin_id, results)
        report_file = f"retrieval_diagnostic_{twin_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(report_file, 'w') as f:
            f.write(report_json)
        
        print(f"\nDetailed report saved to: {report_file}")
        
    except Exception as e:
        print(f"\n{Colors.RED}Diagnostic failed: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
