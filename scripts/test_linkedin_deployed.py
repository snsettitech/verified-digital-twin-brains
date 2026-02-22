#!/usr/bin/env python3
"""
Test if the new LinkedIn handling code is deployed
"""
import httpx
import json

async def test_linkedin_ingestion_api():
    """Test the LinkedIn ingestion via the API"""
    print("=" * 80)
    print("TESTING LINKEDIN INGESTION VIA API")
    print("=" * 80)
    
    # You'll need to get a valid JWT token for this twin
    # For now, just test if the endpoint responds correctly
    
    base_url = "https://verified-digital-twin-brains.onrender.com"
    
    async with httpx.AsyncClient() as client:
        # Test health
        print("\n[1] Health check...")
        r = await client.get(f"{base_url}/health")
        print(f"    Status: {r.status_code}")
        print(f"    Response: {r.text}")
        
        # Check if we can access the API docs
        print("\n[2] API docs...")
        r = await client.get(f"{base_url}/docs")
        print(f"    Status: {r.status_code}")
        
        # Note: To actually test LinkedIn ingestion, we'd need authentication
        print("\n[3] Note: Full LinkedIn test requires authentication")
        print("    The new code should handle HTTP 999 by creating a reference source")
        print("    that allows manual content upload.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_linkedin_ingestion_api())
