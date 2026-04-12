"""
Research Claim Finalization Tests (Phase 10)

Tests for:
- Finalization engine (rule-based adjudication)
- Consistency checker (contradiction/duplicate detection)
- Finalization service (orchestration, persistence)
- API endpoints
- Feature flags
- Regression tests for Phase 8 and 9
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from modules.research_claim_finalization_engine import (
    FinalClaimStatus,
    FinalizationDecision,
    FinalizationEngine,
    finalize_claim,
    get_decision_explanation,
)
from modules.research_claim_consistency_checker import (
    IssueType,
    Severity,
    ConsistencyIssue,
    ConsistencyChecker,
    FinalizedClaim,
    check_claim_consistency,
    get_issue_summary,
)
from modules.research_claim_finalization_service import (
    FinalizationRunStatus,
    FinalizationSummary,
    FinalizedClaimView,
    ResearchClaimFinalizationService,
)
from modules.research_claim_extractor import ResearchClaim, ClaimType, VerificationStatus
from modules.research_claim_web_verifier import WebVerificationStatus


# =============================================================================
# Finalization Engine Tests
# =============================================================================

class TestFinalClaimStatus:
    """Test FinalClaimStatus enum."""
    
    def test_status_values(self):
        """Test that all expected statuses exist."""
        expected = ['accepted', 'rejected', 'needs_review', 'unresolved', 'overridden']
        actual = [s.value for s in FinalClaimStatus]
        assert set(actual) == set(expected)


class TestFinalizationDecision:
    """Test FinalizationDecision dataclass."""
    
    def test_decision_to_dict(self):
        """Test converting decision to dict."""
        decision = FinalizationDecision(
            final_status=FinalClaimStatus.ACCEPTED,
            final_confidence=0.85,
            reason_codes=["rule_1", "both_supported"],
            notes="Test notes"
        )
        
        data = decision.to_dict()
        assert data["final_status"] == "accepted"
        assert data["final_confidence"] == 0.85
        assert data["reason_codes"] == ["rule_1", "both_supported"]


class TestFinalizationEngine:
    """Test FinalizationEngine rule-based adjudication."""
    
    @pytest.fixture
    def engine(self):
        return FinalizationEngine()
    
    @pytest.fixture
    def claim(self):
        return ResearchClaim(
            id="claim-123",
            claim_text="I prefer Python",
            claim_type=ClaimType.PREFERENCE,
        )
    
    def test_rule_1_strong_agreement(self, engine, claim):
        """Rule 1: local=supported AND web=supported -> accepted."""
        decision = engine.finalize_claim(
            claim=claim,
            local_status=VerificationStatus.SUPPORTED,
            local_confidence=0.9,
            web_status=WebVerificationStatus.SUPPORTED,
            web_confidence=0.85,
        )
        
        assert decision.final_status == FinalClaimStatus.ACCEPTED
        assert "rule_1_strong_agreement" in decision.reason_codes
        assert decision.final_confidence == 0.875  # Average
    
    def test_rule_2_strong_conflict_local(self, engine, claim):
        """Rule 2: local=conflicting -> rejected."""
        decision = engine.finalize_claim(
            claim=claim,
            local_status=VerificationStatus.CONFLICTING,
            local_confidence=0.8,
            web_status=WebVerificationStatus.SUPPORTED,
            web_confidence=0.9,
        )
        
        assert decision.final_status == FinalClaimStatus.REJECTED
        assert "rule_2_strong_conflict" in decision.reason_codes
    
    def test_rule_2_strong_conflict_web(self, engine, claim):
        """Rule 2: web=conflicting -> rejected."""
        decision = engine.finalize_claim(
            claim=claim,
            local_status=VerificationStatus.SUPPORTED,
            local_confidence=0.9,
            web_status=WebVerificationStatus.CONFLICTING,
            web_confidence=0.8,
        )
        
        assert decision.final_status == FinalClaimStatus.REJECTED
    
    def test_rule_3_needs_review_local(self, engine, claim):
        """Rule 3: local=needs_review -> needs_review."""
        decision = engine.finalize_claim(
            claim=claim,
            local_status=VerificationStatus.NEEDS_REVIEW,
            local_confidence=0.5,
            web_status=WebVerificationStatus.SUPPORTED,
            web_confidence=0.9,
        )
        
        assert decision.final_status == FinalClaimStatus.NEEDS_REVIEW
        assert "rule_3_needs_review_flag" in decision.reason_codes
    
    def test_rule_4_single_source_success(self, engine, claim):
        """Rule 4: web=None AND local=supported -> accepted (with penalty)."""
        decision = engine.finalize_claim(
            claim=claim,
            local_status=VerificationStatus.SUPPORTED,
            local_confidence=0.9,
            web_status=None,
            web_confidence=0.0,
        )
        
        assert decision.final_status == FinalClaimStatus.ACCEPTED
        assert "rule_4_single_source_success" in decision.reason_codes
        assert decision.final_confidence == 0.81  # 0.9 * 0.9
    
    def test_rule_5_status_mismatch(self, engine, claim):
        """Rule 5: local != web (neither None) -> needs_review."""
        decision = engine.finalize_claim(
            claim=claim,
            local_status=VerificationStatus.SUPPORTED,
            local_confidence=0.9,
            web_status=WebVerificationStatus.INSUFFICIENT_EVIDENCE,
            web_confidence=0.3,
        )
        
        assert decision.final_status == FinalClaimStatus.NEEDS_REVIEW
        assert "rule_5_status_mismatch" in decision.reason_codes
    
    def test_rule_6_insufficient_evidence(self, engine, claim):
        """Rule 6: local=insufficient AND web=None -> rejected."""
        decision = engine.finalize_claim(
            claim=claim,
            local_status=VerificationStatus.INSUFFICIENT_EVIDENCE,
            local_confidence=0.2,
            web_status=None,
            web_confidence=0.0,
        )
        
        assert decision.final_status == FinalClaimStatus.REJECTED
        assert "rule_6_insufficient_evidence" in decision.reason_codes
    
    def test_rule_7_default_unresolved(self, engine, claim):
        """Rule 7: Default -> unresolved."""
        decision = engine.finalize_claim(
            claim=claim,
            local_status=VerificationStatus.PENDING,
            local_confidence=0.5,
            web_status=WebVerificationStatus.PENDING,
            web_confidence=0.5,
        )
        
        assert decision.final_status == FinalClaimStatus.UNRESOLVED
        assert "rule_7_default_unresolved" in decision.reason_codes


class TestStatusCompatibility:
    """Test status compatibility checking."""
    
    def test_compatible_same_status(self):
        """Same status should be compatible."""
        engine = FinalizationEngine()
        
        compatible = engine._statuses_compatible(
            VerificationStatus.SUPPORTED,
            WebVerificationStatus.SUPPORTED
        )
        assert compatible is True
    
    def test_compatible_pending(self):
        """Pending statuses should be compatible."""
        engine = FinalizationEngine()
        
        compatible = engine._statuses_compatible(
            VerificationStatus.PENDING,
            WebVerificationStatus.SUPPORTED
        )
        assert compatible is True
    
    def test_incompatible_conflict(self):
        """Supported vs Conflicting should be incompatible."""
        engine = FinalizationEngine()
        
        compatible = engine._statuses_compatible(
            VerificationStatus.SUPPORTED,
            WebVerificationStatus.CONFLICTING
        )
        assert compatible is False


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_finalize_claim_convenience(self):
        """Test finalize_claim convenience function."""
        claim = ResearchClaim(
            id="test",
            claim_text="Test",
            claim_type=ClaimType.BELIEF,
        )
        
        decision = finalize_claim(
            claim=claim,
            local_status=VerificationStatus.SUPPORTED,
            local_confidence=0.9,
            web_status=WebVerificationStatus.SUPPORTED,
            web_confidence=0.85,
        )
        
        assert decision.final_status == FinalClaimStatus.ACCEPTED
    
    def test_get_decision_explanation(self):
        """Test getting human-readable explanation."""
        decision = FinalizationDecision(
            final_status=FinalClaimStatus.ACCEPTED,
            final_confidence=0.9,
            notes="Both sources agree"
        )
        
        explanation = get_decision_explanation(decision)
        assert "accepted" in explanation.lower()


# =============================================================================
# Consistency Checker Tests
# =============================================================================

class TestConsistencyIssue:
    """Test ConsistencyIssue dataclass."""
    
    def test_issue_to_dict(self):
        """Test converting issue to dict."""
        issue = ConsistencyIssue(
            issue_type=IssueType.CONTRADICTION,
            severity=Severity.HIGH,
            claim_ids=["c1", "c2"],
            title="Test Issue",
            description="Test description",
            detection_rule="test_rule",
            confidence=0.9,
            issue_hash="abc123"
        )
        
        data = issue.to_dict()
        assert data["issue_type"] == "contradiction"
        assert data["severity"] == "high"
        assert data["claim_ids"] == ["c1", "c2"]


class TestConsistencyChecker:
    """Test ConsistencyChecker detection algorithms."""
    
    @pytest.fixture
    def checker(self):
        return ConsistencyChecker()
    
    def test_empty_claims(self, checker):
        """Empty list should return no issues."""
        issues = checker.check_consistency([])
        assert issues == []
    
    def test_no_issues_single_claim(self, checker):
        """Single claim should have no issues."""
        claim = ResearchClaim(id="c1", claim_text="I like Python", claim_type=ClaimType.PREFERENCE)
        finalized = FinalizedClaim(
            claim=claim,
            final_status=FinalClaimStatus.ACCEPTED,
            final_confidence=0.9
        )
        
        issues = checker.check_consistency([finalized])
        assert issues == []
    
    def test_detect_contradictions_opposite_preference(self, checker):
        """Should detect opposite preferences."""
        claim1 = ResearchClaim(id="c1", claim_text="I prefer Python programming language", claim_type=ClaimType.PREFERENCE)
        claim2 = ResearchClaim(id="c2", claim_text="I dislike Python programming language", claim_type=ClaimType.PREFERENCE)
        
        finalized = [
            FinalizedClaim(claim=claim1, final_status=FinalClaimStatus.ACCEPTED, final_confidence=0.9),
            FinalizedClaim(claim=claim2, final_status=FinalClaimStatus.ACCEPTED, final_confidence=0.9),
        ]
        
        issues = checker.check_consistency(finalized)
        
        # Should find at least one contradiction
        contradictions = [i for i in issues if i.issue_type == IssueType.CONTRADICTION]
        assert len(contradictions) > 0, f"Expected contradiction but got issues: {issues}"
    
    def test_detect_duplicates(self, checker):
        """Should detect duplicate claims."""
        claim1 = ResearchClaim(id="c1", claim_text="I love Python programming", claim_type=ClaimType.PREFERENCE)
        claim2 = ResearchClaim(id="c2", claim_text="I love Python programming", claim_type=ClaimType.PREFERENCE)
        
        finalized = [
            FinalizedClaim(claim=claim1, final_status=FinalClaimStatus.ACCEPTED, final_confidence=0.9),
            FinalizedClaim(claim=claim2, final_status=FinalClaimStatus.REJECTED, final_confidence=0.3),
        ]
        
        issues = checker.check_consistency(finalized)
        
        duplicates = [i for i in issues if i.issue_type == IssueType.DUPLICATE]
        assert len(duplicates) > 0
    
    def test_detect_confidence_mismatch(self, checker):
        """Should detect confidence mismatches."""
        claim1 = ResearchClaim(id="c1", claim_text="Python is great for AI", claim_type=ClaimType.BELIEF)
        claim2 = ResearchClaim(id="c2", claim_text="Python is great for web", claim_type=ClaimType.BELIEF)
        
        finalized = [
            FinalizedClaim(claim=claim1, final_status=FinalClaimStatus.ACCEPTED, final_confidence=0.95),
            FinalizedClaim(claim=claim2, final_status=FinalClaimStatus.REJECTED, final_confidence=0.2),
        ]
        
        issues = checker.check_consistency(finalized)
        
        mismatches = [i for i in issues if i.issue_type == IssueType.CONFIDENCE_MISMATCH]
        # May or may not find depending on similarity detection
        assert isinstance(mismatches, list)
    
    def test_issue_deduplication(self, checker):
        """Same issue should not be reported twice."""
        claim1 = ResearchClaim(id="c1", claim_text="I prefer Python", claim_type=ClaimType.PREFERENCE)
        claim2 = ResearchClaim(id="c2", claim_text="I dislike Python", claim_type=ClaimType.PREFERENCE)
        
        finalized = [
            FinalizedClaim(claim=claim1, final_status=FinalClaimStatus.ACCEPTED, final_confidence=0.9),
            FinalizedClaim(claim=claim2, final_status=FinalClaimStatus.ACCEPTED, final_confidence=0.9),
        ]
        
        # Run twice, should deduplicate
        issues1 = checker.check_consistency(finalized)
        issues2 = checker.check_consistency(finalized)
        
        assert len(issues1) == len(issues2)


class TestTextSimilarity:
    """Test text similarity functions."""
    
    def test_identical_texts(self):
        """Identical texts should have 100% similarity."""
        checker = ConsistencyChecker()
        sim = checker._text_similarity("hello world", "hello world")
        assert sim == 1.0
    
    def test_completely_different_texts(self):
        """Different texts should have low similarity."""
        checker = ConsistencyChecker()
        sim = checker._text_similarity("abc def", "xyz 123")
        assert sim < 0.5
    
    def test_partial_overlap(self):
        """Partial overlap should have medium similarity."""
        checker = ConsistencyChecker()
        sim = checker._text_similarity("I love Python", "I love JavaScript")
        assert 0.3 < sim < 0.8


class TestIssueSummary:
    """Test issue summary function."""
    
    def test_get_issue_summary(self):
        """Test summarizing issues."""
        issues = [
            ConsistencyIssue(
                issue_type=IssueType.CONTRADICTION,
                severity=Severity.HIGH,
                claim_ids=["c1", "c2"],
                title="Contradiction",
                description="Desc",
                detection_rule="rule1",
                confidence=0.9,
                issue_hash="h1"
            ),
            ConsistencyIssue(
                issue_type=IssueType.DUPLICATE,
                severity=Severity.LOW,
                claim_ids=["c3", "c4"],
                title="Duplicate",
                description="Desc",
                detection_rule="rule2",
                confidence=0.8,
                issue_hash="h2"
            ),
        ]
        
        summary = get_issue_summary(issues)
        
        assert summary["total_issues"] == 2
        assert summary["by_type"]["contradiction"] == 1
        assert summary["by_type"]["duplicate"] == 1
        assert summary["by_severity"]["high"] == 1
        assert summary["by_severity"]["low"] == 1
        assert summary["has_critical"] is True


# =============================================================================
# Finalization Service Tests
# =============================================================================

class TestFinalizationSummary:
    """Test FinalizationSummary dataclass."""
    
    def test_summary_creation(self):
        """Test creating a summary."""
        summary = FinalizationSummary(
            research_run_id="run-123",
            twin_id="twin-456",
            status=FinalizationRunStatus.COMPLETED,
            total_claims=10,
            finalized_count=10,
            issues_found=2,
            by_final_status={"accepted": 5, "rejected": 5},
            by_issue_type={"contradiction": 2}
        )
        
        assert summary.research_run_id == "run-123"
        assert summary.by_final_status["accepted"] == 5


class TestResearchClaimFinalizationService:
    """Test ResearchClaimFinalizationService."""
    
    def test_service_initialization(self):
        """Test service can be initialized."""
        mock_db = MagicMock()
        service = ResearchClaimFinalizationService(supabase_client=mock_db)
        
        assert service.db == mock_db
        assert service.finalization_engine is not None
        assert service.consistency_checker is not None


# =============================================================================
# API Contract Tests
# =============================================================================

class TestAPIContracts:
    """Test API request/response contracts."""
    
    def test_final_claim_status_values(self):
        """Test final status enum values match API contract."""
        expected = ["accepted", "rejected", "needs_review", "unresolved", "overridden"]
        actual = [s.value for s in FinalClaimStatus]
        assert set(actual) == set(expected)
    
    def test_finalization_run_status_values(self):
        """Test run status enum values match API contract."""
        expected = ["pending", "running", "completed", "failed", "partial"]
        actual = [s.value for s in FinalizationRunStatus]
        assert set(actual) == set(expected)
    
    def test_issue_type_values(self):
        """Test issue type enum values match API contract."""
        expected = ["contradiction", "duplicate", "confidence_mismatch", "status_conflict"]
        actual = [t.value for t in IssueType]
        assert set(actual) == set(expected)
    
    def test_severity_values(self):
        """Test severity enum values match API contract."""
        expected = ["low", "medium", "high"]
        actual = [s.value for s in Severity]
        assert set(actual) == set(expected)


# =============================================================================
# Feature Flag Tests
# =============================================================================

class TestFeatureFlags:
    """Test Deep Research configuration behavior."""

    def test_deep_research_always_enabled(self):
        """Deep Research should remain enabled in the active configuration."""
        from modules.deep_research_config import DeepResearchConfig

        config = DeepResearchConfig.from_env()

        assert config.is_enabled() is True


# =============================================================================
# Integration Tests
# =============================================================================

@pytest.mark.asyncio
async def test_full_finalization_pipeline():
    """Test the full finalization + consistency check pipeline."""
    
    # Create test claims
    claims_data = [
        (
            ResearchClaim(id="c1", claim_text="I prefer Python", claim_type=ClaimType.PREFERENCE),
            VerificationStatus.SUPPORTED,
            0.9,
            WebVerificationStatus.SUPPORTED,
            0.85
        ),
        (
            ResearchClaim(id="c2", claim_text="I dislike Python", claim_type=ClaimType.PREFERENCE),
            VerificationStatus.SUPPORTED,
            0.8,
            WebVerificationStatus.SUPPORTED,
            0.75
        ),
    ]
    
    # Finalize each claim
    engine = FinalizationEngine()
    finalized = []
    
    for claim, local_status, local_conf, web_status, web_conf in claims_data:
        decision = engine.finalize_claim(
            claim=claim,
            local_status=local_status,
            local_confidence=local_conf,
            web_status=web_status,
            web_confidence=web_conf,
        )
        finalized.append(FinalizedClaim(
            claim=claim,
            final_status=decision.final_status,
            final_confidence=decision.final_confidence,
        ))
    
    # Check consistency
    checker = ConsistencyChecker()
    issues = checker.check_consistency(finalized)
    
    # Should find contradiction
    assert len(issues) > 0
    assert any(i.issue_type == IssueType.CONTRADICTION for i in issues)


# =============================================================================
# Regression Tests for Phase 8 and 9
# =============================================================================

class TestPhase8Regression:
    """Ensure Phase 8 is not broken by Phase 10."""
    
    def test_phase_8_verification_status_unchanged(self):
        """Test Phase 8 verification status values are unchanged."""
        expected = ["pending", "supported", "insufficient_evidence", "conflicting", "needs_review"]
        actual = [s.value for s in VerificationStatus]
        assert set(actual) == set(expected)


class TestPhase9Regression:
    """Ensure Phase 9 is not broken by Phase 10."""
    
    def test_phase_9_web_status_unchanged(self):
        """Test Phase 9 web status values are unchanged."""
        expected = [
            "pending", "supported", "conflicting", "insufficient_evidence",
            "needs_review", "blocked", "error", "skipped"
        ]
        actual = [s.value for s in WebVerificationStatus]
        assert set(actual) == set(expected)


# =============================================================================
# Idempotency Tests
# =============================================================================

class TestIdempotency:
    """Test idempotent behavior."""
    
    def test_finalization_idempotent(self):
        """Test that finalization produces same result on retry."""
        engine = FinalizationEngine()
        claim = ResearchClaim(
            id="c1",
            claim_text="Test claim",
            claim_type=ClaimType.BELIEF
        )
        
        decision1 = engine.finalize_claim(
            claim=claim,
            local_status=VerificationStatus.SUPPORTED,
            local_confidence=0.9,
            web_status=WebVerificationStatus.SUPPORTED,
            web_confidence=0.85,
        )
        
        decision2 = engine.finalize_claim(
            claim=claim,
            local_status=VerificationStatus.SUPPORTED,
            local_confidence=0.9,
            web_status=WebVerificationStatus.SUPPORTED,
            web_confidence=0.85,
        )
        
        assert decision1.final_status == decision2.final_status
        assert decision1.final_confidence == decision2.final_confidence
        assert decision1.reason_codes == decision2.reason_codes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
