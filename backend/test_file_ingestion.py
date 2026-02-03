"""
File Ingestion Verification Script - WITH AUTH
Tests the /ingest/file endpoint with proper JWT token
"""
import pytest
import requests
import json
from datetime import datetime

TWIN_ID = "e9c18ffa-ec7b-4f30-ab97-1beccd9fab4a"
BASE_URL = "http://localhost:8000"
FILE_PATH = "./temp_uploads/test_file_verification.txt"

# Token extracted from browser session
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsImtpZCI6IkcxbDk3bG50aTdFQU5KTGciLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL2p2dGZmZGJ1d3lobWN5bmF1ZXR5LnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiI1NWI0YzJiZS1jMGQzLTRjNzItYjllNy1mNjVjMmM2YmI2ZmIiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzY5OTE0MTAzLCJpYXQiOjE3Njk5MTA1MDMsImVtYWlsIjoic2FpbmF0aHNldHRpQGdtYWlsLmNvbSIsInBob25lIjoiIiwiYXBwX21ldGFkYXRhIjp7InByb3ZpZGVyIjoiZ29vZ2xlIiwicHJvdmlkZXJzIjpbImdvb2dsZSJdfSwidXNlcl9tZXRhZGF0YSI6eyJhdmF0YXJfdXJsIjoiaHR0cHM6Ly9saDMuZ29vZ2xldXNlcmNvbnRlbnQuY29tL2EvQUNnOG9jSXBEcXFXc3JCd1VUdWotOW1vV0hUNG94RGg4RWJEUFV5cXpHZjBrajkzdHpLS2I4YXRDUT1zOTYtYyIsImVtYWlsIjoic2FpbmF0aHNldHRpQGdtYWlsLmNvbSIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJmdWxsX25hbWUiOiJTYWluYXRoIFNldHRpIiwiaXNzIjoiaHR0cHM6Ly9hY2NvdW50cy5nb29nbGUuY29tIiwibmFtZSI6IlNhaW5hdGggU2V0dGkiLCJwaG9uZV92ZXJpZmllZCI6ZmFsc2UsInBpY3R1cmUiOiJodHRwczovL2xoMy5nb29nbGV1c2VyY29udGVudC5jb20vYS9BQ2c4b2NJcERxcVdzckJ3VVR1ai05bW9XSFQ0b3hEaDhFYkRQVXlxekdmMGtqOTN0ektLYjhhdENRPXM5Ni1jIiwicHJvdmlkZXJfaWQiOiIxMTU4MzkzMzc3NzIwMjM0MjkzODIiLCJzdWIiOiIxMTU4MzkzMzc3NzIwMjM0MjkzODIifSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJvYXV0aCIsInRpbWVzdGFtcCI6MTc2OTkwMzU0MH1dLCJzZXNzaW9uX2lkIjoiYWQ4MTliYWUtYWEwYS00NmI5LWE1OTQtM2IwYWY5YjhjNjQ4IiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.kJVslTTdLAwP03s8kXlnZc9WT8pj0JPGV5twOWNlQ0Y"

@pytest.mark.network
def test_file_ingestion():
    print(f"\n{'='*70}")
    print(f" FILE INGESTION PROOF PACKET")
    print(f"{'='*70}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Twin ID: {TWIN_ID}")
    print(f"File: {FILE_PATH}")
    print(f"Auto-Index: True")

    # Read file content
    with open(FILE_PATH, 'r') as f:
        content = f.read()
    print(f"\nFile content preview:\n{content[:200]}...")

    # Test 1: File upload with auth
    print(f"\n--- Step 1: POST /ingest/file/{TWIN_ID}?auto_index=true ---")
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }

    try:
        with open(FILE_PATH, 'rb') as f:
            files = {'file': ('test_file_verification.txt', f, 'text/plain')}
            response = requests.post(
                f"{BASE_URL}/ingest/file/{TWIN_ID}?auto_index=true",
                files=files,
                headers=headers
            )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            source_id = result.get('source_id')
            status = result.get('status')

            print(f"\n{'='*70}")
            print(f" PROOF ARTIFACT 1: API RESPONSE")
            print(f"{'='*70}")
            print(json.dumps(result, indent=2))
            print(f"\nsource_id: {source_id}")
            print(f"status: {status}")

            if status == 'live':
                print(f"\n✅ STATUS IS 'live' - PASS")
            else:
                print(f"\n❌ STATUS IS NOT 'live' - FAIL (got: {status})")
        else:
            print(f"\n❌ Upload failed with status {response.status_code}")
            print(f"Detail: {response.text}")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")

    print(f"\n{'='*70}")
    print("NEXT: Check backend logs for [Pinecone] upsert message")
    print("NEXT: Check Supabase sources table for twin_id, status, created_at")
    print(f"{'='*70}")
