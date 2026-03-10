#!/usr/bin/env python3
"""
Test Dumpling AI scrape API for LinkedIn
"""
import os
import sys
import asyncio
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'backend', '.env'))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from modules.dumplingai_client import scrape_webpage

async def test_scrape_api():
    url = "https://www.linkedin.com/in/sainathsetti/"
    
    print("=" * 80)
    print("TESTING DUMPLING AI SCRAPE API FOR LINKEDIN")
    print("=" * 80)
    print(f"\nURL: {url}")
    
    try:
        result = await scrape_webpage(
            url=url,
            format="markdown",
            cleaned=True,
            render_js=True
        )
        
        print(f"\n[1] Result received:")
        print(f"    Type: {type(result)}")
        print(f"    Keys: {result.keys() if isinstance(result, dict) else 'N/A'}")
        
        content = result.get("content", "")
        print(f"\n[2] Content length: {len(content)}")
        
        if content and len(content) > 100:
            print(f"\n[3] Content preview:")
            print("-" * 80)
            print(content[:1000])
            print("-" * 80)
            return True
        else:
            print(f"\n[3] Empty or very short content")
            return False
            
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_scrape_api())
    print("\n" + "=" * 80)
    if success:
        print("SUCCESS!")
    else:
        print("FAILED")
    print("=" * 80)
