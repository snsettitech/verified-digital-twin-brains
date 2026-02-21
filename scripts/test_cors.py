#!/usr/bin/env python3
"""
CORS Testing Script

Tests CORS configuration by making requests from various origins.
Usage:
    python scripts/test_cors.py [backend_url]
"""

import sys
import requests
from urllib.parse import urljoin

def run_cors_check(backend_url: str, origin: str) -> dict:
    """Test CORS for a specific origin."""
    headers = {
        'Origin': origin,
        'Access-Control-Request-Method': 'GET',
        'Access-Control-Request-Headers': 'Content-Type,Authorization'
    }
    
    # Test preflight
    preflight = requests.options(
        urljoin(backend_url, '/health'),
        headers=headers,
        timeout=10
    )
    
    # Test actual request
    actual = requests.get(
        urljoin(backend_url, '/cors-test'),
        headers={'Origin': origin},
        timeout=10
    )
    
    return {
        'origin': origin,
        'preflight_status': preflight.status_code,
        'actual_status': actual.status_code,
        'access_control_allow_origin': preflight.headers.get('access-control-allow-origin', 'NOT SET'),
        'access_control_allow_credentials': preflight.headers.get('access-control-allow-credentials', 'NOT SET'),
        'cors_test_result': actual.json() if actual.status_code == 200 else None
    }

def main():
    backend_url = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8000'
    
    # Test various origins
    test_origins = [
        'http://localhost:3000',
        'http://127.0.0.1:3000',
        'https://digitalbrains.vercel.app',
        'https://my-branch.vercel.app',  # Preview domain
        'https://evil-site.com',  # Should fail
    ]
    
    print(f"Testing CORS configuration for: {backend_url}\n")
    print("=" * 80)
    
    for origin in test_origins:
        print(f"\nTesting origin: {origin}")
        print("-" * 40)
        
        try:
            result = run_cors_check(backend_url, origin)
            
            print(f"  Preflight: {result['preflight_status']}")
            print(f"  Actual: {result['actual_status']}")
            print(f"  Access-Control-Allow-Origin: {result['access_control_allow_origin']}")
            
            if result['cors_test_result']:
                cors_data = result['cors_test_result']
                print(f"  Server says allowed: {cors_data.get('is_allowed', 'N/A')}")
                if cors_data.get('matched_pattern'):
                    print(f"  Matched pattern: {cors_data['matched_pattern']}")
            
            # Determine if CORS is working
            if result['access_control_allow_origin'] == origin or result['access_control_allow_origin'] == '*':
                print(f"  Status: ✅ CORS ALLOWED")
            else:
                print(f"  Status: ❌ CORS REJECTED")
                
        except Exception as e:
            print(f"  ERROR: {e}")
    
    print("\n" + "=" * 80)
    print("\nTo test from browser:")
    print(f"  1. Open {backend_url}/docs")
    print(f"  2. Try the /cors-test endpoint from different origins")
    print(f"  3. Check browser console for CORS errors")

if __name__ == '__main__':
    main()
