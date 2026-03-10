# scripts/manual_verify_phase5.py
"""
Manual Verification Script for Phase 5: YouTube Ingestion.
"""
import sys
import os
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

# 1. Setup paths
if "backend" not in sys.path:
    sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

# 2. Mock Modules GLOBAL
sys.modules["modules.observability"] = MagicMock()
sys.modules["modules.ingestion"] = MagicMock()

# 3. Import App
from fastapi.testclient import TestClient
from main import app
from modules.auth_guard import get_current_user

# 4. Auth Override
app.dependency_overrides[get_current_user] = lambda: {"user_id": "test-user", "tenant_id": "test-tenant", "role": "owner"}

from modules.media_ingestion import MediaIngester

client = TestClient(app)

def run_verification():
    print("Starting Phase 5 Manual Verification...")
    
    # Check what MediaIngester is
    print(f"MediaIngester Repr: {MediaIngester}") 
    
    # Manual Access
    import modules.media_ingestion
    
    # Define Fake Async Method
    async def fake_ingest(self, url): # Accept self if bound, or just url if static?
        # If patched on class, it requires 'self' if normal method.
        # But if assigning function to class attribute, it becomes Unbound unless accessed via instance.
        # When instance calls it, self is passed.
        # So signature should accept self + args
        print(f"FAKE INGEST CALLED with {url}")
        return {
            "success": True,
            "source_id": "verify-123",
            "chunks": 42
        }

    # Backup
    if isinstance(modules.media_ingestion.MediaIngester, type):
        print("MediaIngester is a CLASS.")
        original_method = modules.media_ingestion.MediaIngester.ingest_youtube_video
        modules.media_ingestion.MediaIngester.ingest_youtube_video = fake_ingest
    else:
        print("MediaIngester is a MOCK.")
        # If it is a Mock, setup return_value
        # Instance = MediaIngester(...) -> MediaIngester.return_value
        instance_mock = modules.media_ingestion.MediaIngester.return_value
        # instance.ingest_youtube_video(...) -> side_effect
        instance_mock.ingest_youtube_video.side_effect = lambda url: fake_ingest(None, url) 
        # Note: side_effect receives normal args. But fake_ingest expects self?
        # Let's simple it:
        async def fake_ingest_simple(url):
             print(f"FAKE INGEST CALLED with {url}")
             return {"success": True, "source_id": "verify-123", "chunks": 42}
        instance_mock.ingest_youtube_video.side_effect = fake_ingest_simple

    # Patch Auth
    import routers.enhanced_ingestion
    original_auth = routers.enhanced_ingestion.verify_twin_ownership
    routers.enhanced_ingestion.verify_twin_ownership = MagicMock(return_value=True)

    try:
        print("\n[Step 1] Sending POST to /ingest/youtube/{twin_id}")
        response = client.post(
            "/ingest/youtube/twin-123",
            json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
        )
        
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("Response:", response.json())
            print("API Endpoint Validation Passed")
            
            if routers.enhanced_ingestion.verify_twin_ownership.called:
                print("Auth check verified")
        else:
            print(f"API Failed with Body: {response.text}")

    finally:
        # Restore
        routers.enhanced_ingestion.verify_twin_ownership = original_auth
        if isinstance(modules.media_ingestion.MediaIngester, type):
            modules.media_ingestion.MediaIngester.ingest_youtube_video = original_method

if __name__ == "__main__":
    run_verification()
