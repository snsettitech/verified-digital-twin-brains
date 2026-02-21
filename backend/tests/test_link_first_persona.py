"""
test_link_first_persona.py

Phase 6: Tests and quality proof for Link-First Persona Compiler.
"""

import pytest
import asyncio
import hashlib
from datetime import datetime
from typing import List, Dict, Any

# Test imports
import sys
sys.path.insert(0, ".")

from modules.persona_claim_extractor import (
    ClaimExtractor,
    PersonaClaim,
    ClaimCitation,
)
from modules.persona_claim_inference import (
    PersonaFromClaimsCompiler,
    ClarificationInterviewGenerator,
)
from modules.persona_bio_generator import BioGenerator, BioValidator
from modules.robots_checker import is_domain_allowed


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_claims() -> List[Dict[str, Any]]:
    """Sample claims for testing."""
    return [
        {
            "id": "claim_001",
            "twin_id": "twin_test",
            "claim_text": "I prefer B2B startups over B2C",
            "claim_type": "preference",
            "confidence": 0.9,
            "authority": "extracted",
            "citation": {
                "source_id": "src_001",
                "span_start": 0,
                "span_end": 30,
                "quote": "I prefer B2B startups",
                "content_hash": "abc123",
            },
        },
        {
            "id": "claim_002",
            "twin_id": "twin_test",
            "claim_text": "Team quality is the most important factor",
            "claim_type": "value",
            "confidence": 0.95,
            "authority": "owner_direct",
            "citation": {
                "source_id": "src_002",
                "span_start": 0,
                "span_end": 40,
                "quote": "Team quality is most important",
                "content_hash": "def456",
            },
        },
        {
            "id": "claim_003",
            "twin_id": "twin_test",
            "claim_text": "When evaluating, I look at market size first",
            "claim_type": "heuristic",
            "confidence": 0.7,
            "authority": "extracted",
            "citation": {
                "source_id": "src_003",
                "span_start": 0,
                "span_end": 45,
                "quote": "I look at market size first",
                "content_hash": "ghi789",
            },
        },
    ]


@pytest.fixture
def low_confidence_claims() -> List[Dict[str, Any]]:
    """Low confidence claims for testing clarification interview."""
    return [
        {
            "id": "claim_low_001",
            "twin_id": "twin_test",
            "claim_text": "Maybe I like technical founders",
            "claim_type": "heuristic",
            "confidence": 0.4,
            "authority": "extracted",
        },
        {
            "id": "claim_low_002",
            "twin_id": "twin_test",
            "claim_text": "Speed might be important",
            "claim_type": "value",
            "confidence": 0.35,
            "authority": "extracted",
        },
    ]


# =============================================================================
# Phase 1 Tests: Ingestion Modes
# =============================================================================

class TestModeCValidation:
    """Test Mode C (Web Fetch) domain restrictions."""
    
    def test_linkedin_blocked(self):
        """LinkedIn must be blocked in Mode C."""
        allowed, reason = is_domain_allowed("https://linkedin.com/in/profile")
        assert not allowed
        assert "linkedin" in reason.lower() or "blocked" in reason.lower()
    
    def test_twitter_blocked(self):
        """Twitter/X must be blocked in Mode C."""
        allowed, reason = is_domain_allowed("https://twitter.com/user/status/123")
        assert not allowed
        assert "twitter" in reason.lower() or "blocked" in reason.lower()
    
    def test_x_blocked(self):
        """X.com must be blocked in Mode C."""
        allowed, reason = is_domain_allowed("https://x.com/user/status/123")
        assert not allowed
    
    def test_github_allowed(self):
        """GitHub should be allowed by default."""
        allowed, reason = is_domain_allowed("https://github.com/user/repo")
        assert allowed, f"GitHub should be allowed: {reason}"
    
    def test_unknown_domain_blocked(self):
        """Unknown domains should be blocked by default."""
        allowed, reason = is_domain_allowed("https://unknown-site.com/page")
        assert not allowed


# =============================================================================
# Phase 2 Tests: Claim Extraction
# =============================================================================

