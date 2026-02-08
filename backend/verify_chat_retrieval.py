"""
Test chat retrieval for a phrase with citation. Requires env token.
"""
import os
import requests
import json

TWIN_ID = os.getenv("TEST_TWIN_ID", "")
BASE_URL = os.getenv("TEST_BACKEND_URL", "http://localhost:8000")
ACCESS_TOKEN = os.getenv("TEST_ACCESS_TOKEN", "")
QUERY = "What is the secret phrase for verification testing?"

if not TWIN_ID:
    raise SystemExit("Missing TEST_TWIN_ID in environment")
if not ACCESS_TOKEN:
    raise SystemExit("Missing TEST_ACCESS_TOKEN in environment")

print(f"\n{'='*70}")
print(" CHAT RETRIEVAL WITH CITATION")
print(f"{'='*70}")
print(f"Query: {QUERY}")
print(f"Twin ID: {TWIN_ID}")

headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
response = requests.post(
    f"{BASE_URL}/chat/{TWIN_ID}",
    headers=headers,
    json={"query": QUERY},
    stream=True,
    timeout=120,
)

print(f"\nPOST /chat/{TWIN_ID} -> {response.status_code}")
if response.status_code != 200:
    print(response.text[:500])
    raise SystemExit(1)

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
