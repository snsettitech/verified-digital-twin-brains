#!/usr/bin/env python3
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'backend', '.env'))

from supabase import create_client

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY')

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print("=" * 80)
print("INGESTION & RETRIEVAL SYSTEM STATUS")
print("=" * 80)

print("\n[1] SOURCES BY STATUS]")
statuses = ['live', 'processing', 'pending', 'error', 'staged']
for status in statuses:
    res = supabase.table('sources').select('id', count='exact').eq('status', status).execute()
    count = res.count if hasattr(res, 'count') else 0
    print(f"  {status}: {count}")

print("\n[2] FAILED SOURCES (Last 10)]")
errors = supabase.table('sources').select('filename, citation_url, status, content_text, twins(name)').eq('status', 'error').order('created_at', desc=True).limit(10).execute()
for src in errors.data or []:
    twin = src.get('twins', {}).get('name', 'N/A') if src.get('twins') else 'N/A'
    print(f"  - {src.get('filename')} (Twin: {twin})")
    print(f"    URL: {src.get('citation_url')}")
    print(f"    Content: {len(src.get('content_text') or '')} chars")
print()

print("[3] CONTENT EXTRACTION STATS]")
all_src = supabase.table('sources').select('content_text, status').execute()
total = len(all_src.data)
with_content = sum(1 for s in all_src.data if s.get('content_text') and len(s.get('content_text')) > 100)
empty = sum(1 for s in all_src.data if not s.get('content_text') or len(s.get('content_text', '')) < 50)
print(f"  Total sources: {total}")
print(f"  With content (>100 chars): {with_content}")
print(f"  Minimal/no content: {empty}")

print()
print("[4] CHAT/CONVERSATION STATS]")
conv = supabase.table('conversations').select('id', count='exact').execute()
msg = supabase.table('messages').select('id', count='exact').execute()
print(f"  Total conversations: {conv.count if hasattr(conv, 'count') else 0}")
print(f"  Total messages: {msg.count if hasattr(msg, 'count') else 0}")

print()
print("[5] CHUNKS ANALYSIS]")
chunks_res = supabase.table('chunks').select('id', count='exact').execute()
total_chunks = chunks_res.count if hasattr(chunks_res, 'count') else 0
print(f"  Total chunks: {total_chunks}")

chunks_with_vec = supabase.table('chunks').select('id', count='exact').not_.is_('vector_id', 'null').execute()
with_vec = chunks_with_vec.count if hasattr(chunks_with_vec, 'count') else 0
print(f"  Chunks with vector_ids: {with_vec}")
print(f"  Chunks without vector_ids: {total_chunks - with_vec}")

print()
print("=" * 80)