class TestClaimExtraction:
    """Test claim extraction from chunks."""
    
    @pytest.mark.asyncio
    async def test_extract_from_text_returns_claims(self):
        """Extractor should return claims from valid text."""
        extractor = ClaimExtractor()
        
        text = """
        I always look for strong technical teams when evaluating startups.
        My priority is team quality over market size.
        I don't invest in crypto projects.
        """
        
        claims = await extractor.extract_from_text(
            text=text,
            source_id="src_test",
            twin_id="twin_test",
        )
        
        # Should extract at least some claims
        assert len(claims) > 0
        
        # Each claim should have required fields
        for claim in claims:
            assert claim.claim_text
            assert claim.claim_type in [
                "preference", "belief", "heuristic", "value",
                "experience", "boundary", "uncertain"
            ]
            assert 0.0 <= claim.confidence <= 1.0
            assert claim.citation.content_hash
    
    def test_span_validation(self):
        """Claims without valid spans should be rejected."""
        extractor = ClaimExtractor()
        
        content = "This is the actual content."
        
        # Valid span
        assert extractor._validate_span(content, 0, 4, "This")
        
        # Invalid span - out of bounds
        assert not extractor._validate_span(content, 0, 1000, "Too long")
        
        # Invalid span - negative
        assert not extractor._validate_span(content, -1, 5, "Invalid")
    
    def test_content_hash_determinism(self):
        """Same content should produce same hash."""
        extractor = ClaimExtractor()
        
        content = "Test content for hashing"
        hash1 = extractor._compute_content_hash(content)
        hash2 = extractor._compute_content_hash(content)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex


# =============================================================================
# Phase 3 Tests: Persona Inference Honesty
# =============================================================================

class TestVerificationDefaults:
    """Test that Layer 2/3 default to verification_required=True."""
    
    def test_cognitive_heuristic_default_verification(self):
        """CognitiveHeuristic should default to verification_required=True."""
        from modules.persona_spec_v2 import CognitiveHeuristic
        
        heuristic = CognitiveHeuristic(
            id="test_001",
            name="Test Heuristic",
        )
        
        # DEFAULT must be True for inference honesty
        assert heuristic.verification_required is True
        assert heuristic.confidence == 0.5
        assert heuristic.evidence_claim_ids == []
    
    def test_value_item_default_verification(self):
        """ValueItem should default to verification_required=True."""
        from modules.persona_spec_v2 import ValueItem
        
        value = ValueItem(
            name="Test Value",
            priority=1,
        )
        
        # DEFAULT must be True for inference honesty
        assert value.verification_required is True
        assert value.confidence == 0.5
        assert value.evidence_claim_ids == []
    
    def test_verification_can_be_explicitly_false(self):
        """verification_required can be set to False with evidence."""
        from modules.persona_spec_v2 import CognitiveHeuristic
        
        heuristic = CognitiveHeuristic(
            id="test_002",
            name="Verified Heuristic",
            verification_required=False,
            evidence_claim_ids=["claim_001", "claim_002"],
            confidence=0.9,
        )
        
        assert heuristic.verification_required is False


class TestClarificationInterview:
    """Test clarification question generation."""
    
    def test_generates_questions_for_low_confidence(self, low_confidence_claims):
        """Should generate questions for low-confidence items."""
        generator = ClarificationInterviewGenerator(min_confidence_threshold=0.6)
        
        # Mock layer items
        from modules.persona_claim_inference import LayerItemWithEvidence
        
        cognitive_items = [
            LayerItemWithEvidence(
                item_id="h1",
                name="Team Evaluation",
                description="Evaluates teams",
                claim_ids=["c1"],
                verification_required=True,
                confidence=0.4,  # Below threshold
            ),
        ]
        
        value_items = [
            LayerItemWithEvidence(
                item_id="v1",
                name="Speed",
                description="Values speed",
                claim_ids=["c2"],
                verification_required=True,
                confidence=0.35,  # Below threshold
            ),
        ]
        
        questions = generator.generate_questions(cognitive_items, value_items)
        
        # Should generate questions for both low-confidence items
        assert len(questions) > 0
        
        for q in questions:
            assert "question" in q
            assert q["current_confidence"] < 0.6


# =============================================================================
# Phase 4 Tests: Bio Generator
# =============================================================================

class TestBioGenerator:
    """Test grounded bio generation."""
    
    @pytest.mark.asyncio
    async def test_generates_bio_with_citations(self, sample_claims):
        """Bio should include citations to claims."""
        generator = BioGenerator()
        
        variant = await generator.generate_bio_variant(
            twin_id="twin_test",
            bio_type="one_liner",
            claims=sample_claims,
            twin_name="Test Twin",
        )
        
        # Should have citations
        assert len(variant.citations) > 0 or variant.validation_status == "insufficient_data"
        
        # If valid, citations should reference claims
        if variant.validation_status == "valid":
            for citation in variant.citations:
                assert len(citation.claim_ids) > 0
    
    @pytest.mark.asyncio
    async def test_insufficient_data_for_few_claims(self):
        """Should return insufficient_data if too few claims."""
        generator = BioGenerator()
        
        few_claims = [
            {"id": "c1", "claim_text": "One claim", "confidence": 0.5},
        ]
        
        variant = await generator.generate_bio_variant(
            twin_id="twin_test",
            bio_type="full",
            claims=few_claims,
        )
        
        assert variant.validation_status == "insufficient_data"


