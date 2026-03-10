#!/usr/bin/env python3
"""
Test Dumpling AI extract API for LinkedIn
"""
import os
import sys
import asyncio
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'backend', '.env'))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from modules.dumplingai_client import extract_webpage_data

async def test_extract_api():
    url = "https://www.linkedin.com/in/sainathsetti/"
    
    print("=" * 80)
    print("TESTING DUMPLING AI EXTRACT API FOR LINKEDIN")
    print("=" * 80)
    print(f"\nURL: {url}")
    
    try:
        result = await extract_webpage_data(
            url=url,
            instructions="Extract the LinkedIn profile information including: full name, headline, location, number of followers, about/summary section, current position, experience history, education, skills, and recent posts or activity.",
            render_js=True
        )
        
        print(f"\n[1] Result received:")
        print(f"    Type: {type(result)}")
        print(f"    Keys: {result.keys() if isinstance(result, dict) else 'N/A'}")
        print(f"    Success: {result.get('success') if isinstance(result, dict) else 'N/A'}")
        
        if result and result.get("success"):
            profile_data = result.get("data", {})
            print(f"\n[2] Profile data keys: {profile_data.keys() if isinstance(profile_data, dict) else 'N/A'}")
            
            name = profile_data.get("name", profile_data.get("fullName", "LinkedIn Profile"))
            print(f"    Name: {name}")
            print(f"    Headline: {profile_data.get('headline', 'N/A')}")
            print(f"    Location: {profile_data.get('location', 'N/A')}")
            print(f"    Followers: {profile_data.get('followers', 'N/A')}")
            print(f"    About: {(profile_data.get('about') or '')[:100]}...")
            
            # Build document
            doc_lines = [f"# LinkedIn Profile: {name}", f"URL: {url}"]
            
            if profile_data.get("headline"):
                doc_lines.append(f"\n## Headline\n{profile_data['headline']}")
            if profile_data.get("location"):
                doc_lines.append(f"\n## Location\n{profile_data['location']}")
            if profile_data.get("followers"):
                doc_lines.append(f"\n## Followers\n{profile_data['followers']}")
            if profile_data.get("about"):
                doc_lines.append(f"\n## About\n{profile_data['about']}")
            if profile_data.get("experience"):
                doc_lines.append(f"\n## Experience\n{profile_data['experience']}")
            if profile_data.get("education"):
                doc_lines.append(f"\n## Education\n{profile_data['education']}")
            if profile_data.get("skills"):
                doc_lines.append(f"\n## Skills\n{profile_data['skills']}")
            
            doc = "\n".join(doc_lines)
            print(f"\n[3] Generated document length: {len(doc)}")
            print(f"\nDocument preview:")
            print("-" * 80)
            print(doc[:500])
            print("-" * 80)
            
            return True
        else:
            print(f"\n[2] Extract API returned no success:")
            print(f"    Result: {result}")
            return False
            
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_extract_api())
    print("\n" + "=" * 80)
    if success:
        print("SUCCESS!")
    else:
        print("FAILED")
    print("=" * 80)
