
import requests
import json
import time
import os
from jose import jwt

# Read .env to get JWT_SECRET
def load_env_file(filepath):
    if not os.path.exists(filepath):
        return
    with open(filepath, 'r') as f:
        for line in f:
            if '=' in line:
                key, val = line.strip().split('=', 1)
                os.environ[key] = val

load_env_file("backend/.env")
JWT_SECRET = os.environ.get("JWT_SECRET")

BASE_URL = "http://127.0.0.1:8000"
TWIN_ID = "e9c18ffa-ec7b-4f30-ab97-1beccd9fab4a"

# Token Generation
payload = {
    "sub": "11111111-1111-4111-8111-111111111111",
    "role": "authenticated",
    "aud": "authenticated",
    "email": "test-verify@example.com",
    "user_metadata": {}
}
token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
HEADERS = {"Authorization": f"Bearer {token}"}

def test_flow():
    print(f"\n--- 1. Check Initial Status ---")
    url_status = f"{BASE_URL}/twins/{TWIN_ID}/verification-status"
    res = requests.get(url_status, headers=HEADERS)
    if res.status_code != 200:
        print(f"Error {res.status_code}: {res.text}")
        return
    print(json.dumps(res.json(), indent=2))
    
    print(f"\n--- 2. Run Verification ---")
    url_run = f"{BASE_URL}/verify/twins/{TWIN_ID}/run"
    res = requests.post(url_run, headers=HEADERS)
    print(f"Status Code: {res.status_code}")
    if res.status_code != 200:
        print(f"Error: {res.text}")
    else:
        print(json.dumps(res.json(), indent=2))
    
    print(f"\n--- 3. Verify Status Updated ---")
    res = requests.get(url_status, headers=HEADERS)
    status_data = res.json()
    print(json.dumps(status_data, indent=2))
    is_ready = status_data.get("is_ready", False)
    print(f"Is Ready: {is_ready}")
    
    print(f"\n--- 4. Attempt to Publish ---")
    res = requests.patch(
        f"{BASE_URL}/twins/{TWIN_ID}", 
        headers=HEADERS,
        json={"is_public": True}
    )
    print(f"Status Code: {res.status_code}")
    if res.status_code == 200:
        print("Publish SUCCESS")
    else:
        print(f"Publish FAILED: {res.text}")

if __name__ == "__main__":
    test_flow()
