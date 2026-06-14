"""
Research Claim Web Verification Tests (Phase 9)

Tests for:
- Web search providers (Exa, Brave, Serper, Mock)
- Web verifier (fetch, relevance assessment, status determination)
- Web verification service (orchestration, persistence, idempotency)
- API endpoints
- Feature flags
- Regression tests for Phase 8
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from modules.research_claim_web_search import (
    SearchResult,
    MockSearchProvider,
    ExaSearchProvider,
    BraveSearchProvider,
    SerperSearchProvider,
    build_claim_search_query,
    search_for_claim,
)
from modules.research_claim_web_verifier import (
    WebVerificationStatus,
    WebEvidenceItem,
    WebVerificationResult,
    ClaimWebVerifier,
    verify_claim_against_web,
)
from modules.research_claim_web_verification_service import (
    WebVerificationRunStatus,
    WebVerificationSummary,
    ClaimWithVerification,
    ResearchClaimWebVerificationService,
)
from modules.research_claim_extractor import ResearchClaim, ClaimType, VerificationStatus


# =============================================================================
# Web Search Provider Tests
# =============================================================================

class TestSearchResult:
    """Test SearchResult dataclass."""
    
    def test_search_result_creation(self):
        """Test creating a SearchResult."""
        result = SearchResult(
            url="https://example.com/article",
            title="Example Article",
            snippet="This is a snippet",
            score=0.95,
            source="exa"
        )
        
        assert result.url == "https://example.com/article"
        assert result.score == 0.95
        assert result.source == "exa"


class TestMockSearchProvider:
    """Test MockSearchProvider for deterministic testing."""
    
    @pytest.mark.asyncio
    async def test_mock_provider_returns_configured_results(self):
        """Test mock provider returns configured results."""
        results = [
            SearchResult(url="http://1.com", title="One", snippet="Snippet 1"),
            SearchResult(url="http://2.com", title="Two", snippet="Snippet 2"),
        ]
        
        provider = MockSearchProvider(results)
        returned = await provider.search("test query", num_results=5)
        
        assert len(returned) == 2
        assert returned[0].url == "http://1.com"
        assert provider.search_calls[0]["query"] == "test query"
    
    @pytest.mark.asyncio
    async def test_mock_provider_limits_results(self):
        """Test mock provider respects num_results limit."""
        results = [
            SearchResult(url=f"http://{i}.com", title=f"Title {i}", snippet="")
            for i in range(10)
        ]
        
        provider = MockSearchProvider(results)
        returned = await provider.search("query", num_results=3)
        
        assert len(returned) == 3
    
    @pytest.mark.asyncio
    async def test_mock_provider_empty_results(self):
        """Test mock provider with empty results."""
        provider = MockSearchProvider([])
        returned = await provider.search("query")
        
        assert returned == []


class TestBuildClaimSearchQuery:
    """Test query building for search."""
    
    def test_build_query_removes_first_person(self):
        """Test first-person pronouns are removed."""
        query = build_claim_search_query("I prefer Python over JavaScript")
        
        assert "I " not in query
        assert "prefer" in query
    
    def test_build_query_adds_context_for_experience(self):
        """Test context added for experience claims."""
        query = build_claim_search_query(
            "Worked at Google",
            claim_type="experience",
            include_verification_terms=True
        )
        
        assert "background experience" in query
    
    def test_build_query_limits_length(self):
        """Test long claims are truncated."""
        long_claim = "A" * 300
        query = build_claim_search_query(long_claim)
        
        assert len(query) <= 250


# =============================================================================
# Web Verifier Tests
# =============================================================================

class TestWebEvidenceItem:
    """Test WebEvidenceItem dataclass."""
    
    def test_evidence_to_dict(self):
        """Test converting evidence to dict."""
        evidence = WebEvidenceItem(
            source_url="https://example.com",
            source_title="Example",
            source_snippet="Snippet",
            extracted_quote="Quote",
            relevance_score=0.85,
            evidence_type="supporting",
            content_quality="full",
            domain_tier=1
        )
        
        data = evidence.to_dict()
        assert data["source_url"] == "https://example.com"
        assert data["relevance_score"] == 0.85
        assert data["domain_tier"] == 1


class TestClaimWebVerifier:
    """Test ClaimWebVerifier."""
    
    @pytest.mark.asyncio
    async def test_verify_claim_no_results(self):
        """Test verification with no search results."""
        verifier = ClaimWebVerifier()
        claim = ResearchClaim(
            id="claim-123",
            claim_text="Test claim",
            claim_type=ClaimType.BELIEF,
        )
        
        result = await verifier.verify_claim(claim, [])
        
        assert result.status == WebVerificationStatus.INSUFFICIENT_EVIDENCE
        assert result.confidence == 0.0
        assert result.sources_searched == 0
    
    @pytest.mark.asyncio
    async def test_verify_claim_with_mock_fetch(self):
        """Test verification with mocked fetch."""
        # Mock Firecrawl result
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.content = "This content supports the test claim very well."
        mock_result.metadata = {"title": "Test Page"}
        mock_result.quality.value = "full"
        
        mock_client = MagicMock()
        mock_client.scrape_with_retry = AsyncMock(return_value=mock_result)
        
        verifier = ClaimWebVerifier(firecrawl_client=mock_client)
        
        claim = ResearchClaim(
            id="claim-123",
            claim_text="Content supports test claim",
            claim_type=ClaimType.BELIEF,
        )
        
        search_results = [
            SearchResult(url="https://example.com", title="Test", snippet="Snippet")
        ]
        
        result = await verifier.verify_claim(claim, search_results)
        
        assert result.status == WebVerificationStatus.SUPPORTED
        assert result.confidence > 0.5
        assert len(result.evidence) > 0
    
    @pytest.mark.asyncio
    async def test_verify_claim_fetch_blocked(self):
        """Test verification when fetch is blocked."""
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error = {"failure_type": "GATING"}
        mock_result.metadata = {}
        mock_result.quality.value = "blocked"
        
        mock_client = MagicMock()
        mock_client.scrape_with_retry = AsyncMock(return_value=mock_result)
        
        verifier = ClaimWebVerifier(firecrawl_client=mock_client)
        
        claim = ResearchClaim(
            id="claim-123",
            claim_text="Test claim",
            claim_type=ClaimType.BELIEF,
        )
        
        search_results = [
            SearchResult(url="https://example.com", title="Test", snippet="Snippet")
        ]
        
        result = await verifier.verify_claim(claim, search_results)
        
        # Should be insufficient evidence since fetch failed
        assert result.status == WebVerificationStatus.INSUFFICIENT_EVIDENCE
        assert "blocked" in result.notes.lower() or result.notes == "No web evidence found"
    
    def test_get_domain_tier(self):
        """Test domain tier classification."""
        verifier = ClaimWebVerifier()
        
        assert verifier._get_domain_tier("https://stanford.edu/research") == 1
        assert verifier._get_domain_tier("https://gov.uk/page") == 1
        assert verifier._get_domain_tier("https://medium.com/article") == 2
        assert verifier._get_domain_tier("https://unknown-blog.com") == 3


class TestWebVerificationResult:
    """Test WebVerificationResult dataclass."""
    
    def test_result_to_dict(self):
        """Test converting result to dict."""
        result = WebVerificationResult(
            claim_id="claim-123",
            status=WebVerificationStatus.SUPPORTED,
            confidence=0.85,
            evidence=[],
            notes="Test notes",
            sources_searched=5,
            sources_found=3
        )
        
        data = result.to_dict()
        assert data["claim_id"] == "claim-123"
        assert data["status"] == "supported"
        assert data["confidence"] == 0.85


# =============================================================================
# Web Verification Service Tests
# =============================================================================

class TestWebVerificationSummary:
    """Test WebVerificationSummary dataclass."""
    
    def test_summary_creation(self):
        """Test creating a summary."""
        summary = WebVerificationSummary(
            research_run_id="run-123",
            twin_id="twin-456",
            status=WebVerificationRunStatus.COMPLETED,
            total_claims=10,
            verified_count=8,
            by_status={"supported": 5, "conflicting": 3}
        )
        
        assert summary.research_run_id == "run-123"
        assert summary.by_status["supported"] == 5


class TestResearchClaimWebVerificationService:
    """Test ResearchClaimWebVerificationService."""
    
    def test_service_initialization(self):
        """Test service can be initialized."""
        mock_db = MagicMock()
        service = ResearchClaimWebVerificationService(supabase_client=mock_db)
        
        assert service.db == mock_db
    
    @pytest.mark.asyncio
    async def test_filter_eligible_claims(self):
        """Test filtering claims by eligibility."""
        service = ResearchClaimWebVerificationService()
        
        claims = [
            ResearchClaim(id="1", claim_text="Public fact", claim_type=ClaimType.BELIEF),
            ResearchClaim(id="2", claim_text="Private preference", claim_type=ClaimType.PREFERENCE),
            ResearchClaim(id="3", claim_text="Experience", claim_type=ClaimType.EXPERIENCE),
        ]
        
        eligible = service._filter_eligible_claims(claims)
        
        # Based on taxonomy mapping, some should be filtered
        assert len(eligible) <= len(claims)
    
    @pytest.mark.asyncio
    async def test_map_claim_type_to_class(self):
        """Test claim type to class mapping."""
        service = ResearchClaimWebVerificationService()
        
        assert service._map_claim_type_to_class(ClaimType.EXPERIENCE) == "private_fact"
        assert service._map_claim_type_to_class(ClaimType.BELIEF) == "owner_stance"
        assert service._map_claim_type_to_class(ClaimType.HEURISTIC) == "procedural"


# =============================================================================
# API Contract Tests
# =============================================================================

class TestAPIContracts:
    """Test API request/response contracts."""
    
    def test_web_verification_status_values(self):
        """Test web verification status enum values match API contract."""
        expected = [
            "pending", "supported", "conflicting", "insufficient_evidence",
            "needs_review", "blocked", "error", "skipped"
        ]
        actual = [s.value for s in WebVerificationStatus]
        assert set(actual) == set(expected)
    
    def test_web_verification_run_status_values(self):
        """Test run status enum values match API contract."""
        expected = ["pending", "running", "completed", "failed", "partial"]
        actual = [s.value for s in WebVerificationRunStatus]
        assert set(actual) == set(expected)


# =============================================================================
# Feature Flag Tests
# =============================================================================

class TestFeatureFlags:
    """Test Deep Research configuration behavior."""
    
    @patch("os.getenv")
    def test_legacy_web_disable_flag_not_exposed(self, mock_getenv):
        """Deprecated web verification rollout flag should not remain on the config."""
        from modules.deep_research_config import DeepResearchConfig
        
        def mock_env(key, default=None):
            if key == "DR_PHASE_9_WEB_VERIFICATION_DISABLED":
                return "true"
            return default
        
        mock_getenv.side_effect = mock_env
        config = DeepResearchConfig.from_env()
        
        assert not hasattr(config, "phase_9_web_verification_disabled")
    
    @patch("os.getenv")
    def test_deep_research_always_enabled(self, mock_getenv):
        """Deep Research should remain enabled regardless of legacy env flags."""
        from modules.deep_research_config import DeepResearchConfig
        
        def mock_env(key, default=None):
            if key in ("DEEP_RESEARCH_ENABLED", "DEEP_RESEARCH_GLOBAL_DISABLE"):
                return "false"
            return default
        
        mock_getenv.side_effect = mock_env
        config = DeepResearchConfig.from_env()
        
        assert config.is_enabled() is True


# =============================================================================
# Idempotency Tests
# =============================================================================

class TestIdempotency:
    """Test idempotent behavior."""
    
    @pytest.mark.asyncio
    async def test_verification_idempotent(self):
        """Test that verification is idempotent (same input → same output)."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.content = "Content supporting claim"
        mock_result.metadata = {"title": "Page"}
        mock_result.quality.value = "full"
        
        mock_client = MagicMock()
        mock_client.scrape_with_retry = AsyncMock(return_value=mock_result)
        
        verifier = ClaimWebVerifier(firecrawl_client=mock_client)
        
        claim = ResearchClaim(
            id="claim-123",
            claim_text="Test claim",
            claim_type=ClaimType.BELIEF,
        )
        
        search_results = [
            SearchResult(url="https://example.com", title="Test", snippet="Snippet")
        ]
        
        result1 = await verifier.verify_claim(claim, search_results)
        result2 = await verifier.verify_claim(claim, search_results)
        
        assert result1.status == result2.status
        assert result1.confidence == result2.confidence


