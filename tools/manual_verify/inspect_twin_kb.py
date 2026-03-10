#!/usr/bin/env python3
"""Inspect twin's knowledge base from Pinecone"""
import os
import sys
from dotenv import load_dotenv
load_dotenv('backend/.env')

sys.path.insert(0, 'backend')

from modules.clients import get_pinecone_index
from modules.delphi_namespace import get_namespace_candidates_for_twin

TWIN_ID = "cf3ffed1-5d56-422b-8ce9-1bd99cd43b22"

def inspect_pinecone_vectors():
    """Get sample vectors from Pinecone for this twin."""
    
    print("=" * 70)
    print(f"INSPECTING TWIN: {TWIN_ID}")
    print("=" * 70)
    
    # Get index
    index = get_pinecone_index()
    
    # Get namespaces
    namespaces = get_namespace_candidates_for_twin(TWIN_ID, include_legacy=True)
    print(f"\nNamespaces: {namespaces}")
    
    # Query each namespace
    for ns in namespaces:
        print(f"\n{'-' * 70}")
        print(f"Namespace: {ns}")
        print('-' * 70)
        
        try:
            # Get stats
            stats = index.describe_index_stats()
            ns_stats = stats.namespaces.get(ns, {})
            vector_count = getattr(ns_stats, 'vector_count', 0)
            print(f"Vector count: {vector_count}")
            
            if vector_count == 0:
                continue
            
            # Query with dummy vector to get sample chunks
            # Try 1024 dimensions (text-embedding-3-small)
            results = index.query(
                vector=[0.1] * 1024,
                top_k=10,
                include_metadata=True,
                namespace=ns
            )
            
            print(f"\nSample chunks:")
            for i, match in enumerate(results.matches, 1):
                metadata = match.metadata or {}
                text = metadata.get('text', '')[:200]
                source = metadata.get('source', 'Unknown')
                category = metadata.get('category', 'FACT')
                
                print(f"\n{i}. Score: {match.score:.3f}")
                print(f"   Source: {source}")
                print(f"   Category: {category}")
                print(f"   Text: {text}...")
                
        except Exception as e:
            print(f"Error querying namespace {ns}: {e}")

if __name__ == "__main__":
    inspect_pinecone_vectors()
