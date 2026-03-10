#!/usr/bin/env python3
"""
Check recent ingestion activity
"""
import os
import sys

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'backend', '.env'))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from supabase import create_client

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY')

def main():
    print("=" * 80)
    print("RECENT INGESTION ACTIVITY")
    print("=" * 80)
    
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Get recent sources (last 24 hours)
    import datetime
    from datetime import timezone, timedelta
    
    yesterday = (datetime.datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    
    sources_res = supabase.table("sources")\
        .select("*, twins(name)")\
        .gte("created_at", yesterday)\
        .order("created_at", desc=True)\
        .execute()
    
    if not sources_res.data:
        print("\nNo sources created in last 48 hours")
    else:
        print(f"\nSources created in last 48 hours ({len(sources_res.data)}):\n")
        
        for src in sources_res.data:
            tid = src.get('twin_id')
            tname = src.get('twins', {}).get('name', 'N/A') if src.get('twins') else 'N/A'
            fname = src.get('filename', 'N/A')
            url = src.get('citation_url', 'N/A')
            status = src.get('status', 'N/A')
            created = src.get('created_at', 'N/A')
            content_len = len(src.get('content_text', '') or '')
            
            print(f"Twin: {tname} ({tid})")
            print(f"  Source: {fname}")
            print(f"  URL: {url}")
            print(f"  Status: {status}")
            print(f"  Created: {created}")
            print(f"  Content Length: {content_len} chars")
            
            if url and 'instagram' in url.lower():
                print(f"  *** INSTAGRAM FOUND ***")
                print(f"  Content: {(src.get('content_text', '') or '')[:500]}")
            print()
    
    # Get all sources with Instagram
    print("=" * 80)
    print("ALL INSTAGRAM SOURCES (if any)")
    print("=" * 80)
    
    all_sources = supabase.table("sources").select("*, twins(name)").execute()
    instagram_sources = []
    
    for src in all_sources.data or []:
        url = src.get('citation_url', '') or ''
        if 'instagram' in url.lower():
            instagram_sources.append(src)
    
    if instagram_sources:
        print(f"\nFound {len(instagram_sources)} Instagram sources:\n")
        for src in instagram_sources:
            tid = src.get('twin_id')
            tname = src.get('twins', {}).get('name', 'N/A') if src.get('twins') else 'N/A'
            fname = src.get('filename', 'N/A')
            url = src.get('citation_url', 'N/A')
            status = src.get('status', 'N/A')
            content = src.get('content_text', '') or ''
            
            print(f"Twin: {tname} ({tid})")
            print(f"  Source: {fname}")
            print(f"  URL: {url}")
            print(f"  Status: {status}")
            print(f"  Content Length: {len(content)} chars")
            if content:
                print(f"  Content Preview:\n{content[:1000]}...")
            print()
    else:
        print("\nNo Instagram sources found in database")
    
    # Check ingestion events
    print("=" * 80)
    print("RECENT INGESTION EVENTS")
    print("=" * 80)
    
    try:
        events_res = supabase.table("ingestion_events")\
            .select("*")\
            .order("created_at", desc=True)\
            .limit(20)\
            .execute()
        
        if events_res.data:
            print(f"\nLast {len(events_res.data)} events:\n")
            for evt in events_res.data:
                created = evt.get('created_at', 'N/A')
                step = evt.get('step', 'N/A')
                status = evt.get('status', 'N/A')
                msg = evt.get('message', 'N/A')
                twin_id = evt.get('twin_id', 'N/A')
                print(f"  {created}")
                print(f"    Twin: {twin_id}")
                print(f"    Step: {step} | Status: {status}")
                print(f"    Message: {msg}")
                print()
        else:
            print("\nNo ingestion events found")
    except Exception as e:
        print(f"\nError fetching events: {e}")

if __name__ == "__main__":
    main()
