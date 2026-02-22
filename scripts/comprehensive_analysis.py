#!/usr/bin/env python3
"""
Comprehensive Analysis of Digital Twin System
"""
import os
import sys
import asyncio
import json

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'backend', '.env'))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from supabase import create_client
from modules.clients import get_pinecone_index
from modules.delphi_namespace import get_namespace_candidates_for_twin

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY')

# Initialize clients
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================================================
# PART 1: Debug Frontend Twin ID Issue
# ============================================================================
def analyze_frontend_twin_id_issue():
    print("=" * 80)
    print("PART 1: FRONTEND TWIN ID ISSUE ANALYSIS")
    print("=" * 80)
    
    # The twin ID from the error: 11839ada-d93a-418f-a851-21f9c5a3ae36
    error_twin_id = "11839ada-d93a-418f-a851-21f9c5a3ae36"
    
    print(f"\nTwin ID from error: {error_twin_id}")
    
    # Check if this twin exists
    twin_res = supabase.table("twins").select("*").eq("id", error_twin_id).execute()
    
    if twin_res.data:
        print("  [FOUND] Twin exists in database!")
        print(f"  Name: {twin_res.data[0].get('name')}")
        print(f"  Tenant: {twin_res.data[0].get('tenant_id')}")
        print(f"  Created: {twin_res.data[0].get('created_at')}")
    else:
        print("  [NOT FOUND] Twin does NOT exist in database!")
        print("\n  Possible causes:")
        print("  1. Twin was deleted but frontend still has cached ID")
        print("  2. Frontend is using localStorage with stale data")
        print("  3. Different environment (dev vs prod)")
        print("  4. Race condition in twin creation")
        
        # Check localStorage pattern
        print("\n  Frontend localStorage pattern:")
        print("  - activeTwinId is stored in localStorage")
        print("  - If user deletes twin, localStorage may not be cleared")
        print("  - Or if twin creation fails partially, ID might be set without DB record")
    
    # Check all twins for this user (if we can identify them)
    print("\n  All twins in database (recent 10):")
    all_twins = supabase.table("twins").select("id, name, tenant_id, created_at").order("created_at", desc=True).limit(10).execute()
    
    for twin in all_twins.data or []:
        tid = twin.get('id')
        name = twin.get('name', 'N/A')
        print(f"    - {name}: {tid}")
        if tid == error_twin_id:
            print("      ^^^ THIS IS THE MISSING TWIN!")

