"""
Verify sources via API endpoint. Requires env token.
"""
import os
import requests

TWIN_ID = os.getenv("TEST_TWIN_ID", "")
SOURCE_ID = os.getenv("TEST_SOURCE_ID", "")
BASE_URL = os.getenv("TEST_BACKEND_URL", "http://localhost:8000")
ACCESS_TOKEN = os.getenv("TEST_ACCESS_TOKEN", "")

if not TWIN_ID:
    raise SystemExit("Missing TEST_TWIN_ID in environment")
if not ACCESS_TOKEN:
    raise SystemExit("Missing TEST_ACCESS_TOKEN in environment")

print(f"\n{'='*70}")
print(" SUPABASE SOURCES ROW (via API)")
print(f"{'='*70}")

headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
response = requests.get(f"{BASE_URL}/sources/{TWIN_ID}", headers=headers, timeout=60)
print(f"GET /sources/{TWIN_ID} -> {response.status_code}")

if response.status_code == 200:
    sources = response.json()
    if SOURCE_ID:
        src = next((s for s in sources if s.get("id") == SOURCE_ID), None)
    else:
        src = sources[0] if sources else None
    if src:
        print(f"id: {src.get('id')}")
        print(f"twin_id: {src.get('twin_id')}")
        print(f"status: {src.get('status')}")
        print(f"filename: {src.get('filename')}")
        print(f"chunk_count: {src.get('chunk_count')}")
    else:
        print("No sources found")
else:
    print(f"Error: {response.text}")
