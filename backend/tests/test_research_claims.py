"""
Research Claims Tests (Phase 8)

Tests for:
- Claim extraction
- Claim verification
- Claim enrichment service
- API endpoints
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from modules.research_claim_extractor import (
    ResearchClaim,
    ClaimType,
    VerificationStatus,
    EvidenceQuote,
    ResearchClaimExtractor,
    extract_claims_from_research_sources,
)
from modules.research_claim_verifier import (
    ClaimVerifier,
    VerificationResult,
    verify_research_claims,
)
from modules.research_claim_service import (
    ResearchClaimService,
    EnrichmentStatus,
    EnrichmentSummary,
)


# =============================================================================
# Claim Extraction Tests
# =============================================================================

class TestResearchClaim:
    """Test ResearchClaim dataclass."""
    
    def test_claim_creation(self):
        """Test creating a ResearchClaim."""
        claim = ResearchClaim(
            id="claim-123",
            research_run_id="run-456",
            twin_id="twin-789",
            claim_text="I prefer Python over JavaScript",
            claim_type=ClaimType.PREFERENCE,
            verification_status=VerificationStatus.PENDING,
            confidence=0.9,
            source_id="source-001",
            source_url="https://example.com/blog",
        )
        
        assert claim.id == "claim-123"
        assert claim.claim_type == ClaimType.PREFERENCE
        assert claim.verification_status == VerificationStatus.PENDING
    
    def test_claim_to_dict(self):
        """Test converting claim to dictionary."""
        claim = ResearchClaim(
            claim_text="Test claim",
            claim_type=ClaimType.BELIEF,
            confidence=0.8,
            evidence_quotes=[EvidenceQuote(quote="Evidence", relevance=0.9)],
        )
        
        data = claim.to_dict()
        assert data["claim_text"] == "Test claim"
        assert data["claim_type"] == "belief"
        assert "evidence_quotes" in data
    
    def test_claim_from_dict(self):
        """Test creating claim from dictionary."""
        data = {
            "id": "claim-123",
            "claim_text": "Test claim",
            "claim_type": "heuristic",
            "verification_status": "supported",
            "confidence": 0.85,
            "evidence_quotes": '[{"quote": "Evidence", "relevance": 0.9}]',
        }
        
        claim = ResearchClaim.from_dict(data)
        assert claim.id == "claim-123"
        assert claim.claim_type == ClaimType.HEURISTIC
        assert claim.verification_status == VerificationStatus.SUPPORTED
        assert len(claim.evidence_quotes) == 1


class TestResearchClaimExtractor:
    """Test ResearchClaimExtractor."""
    
    @pytest.mark.asyncio
    async def test_extract_from_source_empty_content(self):
        """Test extraction with empty content returns empty list."""
        extractor = ResearchClaimExtractor()
        claims = await extractor.extract_from_source(
            content="",
            source_id="source-001",
        )
        assert claims == []
    
    @pytest.mark.asyncio
    async def test_extract_from_source_short_content(self):
        """Test extraction with short content returns empty list."""
        extractor = ResearchClaimExtractor()
        claims = await extractor.extract_from_source(
            content="Short",
            source_id="source-001",
        )
        assert claims == []
    
    @pytest.mark.asyncio
    async def test_extract_from_source_mock_llm(self):
        """Test extraction with mocked LLM response."""
        mock_llm = AsyncMock(return_value=({
            "claims": [
                {
                    "claim_text": "I prefer remote work",
                    "claim_type": "preference",
                    "quote": "I prefer working remotely",
                    "confidence": 0.9,
                }
            ]
        }, None))
        
        extractor = ResearchClaimExtractor(llm_invoke_func=mock_llm)
        claims = await extractor.extract_from_source(
            content="I prefer working remotely because it gives me flexibility. " * 10,
            source_id="source-001",
            source_url="https://example.com",
            twin_id="twin-123",
            research_run_id="run-456",
        )
        
        assert len(claims) == 1
        assert claims[0].claim_text == "I prefer remote work"
        assert claims[0].claim_type == ClaimType.PREFERENCE
        assert claims[0].twin_id == "twin-123"
        assert claims[0].research_run_id == "run-456"
    
    @pytest.mark.asyncio
    async def test_extract_from_multiple_sources(self):
        """Test extraction from multiple sources."""
        mock_llm = AsyncMock(return_value=({
            "claims": [
                {
                    "claim_text": "Claim from source",
                    "claim_type": "belief",
                    "quote": "I believe in testing",
                    "confidence": 0.8,
                }
            ]
        }, None))
        
        extractor = ResearchClaimExtractor(llm_invoke_func=mock_llm)
        sources = [
            {"id": "source-1", "content": "Content 1 " * 20, "url": "http://1.com", "title": "Title 1"},
            {"id": "source-2", "content": "Content 2 " * 20, "url": "http://2.com", "title": "Title 2"},
        ]
        
        claims = await extractor.extract_from_sources(
            sources=sources,
            twin_id="twin-123",
        )
        
        assert len(claims) == 2  # One from each source


class TestExtractClaimsConvenienceFunction:
    """Test the extract_claims_from_research_sources convenience function."""
    
    @pytest.mark.asyncio
    async def test_extract_claims_function(self):
        """Test the main extraction entry point."""
        mock_llm = AsyncMock(return_value=({
            "claims": [
                {
                    "claim_text": "Test claim",
                    "claim_type": "value",
                    "quote": "I value testing",
                    "confidence": 0.95,
                }
            ]
        }, None))
        
        sources = [
            {"id": "source-1", "content": "Content " * 20},
        ]
        
        result = await extract_claims_from_research_sources(
            sources=sources,
            twin_id="twin-123",
            research_run_id="run-456",
            llm_invoke_func=mock_llm,
        )
        
        assert result["extracted_count"] == 1
        assert len(result["claims"]) == 1


# =============================================================================
# Claim Verification Tests
# =============================================================================

class TestClaimVerifier:
    """Test ClaimVerifier."""
    
    @pytest.mark.asyncio
    async def test_verify_claim_with_strong_support(self):
        """Test verification when strong evidence exists (2+ sources)."""
        verifier = ClaimVerifier(similarity_threshold=0.3)
        
        claim = ResearchClaim(
            claim_text="I prefer remote work",
            claim_type=ClaimType.PREFERENCE,
        )
        
        # Multiple sources for strong support
        sources = [
            {"id": "source-1", "content": "I prefer remote work because it's flexible."},
            {"id": "source-2", "content": "My preference is definitely for remote work options."},
        ]
        
        result = await verifier.verify_claim(claim, sources)
        
        # With 2+ supporting sources, should be supported
        assert result.status == VerificationStatus.SUPPORTED
        assert len(result.supporting_evidence) >= 2
    
    @pytest.mark.asyncio
    async def test_verify_claim_with_no_support(self):
        """Test verification when no evidence exists."""
        verifier = ClaimVerifier(similarity_threshold=0.9)  # High threshold
        
        claim = ResearchClaim(
            claim_text="I prefer remote work",
            claim_type=ClaimType.PREFERENCE,
        )
        
        sources = [
            {"id": "source-1", "content": "Completely unrelated content that doesn't match."},
        ]
        
        result = await verifier.verify_claim(claim, sources)
        
        assert result.status == VerificationStatus.INSUFFICIENT_EVIDENCE
    
    @pytest.mark.asyncio
    async def test_verify_claim_with_weak_support(self):
        """Test verification with weak evidence triggers insufficient_evidence."""
        verifier = ClaimVerifier(similarity_threshold=0.9)
        
        claim = ResearchClaim(
            claim_text="I prefer remote work over office work",
            claim_type=ClaimType.PREFERENCE,
        )
        
        # Weak/partial match with high threshold
        sources = [
            {"id": "source-1", "content": "Remote work is something I think about sometimes."},
        ]
        
        result = await verifier.verify_claim(claim, sources)
        
        # Should be insufficient_evidence when threshold is not met
        assert result.status == VerificationStatus.INSUFFICIENT_EVIDENCE


class TestVerifyClaimsConvenienceFunction:
    """Test the verify_research_claims convenience function."""
    
    @pytest.mark.asyncio
    async def test_verify_claims_function(self):
        """Test the main verification entry point."""
        claims = [
            ResearchClaim(
                claim_text="I prefer remote work",
                claim_type=ClaimType.PREFERENCE,
            ),
        ]
        
        sources = [
            {"id": "source-1", "content": "I prefer remote work because it's flexible."},
        ]
        
        result = await verify_research_claims(
            claims=claims,
            sources=sources,
            similarity_threshold=0.5,
        )
        
        assert result["verified_count"] == 1
        assert VerificationStatus.SUPPORTED in result["by_status"]


# =============================================================================
# Claim Service Tests
# =============================================================================

class TestEnrichmentSummary:
    """Test EnrichmentSummary dataclass."""
    
    def test_summary_creation(self):
        """Test creating enrichment summary."""
        summary = EnrichmentSummary(
            research_run_id="run-123",
            status=EnrichmentStatus.COMPLETED,
            total_claims=10,
            supported_count=5,
        )
        
        assert summary.research_run_id == "run-123"
        assert summary.status == EnrichmentStatus.COMPLETED
        assert summary.total_claims == 10


class TestResearchClaimService:
    """Test ResearchClaimService."""
    
    def test_service_initialization(self):
        """Test service can be initialized."""
        mock_db = MagicMock()
        service = ResearchClaimService(supabase_client=mock_db)
        
        assert service.db == mock_db
    
    @pytest.mark.asyncio
    async def test_get_enrichment_status_not_started(self):
        """Test getting status when enrichment hasn't started."""
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=None)
        
        service = ResearchClaimService(supabase_client=mock_db)
        status = await service.get_enrichment_status("run-123", "twin-456")
        
        assert status is None

    @pytest.mark.asyncio
    async def test_persist_claims_generates_missing_ids(self):
        """Persisted claims should always have UUIDs even if extractor left id unset."""
        mock_db = MagicMock()
        insert_mock = mock_db.table.return_value.insert.return_value
        insert_mock.execute.return_value = MagicMock()

        service = ResearchClaimService(supabase_client=mock_db)
        claim = ResearchClaim(
            research_run_id="run-123",
            twin_id="twin-456",
            claim_text="I prefer remote work",
            claim_type=ClaimType.PREFERENCE,
        )
        result = VerificationResult(
            claim=claim,
            status=VerificationStatus.SUPPORTED,
            confidence=0.91,
            supporting_evidence=[EvidenceQuote(quote="I prefer remote work", relevance=0.91)],
            conflicting_evidence=[],
            reasoning="Supported by source text",
        )

        await service._persist_claims([result])

        inserted_payload = mock_db.table.return_value.insert.call_args.args[0]
        assert inserted_payload["id"]
        assert claim.id == inserted_payload["id"]


