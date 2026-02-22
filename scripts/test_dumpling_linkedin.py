#!/usr/bin/env python3
"""
Test Dumpling AI LinkedIn Profile API directly
"""
import os
import sys
import asyncio
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'backend', '.env'))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import httpx

DUMPLING_API_BASE = "https://app.dumplingai.com/api/v1"
API_KEY = os.getenv("DUMPLING_API_KEY", "").strip()

async def test_linkedin_api():
    url = "https://www.linkedin.com/in/sainathsetti/"
    
    print("=" * 80)
    print("TESTING DUMPLING AI LINKEDIN PROFILE API")
    print("=" * 80)
    print(f"\nAPI Key: {API_KEY[:10]}...{API_KEY[-5:] if len(API_KEY) > 15 else ''} (length: {len(API_KEY)})")
    print(f"URL: {url}")
    print(f"Endpoint: {DUMPLING_API_BASE}/linkedin/profile")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }
    
    payload = {"url": url}
    
    print(f"\nHeaders: {headers}")
    print(f"Payload: {payload}")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        print("\n[1] Making POST request...")
        try:
            response = await client.post(
                f"{DUMPLING_API_BASE}/linkedin/profile",
                headers=headers,
                json=payload,
            )
            print(f"    Status: {response.status_code}")
            print(f"    Headers: {dict(response.headers)}")
            
            # Check content type
            content_type = response.headers.get('content-type', '')
            print(f"    Content-Type: {content_type}")
            
            # Get raw text
            raw_text = response.text
            print(f"\n[2] Raw response (first 500 chars):")
            print("-" * 80)
            print(raw_text[:500])
            print("-" * 80)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"\n[3] Parsed JSON:")
                    print(f"    Success: {data.get('success')}")
                    print(f"    Name: {data.get('name')}")
                    print(f"    Location: {data.get('location')}")
                    print(f"    Followers: {data.get('followers')}")
                    print(f"    About length: {len(data.get('about') or '')}")
                    print(f"    Experience count: {len(data.get('experience') or [])}")
                    return data
                except Exception as e:
                    print(f"\n[3] JSON parse error: {e}")
                    return None
            else:
                print(f"\n[3] Error response:")
                try:
                    error_data = response.json()
                    print(f"    Error: {error_data.get('error')}")
                except:
                    print(f"    Raw: {raw_text[:200]}")
                return None
                
        except httpx.HTTPStatusError as e:
            print(f"    HTTP Error: {e}")
            print(f"    Response: {e.response.text[:500]}")
            return None
        except Exception as e:
            print(f"    Error: {type(e).__name__}: {e}")
            return None

if __name__ == "__main__":
    result = asyncio.run(test_linkedin_api())
    if result:
        print("\n✅ SUCCESS!")
    else:
        print("\n❌ FAILED")
