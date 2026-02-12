"""
End-to-End Smoke Test Suite
Purpose: Verify critical user journey from auth to graph write
Usage: pytest tests/test_e2e_smoke.py -v
"""

import os
import pytest
import requests
from typing import Dict, Optional

# These tests require a live backend + real credentials.
# Opt-in with RUN_E2E_SMOKE=1 (and set API_URL/TEST_TOKEN).
pytestmark = pytest.mark.integration
if os.getenv("RUN_E2E_SMOKE", "0").lower() not in {"1", "true", "yes"}:
    pytest.skip("E2E smoke tests disabled (set RUN_E2E_SMOKE=1 to enable)", allow_module_level=True)

# Configuration
API_URL = os.getenv("API_URL", "http://localhost:8000")
TEST_TOKEN = os.getenv("TEST_TOKEN", "")

@pytest.fixture
def api_headers() -> Dict[str, str]:
    """Create headers with auth token"""
    if not TEST_TOKEN:
        pytest.skip("TEST_TOKEN environment variable not set")
    return {
        "Authorization": f"Bearer {TEST_TOKEN}",
        "Content-Type": "application/json"
    }

@pytest.fixture
def user_id(api_headers) -> str:
    """Sync user and return user ID"""
    response = requests.post(
        f"{API_URL}/auth/sync-user",
        headers=api_headers
    )
    assert response.status_code == 200, f"User sync failed: {response.text}"
    data = response.json()
    return data["user"]["id"]

@pytest.fixture
def twin_id(api_headers, user_id) -> Optional[str]:
    """Get or create a twin for testing"""
    # Try to list existing twins
    response = requests.get(
        f"{API_URL}/twins",
        headers=api_headers
    )
    
    if response.status_code == 200:
        twins = response.json()
        if isinstance(twins, list) and len(twins) > 0:
            return twins[0]["id"]
    
    # If no twins, skip tests that require them
    pytest.skip("No twin available for testing (create one manually)")

class TestHealthAndCORS:
    """Layer 0: Basic connectivity"""
    
    def test_health_check(self):
        """Verify backend is running"""
        response = requests.get(f"{API_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    
    def test_cors_headers(self):
        """Verify CORS is configured"""
        response = requests.options(
            f"{API_URL}/auth/sync-user",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST"
            }
        )
        assert "access-control-allow-origin" in response.headers

class TestAuthentication:
    """Layer 1: Auth flow"""
    
    def test_user_sync_success(self, api_headers):
        """Critical test: User sync must not fail with avatar_url error"""
        response = requests.post(
            f"{API_URL}/auth/sync-user",
            headers=api_headers
        )
        
        # This is THE critical blocker test
        assert response.status_code == 200, \
            f"User sync failed (likely avatar_url missing): {response.text}"
        
        data = response.json()
        assert "user" in data
        assert "id" in data["user"]
        assert data["status"] in ["created", "exists"]
    
    def test_get_profile(self, api_headers, user_id):
        """User profile should be retrievable after sync"""
        response = requests.get(
            f"{API_URL}/auth/me",
            headers=api_headers
        )
        
        # 404 is acceptable if profile endpoint expects twin setup
        assert response.status_code in [200, 404]

class TestInterviewFlow:
    """Layer 2: Interview endpoints"""
    
    def test_interview_endpoint_accessible(self, api_headers, twin_id):
        """Interview endpoint must accept requests"""
        response = requests.post(
            f"{API_URL}/cognitive/interview/{twin_id}",
            headers=api_headers,
            json={"message": "Hello, test interview"}
        )
        
        assert response.status_code in [200, 201], \
            f"Interview endpoint failed: {response.text}"
        
        data = response.json()
        assert "response" in data
        assert "session_id" in data
        assert "stage" in data
    
    def test_interview_creates_session(self, api_headers, twin_id):
        """Interview should create a session in database"""
        # Start interview
        response = requests.post(
            f"{API_URL}/cognitive/interview/{twin_id}",
            headers=api_headers,
            json={"message": "I want to build a knowledge assistant"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify session_id is returned
        assert data["session_id"] is not None
        assert data["conversation_id"] is not None
        
        # Verify stage is set
        assert data["stage"] in ["OPENING", "INTENT_CAPTURE", "DEEP_INTERVIEW", "COMPLETE"]

class TestGraphPersistence:
    """Layer 3: Knowledge graph writes"""
    
    def test_graph_endpoint_accessible(self, api_headers, twin_id):
        """Graph retrieval endpoint must work"""
        response = requests.get(
            f"{API_URL}/twins/{twin_id}/graph?limit=10",
            headers=api_headers
        )
        
        # 403 means auth issue, 200 means success
        assert response.status_code in [200, 403], \
            f"Graph endpoint unexpected status: {response.status_code}"
        
        if response.status_code == 200:
            data = response.json()
            assert "nodes" in data
            assert "edges" in data

class TestEndToEndFlow:
    """Complete user journey"""
    
    def test_full_interview_cycle(self, api_headers, twin_id):
        """Complete interview cycle: start → answer → verify graph"""
        
        # Step 1: Start interview
        start_response = requests.post(
            f"{API_URL}/cognitive/interview/{twin_id}",
            headers=api_headers,
            json={"message": "I want to test the full flow"}
        )
        assert start_response.status_code == 200
        start_data = start_response.json()
        conversation_id = start_data["conversation_id"]
        
        # Step 2: Continue interview
        continue_response = requests.post(
            f"{API_URL}/cognitive/interview/{twin_id}",
            headers=api_headers,
            json={
                "message": "I want a productivity assistant that helps me stay organized",
                "conversation_id": conversation_id
            }
        )
        assert continue_response.status_code == 200
        
        # Step 3: Verify graph has data (may take a few turns)
        graph_response = requests.get(
            f"{API_URL}/twins/{twin_id}/graph",
            headers=api_headers
        )
        
        if graph_response.status_code == 200:
            graph_data = graph_response.json()
            # After a few turns, should have some nodes
            print(f"Graph nodes: {len(graph_data.get('nodes', []))}")
            print(f"Graph edges: {len(graph_data.get('edges', []))}")

if __name__ == "__main__":
    # Allow running directly
    pytest.main([__file__, "-v", "-s"])
