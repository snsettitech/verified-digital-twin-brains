#!/usr/bin/env python3
"""
Check LinkedIn sources status
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'backend', '.env'))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from supabase import create_client

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY')

def check_sources():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Get all LinkedIn sources
    sources = supabase.table("sources").select("*").ilike("citation_url", "%linkedin%").execute()
    
    print("=" * 80)
    print(f"LINKEDIN SOURCES ({len(sources.data)} total)")
    print("=" * 80)
    
    for s in sources.data:
        print(f"\nID: {s.get('id')}")
        print(f"  Filename: {s.get('filename')}")
        print(f"  Status: {s.get('status')}")
        print(f"  URL: {s.get('citation_url')}")
        print(f"  Content length: {len(s.get('content_text') or '')}")
        print(f"  Chunk count: {s.get('chunk_count')}")
        print(f"  Created: {s.get('created_at')}")

if __name__ == "__main__":
    check_sources()