# =============================================================================
# API Contract Tests
# =============================================================================

class TestAPIContracts:
    """Test API request/response contracts."""
    
    def test_verification_status_values(self):
        """Test verification status enum values match API contract."""
        expected = ["pending", "supported", "insufficient_evidence", "conflicting", "needs_review"]
        actual = [s.value for s in VerificationStatus]
        assert set(actual) == set(expected)
    
    def test_claim_type_values(self):
        """Test claim type enum values match API contract."""
        expected = ["preference", "belief", "heuristic", "value", "experience", "boundary", "uncertain"]
        actual = [t.value for t in ClaimType]
        assert set(actual) == set(expected)
    
    def test_enrichment_status_values(self):
        """Test enrichment status enum values match API contract."""
        expected = ["pending", "enriching", "completed", "failed"]
        actual = [s.value for s in EnrichmentStatus]
        assert set(actual) == set(expected)


# =============================================================================
# Feature Flag Tests
# =============================================================================

class TestFeatureFlags:
    """Test Deep Research configuration behavior."""
    
    @patch("os.getenv")
    def test_legacy_disable_flags_not_exposed(self, mock_getenv):
        """Deprecated Deep Research disable flags should not remain on the config."""
        from modules.deep_research_config import DeepResearchConfig
        
        def mock_env(key, default=None):
            if key == "DR_PHASE_8_CLAIMS_DISABLED":
                return "true"
            return default
        
        mock_getenv.side_effect = mock_env
        config = DeepResearchConfig.from_env()
        
        assert hasattr(config, "enabled")
        assert hasattr(config, "name_only_deep_research_enabled")
        assert not hasattr(config, "global_disable")
        assert not hasattr(config, "phase_8_claims_disabled")
        assert not hasattr(config, "phase_11_human_adjudication_disabled")
        assert not hasattr(config, "phase_12_runtime_publication_disabled")
    
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
# Integration Tests
# =============================================================================

