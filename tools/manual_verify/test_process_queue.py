#!/usr/bin/env python3
"""
Test script for Process Queue endpoint.
This simulates what the frontend button does.
"""
__test__ = False  # Prevent pytest from collecting this script as a test module.

import os
import sys
import requests
from dotenv import load_dotenv

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

load_dotenv()

def test_process_queue(twin_id: str, auth_token: str):
    """Test the process queue endpoint."""
    backend_url = os.getenv("NEXT_PUBLIC_BACKEND_URL", "http://localhost:8000")
    
    # Remove trailing slash if present
    backend_url = backend_url.rstrip('/')
    
    endpoint = f"{backend_url}/training-jobs/process-queue"
    params = {"twin_id": twin_id}
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }
    
    print("=" * 60)
    print("Testing Process Queue Endpoint")
    print("=" * 60)
    print(f"Backend URL: {backend_url}")
    print(f"Endpoint: {endpoint}")
    print(f"Twin ID: {twin_id}")
    print(f"Auth Token: {auth_token[:20]}..." if len(auth_token) > 20 else "Auth Token: [PROVIDED]")
    print()
    
    try:
        print("Sending POST request...")
        response = requests.post(endpoint, params=params, headers=headers, timeout=60)
        
        print(f"Status Code: {response.status_code}")
        print()
        
        if response.status_code == 200:
            result = response.json()
            print("[SUCCESS] Queue processed successfully!")
            print()
            print("Results:")
            print(f"  Processed: {result.get('processed', 0)} job(s)")
            print(f"  Failed: {result.get('failed', 0)} job(s)")
            print(f"  Remaining: {result.get('remaining', 0)} job(s)")
            print(f"  Message: {result.get('message', 'N/A')}")
            
            if result.get('processed', 0) > 0:
                print()
                print("[INFO] Jobs were processed. Check your sources - they should now be 'Live'.")
            elif result.get('remaining', 0) > 0:
                print()
                print("[INFO] There are still jobs in the queue. Run this script again to process them.")
            else:
                print()
                print("[INFO] No jobs were found in the queue.")
                
        elif response.status_code == 401:
            print("[ERROR] Authentication failed. Check your auth token.")
            print(f"Response: {response.text}")
        elif response.status_code == 403:
            print("[ERROR] Access denied. Make sure you own this twin.")
            print(f"Response: {response.text}")
        else:
            print(f"[ERROR] Request failed with status {response.status_code}")
            try:
                error_data = response.json()
                print(f"Error: {error_data.get('detail', response.text)}")
            except:
                print(f"Response: {response.text}")
                
    except requests.exceptions.Timeout:
        print("[ERROR] Request timed out. The queue processing might be taking too long.")
    except requests.exceptions.ConnectionError:
        print("[ERROR] Could not connect to backend. Check:")
        print("  1. Backend is running")
        print("  2. NEXT_PUBLIC_BACKEND_URL is correct")
        print("  3. Network connectivity")
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()

def main():
    print("Process Queue Test Script")
    print("=" * 60)
    print()
    
    # Get inputs
    twin_id = input("Enter your Twin ID: ").strip()
    if not twin_id:
        print("[ERROR] Twin ID is required")
        return
    
    auth_token = input("Enter your auth token (or press Enter to use from .env): ").strip()
    if not auth_token:
        # Try to get from environment or Supabase
        print("[INFO] Attempting to get auth token from environment...")
        # For now, require manual input
        auth_token = input("Please enter your Supabase auth token: ").strip()
        if not auth_token:
            print("[ERROR] Auth token is required")
            print()
            print("To get your auth token:")
            print("1. Open your browser's developer tools (F12)")
            print("2. Go to Application/Storage → Local Storage")
            print("3. Find 'sb-<project-id>-auth-token'")
            print("4. Copy the 'access_token' value")
            return
    
    print()
    test_process_queue(twin_id, auth_token)
    
    print()
    print("=" * 60)
    print("Test Complete")
    print("=" * 60)

if __name__ == "__main__":
    main()

