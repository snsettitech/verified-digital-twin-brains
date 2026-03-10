# scripts/manual_verify_phase2.py
import asyncio
import sys
import os
import uuid
from unittest.mock import MagicMock, AsyncMock, patch

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

# Use a valid UUID for simulating twin_id to pass validation check if it reaches validation
TEST_TWIN_ID = "00000000-0000-0000-0000-000000000000"

async def verify_web_crawler():
    print("\nVerifying Web Crawler...")
    
    # Mocking at module level before function execution
    with patch("modules.web_crawler.supabase") as mock_supabase, \
         patch("modules.ingestion.process_and_index_text", new_callable=AsyncMock) as mock_process, \
         patch("modules.web_crawler.get_firecrawl_client") as mock_get_client:
        
        # Configure mocks
        mock_process.return_value = 10
        
        # Mock Firecrawl client
        mock_firecrawl = MagicMock()
        mock_firecrawl.crawl_url.return_value = {
            "data": [
                {"markdown": "# Home\nWelcome", "metadata": {"title": "Home", "sourceURL": "http://test.com"}},
                {"markdown": "# About\nUs", "metadata": {"title": "About", "sourceURL": "http://test.com/about"}}
            ]
        }
        mock_get_client.return_value = mock_firecrawl
        
        from modules.web_crawler import crawl_website
        
        print("   Running crawl_website(http://test.com)...")
        try:
            result = await crawl_website("http://test.com", TEST_TWIN_ID)
            
            if result["success"]:
                print(f"Crawl Successful: {result['pages_crawled']} pages, source_id={result['source_id']}")
                # Validate DB calls were made to mock
                if mock_supabase.table.called:
                    print(f"   (Verified) DB write attempted to mock Supabase.")
            else:
                print(f"Crawl Failed: {result.get('error')}")
                
        except Exception as e:
            print(f"Exception during crawl: {e}")

async def verify_social_ingestion():
    print("\nVerifying Social Ingestion...")
    
    with patch("modules.social_ingestion.supabase") as mock_supabase, \
         patch("modules.ingestion.process_and_index_text", new_callable=AsyncMock) as mock_process:
        
        mock_process.return_value = 5
        
        from modules.social_ingestion import TwitterScraper, LinkedInScraper
        
        # Test Twitter
        print("   Testing Twitter Scraper...")
        try:
            # We skip actual Twitter call as it requires httpx/sockets. 
            # Just verify class exists.
            print("TwitterScraper module loaded.")
        except:
            print("Failed to load TwitterScraper")

        # Test LinkedIn
        print("   Testing LinkedIn Scraper via Export...")
        try:
            profile_data = {
                "name": "Test User",
                "headline": "CEO",
                "summary": "Building things."
            }
            
            result = await LinkedInScraper.ingest_linkedin_export(TEST_TWIN_ID, profile_data)
            
            if result["success"]:
                print(f"LinkedIn Ingestion Successful: {result['chunks_indexed']} chunks")
                if mock_supabase.table.called:
                    print(f"   (Verified) DB write attempted to mock Supabase.")
            else:
                print(f"LinkedIn Ingestion Failed: {result.get('error')}")
                
        except Exception as e:
            print(f"Exception during LinkedIn ingestion: {e}")

async def main():
    print("Starting Phase 2 Manual Verification")
    await verify_web_crawler()
    await verify_social_ingestion()
    print("\nVerification Complete")

if __name__ == "__main__":
    asyncio.run(main())