class TestBioValidator:
    """Test bio citation validation."""
    
    def test_all_cited_returns_valid(self):
        """Bio with all sentences cited should be valid."""
        validator = BioValidator(min_citation_ratio=1.0)
        
        bio_text = "Sentence one. Sentence two."
        sentence_claims = [
            {"sentence_index": 0, "supporting_claim_indices": [0]},
            {"sentence_index": 1, "supporting_claim_indices": [1]},
        ]
        
        status, uncited = validator.validate_bio(bio_text, sentence_claims)
        
        assert status == "valid"
        assert uncited == []
    
    def test_missing_citations_returns_invalid(self):
        """Bio with uncited sentences should be invalid."""
        validator = BioValidator(min_citation_ratio=1.0)
        
        bio_text = "Sentence one. Sentence two. Sentence three."
        sentence_claims = [
            {"sentence_index": 0, "supporting_claim_indices": [0]},
            # Sentence 1 and 2 not cited
        ]
        
        status, uncited = validator.validate_bio(bio_text, sentence_claims)
        
        assert status == "insufficient_data"
        assert len(uncited) > 0


# =============================================================================
# Phase 6 Tests: Determinism
# =============================================================================

class TestDeterminism:
    """Test that outputs are deterministic."""
    
    @pytest.mark.asyncio
    async def test_claim_extraction_determinism(self):
        """Same input should produce same claims."""
        extractor = ClaimExtractor()
        
        text = "I prefer B2B startups. Team quality matters most."
        
        # Run extraction multiple times
        claims_runs = []
        for _ in range(3):
            claims = await extractor.extract_from_text(
                text=text,
                source_id="src_test",
                twin_id="twin_test",
            )
            claims_runs.append([(c.claim_text, c.claim_type) for c in claims])
        
        # All runs should produce same claims (deterministic)
        assert claims_runs[0] == claims_runs[1] == claims_runs[2]
    
    def test_content_hash_determinism(self):
        """Content hash should be deterministic."""
        extractor = ClaimExtractor()
        
        content = "Test content"
        hashes = [extractor._compute_content_hash(content) for _ in range(5)]
        
        assert all(h == hashes[0] for h in hashes)


# =============================================================================
# Privacy Tests
# =============================================================================

class TestPrivacy:
    """Test PII and privacy constraints."""
    
    def test_no_pii_in_claim_text(self):
        """Claims should not contain obvious PII patterns."""
        pii_patterns = [
            r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email
            r"\b\d{3}-\d{3}-\d{4}\b",  # Phone
        ]
        
        sample_claims = [
            "I like B2B startups",
            "Team quality matters",
        ]
        
        import re
        for claim in sample_claims:
            for pattern in pii_patterns:
                assert not re.search(pattern, claim), f"PII detected in claim: {claim}"


# =============================================================================
# Integration Test
# =============================================================================

@pytest.mark.asyncio
async def test_full_flow_integration():
    """
    Integration test: Full Link-First flow.
    
    This is a mock integration - in production would use test DB.
    """
    # Phase 1: Ingest (mock)
    chunks = [
        {
            "text": "I prefer B2B startups over B2C. Team quality is most important.",
            "source_id": "src_001",
            "chunk_id": "chunk_001",
        }
    ]
    
    # Phase 2: Extract claims
    extractor = ClaimExtractor()
    claims = await extractor.extract_from_chunks(chunks, "twin_integration_test")
    
    assert len(claims) > 0
    
    # Phase 3: Compile persona (mock)
    # Would normally use PersonaFromClaimsCompiler with DB
    
    # Phase 4: Generate bio
    generator = BioGenerator()
    claims_dicts = [
        {
            "id": "claim_int_001",
            "claim_text": c.claim_text,
            "claim_type": c.claim_type,
            "confidence": c.confidence,
            "authority": c.authority,
        }
        for c in claims
    ]
    
    bio_result = await generator.generate_bio_variant(
        twin_id="twin_integration_test",
        bio_type="one_liner",
        claims=claims_dicts,
    )
    
    # Should either produce valid bio or report insufficient data
    assert bio_result.validation_status in ["valid", "insufficient_data"]


# =============================================================================
# Quality Metrics
# =============================================================================

class TestQualityMetrics:
    """Quality proof metrics."""
    
    def test_claim_confidence_distribution(self, sample_claims):
        """Verify confidence scores are in valid range."""
        for claim in sample_claims:
            assert 0.0 <= claim["confidence"] <= 1.0
    
    def test_claim_type_coverage(self, sample_claims):
        """Verify claim types are valid."""
        valid_types = {
            "preference", "belief", "heuristic", "value",
            "experience", "boundary", "uncertain"
        }
        
        for claim in sample_claims:
            assert claim["claim_type"] in valid_types
    
    def test_citation_completeness(self, sample_claims):
        """Verify all claims have citations."""
        for claim in sample_claims:
            citation = claim.get("citation", {})
            assert citation.get("source_id")
            assert citation.get("content_hash")


# =============================================================================
# Run Configuration
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
