"""
Diagnose ingestion status for a specific twin.
Checks: sources, graph nodes, Pinecone vectors.
"""
__test__ = False

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from modules.observability import supabase
from modules.clients import get_pinecone_index
from modules.graph_context import get_graph_stats

TWIN_ID = "c3cd4ad0-d4cc-4e82-a020-82b48de72d42"

def check_sources():
    """Check sources in Supabase."""
    print("\n[1] SOURCES (Supabase)")
    print("-" * 40)
    
    res = supabase.table("sources").select("id, filename, status, created_at").eq("twin_id", TWIN_ID).execute()
    sources = res.data or []
    
    if not sources:
        print("   No sources found!")
        return []
    
    for s in sources:
        print(f"   - {s['filename']}")
        print(f"     Status: {s['status']}")
        print(f"     ID: {s['id']}")
        print(f"     Created: {s['created_at']}")
    
    return sources

def check_graph_nodes():
    """Check graph nodes in Supabase."""
    print("\n[2] GRAPH NODES (Supabase)")
    print("-" * 40)
    
    stats = get_graph_stats(TWIN_ID)
    print(f"   Node count: {stats['node_count']}")
    print(f"   Has graph: {stats['has_graph']}")
    
    if stats['top_nodes']:
        print("   Top nodes:")
        for n in stats['top_nodes'][:5]:
            print(f"     - {n['name']} ({n['type']})")
    
    return stats

def check_pinecone_vectors():
    """Check vectors in Pinecone."""
    print("\n[3] PINECONE VECTORS")
    print("-" * 40)
    
    try:
        index = get_pinecone_index()
        
        # Get namespace stats
        stats = index.describe_index_stats()
        namespaces = stats.get("namespaces", {})
        
        if TWIN_ID in namespaces:
            ns_stats = namespaces[TWIN_ID]
            print(f"   Namespace: {TWIN_ID}")
            print(f"   Vector count: {ns_stats.get('vector_count', 0)}")
        else:
            print(f"   Namespace {TWIN_ID} not found!")
            print(f"   Available namespaces: {list(namespaces.keys())[:5]}")
        
        return namespaces.get(TWIN_ID, {})
    except Exception as e:
        print(f"   Error: {e}")
        return {}

def check_edges():
    """Check edges in Supabase."""
    print("\n[4] GRAPH EDGES (Supabase)")
    print("-" * 40)
    
    res = supabase.table("edges").select("id, type, from_node_id, to_node_id").eq("twin_id", TWIN_ID).limit(10).execute()
    edges = res.data or []
    
    print(f"   Edge count: {len(edges)}")
    for e in edges[:5]:
        print(f"     - {e['type']}")
    
    return edges

def main():
    print("=" * 50)
    print(f"INGESTION DIAGNOSIS: {TWIN_ID}")
    print("=" * 50)
    
    sources = check_sources()
    stats = check_graph_nodes()
    vectors = check_pinecone_vectors()
    edges = check_edges()
    
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    
    print(f"   Sources: {len(sources)}")
    print(f"   Graph nodes: {stats.get('node_count', 0)}")
    print(f"   Graph edges: {len(edges)}")
    print(f"   Pinecone vectors: {vectors.get('vector_count', 0)}")
    
    if sources and stats.get('node_count', 0) > 0 and vectors.get('vector_count', 0) > 0:
        print("\n[OK] Ingestion successful!")
    else:
        print("\n[WARN] Some components may be missing.")

if __name__ == "__main__":
    main()
