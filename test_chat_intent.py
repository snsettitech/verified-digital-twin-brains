#!/usr/bin/env python3
"""Test chat with intent classification"""
import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv('backend/.env')

TEST_TOKEN = os.getenv("TEST_TOKEN", "")
BASE_URL = "https://verified-digital-twin-brains.onrender.com"

# Test queries that should trigger different intents
test_queries = [
    "Hello!",  # greeting - should skip retrieval
    "What do you think about AI?",  # opinion
    "Summarize your work experience",  # summarization
    "Compare Python and JavaScript",  # comparison
    "How do you learn new skills?",  # procedural
]

async def test_chat():
    """Test chat endpoint."""
    # First, get available twins
    async with httpx.AsyncClient() as client:
        # List twins
        resp = await client.get(
            f"{BASE_URL}/twins",
            headers={"Authorization": f"Bearer {TEST_TOKEN}"}
        )
        if resp.status_code != 200:
            print(f"Failed to list twins: {resp.status_code}")
            print(resp.text)
            return
        
        twins = resp.json()
        if not twins:
            print("No twins found")
            return
        
        twin_id = twins[0].get("id")
        twin_name = twins[0].get("name", "Unknown")
        print(f"Testing with twin: {twin_name} ({twin_id[:8]}...)")
        
        # Test each query
        for query in test_queries:
            print(f"\n=== Testing: '{query}' ===")
            try:
                resp = await client.post(
                    f"{BASE_URL}/chat/{twin_id}",
                    headers={"Authorization": f"Bearer {TEST_TOKEN}"},
                    json={"message": query},
                    timeout=30.0
                )
                if resp.status_code == 200:
                    data = resp.json()
                    print(f"  Response: {data.get('response', 'No response')[:100]}...")
                    print(f"  Citations: {len(data.get('citations', []))}")
                else:
                    print(f"  Error {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                print(f"  Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_chat())
