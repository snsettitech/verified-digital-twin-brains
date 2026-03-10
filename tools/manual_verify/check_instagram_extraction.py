#!/usr/bin/env python3
"""
Check what was extracted from the Instagram link
"""
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from modules.observability import supabase
from modules.clients import get_pinecone_index
from modules.delphi_namespace import get_namespace_candidates_for_twin

TWIN_ID = "11839ada-d93a-418f-a851-21f9c5a3ae36"

def check_database():
    """Check sources and chunks in database"""
    print("=" * 80)
    print(f"CHECKING DATABASE FOR TWIN: {TWIN_ID}")
    print("=" * 80)
    
    # Get all sources for this twin
    sources_res = supabase.table("sources").select("*").eq("twin_id", TWIN_ID).order("created_at", desc=True).execute()
    
    if not sources_res.data:
        print("\n[ERROR] No sources found for this twin")
        return
    
    print(f"\n[FOUND] Found {len(sources_res.data)} sources:\n")
    
    for i, source in enumerate(sources_res.data, 1):
        source_id = source.get('id')
        filename = source.get('filename', 'N/A')
        url = source.get('citation_url', 'N/A')
        status = source.get('status', 'N/A')
        text_length = source.get('extracted_text_length', 0) or len(source.get('content_text', '') or '')
        
        print(f"  {i}. {filename}")
        print(f"     ID: {source_id}")
        print(f"     URL: {url}")
        print(f"     Status: {status}")
        print(f"     Content Length: {text_length} chars")
        
        # Check for Instagram
        if 'instagram' in (url or '').lower():
            print(f"     [INSTAGRAM] INSTAGRAM SOURCE FOUND!")
            print(f"     Content preview (first 500 chars):")
            content = source.get('content_text', '')
            if content:
                print(f"     {content[:500]}...")
            else:
                print(f"     [WARNING] NO CONTENT EXTRACTED!")
        
        # Get chunks for this source
        chunks_res = supabase.table("chunks").select("*").eq("source_id", source_id).execute()
        chunks_count = len(chunks_res.data) if chunks_res.data else 0
        print(f"     Chunks: {chunks_count}")
        
        if chunks_res.data and chunks_count > 0:
            print(f"     Chunk previews:")
            for j, chunk in enumerate(chunks_res.data[:3], 1):  # Show first 3 chunks
                content = chunk.get('content', '')
                vector_id = chunk.get('vector_id', 'N/A')
                print(f"       Chunk {j}: {len(content)} chars, Vector ID: {vector_id}")
                if content:
                    print(f"       Preview: {content[:200]}...")
        
        print()

def check_pinecone():
    """Check vectors in Pinecone"""
    print("=" * 80)
    print(f"CHECKING PINECONE FOR TWIN: {TWIN_ID}")
    print("=" * 80)
    
    try:
        index = get_pinecone_index()
        stats = index.describe_index_stats()
        
        print(f"\n📊 Pinecone Index Stats:")
        print(f"   Total Vectors: {stats.total_vector_count}")
        print(f"   Dimension: {stats.dimension}")
        print(f"   Namespaces: {len(stats.namespaces)}")
        
        # Get namespaces for this twin
        namespaces = get_namespace_candidates_for_twin(twin_id=TWIN_ID, include_legacy=True)
        print(f"\n[CHECKING] Checking namespaces: {namespaces}\n")
        
        for namespace in namespaces:
            ns_stats = stats.namespaces.get(namespace, {})
            vector_count = ns_stats.get('vector_count', 0)
            
            print(f"  Namespace: {namespace}")
            print(f"  Vector Count: {vector_count}")
            
            if vector_count > 0:
                # Query some vectors to see what we have
                try:
                    query_res = index.query(
                        vector=[0.1] * stats.dimension,
                        top_k=5,
                        include_metadata=True,
                        namespace=namespace
                    )
                    matches = query_res.get('matches', [])
                    print(f"  Sample vectors:")
                    for i, match in enumerate(matches, 1):
                        metadata = match.get('metadata', {})
                        source_type = metadata.get('source_type', 'N/A')
                        category = metadata.get('category', 'N/A')
                        score = match.get('score', 0)
                        print(f"    {i}. Score: {score:.4f}, Type: {source_type}, Category: {category}")
                except Exception as e:
                    print(f"  [WARNING] Error querying: {e}")
            else:
                print(f"  [WARNING] No vectors in this namespace")
            print()
            
    except Exception as e:
        print(f"\n[ERROR] Error connecting to Pinecone: {e}")

def main():
    print("\n" + "=" * 80)
    print("INSTAGRAM LINK EXTRACTION REPORT")
    print("=" * 80 + "\n")
    
    check_database()
    print("\n")
    check_pinecone()
    
    print("\n" + "=" * 80)
    print("REPORT COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()
