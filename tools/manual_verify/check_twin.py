#!/usr/bin/env python3
import os
from dotenv import load_dotenv
load_dotenv('backend/.env')

from supabase import create_client

supabase = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_SERVICE_KEY')
)

# Get twin sources
sources = supabase.table('sources').select('*').eq('twin_id', '88289f30-a068-4350-8c95-4c228f436fee').execute()
print(f'\nSources ({len(sources.data)}):')
for s in sources.data[:5]:
    filename = s.get('filename', 'Unknown')
    status = s.get('status', 'unknown')
    print(f'  - {filename}: {status}')

# Get twin details
twin = supabase.table('twins').select('*').eq('id', '88289f30-a068-4350-8c95-4c228f436fee').execute()
if twin.data:
    t = twin.data[0]
    print(f"\nTwin: {t.get('name', 'Unknown')}")
    print(f"Owner: {t.get('user_id', 'Unknown')}")
    print(f"Status: {t.get('status', 'Unknown')}")
    
    # Get owner email
    owner = supabase.table('profiles').select('email').eq('id', t.get('user_id')).execute()
    if owner.data:
        print(f"Owner Email: {owner.data[0].get('email')}")
