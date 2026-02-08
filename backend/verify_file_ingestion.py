"""
File Ingestion Verification Script - requires env token.
"""
import os
import requests
import json
from datetime import datetime

TWIN_ID = os.getenv("TEST_TWIN_ID", "")
BASE_URL = os.getenv("TEST_BACKEND_URL", "http://localhost:8000")
FILE_PATH = "./temp_uploads/test_file_verification.txt"
ACCESS_TOKEN = os.getenv("TEST_ACCESS_TOKEN", "")

if not TWIN_ID:
    raise SystemExit("Missing TEST_TWIN_ID in environment")
if not ACCESS_TOKEN:
    raise SystemExit("Missing TEST_ACCESS_TOKEN in environment")

print(f"\n{'='*70}")
print(" FILE INGESTION PROOF PACKET")
print(f"{'='*70}")
print(f"Timestamp: {datetime.now().isoformat()}")
print(f"Twin ID: {TWIN_ID}")
print(f"File: {FILE_PATH}")

with open(FILE_PATH, 'r', encoding='utf-8') as f:
    content = f.read()
print(f"\nFile content preview:\n{content[:200]}...")

print(f"\n--- Step 1: POST /ingest/file/{TWIN_ID} ---")
headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}

try:
    with open(FILE_PATH, 'rb') as f:
        files = {'file': ('test_file_verification.txt', f, 'text/plain')}
        response = requests.post(
            f"{BASE_URL}/ingest/file/{TWIN_ID}",
            files=files,
            headers=headers,
            timeout=120,
        )

    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")

    if response.status_code == 200:
        result = response.json()
        print("\nProof artifact:")
        print(json.dumps(result, indent=2))
    else:
        print("\nUpload failed")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
