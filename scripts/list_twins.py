#!/usr/bin/env python3
"""
List all twins
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from modules.observability import supabase

def main():
    print("Listing all twins...\n")
    
    # Try to get twins
    try:
        res = supabase.table("twins").select("*").order("created_at", desc=True).limit(20).execute()
        
        if res.data:
            print(f"Found {len(res.data)} twins:\n")
            for twin in res.data:
                tid = twin.get('id')
                name = twin.get('name', 'N/A')
                created = twin.get('created_at', 'N/A')
                print(f"  ID: {tid}")
                print(f"  Name: {name}")
                print(f"  Created: {created}")
                print()
                
                # Get sources for this twin
                sources_res = supabase.table("sources").select("id, filename, citation_url, status").eq("twin_id", tid).execute()
                if sources_res.data:
                    print(f"    Sources ({len(sources_res.data)}):")
                    for src in sources_res.data:
                        fname = src.get('filename', 'N/A')
                        url = src.get('citation_url', 'N/A')
                        status = src.get('status', 'N/A')
                        print(f"      - {fname} [{status}]")
                        if url:
                            print(f"        URL: {url}")
                else:
                    print("    No sources")
                print()
        else:
            print("No twins found")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