# ============================================================================
# PART 2: Check Pinecone Vectors for Actual Twins
# ============================================================================
def analyze_pinecone_vectors():
    print("\n" + "=" * 80)
    print("PART 2: PINECONE VECTORS ANALYSIS")
    print("=" * 80)
    
    try:
        index = get_pinecone_index()
        stats = index.describe_index_stats()
        
        print(f"\n[Pinecone Index Stats]")
        print(f"  Total Vectors: {stats.total_vector_count}")
        print(f"  Dimension: {stats.dimension}")
        print(f"  Total Namespaces: {len(stats.namespaces)}")
        
        # Get all twins
        twins_res = supabase.table("twins").select("id, name").execute()
        
        print(f"\n[Vector Analysis by Twin]")
        print(f"  Checking {len(twins_res.data)} twins...\n")
        
        for twin in twins_res.data:
            tid = twin.get('id')
            tname = twin.get('name', 'N/A')
            
            namespaces = get_namespace_candidates_for_twin(twin_id=tid, include_legacy=True)
            total_vectors = 0
            
            print(f"  Twin: {tname} ({tid[:8]}...)")
            
            for ns in namespaces:
                ns_stats = stats.namespaces.get(ns, {})
                vec_count = ns_stats.get('vector_count', 0)
                total_vectors += vec_count
                print(f"    Namespace '{ns}': {vec_count} vectors")
            
            print(f"    TOTAL: {total_vectors} vectors\n")
            
            # Sample some vectors if they exist
            if total_vectors > 0:
                try:
                    for ns in namespaces:
                        ns_stats = stats.namespaces.get(ns, {})
                        if ns_stats.get('vector_count', 0) > 0:
                            query_res = index.query(
                                vector=[0.1] * stats.dimension,
                                top_k=3,
                                include_metadata=True,
                                namespace=ns
                            )
                            matches = query_res.get('matches', [])
                            if matches:
                                print(f"    Sample from '{ns}':")
                                for i, match in enumerate(matches, 1):
                                    meta = match.get('metadata', {})
                                    source_type = meta.get('source_type', 'N/A')
                                    text_preview = (meta.get('chunk_text', '') or meta.get('text', ''))[:80]
                                    print(f"      {i}. Type: {source_type}")
                                    if text_preview:
                                        print(f"         Text: {text_preview}...")
                                print()
                            break
                except Exception as e:
                    print(f"    Error sampling: {e}")
        
        # Check for orphaned vectors (namespaces without twins)
        print(f"\n[Orphaned Namespaces Check]")
        all_twin_ids = {t.get('id') for t in twins_res.data}
        orphaned = []
        
        for ns_name in stats.namespaces.keys():
            # Check if namespace belongs to a twin
            is_orphaned = True
            for tid in all_twin_ids:
                if tid in ns_name or ns_name in get_namespace_candidates_for_twin(tid, include_legacy=True):
                    is_orphaned = False
                    break
            if is_orphaned and not ns_name.startswith('creator_'):
                orphaned.append(ns_name)
        
        if orphaned:
            print(f"  Found {len(orphaned)} potentially orphaned namespaces:")
            for ns in orphaned[:10]:
                count = stats.namespaces.get(ns, {}).get('vector_count', 0)
                print(f"    - {ns}: {count} vectors")
        else:
            print("  No orphaned namespaces found")
            
    except Exception as e:
        print(f"\n[ERROR] Could not connect to Pinecone: {e}")
        import traceback
        traceback.print_exc()

# ============================================================================
# PART 3: Test Dumpling AI Integration for Instagram
# ============================================================================
async def test_dumpling_ai_instagram():
    print("\n" + "=" * 80)
    print("PART 3: DUMPLING AI INSTAGRAM TEST")
    print("=" * 80)
    
    from modules.dumplingai_client import scrape_webpage
    
    # Test URLs
    test_urls = [
        ("Instagram Profile", "https://www.instagram.com/nasa/"),
        ("Instagram Post", "https://www.instagram.com/p/C3hYb1Yr5zX/"),
        ("LinkedIn Profile", "https://www.linkedin.com/in/satyanadella/"),
        ("Regular Website", "https://example.com"),
    ]
    
    print("\nTesting Dumpling AI with various URLs:\n")
    
    for name, url in test_urls:
        print(f"  Testing: {name}")
        print(f"  URL: {url}")
        
        try:
            result = await scrape_webpage(
                url=url,
                format="markdown",
                cleaned=True,
                render_js=True,
            )
            
            if result and isinstance(result, dict):
                content = result.get("content", "") or result.get("markdown", "") or ""
                title = result.get("title", "N/A")
                
                print(f"  Status: SUCCESS")
                print(f"  Title: {title}")
                print(f"  Content Length: {len(content)} chars")
                
                if content:
                    preview = content[:300].replace('\n', ' ')
                    print(f"  Preview: {preview}...")
                else:
                    print(f"  [WARNING] No content returned!")
            else:
                print(f"  Status: FAILED - Invalid response format")
                print(f"  Response: {result}")
                
        except Exception as e:
            print(f"  Status: FAILED")
            print(f"  Error: {e}")
        
        print()