# =============================================================================
# Integration Tests
# =============================================================================

@pytest.mark.asyncio
async def test_full_web_verification_pipeline():
    """Test the full search → fetch → verify → output pipeline."""
    
    # Setup mock search provider
    search_results = [
        SearchResult(
            url="https://example.com/article",
            title="Test Article",
            snippet="This supports the claim",
        )
    ]
    search_provider = MockSearchProvider(search_results)
    
    # Setup mock Firecrawl
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.content = "This article fully supports the test claim about software development."
    mock_result.metadata = {"title": "Test Article"}
    mock_result.quality.value = "full"
    
    mock_client = MagicMock()
    mock_client.scrape_with_retry = AsyncMock(return_value=mock_result)
    
    # Create verifier
    verifier = ClaimWebVerifier(firecrawl_client=mock_client)
    
    # Test claim
    claim = ResearchClaim(
        id="claim-123",
        claim_text="Software development is important",
        claim_type=ClaimType.BELIEF,
    )
    
    # Search
    results = await search_provider.search("software development important")
    assert len(results) == 1
    
    # Verify
    verification = await verifier.verify_claim(claim, results)
    
    # Assert
    assert verification.status == WebVerificationStatus.SUPPORTED
    assert verification.confidence > 0.5
    assert len(verification.evidence) > 0


