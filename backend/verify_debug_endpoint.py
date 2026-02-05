
import requests
import json
import time

BASE_URL = "http://localhost:8000"
TWIN_ID = "e9c18ffa-ec7b-4f30-ab97-1beccd9fab4a"

def run_query(query_text, expect_results=True):
    print(f"\n--- Testing Query: '{query_text}' ---")
    url = f"{BASE_URL}/debug/retrieval"
    payload = {
        "query": query_text,
        "twin_id": TWIN_ID,
        "top_k": 5
    }
    
    try:
        start_time = time.time()
        response = requests.post(url, json=payload)
        duration = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            count = data.get('results_count')
            diagnostics = data.get('diagnostics', {})
            contexts = data.get("contexts", [])
            print(f"Status: 200 OK | Time: {duration:.2f}s | Count: {count}")
            print(f"Diagnostics: {diagnostics}")
            
            if count > 0:
                top_score = contexts[0].get('score')
                print(f"Top Score: {top_score}")
                print(f"Top Source: {contexts[0].get('source_filename', 'Unknown')}")
            
            if expect_results and count == 0:
                print("❌ FAILED: Expected results but got none.")
            elif not expect_results and count > 0:
                print(f"❌ FAILED: Expected NO results (I don't know), but got {count}.")
            else:
                print("✅ PASSED expectation.")
                
        else:
            print(f"Error: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    # Test 1: Known content
    run_query("What is the secret phrase? (XYLOPHONE)", expect_results=True)
    
    # Test 2: Nonsense (should trigger I don't know)
    run_query("What is the flying velocity of an unladen swallow in Mars syntax?", expect_results=False)
