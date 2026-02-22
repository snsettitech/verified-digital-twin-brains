#!/usr/bin/env python3
"""
Check what was extracted from sources for a specific twin
"""
import os
import sys

# Load env from backend/.env
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'backend', '.env'))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from supabase import create_client

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY')

TWIN_ID = "11839ada-d93a-418f-a851-21f9c5a3ae36"

def main():
    print("=" * 80)
    print(f"CHECKING EXTRACTION FOR TWIN: {TWIN_ID}")
    print("=" * 80)
    
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Get twin info
    print("\n[1] TWIN INFO:")
    twin_res = supabase.table("twins").select("*").eq("id", TWIN_ID).single().execute()
    if twin_res.data:
        print(f"  Name: {twin_res.data.get('name', 'N/A')}")
        print(f"  Created: {twin_res.data.get('created_at', 'N/A')}")
        print(f"  Specialization: {twin_res.data.get('specialization', 'N/A')}")
    else:
        print("  Twin not found!")
        return
    
    # Get all sources
    print("\n[2] SOURCES:")
    sources_res = supabase.table("sources").select("*").eq("twin_id", TWIN_ID).order("created_at", desc=True).execute()
    
    if not sources_res.data:
        print("  No sources found for this twin")
        return
    
    print(f"  Found {len(sources_res.data)} sources:\n")
    
    instagram_sources = []
    
    for i, source in enumerate(sources_res.data, 1):
        source_id = source.get('id')
        filename = source.get('filename', 'N/A')
        url = source.get('citation_url', 'N/A')
        status = source.get('status', 'N/A')
        content_text = source.get('content_text', '') or ''
        text_length = len(content_text)
        
        is_instagram = 'instagram' in (url or '').lower()
        
        print(f"  Source #{i}:")
        print(f"    ID: {source_id}")
        print(f"    Filename: {filename}")
        print(f"    URL: {url}")
        print(f"    Status: {status}")
        print(f"    Content Length: {text_length} chars")
        
        if is_instagram:
            print(f"    *** INSTAGRAM SOURCE ***")
            instagram_sources.append(source)
            
        if content_text:
            preview = content_text[:500].replace('\n', ' ')
            print(f"    Content Preview: {preview}...")
        else:
            print(f"    [WARNING] No content extracted!")
        
        # Get chunks
        chunks_res = supabase.table("chunks").select("*").eq("source_id", source_id).execute()
        chunks_count = len(chunks_res.data) if chunks_res.data else 0
        print(f"    Chunks: {chunks_count}")
        
        if chunks_res.data:
            for j, chunk in enumerate(chunks_res.data[:2], 1):
                chunk_content = chunk.get('content', '')
                vector_id = chunk.get('vector_id', 'N/A')
                print(f"      Chunk {j}: {len(chunk_content)} chars, Vector ID: {vector_id}")
                if chunk_content:
                    preview = chunk_content[:150].replace('\n', ' ')
                    print(f"        Preview: {preview}...")
        print()
    
    # Detailed Instagram analysis
    if instagram_sources:
        print("\n" + "=" * 80)
        print("[3] INSTAGRAM SOURCE DETAILED ANALYSIS:")
        print("=" * 80)
        
        for src in instagram_sources:
            print(f"\n  Source ID: {src.get('id')}")
            print(f"  URL: {src.get('citation_url')}")
            print(f"  Status: {src.get('status')}")
            
            content = src.get('content_text', '') or ''
            print(f"  Full Content Length: {len(content)} chars")
            print(f"\n  FULL CONTENT:\n")
            print("  " + "-" * 76)
            # Print full content with line wrapping
            lines = content.split('\n')
            for line in lines:
                if line.strip():
                    print(f"  {line}")
            print("  " + "-" * 76)
    else:
        print("\n[3] No Instagram sources found")
    
    # Check Pinecone
    print("\n" + "=" * 80)
    print("[4] PINECONE VECTORS:")
    print("=" * 80)
    
    try:
        from modules.clients import get_pinecone_index
        from modules.delphi_namespace import get_namespace_candidates_for_twin
        
        index = get_pinecone_index()
        stats = index.describe_index_stats()
        
        print(f"  Total Index Vectors: {stats.total_vector_count}")
        print(f"  Dimension: {stats.dimension}")
        
        namespaces = get_namespace_candidates_for_twin(twin_id=TWIN_ID, include_legacy=True)
        print(f"\n  Checking namespaces: {namespaces}")
        
        for namespace in namespaces:
            ns_stats = stats.namespaces.get(namespace, {})
            vector_count = ns_stats.get('vector_count', 0)
            
            print(f"\n  Namespace: {namespace}")
            print(f"  Vector Count: {vector_count}")
            
            if vector_count > 0:
                try:
                    query_res = index.query(
                        vector=[0.1] * stats.dimension,
                        top_k=10,
                        include_metadata=True,
                        namespace=namespace
                    )
                    matches = query_res.get('matches', [])
                    print(f"  Sample vectors:")
                    for i, match in enumerate(matches[:5], 1):
                        metadata = match.get('metadata', {})
                        source_type = metadata.get('source_type', 'N/A')
                        category = metadata.get('category', 'N/A')
                        score = match.get('score', 0)
                        text_preview = metadata.get('chunk_text', '')[:100] or metadata.get('text', '')[:100]
                        print(f"    {i}. Score: {score:.4f}, Type: {source_type}, Category: {category}")
                        if text_preview:
                            print(f"       Text: {text_preview}...")
                except Exception as e:
                    print(f"  Error querying: {e}")
            else:
                print(f"  [WARNING] No vectors in this namespace")
                
    except Exception as e:
        print(f"  [ERROR] Error connecting to Pinecone: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("REPORT COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()
