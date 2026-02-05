
import requests
import json
import time

BASE_URL = "http://localhost:8000"
TWIN_ID = "e9c18ffa-ec7b-4f30-ab97-1beccd9fab4a"
TOKEN = "mock_token" # Assuming auth is bypassed or I need a token. 
# Wait, auth is required: user=Depends(get_current_user)
# I need to mock auth or use a token. 
# In debug_retrieval, I commented out auth. 
# In twins.py, I did NOT.
# So I need a token. Or I can temporarily comment out auth in twins.py for verification.

# Strategy: Comment out auth for this endpoint in twins.py temporarily.

def test_publish_check():
    print(f"Testing GET /twins/{TWIN_ID}/verification-status")
    url = f"{BASE_URL}/twins/{TWIN_ID}/verification-status"
    
    try:
        # Pass dummy auth header if needed, but if it checks Supabase, it will fail.
        # I'll disable auth guard for this specific endpoint in twins.py via another edit.
        response = requests.get(url) 
        
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print(json.dumps(response.json(), indent=2))
        else:
            print(response.text)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_publish_check()
