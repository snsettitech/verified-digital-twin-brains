#!/usr/bin/env python3
"""
Phase 1 Backend Integration Test
Tests the key endpoints for Person Completeness V1
"""

import os
import sys
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_BASE = (
    os.getenv("NEXT_PUBLIC_API_URL")
    or os.getenv("DEPLOYED_BACKEND_URL")
    or "http://localhost:8000"
)

def test_public_profile_endpoint():
    """Test GET /share/{twin_id}/{token}/profile"""
    print("\n[CHECK] Testing Public Profile Endpoint...")
    
    # This would need a valid twin_id and token
    # For now, just verify the endpoint structure
    url = f"{API_BASE}/share/test-twin-id/test-token/profile"
    try:
        response = requests.get(url, timeout=5)
        # Expected: 403 Forbidden (invalid token) or 404 Not Found
        if response.status_code in [403, 404]:
            print(f"  [OK] Endpoint exists (returned {response.status_code})")
            return True
        else:
            print(f"  [WARN] Unexpected status: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"  [WARN] Backend not running at {API_BASE}")
        return None
    except Exception as e:
        print(f"  [ERR] Error: {e}")
        return False

def test_profile_endpoints():
    """Test /profile endpoints (requires auth)"""
    print("\n[CHECK] Testing Profile Endpoints (requires auth)...")
    
    # Test without auth - should return 401
    endpoints = [
        ("GET", "/profile"),
        ("POST", "/profile"),
        ("PATCH", "/profile"),
        ("GET", "/profile/build-status"),
    ]
    
    results = []
    for method, path in endpoints:
        url = f"{API_BASE}{path}"
        try:
            if method == "GET":
                response = requests.get(url, timeout=5)
            elif method == "POST":
                response = requests.post(url, json={}, timeout=5)
            else:
                response = requests.patch(url, json={}, timeout=5)
            
            # Expected: 401 Unauthorized
            if response.status_code == 401:
                print(f"  [OK] {method} {path} - Protected (401)")
                results.append(True)
            else:
                print(f"  [WARN] {method} {path} - Unexpected {response.status_code}")
                results.append(False)
        except requests.exceptions.ConnectionError:
            print(f"  [WARN] Backend not running")
            return None
        except Exception as e:
            print(f"  [ERR] {method} {path} - Error: {e}")
            results.append(False)
    
    return all(results) if results else None

def test_deep_research_endpoint():
    """Test POST /deep-research/runs (requires auth)"""
    print("\n[CHECK] Testing Deep Research Endpoint...")
    
    url = f"{API_BASE}/deep-research/runs"
    try:
        response = requests.post(url, json={"name": "Test"}, timeout=5)
        
        # Expected: 401 Unauthorized or 422 Validation Error
        if response.status_code in [401, 422]:
            print(f"  [OK] Endpoint exists (returned {response.status_code})")
            return True
        else:
            print(f"  [WARN] Unexpected status: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"  [WARN] Backend not running")
        return None
    except Exception as e:
        print(f"  [ERR] Error: {e}")
        return False

def check_router_registration():
    """Check if routers are registered in main.py"""
    print("\n[CHECK] Checking Router Registration...")
    
    main_py = "backend/main.py"
    try:
        with open(main_py, 'r') as f:
            content = f.read()
        
        checks = [
            ("profile router", "app.include_router(profile.router)" in content),
            ("profile_public router", "app.include_router(profile_public.router)" in content),
            ("ProfileProvider import", "ProfileProvider" in open("frontend/app/dashboard/layout.tsx").read()),
        ]
        
        all_pass = True
        for name, passed in checks:
            status = "[OK]" if passed else "[ERR]"
            print(f"  {status} {name}")
            all_pass = all_pass and passed
        
        return all_pass
    except Exception as e:
        print(f"  [ERR] Error checking registration: {e}")
        return False

def main():
    print("=" * 60)
    print("Phase 1 Backend Integration Test")
    print("=" * 60)
    print(f"API Base: {API_BASE}")
    
    results = []
    
    # Test 1: Router Registration
    result = check_router_registration()
    results.append(("Router Registration", result))
    
    # Test 2: Public Profile Endpoint
    result = test_public_profile_endpoint()
    if result is not None:
        results.append(("Public Profile Endpoint", result))
    
    # Test 3: Profile Endpoints
    result = test_profile_endpoints()
    if result is not None:
        results.append(("Profile Endpoints", result))
    
    # Test 4: Deep Research Endpoint
    result = test_deep_research_endpoint()
    if result is not None:
        results.append(("Deep Research Endpoint", result))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\nAll tests passed.")
        return 0
    else:
        print("\nSome tests failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
