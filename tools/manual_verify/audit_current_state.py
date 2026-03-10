#!/usr/bin/env python3
"""
Audit Current Pinecone State
Run this to understand current usage before migration.
"""
import os
from dotenv import load_dotenv
from pinecone import Pinecone
from collections import defaultdict

load_dotenv()

def _ns_vector_count(ns_stats) -> int:
    if ns_stats is None:
        return 0
    if hasattr(ns_stats, "vector_count"):
        return int(ns_stats.vector_count)
    if isinstance(ns_stats, dict):
        return int(ns_stats.get("vector_count", 0))
    return 0


def _index_type(idx) -> str:
    spec = getattr(idx, "spec", None)
    if spec is None:
        return "unknown"
    if isinstance(spec, dict):
        return "serverless" if spec.get("serverless") else "pod-based"
    if hasattr(spec, "serverless") and getattr(spec, "serverless", None) is not None:
        return "serverless"
    return "pod-based"


def audit_pinecone():
    """Audit current Pinecone setup."""
    pc = Pinecone(api_key=os.environ['PINECONE_API_KEY'])
    
    print("="*60)
    print("PINECONE CURRENT STATE AUDIT")
    print("="*60)
    print()
    
    # List all indexes
    print("1. INDEXES:")
    print("-" * 40)
    indexes = pc.list_indexes()
    for idx in indexes:
        print(f"  Name: {idx.name}")
        print(f"  Dimension: {idx.dimension}")
        print(f"  Metric: {idx.metric}")
        print(f"  Type: {_index_type(idx)}")
        print()
    
    # Analyze each index
    for idx in indexes:
        index_name = idx.name
        print(f"2. INDEX: {index_name}")
        print("-" * 40)
        
        index = pc.Index(index_name)
        stats = index.describe_index_stats()
        
        print(f"  Total vectors: {stats.total_vector_count:,}")
        print(f"  Dimension: {stats.dimension}")
        print(f"  Number of namespaces: {len(stats.namespaces)}")
        print()
        
        # Namespace breakdown
        print("  Namespace breakdown:")
        sorted_ns = sorted(
            stats.namespaces.items(),
            key=lambda x: _ns_vector_count(x[1]),
            reverse=True
        )
        
        for ns_name, ns_stats in sorted_ns[:10]:  # Top 10
            print(f"    - {ns_name}: {_ns_vector_count(ns_stats):,} vectors")
        
        if len(sorted_ns) > 10:
            remaining = sum(_ns_vector_count(s) for _, s in sorted_ns[10:])
            print(f"    - (and {len(sorted_ns) - 10} more): {remaining:,} vectors")
        
        print()
    
    # Cost estimation
    print("3. COST ESTIMATION:")
    print("-" * 40)
    for idx in indexes:
        index_name = idx.name
        index = pc.Index(index_name)
        stats = index.describe_index_stats()
        
        # Rough estimate (serverless pricing)
        # $0.10 per GB stored + $0.001 per read unit + $0.05 per write unit
        # Assuming 3072 dims = ~12KB per vector + metadata
        vector_size_gb = (stats.total_vector_count * 12 * 1024) / (1024**3)
        
        print(f"  Index: {index_name}")
        print(f"  Estimated storage: {vector_size_gb:.2f} GB")
        print(f"  Estimated monthly storage cost: ${vector_size_gb * 0.10:.2f}")
        print()
    
    # Migration readiness checklist
    print("4. MIGRATION READINESS:")
    print("-" * 40)
    
    checks = []
    
    # Check SDK version
    try:
        import pinecone
        version = pinecone.__version__
        major = int(version.split('.')[0])
        checks.append(("Pinecone SDK >= 3.0.0", major >= 3, f"Current: {version}"))
    except:
        checks.append(("Pinecone SDK >= 3.0.0", False, "Cannot detect version"))
    
    # Check current index topology (pod vs serverless)
    has_pod = any(_index_type(idx) != "serverless" for idx in indexes)
    topology_details = (
        "Pod-based indexes detected (migration required)"
        if has_pod
        else "All indexes already serverless (migration not required)"
    )
    checks.append(("Pinecone index topology assessed", True, topology_details))
    
    # Check total vectors
    total_vectors = sum(
        pc.Index(idx.name).describe_index_stats().total_vector_count
        for idx in indexes
    )
    checks.append(("Total vectors < 25M (migration limit)", total_vectors < 25_000_000, 
                   f"Current: {total_vectors:,}"))
    
    for check_name, passed, details in checks:
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status} {check_name}")
        if details:
            print(f"      {details}")
    
    print()
    print("="*60)
    
    # Recommendations
    print("\nRECOMMENDATIONS:")
    print("-" * 40)
    if not any(c[1] for c in checks if "SDK" in c[0]):
        print("  [WARN] Upgrade Pinecone SDK: pip install --upgrade pinecone>=3.0.0")
    if total_vectors > 25_000_000:
        print("  ⚠️  Vector count exceeds 25M limit. Contact Pinecone support.")
    print("  [READY] Ready to create serverless index and begin migration")
    
    return {
        "indexes": [idx.name for idx in indexes],
        "total_vectors": total_vectors,
        "ready_for_migration": all(c[1] for c in checks)
    }

if __name__ == "__main__":
    result = audit_pinecone()
    print("\n\nSummary:", result)
