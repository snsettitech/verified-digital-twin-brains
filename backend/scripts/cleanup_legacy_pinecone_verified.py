#!/usr/bin/env python3
"""
Cleanup Legacy Pinecone Verified Vectors

This script removes legacy verified vectors from Pinecone that were created
via the old inject_verified_memory() function. These vectors are no longer
needed since we now use Postgres-only storage for verified QnA.

Usage:
    python scripts/cleanup_legacy_pinecone_verified.py [--dry-run] [--namespace <twin_id>]

Options:
    --dry-run: Show what would be deleted without actually deleting
    --namespace: Only clean up vectors for a specific twin (namespace)
"""

import os
import sys
import argparse
from dotenv import load_dotenv

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

load_dotenv()

from modules.clients import get_pinecone_index
from modules.observability import supabase


def get_all_twin_ids() -> list:
    """Get all twin IDs from the database."""
    try:
        response = supabase.table("twins").select("id").execute()
        return [twin["id"] for twin in (response.data or [])]
    except Exception as e:
        print(f"Error fetching twin IDs: {e}")
        return []


def cleanup_verified_vectors_for_namespace(index, namespace: str, dry_run: bool = False) -> int:
    """
    Delete all verified vectors for a specific namespace (twin_id).
    
    Args:
        index: Pinecone index client
        namespace: Twin ID (namespace in Pinecone)
        dry_run: If True, only count vectors without deleting
        
    Returns:
        Number of vectors deleted (or would be deleted in dry-run)
    """
    deleted_count = 0
    
    try:
        # Query for verified vectors in this namespace
        # Use a dummy embedding to query (we only care about the filter)
        dummy_embedding = [0.0] * 3072  # text-embedding-3-large dimension
        
        results = index.query(
            vector=dummy_embedding,
            top_k=10000,  # Large number to get all matches
            include_metadata=True,
            namespace=namespace,
            filter={"is_verified": {"$eq": True}}
        )
        
        matches = results.get("matches", [])
        if not matches:
            print(f"  No verified vectors found for twin {namespace}")
            return 0
        
        print(f"  Found {len(matches)} verified vectors for twin {namespace}")
        
        if dry_run:
            print(f"  [DRY RUN] Would delete {len(matches)} vectors")
            for match in matches:
                print(f"    - Vector ID: {match['id']}, Score: {match.get('score', 'N/A')}")
            return len(matches)
        
        # Delete vectors by ID
        vector_ids = [match["id"] for match in matches]
        
        # Pinecone delete_by_ids requires namespace
        # Delete in batches if needed (Pinecone has limits)
        batch_size = 1000
        for i in range(0, len(vector_ids), batch_size):
            batch = vector_ids[i:i + batch_size]
            index.delete(ids=batch, namespace=namespace)
            deleted_count += len(batch)
        
        print(f"  Deleted {deleted_count} verified vectors for twin {namespace}")
        
    except Exception as e:
        print(f"  Error cleaning up namespace {namespace}: {e}")
    
    return deleted_count


def main():
    parser = argparse.ArgumentParser(description="Cleanup legacy Pinecone verified vectors")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without deleting")
    parser.add_argument("--namespace", type=str, help="Only clean up vectors for a specific twin (namespace)")
    args = parser.parse_args()
    
    print("=" * 60)
    print("Legacy Pinecone Verified Vectors Cleanup")
    print("=" * 60)
    
    if args.dry_run:
        print("DRY RUN MODE - No vectors will be deleted")
    print()
    
    try:
        index = get_pinecone_index()
    except Exception as e:
        print(f"Error initializing Pinecone index: {e}")
        print("Make sure PINECONE_API_KEY and PINECONE_INDEX_NAME are set")
        sys.exit(1)
    
    total_deleted = 0
    
    if args.namespace:
        # Clean up specific namespace
        print(f"Cleaning up verified vectors for twin: {args.namespace}")
        deleted = cleanup_verified_vectors_for_namespace(index, args.namespace, args.dry_run)
        total_deleted += deleted
    else:
        # Clean up all namespaces
        print("Fetching all twin IDs...")
        twin_ids = get_all_twin_ids()
        
        if not twin_ids:
            print("No twins found in database")
            sys.exit(1)
        
        print(f"Found {len(twin_ids)} twins")
        print()
        
        for twin_id in twin_ids:
            print(f"Processing twin: {twin_id}")
            deleted = cleanup_verified_vectors_for_namespace(index, twin_id, args.dry_run)
            total_deleted += deleted
            print()
    
    print("=" * 60)
    if args.dry_run:
        print(f"DRY RUN COMPLETE: Would delete {total_deleted} verified vectors")
    else:
        print(f"Cleanup complete: Deleted {total_deleted} verified vectors")
    print("=" * 60)
    
    print()
    print("Note: Verified QnA data is now stored only in Postgres.")
    print("      The verified_qna table contains all verified answers with embeddings.")
    print("      Semantic matching now uses Postgres embeddings instead of Pinecone.")


if __name__ == "__main__":
    main()

