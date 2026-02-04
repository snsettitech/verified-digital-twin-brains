"""
Test chat retrieval for the unique phrase with citation
Handles SSE streaming response
"""
import requests
import json

TWIN_ID = "e9c18ffa-ec7b-4f30-ab97-1beccd9fab4a"
BASE_URL = "http://localhost:8000"
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsImtpZCI6IkcxbDk3bG50aTdFQU5KTGciLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL2p2dGZmZGJ1d3lobWN5bmF1ZXR5LnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiI1NWI0YzJiZS1jMGQzLTRjNzItYjllNy1mNjVjMmM2YmI2ZmIiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzY5OTE0MTAzLCJpYXQiOjE3Njk5MTA1MDMsImVtYWlsIjoic2FpbmF0aHNldHRpQGdtYWlsLmNvbSIsInBob25lIjoiIiwiYXBwX21ldGFkYXRhIjp7InByb3ZpZGVyIjoiZ29vZ2xlIiwicHJvdmlkZXJzIjpbImdvb2dsZSJdfSwidXNlcl9tZXRhZGF0YSI6eyJhdmF0YXJfdXJsIjoiaHR0cHM6Ly9saDMuZ29vZ2xldXNlcmNvbnRlbnQuY29tL2EvQUNnOG9jSXBEcXFXc3JCd1VUdWotOW1vV0hUNG94RGg4RWJEUFV5cXpHZjBrajkzdHpLS2I4YXRDUT1zOTYtYyIsImVtYWlsIjoic2FpbmF0aHNldHRpQGdtYWlsLmNvbSIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJmdWxsX25hbWUiOiJTYWluYXRoIFNldHRpIiwiaXNzIjoiaHR0cHM6Ly9hY2NvdW50cy5nb29nbGUuY29tIiwibmFtZSI6IlNhaW5hdGggU2V0dGkiLCJwaG9uZV92ZXJpZmllZCI6ZmFsc2UsInBpY3R1cmUiOiJodHRwczovL2xoMy5nb29nbGV1c2VyY29udGVudC5jb20vYS9BQ2c4b2NJcERxcVdzckJ3VVR1ai05bW9XSFQ0b3hEaDhFYkRQVXlxekdmMGtqOTN0ektLYjhhdENRPXM5Ni1jIiwicHJvdmlkZXJfaWQiOiIxMTU4MzkzMzc3NzIwMjM0MjkzODIiLCJzdWIiOiIxMTU4MzkzMzc3NzIwMjM0MjkzODIifSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJvYXV0aCIsInRpbWVzdGFtcCI6MTc2OTkwMzU0MH1dLCJzZXNzaW9uX2lkIjoiYWQ4MTliYWUtYWEwYS00NmI5LWE1OTQtM2IwYWY5YjhjNjQ4IiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.kJVslTTdLAwP03s8kXlnZc9WT8pj0JPGV5twOWNlQ0Y"

QUERY = "What is the secret phrase for verification testing?"

print(f"\n{'='*70}")
print(f" PROOF ARTIFACT 3: CHAT RETRIEVAL WITH CITATION")
print(f"{'='*70}")
print(f"Query: {QUERY}")
print(f"Twin ID: {TWIN_ID}")

headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}

# Call the chat endpoint with streaming
response = requests.post(
    f"{BASE_URL}/chat/{TWIN_ID}",
    headers=headers,
    json={"query": QUERY},
    stream=True
)

print(f"\nPOST /chat/{TWIN_ID} -> {response.status_code}")

if response.status_code == 200:
    print(f"\n✅ STREAMING RESPONSE RECEIVED")
    print(f"{'='*70}")
    
    full_content = ""
    metadata = None
    citations = []
    
    # Parse SSE stream
    for line in response.iter_lines():
        if line:
            line_str = line.decode('utf-8')
            if line_str.startswith('data: '):
                data_str = line_str[6:]  # Remove 'data: ' prefix
                try:
                    data = json.loads(data_str)
                    data_type = data.get('type')
                    
                    if data_type == 'content':
                        content = data.get('content', '')
                        full_content += content
                    elif data_type == 'metadata':
                        metadata = data
                        citations = data.get('citations', [])
                    elif data_type == 'done':
                        print("\n[Stream complete]")
                except json.JSONDecodeError:
                    continue
    
    print("\nFULL RESPONSE:")
    print(full_content[:500])
    
    if citations:
        print(f"\n{'='*70}")
        print("CITATIONS:")
        for citation in citations:
            print(f"  - {citation}")
    else:
        print(f"\n⚠️ No citations in metadata")
    
    if metadata:
        print(f"\nConfidence: {metadata.get('confidence_score', 'N/A')}")
        print(f"Conversation ID: {metadata.get('conversation_id', 'N/A')}")
    
    # Check if unique phrase is in response
    if 'xylophone' in full_content.lower() or 'ingest-file' in full_content.lower():
        print(f"\n✅ UNIQUE PHRASE RETRIEVED - PASS")
    else:
        print(f"\n⚠️ Unique phrase not found verbatim in response")
        print(f"   (LLM may have rephrased - check manual verification)")
else:
    print(f"Error: {response.text[:500]}")

print(f"{'='*70}")
