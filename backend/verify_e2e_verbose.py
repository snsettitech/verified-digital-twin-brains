"""
Verbose end-to-end ingestion/chat check. Requires env token.
"""
import os
import json
import requests

TWIN_ID = os.getenv("TEST_TWIN_ID", "")
BASE_URL = os.getenv("TEST_BACKEND_URL", "http://localhost:8000")
ACCESS_TOKEN = os.getenv("TEST_ACCESS_TOKEN", "")
SOURCE_ID = os.getenv("TEST_SOURCE_ID", "")

if not TWIN_ID:
    raise SystemExit("Missing TEST_TWIN_ID in environment")
if not ACCESS_TOKEN:
    raise SystemExit("Missing TEST_ACCESS_TOKEN in environment")

headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}

print(f"{'='*70}")
print("STEP 1: Verify source")
print(f"{'='*70}")

response = requests.get(f"{BASE_URL}/sources/{TWIN_ID}", headers=headers, timeout=60)
print(f"GET /sources/{TWIN_ID} -> {response.status_code}")
if response.status_code == 200 and SOURCE_ID:
    sources = response.json()
    src = next((s for s in sources if s.get("id") == SOURCE_ID), None)
    if src:
        print(f"Source found: {src.get('filename')} [{src.get('status')}]")

print(f"\n{'='*70}")
print("STEP 2: Chat retrieve")
print(f"{'='*70}")

query = "What is INGEST-FILE-XYLOPHONE-PURPLE-2024?"
response = requests.post(
    f"{BASE_URL}/chat/{TWIN_ID}",
    headers=headers,
    json={"query": query},
    stream=True,
    timeout=120,
)
print(f"POST /chat/{TWIN_ID} -> {response.status_code}")

full_content = ""
metadata = None
for line in response.iter_lines():
    if not line:
        continue
    line_str = line.decode("utf-8")
    if line_str.startswith("data: "):
        line_str = line_str[6:]
    try:
        data = json.loads(line_str)
    except json.JSONDecodeError:
        continue
    if data.get("type") == "content":
        full_content += data.get("content", "")
    elif data.get("type") == "metadata":
        metadata = data

print("\nFULL RESPONSE:")
print(full_content[:500])
if metadata:
    print("\nMETADATA:")
    print(json.dumps(metadata, indent=2)[:800])
