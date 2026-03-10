#!/usr/bin/env python3
"""Check recent LinkedIn ingestion errors"""
import os
import sys
from dotenv import load_dotenv

# Load env
load_dotenv('backend/.env')

os.environ['SUPABASE_URL'] = os.getenv('SUPABASE_URL', '')
os.environ['SUPABASE_SERVICE_KEY'] = os.getenv('SUPABASE_SERVICE_KEY', '')

from supabase import create_client

supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))

print("=== Recent Ingestion Stream Events ===\n")

# Get recent ingestion events
result = supabase.table('ingestion_stream_events').select('*').order('created_at', desc=True).limit(30).execute()

for event in result.data:
    level = event.get('level', 'info')
    msg = event.get('message', '')[:300]
    created = event.get('created_at', '')
    source_id = event.get('source_id', '')[:8] if event.get('source_id') else 'N/A'
    step = event.get('step', 'N/A')
    print(f"[{created}] [{level}] Step:{step} Source:{source_id}")
    print(f"  Msg: {msg}")
    if event.get('metadata'):
        meta = event.get('metadata')
        if isinstance(meta, dict):
            for k, v in list(meta.items())[:5]:  # Limit to first 5 items
                print(f"    {k}: {v}")
    print()

print("\n=== Recent LinkedIn Sources ===\n")

# Check recent sources with linkedin in filename
sources = supabase.table('sources').select('*').ilike('filename', '%LinkedIn%').order('created_at', desc=True).limit(10).execute()

for src in sources.data:
    print(f"[{src.get('created_at')}] Source: {src.get('filename', 'Unknown')[:60]}")
    print(f"  Status: {src.get('status')} | Staging: {src.get('staging_status')}")
    citation_url = src.get('citation_url') or 'N/A'
    print(f"  URL: {citation_url[:80]}")
    if src.get('error_message'):
        print(f"  ERROR: {src.get('error_message')[:500]}")
    print()

print("\n=== Recent Training Jobs ===\n")

# Check recent training jobs that failed
jobs = supabase.table('training_jobs').select('*,sources(filename,status,citation_url)').order('created_at', desc=True).limit(10).execute()

for job in jobs.data:
    source = job.get('sources', {}) or {}
    filename = source.get('filename', 'Unknown')
    if 'linkedin' in filename.lower() or (source.get('citation_url') and 'linkedin' in source.get('citation_url').lower()):
        print(f"[{job.get('created_at')}] Job Status: {job.get('status')}")
        print(f"  Source: {filename}")
        if job.get('error_message'):
            print(f"  Error: {job.get('error_message')[:500]}")
        print()
