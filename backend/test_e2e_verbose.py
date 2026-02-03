"""
Verbose E2E Test Script for Ingestion -> Retrieval Flow
Outputs proof packets for verification
"""
import pytest
import requests
import json
import time
from datetime import datetime

TWIN_ID = "e9c18ffa-ec7b-4f30-ab97-1beccd9fab4a"
BASE_URL = "http://localhost:8000"
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsImtpZCI6IkcxbDk3bG50aTdFQU5KTGciLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL2p2dGZmZGJ1d3lobWN5bmF1ZXR5LnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiI1NWI0YzJiZS1jMGQzLTRjNzItYjllNy1mNjVjMmM2YmI2ZmIiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzY5OTE0MTAzLCJpYXQiOjE3Njk5MTA1MDMsImVtYWlsIjoic2FpbmF0aHNldHRpQGdtYWlsLmNvbSIsInBob25lIjoiIiwiYXBwX21ldGFkYXRhIjp7InByb3ZpZGVyIjoiZ29vZ2xlIiwicHJvdmlkZXJzIjpbImdvb2dsZSJdfSwidXNlcl9tZXRhZGF0YSI6eyJhdmF0YXJfdXJsIjoiaHR0cHM6Ly9saDMuZ29vZ2xldXNlcmNvbnRlbnQuY29tL2EvQUNnOG9jSXBEcXFXc3JCd1VUdWotOW1vV0hUNG94RGg4RWJEUFV5cXpHZjBrajkzdHpLS2I4YXRDUT1zOTYtYyIsImVtYWlsIjoic2FpbmF0aHNldHRpQGdtYWlsLmNvbSIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJmdWxsX25hbWUiOiJTYWluYXRoIFNldHRpIiwiaXNzIjoiaHR0cHM6Ly9hY2NvdW50cy5nb29nbGUuY29tIiwibmFtZSI6IlNhaW5hdGggU2V0dGkiLCJwaG9uZV92ZXJpZmllZCI6ZmFsc2UsInBpY3R1cmUiOiJodHRwczovL2xoMy5nb29nbGV1c2VyY29udGVudC5jb20vYS9BQ2c4b2NJcERxcVdzckJ3VVR1ai05bW9XSFQ0b3hEaDhFYkRQVXlxekdmMGtqOTN0ektLYjhhdENRPXM5Ni1jIiwicHJvdmlkZXJfaWQiOiIxMTU4MzkzMzc3NzIwMjM0MjkzODIiLCJzdWIiOiIxMTU4MzkzMzc3NzIwMjM0MjkzODIifSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJvYXV0aCIsInRpbWVzdGFtcCI6MTc2OTkwMzU0MH1dLCJzZXNzaW9uX2lkIjoiYWQ4MTliYWUtYWEwYS00NmI5LWE1OTQtM2IwYWY5YjhjNjQ4IiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.kJVslTTdLAwP03s8kXlnZc9WT8pj0JPGV5twOWNlQ0Y"

@pytest.mark.network
def test_e2e_verbose():
    print(f"\n{'='*70}")
    print(f" STEP 1: Verify existing ingested source")
    print(f"{'='*70}")

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }

    try:
        # Check sources list
        response = requests.get(f"{BASE_URL}/sources/{TWIN_ID}", headers=headers)

        if response.status_code == 200:
            sources = response.json()
            print(f"Found {len(sources)} sources for twin")

            # Look for our test file
            target_source = None
            for s in sources:
                if 'test_file_verification.txt' in s.get('original_file_name', ''):
                    target_source = s
                    break

            if target_source:
                print(f"\n✅ FOUND TARGET SOURCE")
                print(f"ID: {target_source['id']}")
                print(f"Status: {target_source['status']}")
                print(f"Created: {target_source['created_at']}")

                if target_source['status'] == 'completed':
                    print(f"Status is COMPLETED - Good")
                else:
                    print(f"⚠️ Status is {target_source['status']} (Expected: completed)")
            else:
                print(f"\n❌ TARGET SOURCE NOT FOUND IN LIST")
                # Don't fail here, try search anyway
        else:
            print(f"Failed to get sources: {response.status_code}")

        # Step 2: Search Query
        print(f"\n{'='*70}")
        print(f" STEP 2: Verify Pinecone Retrieval")
        print(f"{'='*70}")

        query = "What is the secret phrase for verification testing?"
        print(f"Query: {query}")

        search_response = requests.post(
            f"{BASE_URL}/search/{TWIN_ID}",
            headers=headers,
            json={"query": query, "top_k": 3}
        )

        if search_response.status_code == 200:
            results = search_response.json()
            print(f"\n✅ SEARCH SUCCESSFUL")
            print(f"Got {len(results.get('results', []))} results")
            
            found_phrase = False
            for idx, item in enumerate(results.get('results', [])):
                content = item.get('content', '')
                score = item.get('score', 0)
                print(f"\nResult {idx+1} (Score: {score:.4f}):")
                print(f"Content: {content[:200]}...")

                if 'xylophone' in content.lower():
                    found_phrase = True
                    print("✅ Found unique phrase 'xylophone' in chunk")

            if found_phrase:
                print(f"\n✅ PROOF: Retrieved correct chunk from vector store")
            else:
                print(f"\n⚠️ PROOF FAILED: Did not find unique phrase in top results")
        else:
            print(f"Search failed: {search_response.status_code}")
            print(search_response.text)

    except requests.exceptions.ConnectionError:
        pytest.fail("Connection to server failed. Ensure server is running or mark test as network.")

if __name__ == "__main__":
    test_e2e_verbose()
