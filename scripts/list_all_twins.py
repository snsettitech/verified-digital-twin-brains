#!/usr/bin/env python3
"""
List all twins and their sources
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
    print("LISTING ALL TWINS")
    print("=" * 80)
    
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Get all twins
    twins_res = supabase.table("twins").select("*").order("created_at", desc=True).limit(20).execute()
    
    if not twins_res.data:
        print("No twins found!")
        return
    
    print(f"\nFound {len(twins_res.data)} twins:\n")
    
    for twin in twins_res.data:
        tid = twin.get('id')
        name = twin.get('name', 'N/A')
        created = twin.get('created_at', 'N/A')
        tenant_id = twin.get('tenant_id', 'N/A')
        
        print("-" * 80)
        print(f"Twin: {name}")
        print(f"  ID: {tid}")
        print(f"  Tenant ID: {tenant_id}")
        print(f"  Created: {created}")
        
        # Get sources for this twin
        sources_res = supabase.table("sources").select("*").eq("twin_id", tid).order("created_at", desc=True).execute()
        
        if sources_res.data:
            print(f"\n  Sources ({len(sources_res.data)}):")
            for src in sources_res.data:
                sid = src.get('id')
                fname = src.get('filename', 'N/A')
                url = src.get('citation_url', 'N/A')
                status = src.get('status', 'N/A')
                content_len = len(src.get('content_text', '') or '')
                
                print(f"    - {fname}")
                print(f"      ID: {sid}")
                print(f"      URL: {url}")
                print(f"      Status: {status}")
                print(f"      Content: {content_len} chars")
                
                # Check for Instagram
                if url and 'instagram' in url.lower():
                    print(f"      *** INSTAGRAM SOURCE ***")
                    if content_len > 0:
                        preview = (src.get('content_text', '') or '')[:300].replace('\n', ' ')
                        print(f"      Preview: {preview}...")
                print()
        else:
            print("  No sources")
            print()

if __name__ == "__main__":
    main()
