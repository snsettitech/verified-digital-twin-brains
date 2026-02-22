#!/usr/bin/env python3
"""
Test LinkedIn OpenGraph metadata extraction
"""
import httpx
from bs4 import BeautifulSoup

def extract_og(soup, prop):
    tag = soup.find("meta", property=prop)
    return tag.get("content") if tag else None

def extract_canonical(soup):
    tag = soup.find("link", rel="canonical")
    return tag.get("href") if tag else None

def extract_meta_name(soup, name):
    tag = soup.find("meta", attrs={"name": name})
    return tag.get("content") if tag else None

async def test_linkedin_og():
    url = "https://www.linkedin.com/in/sainathsetti/"
    
    print("=" * 80)
    print("TESTING LINKEDIN OPENGRAPH METADATA")
    print("=" * 80)
    print(f"\nURL: {url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }
    
    async with httpx.AsyncClient(timeout=20, headers=headers, follow_redirects=True) as client:
        print("\n[1] Fetching URL...")
        resp = await client.get(url)
        
        print(f"    Status: {resp.status_code}")
        print(f"    Final URL: {resp.url}")
        print(f"    Content length: {len(resp.text)}")
        
        html_text = resp.text
        
        # Check for login wall indicators
        if "login" in html_text.lower()[:5000] or "sign in" in html_text.lower()[:5000]:
            print("\n    ⚠️  Login wall detected!")
        
        soup = BeautifulSoup(html_text, "html.parser")
        
        print("\n[2] Extracting OpenGraph metadata:")
        og_title = extract_og(soup, "og:title")
        og_desc = extract_og(soup, "og:description")
        og_image = extract_og(soup, "og:image")
        og_url = extract_og(soup, "og:url")
        canonical = extract_canonical(soup)
        page_title = soup.title.string.strip() if soup.title and soup.title.string else None
        
        print(f"    og:title: {og_title}")
        print(f"    og:description: {og_desc[:100]}..." if og_desc and len(og_desc) > 100 else f"    og:description: {og_desc}")
        print(f"    og:image: {og_image[:50]}..." if og_image and len(og_image) > 50 else f"    og:image: {og_image}")
        print(f"    og:url: {og_url}")
        print(f"    canonical: {canonical}")
        print(f"    page_title: {page_title}")
        
        # Check if we got useful data
        if og_title and og_desc and "linkedin" not in og_title.lower():
            print("\n[3] ✅ Got useful OpenGraph data!")
            
            # Build minimal profile doc
            doc_lines = [f"# LinkedIn Profile: {og_title}"]
            doc_lines.append(f"URL: {url}")
            if og_desc:
                doc_lines.append(f"\n## About\n{og_desc}")
            
            doc = "\n".join(doc_lines)
            print(f"\nGenerated document ({len(doc)} chars):")
            print("-" * 80)
            print(doc)
            print("-" * 80)
            return True
        else:
            print("\n[3] ❌ No useful OpenGraph data (login wall or generic page)")
            # Print first 500 chars to see what we got
            print(f"\nPage content preview:")
            print("-" * 80)
            print(html_text[:500])
            print("-" * 80)
            return False

if __name__ == "__main__":
    import asyncio
    success = asyncio.run(test_linkedin_og())
    print("\n" + "=" * 80)
    if success:
        print("SUCCESS - OpenGraph works!")
    else:
        print("FAILED - LinkedIn blocks OpenGraph scraping")
    print("=" * 80)
