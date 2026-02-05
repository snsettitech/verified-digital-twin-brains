"""
Verify sources via the API endpoint
"""
import requests
import json

TWIN_ID = "e9c18ffa-ec7b-4f30-ab97-1beccd9fab4a"
SOURCE_ID = "d879679d-75b1-474a-b5b0-b2561f3864af"
BASE_URL = "http://localhost:8000"
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsImtpZCI6IkcxbDk3bG50aTdFQU5KTGciLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL2p2dGZmZGJ1d3lobWN5bmF1ZXR5LnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiI1NWI0YzJiZS1jMGQzLTRjNzItYjllNy1mNjVjMmM2YmI2ZmIiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzY5OTE0MTAzLCJpYXQiOjE3Njk5MTA1MDMsImVtYWlsIjoic2FpbmF0aHNldHRpQGdtYWlsLmNvbSIsInBob25lIjoiIiwiYXBwX21ldGFkYXRhIjp7InByb3ZpZGVyIjoiZ29vZ2xlIiwicHJvdmlkZXJzIjpbImdvb2dsZSJdfSwidXNlcl9tZXRhZGF0YSI6eyJhdmF0YXJfdXJsIjoiaHR0cHM6Ly9saDMuZ29vZ2xldXNlcmNvbnRlbnQuY29tL2EvQUNnOG9jSXBEcXFXc3JCd1VUdWotOW1vV0hUNG94RGg4RWJEUFV5cXpHZjBrajkzdHpLS2I4YXRDUT1zOTYtYyIsImVtYWlsIjoic2FpbmF0aHNldHRpQGdtYWlsLmNvbSIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJmdWxsX25hbWUiOiJTYWluYXRoIFNldHRpIiwiaXNzIjoiaHR0cHM6Ly9hY2NvdW50cy5nb29nbGUuY29tIiwibmFtZSI6IlNhaW5hdGggU2V0dGkiLCJwaG9uZV92ZXJpZmllZCI6ZmFsc2UsInBpY3R1cmUiOiJodHRwczovL2xoMy5nb29nbGV1c2VyY29udGVudC5jb20vYS9BQ2c4b2NJcERxcVdzckJ3VVR1ai05bW9XSFQ0b3hEaDhFYkRQVXlxekdmMGtqOTN0ektLYjhhdENRPXM5Ni1jIiwicHJvdmlkZXJfaWQiOiIxMTU4MzkzMzc3NzIwMjM0MjkzODIiLCJzdWIiOiIxMTU4MzkzMzc3NzIwMjM0MjkzODIifSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJvYXV0aCIsInRpbWVzdGFtcCI6MTc2OTkwMzU0MH1dLCJzZXNzaW9uX2lkIjoiYWQ4MTliYWUtYWEwYS00NmI5LWE1OTQtM2IwYWY5YjhjNjQ4IiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.kJVslTTdLAwP03s8kXlnZc9WT8pj0JPGV5twOWNlQ0Y"

print(f"\n{'='*70}")
print(f" PROOF ARTIFACT 2: SUPABASE SOURCES ROW (via API)")
print(f"{'='*70}")

headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}

# Get all sources for this twin
response = requests.get(
    f"{BASE_URL}/sources/{TWIN_ID}",
    headers=headers
)

print(f"GET /sources/{TWIN_ID} -> {response.status_code}")

if response.status_code == 200:
    sources = response.json()
    # Find our source
    our_source = None
    for src in sources:
        if src.get('id') == SOURCE_ID:
            our_source = src
            break
    
    if our_source:
        print(f"\n✅ SOURCE FOUND")
        print(f"{'='*70}")
        print(f"id:             {our_source.get('id')}")
        print(f"twin_id:        {our_source.get('twin_id')}")
        print(f"status:         {our_source.get('status')}")
        print(f"staging_status: {our_source.get('staging_status')}")
        print(f"filename:       {our_source.get('filename')}")
        print(f"chunk_count:    {our_source.get('chunk_count')}")
        print(f"created_at:     {our_source.get('created_at')}")
        
        if our_source.get('twin_id') == TWIN_ID:
            print(f"\n✅ twin_id MATCHES - PASS")
        else:
            print(f"\n❌ twin_id MISMATCH - FAIL")
            
        if our_source.get('status') == 'live':
            print(f"✅ status='live' - PASS")
        else:
            print(f"❌ status != 'live' - FAIL (got: {our_source.get('status')})")
    else:
        print(f"\n⚠️ SOURCE ID not found in list, but showing first 3 sources:")
        for src in sources[:3]:
            print(f"  - {src.get('id')}: {src.get('filename')} [{src.get('status')}]")
else:
    print(f"Error: {response.text}")

print(f"{'='*70}")