# ============================================================================
# PART 4: Ingestion System Analysis
# ============================================================================
def analyze_ingestion_system():
    print("\n" + "=" * 80)
    print("PART 4: INGESTION SYSTEM ANALYSIS")
    print("=" * 80)
    
    # Check sources by status
    print("\n[Sources by Status]")
    
    statuses = ['live', 'processing', 'pending', 'error', 'staged']
    for status in statuses:
        count_res = supabase.table("sources").select("id", count="exact").eq("status", status).execute()
        count = count_res.count if hasattr(count_res, 'count') else 0
        print(f"  {status}: {count}")
    
    # Check recent errors
    print("\n[Recent Failed Sources]")
    error_sources = supabase.table("sources")\
        .select("*, twins(name)")\
        .eq("status", "error")\
        .order("created_at", desc=True)\
        .limit(10)\
        .execute()
    
    if error_sources.data:
        for src in error_sources.data:
            twin_name = src.get('twins', {}).get('name', 'N/A') if src.get('twins') else 'N/A'
            fname = src.get('filename', 'N/A')
            url = src.get('citation_url', 'N/A')
            print(f"  - {fname} (Twin: {twin_name})")
            print(f"    URL: {url}")
    else:
        print("  No failed sources")
    
    # Check content extraction stats
    print("\n[Content Extraction Stats]")
    all_sources = supabase.table("sources").select("content_text, status").execute()
    
    total = len(all_sources.data) if all_sources.data else 0
    with_content = sum(1 for s in all_sources.data if s.get('content_text') and len(s.get('content_text')) > 100)
    empty_content = sum(1 for s in all_sources.data if not s.get('content_text') or len(s.get('content_text')) < 50)
    
    print(f"  Total sources: {total}")
    print(f"  With substantial content (>100 chars): {with_content}")
    print(f"  With minimal/no content: {empty_content}")
    
    # Check chunks
    print("\n[Chunks Analysis]")
    chunks_count = supabase.table("chunks").select("id", count="exact").execute()
    total_chunks = chunks_count.count if hasattr(chunks_count, 'count') else 0
    print(f"  Total chunks: {total_chunks}")
    
    # Chunks with vector_ids
    chunks_with_vectors = supabase.table("chunks").select("id", count="exact").not_.is_("vector_id", "null").execute()
    with_vec = chunks_with_vectors.count if hasattr(chunks_with_vectors, 'count') else 0
    print(f"  Chunks with vector_ids: {with_vec}")
    print(f"  Chunks without vector_ids: {total_chunks - with_vec}")

# ============================================================================
# PART 5: Chat Retrieval Analysis
# ============================================================================
def analyze_chat_retrieval():
    print("\n" + "=" * 80)
    print("PART 5: CHAT RETRIEVAL ANALYSIS")
    print("=" * 80)
    
    # Check conversations
    print("\n[Conversations Stats]")
    conv_count = supabase.table("conversations").select("id", count="exact").execute()
    print(f"  Total conversations: {conv_count.count if hasattr(conv_count, 'count') else 0}")
    
    # Check messages
    msg_count = supabase.table("messages").select("id", count="exact").execute()
    print(f"  Total messages: {msg_count.count if hasattr(msg_count, 'count') else 0}")
    
    # Recent conversations
    print("\n[Recent Conversations]")
    recent_conv = supabase.table("conversations")\
        .select("*, twins(name)")\
        .order("created_at", desc=True)\
        .limit(5)\
        .execute()
    
    if recent_conv.data:
        for conv in recent_conv.data:
            twin_name = conv.get('twins', {}).get('name', 'N/A') if conv.get('twins') else 'N/A'
            cid = conv.get('id')
            created = conv.get('created_at')
            print(f"  - {cid[:8]}... (Twin: {twin_name}, Created: {created})")
            
            # Get message count for this conversation
            msgs = supabase.table("messages").select("id", count="exact").eq("conversation_id", cid).execute()
            print(f"    Messages: {msgs.count if hasattr(msgs, 'count') else 0}")
    
    # Check retrieval configuration
    print("\n[Retrieval Configuration]")
    print(f"  PINECONE_INDEX_MODE: {os.getenv('PINECONE_INDEX_MODE', 'not set')}")
    print(f"  PINECONE_HOST: {'set' if os.getenv('PINECONE_HOST') else 'not set'}")
    print(f"  DELPHI_DUAL_READ: {os.getenv('DELPHI_DUAL_READ', 'not set')}")
    
    # Check for common retrieval issues
    print("\n[Potential Retrieval Issues]")
    
    # 1. Twins without any vectors
    twins_res = supabase.table("twins").select("id, name").execute()
    twins_without_vectors = []
    
    try:
        index = get_pinecone_index()
        stats = index.describe_index_stats()
        
        for twin in twins_res.data:
            tid = twin.get('id')
            namespaces = get_namespace_candidates_for_twin(twin_id=tid, include_legacy=True)
            has_vectors = False
            
            for ns in namespaces:
                if ns in stats.namespaces and stats.namespaces[ns].get('vector_count', 0) > 0:
                    has_vectors = True
                    break
            
            if not has_vectors:
                sources = supabase.table("sources").select("id", count="exact").eq("twin_id", tid).execute()
                source_count = sources.count if hasattr(sources, 'count') else 0
                if source_count > 0:
                    twins_without_vectors.append((twin.get('name'), tid, source_count))
        
        if twins_without_vectors:
            print(f"  [ISSUE] Twins with sources but NO vectors:")
            for name, tid, scount in twins_without_vectors:
                print(f"    - {name} ({tid[:8]}...): {scount} sources, 0 vectors")
            print(f"    This means chat retrieval will return NO results for these twins!")
        else:
            print("  [OK] All twins with sources have vectors")
            
    except Exception as e:
        print(f"  [ERROR] Could not check: {e}")