@pytest.mark.asyncio
async def test_full_enrichment_pipeline():
    """Test the full extraction → verification → persistence pipeline."""
    
    # Mock LLM for extraction
    mock_extract_llm = AsyncMock(return_value=({
        "claims": [
            {
                "claim_text": "I prefer remote work",
                "claim_type": "preference",
                "quote": "I prefer working remotely",
                "confidence": 0.9,
            },
            {
                "claim_text": "Testing is important",
                "claim_type": "belief",
                "quote": "I believe testing is crucial",
                "confidence": 0.85,
            }
        ]
    }, None))
    
    # Setup
    sources = [
        {
            "id": "source-1",
            "content": "I prefer working remotely because it gives me flexibility. Testing is crucial for quality.",
            "url": "https://example.com",
            "title": "My Blog",
        },
    ]
    
    # Extraction
    extraction_result = await extract_claims_from_research_sources(
        sources=sources,
        twin_id="twin-123",
        research_run_id="run-456",
        llm_invoke_func=mock_extract_llm,
    )
    
    assert extraction_result["extracted_count"] == 2
    
    # Verification
    claims = extraction_result["claims"]
    verification_result = await verify_research_claims(
        claims=claims,
        sources=sources,
        similarity_threshold=0.5,
    )
    
    assert verification_result["verified_count"] == 2
    
    # Check statuses
    by_status = verification_result["by_status"]
    assert VerificationStatus.SUPPORTED in by_status


# =============================================================================
# Idempotency Tests
# =============================================================================

class TestIdempotency:
    """Test idempotent behavior."""
    
    @pytest.mark.asyncio
    async def test_extract_idempotent(self):
        """Test that extraction is idempotent (same input → same output)."""
        mock_llm = AsyncMock(return_value=({
            "claims": [{"claim_text": "Test", "claim_type": "belief", "quote": "I test", "confidence": 0.9}]
        }, None))
        
        extractor = ResearchClaimExtractor(llm_invoke_func=mock_llm)
        
        source = {"content": "Content " * 20, "id": "source-1"}
        
        claims1 = await extractor.extract_from_sources([source], "twin-123")
        claims2 = await extractor.extract_from_sources([source], "twin-123")
        
        assert len(claims1) == len(claims2)
        assert claims1[0].claim_text == claims2[0].claim_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
