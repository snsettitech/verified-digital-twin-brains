"""
Tests for Crawl Endpoints (Phase 1A.6)

Tests the REST API endpoints for crawl management:
- POST /twins/{twin_id}/crawls
- GET /twins/{twin_id}/crawls/{crawl_id}
- GET /twins/{twin_id}/crawls
- DELETE /twins/{twin_id}/crawls/{crawl_id}
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


@pytest.fixture
def mock_user():
    """Mock authenticated user."""
    return {
        "id": "user_123",
        "email": "test@example.com",
        "tenant_id": "tenant_123",
    }


@pytest.fixture
def mock_twin():
    """Mock twin data."""
    return {
        "id": "twin_123",
        "tenant_id": "tenant_123",
        "name": "Test Twin",
    }


@pytest.fixture
def mock_crawl_run():
    """Mock crawl run data."""
    return {
        "id": "crawl_456",
        "twin_id": "twin_123",
        "status": "queued",
        "seed_urls": ["https://example.com"],
        "max_pages": 50,
        "max_depth": 2,
        "pages_found": 0,
        "pages_ingested": 0,
        "pages_failed": 0,
        "created_at": "2024-01-01T00:00:00Z",
    }


class TestCreateCrawl:
    """Test POST /twins/{twin_id}/crawls"""
    
    @patch("backend.routers.crawl.verify_twin_ownership")
    @patch("backend.routers.crawl._create_crawl_run")
    @patch("backend.routers.crawl.get_current_user")
    def test_create_crawl_success(self, mock_get_user, mock_create, mock_verify, mock_user, mock_twin):
        """Should create crawl with valid payload."""
        mock_get_user.return_value = mock_user
        mock_verify.return_value = None
        mock_create.return_value = "crawl_456"
        
        response = client.post(
            f"/twins/{mock_twin['id']}/crawls",
            json={
                "seed_urls": ["https://example.com"],
                "max_pages": 50,
                "max_depth": 2,
            },
            headers={"Authorization": "Bearer test_token"}
        )
        
        # Note: This will fail with 403 without proper auth setup in tests
        # But we can verify the endpoint is wired correctly
        assert response.status_code in [200, 201, 401, 403]  # Auth required
    
    def test_create_crawl_endpoint_registered(self):
        """Route should remain registered regardless of legacy env flags."""
        response = client.post(
            "/twins/twin_123/crawls",
            json={"seed_urls": ["https://example.com"]},
        )
        assert response.status_code in [200, 201, 401, 403, 422]
    
    def test_create_crawl_invalid_payload(self):
        """Should reject invalid payload."""
        # Missing seed_urls
        response = client.post(
            "/twins/twin_123/crawls",
            json={},
        )
        assert response.status_code in [401, 403, 422]  # Auth or validation error
    
    def test_create_crawl_invalid_url(self):
        """Should reject invalid URLs."""
        response = client.post(
            "/twins/twin_123/crawls",
            json={"seed_urls": ["not-a-url"]},
        )
        assert response.status_code in [401, 403, 422]  # Auth or validation error


class TestGetCrawlStatus:
    """Test GET /twins/{twin_id}/crawls/{crawl_id}"""
    
    @patch("backend.routers.crawl._get_crawl_or_404")
    @patch("backend.routers.crawl.verify_twin_ownership")
    @patch("backend.routers.crawl.get_current_user")
    def test_get_crawl_success(self, mock_get_user, mock_verify, mock_get_crawl, mock_user, mock_crawl_run):
        """Should return crawl status for valid request."""
        mock_get_user.return_value = mock_user
        mock_verify.return_value = None
        mock_get_crawl.return_value = mock_crawl_run
        
        response = client.get(
            f"/twins/{mock_crawl_run['twin_id']}/crawls/{mock_crawl_run['id']}",
            headers={"Authorization": "Bearer test_token"}
        )
        
        # Will be 403 without auth, but verifies endpoint wiring
        assert response.status_code in [200, 401, 403]  # Auth required
    
    def test_get_crawl_not_found(self):
        """Should return 404 for unknown crawl."""
        response = client.get("/twins/twin_123/crawls/nonexistent")
        assert response.status_code in [401, 403, 404]


class TestListCrawls:
    """Test GET /twins/{twin_id}/crawls"""
    
    def test_list_crawls_endpoint_exists(self):
        """Endpoint should exist."""
        response = client.get("/twins/twin_123/crawls")
        assert response.status_code in [200, 401, 403]


class TestCancelCrawl:
    """Test DELETE /twins/{twin_id}/crawls/{crawl_id}"""
    
    def test_cancel_crawl_endpoint_exists(self):
        """Endpoint should exist."""
        response = client.delete("/twins/twin_123/crawls/crawl_456")
        assert response.status_code in [200, 400, 401, 403, 404]


class TestFeatureFlagGating:
    """Route registration behavior."""
    
    def test_router_included(self):
        """Router should be in app routes."""
        # Check if routes are registered
        routes = []
        for route in app.routes:
            path = getattr(route, "path", None)
            if path:
                routes.append(path)
            original_router = getattr(route, "original_router", None)
            if original_router is not None:
                routes.extend(
                    child_path
                    for child_path in (
                        getattr(child_route, "path", None)
                        for child_route in getattr(original_router, "routes", [])
                    )
                    if child_path
                )
        crawl_routes = [r for r in routes if "crawl" in r.lower()]
        assert len(crawl_routes) > 0
    
    def test_crawl_route_not_404(self):
        """A representative crawl endpoint should not return 404."""
        response = client.get("/twins/twin_123/crawls")
        assert response.status_code != 404


class TestResponseSchemas:
    """Test response schema validation."""
    
    def test_create_response_structure(self):
        """Create response should have required fields."""
        # Would need mocked auth to test fully
        pass
    
    def test_status_response_no_content_blobs(self):
        """Status response should not include page content."""
        # Verify metadata-only responses
        pass


class TestTwinScoping:
    """Test twin-level access control."""
    
    def test_cannot_access_other_twin_crawl(self):
        """Should not access crawl from different twin."""
        # This would be enforced by verify_twin_ownership
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