# ============================================================================
# PART 6: Recommendations
# ============================================================================
def provide_recommendations():
    print("\n" + "=" * 80)
    print("PART 6: RECOMMENDATIONS")
    print("=" * 80)
    
    print("""
[CRITICAL ISSUES]

1. FRONTEND TWIN ID CACHING BUG
   - The frontend is using twin ID '11839ada-d93a-418f-a851-21f9c5a3ae36' which doesn't exist
   - This is cached in localStorage (activeTwinId)
   - FIX: Clear localStorage in browser or add validation in TwinContext

2. LINKEDIN INGESTION FAILING
   - All LinkedIn sources show 'error' status with 0 content
   - This is expected - LinkedIn blocks scraping aggressively
   - FIX: Use Dumpling AI's dedicated LinkedIn endpoint (already implemented)

3. TWINS WITHOUT VECTORS
   - Some twins have sources but no Pinecone vectors
   - This breaks chat retrieval completely
   - FIX: Re-index those sources or investigate ingestion pipeline

[IMPROVEMENTS NEEDED]

1. INGESTION PIPELINE
   - Add retry logic for failed sources
   - Better error messages to users
   - Progress tracking for long-running ingestions
   - Validate content extraction before marking as 'live'

2. CHAT RETRIEVAL
   - Add fallback to keyword search if semantic search returns nothing
   - Better context window management
   - Citation accuracy improvements
   - Handle cases where no relevant chunks found

3. DUMPLING AI INTEGRATION
   - Already improved in latest commit
   - Monitor Instagram extraction quality
   - Add more social media specific handling

4. FRONTEND ROBUSTNESS
   - Validate twin ID exists before API calls
   - Clear localStorage on twin deletion
   - Better error handling for 500 errors

[MONITORING]

1. Add alerting for:
   - Sources stuck in 'processing' > 30 minutes
   - Twins with sources but 0 vectors
   - Failed ingestion events
   - 500 errors from backend

2. Add dashboard metrics:
   - Ingestion success rate by source type
   - Average chunks per source
   - Chat retrieval success rate
""")

async def main():
    analyze_frontend_twin_id_issue()
    analyze_pinecone_vectors()
    await test_dumpling_ai_instagram()
    analyze_ingestion_system()
    analyze_chat_retrieval()
    provide_recommendations()

if __name__ == "__main__":
    asyncio.run(main())
