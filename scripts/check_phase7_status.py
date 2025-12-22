import os
import sys
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path='backend/.env')

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
API_URL = "http://localhost:8000"

def check_tables():
    print("--- Checking Phase 7 Tables ---")
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    
    tables = [
        "twin_api_keys",
        "sessions",
        "rate_limit_tracking",
        "user_invitations"
    ]
    
    for table in tables:
        url = f"{SUPABASE_URL}/rest/v1/{table}?limit=1"
        try:
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                print(f"✅ Table '{table}' exists.")
            else:
                print(f"❌ Table '{table}' check failed: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"❌ Error checking table '{table}': {e}")

def check_endpoints():
    print("\n--- Checking Phase 7 API Endpoints ---")
    
    endpoints = [
        ("GET", "/api-keys"),
        ("GET", "/users"),
        ("POST", "/chat-widget/test-id")
    ]
    
    for method, path in endpoints:
        url = f"{API_URL}{path}"
        try:
            # We expect 401/403/404/422 but not 404 Not Found (meaning the route exists)
            resp = requests.request(method, url)
            if resp.status_code == 404 and "detail" not in resp.text:
                print(f"❌ Endpoint {method} {path} NOT FOUND (404)")
            else:
                print(f"✅ Endpoint {method} {path} exists (Returned {resp.status_code})")
        except Exception as e:
            print(f"❌ Error connecting to {url}: {e}")

if __name__ == "__main__":
    check_tables()
    check_endpoints()
    print("\nNote: Table existence check requires the Phase 7 SQL migration to be applied in Supabase.")