# =============================================================================
# Regression Tests for Phase 8
# =============================================================================

class TestPhase8Regression:
    """Ensure Phase 8 is not broken by Phase 9."""
    
    def test_phase_8_verification_status_unchanged(self):
        """Test Phase 8 verification status values are unchanged."""
        expected = ["pending", "supported", "insufficient_evidence", "conflicting", "needs_review"]
        actual = [s.value for s in VerificationStatus]
        assert set(actual) == set(expected)
    
    def test_phase_8_claim_model_unchanged(self):
        """Test Phase 8 claim model fields are unchanged."""
        claim = ResearchClaim(
            id="test",
            claim_text="Test",
            verification_status=VerificationStatus.SUPPORTED,
        )
        
        # Should have Phase 8 fields
        assert hasattr(claim, 'verification_status')
        assert hasattr(claim, 'confidence')
        assert hasattr(claim, 'evidence_quotes')
        
        # Should NOT have Phase 9 fields (separate table)
        assert not hasattr(claim, 'web_verification_status')


# =============================================================================
# URL Deduplication Tests
# =============================================================================

class TestURLDeduplication:
    """Test URL deduplication in verifier."""
    
    @pytest.mark.asyncio
    async def test_duplicate_urls_deduplicated(self):
        """Test duplicate URLs are deduplicated."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.content = "Content"
        mock_result.metadata = {}
        mock_result.quality.value = "full"
        
        mock_client = MagicMock()
        mock_client.scrape_with_retry = AsyncMock(return_value=mock_result)
        
        verifier = ClaimWebVerifier(firecrawl_client=mock_client)
        
        claim = ResearchClaim(id="claim-123", claim_text="Test", claim_type=ClaimType.BELIEF)
        
        # Duplicate URLs
        search_results = [
            SearchResult(url="https://example.com", title="Test", snippet=""),
            SearchResult(url="https://example.com", title="Test", snippet=""),
            SearchResult(url="https://example.com/page", title="Test", snippet=""),
        ]
        
        result = await verifier.verify_claim(claim, search_results)
        
        # Should only fetch 2 unique URLs
        assert mock_client.scrape_with_retry.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
