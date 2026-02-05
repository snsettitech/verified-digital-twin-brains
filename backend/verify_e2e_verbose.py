"""
Full end-to-end test with verbose logging:
1. Upload file with unique phrase
2. Chat to retrieve the phrase
3. Capture all logs
"""
import requests
import json
import time

TWIN_ID = "e9c18ffa-ec7b-4f30-ab97-1beccd9fab4a"
BASE_URL = "http://localhost:8000"
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsImtpZCI6IkcxbDk3bG50aTdFQU5KTGciLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL2p2dGZmZGJ1d3lobWN5bmF1ZXR5LnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiI1NWI0YzJiZS1jMGQzLTRjNzItYjllNy1mNjVjMmM2YmI2ZmIiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzY5OTE0MTAzLCJpYXQiOjE3Njk5MTA1MDMsImVtYWlsIjoic2FpbmF0aHNldHRpQGdtYWlsLmNvbSIsInBob25lIjoiIiwiYXBwX21ldGFkYXRhIjp7InByb3ZpZGVyIjoiZ29vZ2xlIiwicHJvdmlkZXJzIjpbImdvb2dsZSJdfSwidXNlcl9tZXRhZGF0YSI6eyJhdmF0YXJfdXJsIjoiaHR0cHM6Ly9saDMuZ29vZ2xldXNlcmNvbnRlbnQuY29tL2EvQUNnOG9jSXBEcXFXc3JCd1VUdWotOW1vV0hUNG94RGg4RWJEUFV5cXpHZjBrajkzdHpLS2I4YXRDUT1zOTYtYyIsImVtYWlsIjoic2FpbmF0aHNldHRpQGdtYWlsLmNvbSIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJmdWxsX25hbWUiOiJTYWluYXRoIFNldHRpIiwiaXNzIjoiaHR0cHM6Ly9hY2NvdW50cy5nb29nbGUuY29tIiwibmFtZSI6IlNhaW5hdGggU2V0dGkiLCJwaG9uZV92ZXJpZmllZCI6ZmFsc2UsInBpY3R1cmUiOiJodHRwczovL2xoMy5nb29nbGV1c2VyY29udGVudC5jb20vYS9BQ2c4b2NJcERxcVdzckJ3VVR1ai05bW9XSFQ0b3hEaDhFYkRQVXlxekdmMGtqOTN0ektLYjhhdENRPXM5Ni1jIiwicHJvdmlkZXJfaWQiOiIxMTU4MzkzMzc3NzIwMjM0MjkzODIiLCJzdWIiOiIxMTU4MzkzMzc3NzIwMjM0MjkzODIifSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJvYXV0aCIsInRpbWVzdGFtcCI6MTc2OTkwMzU0MH1dLCJzZXNzaW9uX2lkIjoiYWQ4MTliYWUtYWEwYS00NmI5LWE1OTQtM2IwYWY5YjhjNjQ4IiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.kJVslTTdLAwP03s8kXlnZc9WT8pj0JPGV5twOWNlQ0Y"

headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}

# STEP 1: Verify existing source exists
print(f"{'='*70}")
print("STEP 1: Verify existing ingested source")
print(f"{'='*70}")
SOURCE_ID = "d879679d-75b1-474a-b5b0-b2561f3864af"

response = requests.get(f"{BASE_URL}/sources/{TWIN_ID}", headers=headers)
if response.status_code == 200:
    sources = response.json()
    our_source = next((s for s in sources if s.get('id') == SOURCE_ID), None)
    if our_source:
        print(f"✅ Source found: {our_source['filename']}")
        print(f"   status: {our_source.get('status')}")
        print(f"   chunk_count: {our_source.get('chunk_count')}")
    else:
        print(f"⚠️ Source {SOURCE_ID} not found")
else:
    print(f"❌ Failed to get sources: {response.status_code}")

# STEP 2: Chat to retrieve phrase
print(f"\n{'='*70}")
print("STEP 2: Chat to retrieve the unique phrase")
print(f"{'='*70}")

QUERY = "What is INGEST-FILE-XYLOPHONE-PURPLE-2024?"

print(f"Query: {QUERY}")
print(f"Twin ID: {TWIN_ID}")
print("")

response = requests.post(
    f"{BASE_URL}/chat/{TWIN_ID}",
    headers=headers,
    json={"query": QUERY},
    stream=True
)

print(f"POST /chat/{TWIN_ID} -> {response.status_code}")
print(f"Content-Type: {response.headers.get('content-type')}")
print("")

full_content = ""
metadata = None
events_received = 0

print("SSE EVENTS:")
print("-" * 50)
for line in response.iter_lines():
    if line:
        line_str = line.decode('utf-8')
        events_received += 1
        print(f"[Event {events_received}] {line_str[:200]}{'...' if len(line_str) > 200 else ''}")
        
        if line_str.startswith('data: '):
            line_str = line_str[6:]
        
        try:
            data = json.loads(line_str)
            data_type = data.get('type')
            
            if data_type == 'content':
                full_content += data.get('content', '')
            elif data_type == 'metadata':
                metadata = data
            elif data_type == 'error':
                print(f"⚠️ ERROR EVENT: {data.get('error')}")
        except json.JSONDecodeError:
            pass

print("-" * 50)
print(f"\nTotal SSE events: {events_received}")

if metadata:
    print(f"\nMETADATA:")
    print(f"  confidence_score: {metadata.get('confidence_score')}")
    print(f"  citations: {metadata.get('citations')}")

print(f"\nFULL RESPONSE:")
if full_content:
    print(full_content[:500])
    if 'xylophone' in full_content.lower() or 'ingest-file' in full_content.lower():
        print(f"\n✅ UNIQUE PHRASE FOUND - PASS")
    else:
        print(f"\n⚠️ Unique phrase not in response")
else:
    print("(empty)")
    print(f"\n❌ EMPTY RESPONSE - FAIL")

print(f"\n{'='*70}")
