"""
Tests for Identity Confidence Scorer Module (Phase 3.1)

Covers:
- Exact full-name matching
- Partial name matching
- Location matching
- URL slug matching
- Social handle extraction and matching
- False positive resistance
- Content quality handling
- Score thresholds and confidence levels
- Edge cases and empty inputs
"""

import pytest
from typing import Dict, Any

from modules.identity_confidence_scorer import (
    IdentityConfidenceScorer,
    IdentityScoreResult,
    ScoringWeights,
    ConfidenceLevel,
    score_identity_confidence,
)
from modules.firecrawl_client import ContentQuality


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def scorer() -> IdentityConfidenceScorer:
    """Default scorer instance."""
    return IdentityConfidenceScorer()


@pytest.fixture
def renee_identity() -> Dict[str, Any]:
    """Sample claimed identity for Renee Sferrazza."""
    return {
        "full_name": "Renee Sferrazza",
        "location": "Toronto, Ontario, Canada",
        "submitted_links": [
            "https://linkedin.com/in/renee-sferrazza",
            "https://youtube.com/@WineByRenee",
            "https://instagram.com/wine.by.renee"
        ]
    }


@pytest.fixture
def john_identity() -> Dict[str, Any]:
    """Sample claimed identity for John Smith."""
    return {
        "full_name": "John Smith",
        "location": "New York, NY",
        "submitted_links": [
            "https://linkedin.com/in/johnsmith",
            "https://twitter.com/@johnsmith"
        ]
    }


# ============================================================================
# Full Name Match Tests
# ============================================================================

class TestFullNameMatching:
    """Test exact and near-exact full name matching."""
    
    def test_exact_full_name_in_title(self, scorer, renee_identity):
        """Full name in title should give high score."""
        result = scorer.score_page(
            page_content="Some content about wine",
            page_metadata={
                "title": "About Renee Sferrazza | Wine Expert",
                "url": "https://example.com/about"
            },
            claimed_identity=renee_identity,
        )
        
        assert result.score >= 0.3  # Name in title (0.25) + profile indicators
        assert "name_in_title" in result.matched_signals
        assert result.confidence_level in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW)
    
    def test_exact_full_name_in_content(self, scorer, renee_identity):
        """Full name multiple times in content should score well."""
        content = """
        Renee Sferrazza is a wine expert based in Toronto.
        Renee Sferrazza has been working in the wine industry for over 10 years.
        Contact Renee Sferrazza for wine consulting.
        """
        
        result = scorer.score_page(
            page_content=content,
            page_metadata={"title": "Wine Expert", "url": "https://example.com"},
            claimed_identity=renee_identity,
        )
        
        assert result.score >= 0.2  # Name in content + location + indicators
        assert "name_in_content" in result.matched_signals
    
    def test_full_name_not_present(self, scorer, renee_identity):
        """Page without the claimed identity name should score low."""
        result = scorer.score_page(
            page_content="This page is about Jane Doe and her art portfolio.",
            page_metadata={"title": "Jane Doe Art", "url": "https://janedoe.com"},
            claimed_identity=renee_identity,
        )
        
        assert result.score < 0.5
        assert result.confidence_level == ConfidenceLevel.LOW
        assert result.is_auto_reject() is True


# ============================================================================
# Partial Name Match Tests
# ============================================================================

class TestPartialNameMatching:
    """Test partial/fuzzy name matching."""
    
    def test_last_name_only_in_title(self, scorer, renee_identity):
        """Last name only in title should give moderate score."""
        result = scorer.score_page(
            page_content="Content about wine",
            page_metadata={
                "title": "Sferrazza Wine Consulting",
                "url": "https://example.com"
            },
            claimed_identity=renee_identity,
        )
        
        assert result.score >= 0.15  # Last name in title is 0.6 * 0.25 = 0.15
        assert "name_in_title" in result.matched_signals
    
    def test_first_name_only_weak_signal(self, scorer, renee_identity):
        """First name only should give weak signal."""
        result = scorer.score_page(
            page_content="Renee is a common name. This Renee works in finance.",
            page_metadata={"title": "Team Page", "url": "https://example.com/team"},
            claimed_identity=renee_identity,
        )
        
        # Should have some signal but not high
        assert result.score < 0.6
        assert "name_in_content" in result.matched_signals
    
    def test_all_name_parts_in_content(self, scorer, john_identity):
        """Both first and last name in content (not adjacent) should score."""
        content = "John is a software engineer. Smith has worked at many companies."
        
        result = scorer.score_page(
            page_content=content,
            page_metadata={"title": "About", "url": "https://example.com"},
            claimed_identity=john_identity,
        )
        
        assert result.score > 0
        assert "name_in_content" in result.matched_signals


# ============================================================================
# Location Match Tests
# ============================================================================

class TestLocationMatching:
    """Test location matching signals."""
    
    def test_full_location_match(self, scorer, renee_identity):
        """Full location in content should score well."""
        content = "Renee Sferrazza is based in Toronto, Ontario, Canada."
        
        result = scorer.score_page(
            page_content=content,
            page_metadata={"title": "About", "url": "https://example.com"},
            claimed_identity=renee_identity,
        )
        
        assert "location_match" in result.matched_signals
        assert result.details["component_scores"]["location_match"] >= 0.8
    
    def test_partial_location_match(self, scorer, renee_identity):
        """Partial location (city only) should give moderate score."""
        content = "Renee works in Toronto."
        
        result = scorer.score_page(
            page_content=content,
            page_metadata={"title": "About", "url": "https://example.com"},
            claimed_identity=renee_identity,
        )
        
        # Should have some location signal
        loc_score = result.details["component_scores"]["location_match"]
        assert loc_score > 0
    
    def test_location_mismatch(self, scorer, renee_identity):
        """Different location should not add score."""
        content = "Based in London, United Kingdom"
        
        result = scorer.score_page(
            page_content=content,
            page_metadata={"title": "About", "url": "https://example.com"},
            claimed_identity=renee_identity,
        )
        
        # Location shouldn't match
        assert result.details["component_scores"]["location_match"] == 0.0


# ============================================================================
# URL Slug Match Tests
# ============================================================================

class TestUrlSlugMatching:
    """Test URL slug matching for identity."""
    
    def test_slug_matches_full_name(self, scorer, renee_identity):
        """URL slug matching full name should score high."""
        result = scorer.score_page(
            page_content="About page content",
            page_metadata={
                "title": "About",
                "url": "https://reneesferrazza.com/about-renee-sferrazza"
            },
            claimed_identity=renee_identity,
        )
        
        assert "url_slug_match" in result.matched_signals
        assert result.details["component_scores"]["url_slug_match"] >= 0.8
    
    def test_slug_matches_last_name(self, scorer, john_identity):
        """URL slug with last name should score moderately."""
        result = scorer.score_page(
            page_content="Portfolio content",
            page_metadata={
                "title": "Portfolio",
                "url": "https://johnsmith.com/portfolio"
            },
            claimed_identity=john_identity,
        )
        
        assert "url_slug_match" in result.matched_signals
        assert result.details["component_scores"]["url_slug_match"] >= 0.4
    
    def test_slug_no_match(self, scorer, renee_identity):
        """Unrelated URL slug should not score."""
        result = scorer.score_page(
            page_content="Content",
            page_metadata={
                "title": "Page",
                "url": "https://example.com/random-page-123"
            },
            claimed_identity=renee_identity,
        )
        
        assert result.details["component_scores"]["url_slug_match"] == 0.0


# ============================================================================
# Social Handle Tests
# ============================================================================

class TestSocialHandleMatching:
    """Test social handle extraction and matching."""
    
    def test_linkedin_handle_extraction(self, scorer):
        """Should extract LinkedIn handle from submitted links."""
        identity = {
            "full_name": "Test User",
            "submitted_links": ["https://linkedin.com/in/test-user-123"]
        }
        
        result = scorer.score_page(
            page_content="Connect with me on LinkedIn at linkedin.com/in/test-user-123",
            page_metadata={"title": "About", "url": "https://example.com"},
            claimed_identity=identity,
        )
        
        assert "social_handle_match" in result.matched_signals
    
    def test_youtube_handle_extraction(self, scorer, renee_identity):
        """Should extract YouTube handle and match in content."""
        result = scorer.score_page(
            page_content="Subscribe to my YouTube channel @WineByRenee for more content",
            page_metadata={"title": "About", "url": "https://example.com"},
            claimed_identity=renee_identity,
        )
        
        assert "social_handle_match" in result.matched_signals
    
    def test_instagram_handle_extraction(self, scorer, renee_identity):
        """Should extract Instagram handle."""
        result = scorer.score_page(
            page_content="Follow me on Instagram @wine.by.renee",
            page_metadata={"title": "About", "url": "https://example.com"},
            claimed_identity=renee_identity,
        )
        
        assert "social_handle_match" in result.matched_signals
    
    def test_no_handle_match(self, scorer, renee_identity):
        """No matching handles should not score."""
        result = scorer.score_page(
            page_content="Follow me @someoneelse on social media",
            page_metadata={"title": "About", "url": "https://example.com"},
            claimed_identity=renee_identity,
        )
        
        assert "social_handle_match" not in result.matched_signals
        assert result.details["component_scores"]["social_handle_match"] == 0.0


# ============================================================================
# Profile Indicator Tests
# ============================================================================

class TestProfileIndicators:
    """Test profile indicator keyword scoring."""
    
    def test_multiple_indicators(self, scorer, renee_identity):
        """Multiple profile indicators should score high."""
        content = """
        About Renee Sferrazza
        Bio: Wine expert and consultant
        Background: 10 years in the industry
        Contact: renee@example.com
        """
        
        result = scorer.score_page(
            page_content=content,
            page_metadata={"title": "About", "url": "https://example.com"},
            claimed_identity=renee_identity,
        )
        
        assert "profile_indicators" in result.matched_signals
        assert result.details["component_scores"]["profile_indicators"] >= 0.7
    
    def test_founder_indicator(self, scorer, renee_identity):
        """Founder indicator should contribute to score."""
        result = scorer.score_page(
            page_content="Renee Sferrazza is the founder of Wine by Renee.",
            page_metadata={"title": "Founder of Wine by Renee", "url": "https://example.com"},
            claimed_identity=renee_identity,
        )
        
        assert "profile_indicators" in result.matched_signals
    
    def test_no_indicators(self, scorer, renee_identity):
        """No profile indicators should not penalize."""
        result = scorer.score_page(
            page_content="This page discusses grapes and vineyards in detail.",
            page_metadata={"title": "Grape Discussion", "url": "https://example.com"},
            claimed_identity=renee_identity,
        )
        
        # Check that score is not artificially inflated by indicators
        # None of these words are profile indicators
        assert result.details["component_scores"]["profile_indicators"] == 0.0


# ============================================================================
# False Positive Resistance Tests
# ============================================================================

class TestFalsePositiveResistance:
    """Test resistance to false positives."""
    
    def test_different_person_same_first_name(self, scorer, renee_identity):
        """Page about different person with same first name should score low."""
        content = """
        Renee Williams is a software engineer based in San Francisco.
        Renee has worked at Google and Facebook.
        Contact Renee for consulting.
        """
        
        result = scorer.score_page(
            page_content=content,
            page_metadata={"title": "Renee Williams - Software Engineer", "url": "https://example.com"},
            claimed_identity=renee_identity,
        )
        
        # Should be low confidence due to different last name
        assert result.score < 0.6
        assert result.confidence_level in (ConfidenceLevel.LOW, ConfidenceLevel.MEDIUM)
    
    def test_common_name_no_other_signals(self, scorer):
        """Common name with no other identity signals should score low."""
        identity = {"full_name": "John Smith"}  # Very common name
        
        result = scorer.score_page(
            page_content="John Smith is mentioned in this article.",
            page_metadata={"title": "Article", "url": "https://example.com/article"},
            claimed_identity=identity,
        )
        
        # Just first name match shouldn't be enough for auto-confirm
        assert not result.is_auto_confirm()
    
    def test_organization_page_not_person(self, scorer, renee_identity):
        """Organization page without person mention should score low."""
        result = scorer.score_page(
            page_content="Wine by Renee is a company that sells wine. The company was founded in 2020.",
            page_metadata={
                "title": "Wine by Renee Company",
                "url": "https://winebyrenee.com/company"
            },
            claimed_identity=renee_identity,
        )
        
        # Company name match but no personal identity signals
        assert not result.is_auto_confirm()


# ============================================================================
# Content Quality Tests
# ============================================================================

class TestContentQualityHandling:
    """Test handling of Phase 3.0 content quality statuses."""
    
    def test_full_content_no_penalty(self, scorer, renee_identity):
        """Full content should have no quality penalty."""
        result = scorer.score_page(
            page_content="Renee Sferrazza is a wine expert.",
            page_metadata={"title": "About Renee Sferrazza", "url": "https://example.com"},
            claimed_identity=renee_identity,
            content_quality="full"
        )
        
        assert result.details["quality_penalty"] == 0.0
    
    def test_partial_content_reduces_confidence(self, scorer, renee_identity):
        """Partial content should reduce confidence slightly."""
        result = scorer.score_page(
            page_content="Renee Sferrazza - Wine Expert",
            page_metadata={"title": "Renee Sferrazza", "url": "https://example.com"},
            claimed_identity=renee_identity,
            content_quality="partial"
        )
        
        assert result.details["quality_penalty"] == 0.1
        assert result.details["content_quality"] == "partial"
    
    def test_blocked_content_major_penalty(self, scorer, renee_identity):
        """Blocked content should have major penalty."""
        result = scorer.score_page(
            page_content="",
            page_metadata={"title": "", "url": "https://linkedin.com/in/renee-sferrazza"},
            claimed_identity=renee_identity,
            content_quality="blocked"
        )
        
        assert result.details["quality_penalty"] == 0.3
        assert result.confidence_level == ConfidenceLevel.LOW
    
    def test_manual_needed_penalty(self, scorer, renee_identity):
        """Manual needed content should have moderate penalty."""
        result = scorer.score_page(
            page_content="Video description only",
            page_metadata={
                "title": "Renee Sferrazza Wine Video",
                "url": "https://youtube.com/watch?v=123"
            },
            claimed_identity=renee_identity,
            content_quality="manual_needed"
        )
        
        assert result.details["quality_penalty"] == 0.2


# ============================================================================
# Threshold and Confidence Level Tests
# ============================================================================

class TestThresholdsAndConfidenceLevels:
    """Test score thresholds and confidence level classification."""
    
    def test_high_confidence_threshold(self, scorer, renee_identity):
        """Score >= 0.8 should be high confidence."""
        # Strong signals: name in title, URL slug, content
        result = scorer.score_page(
            page_content="""
            Renee Sferrazza is a wine expert in Toronto, Ontario, Canada.
            Renee Sferrazza founded Wine by Renee.
            Contact Renee Sferrazza at renee@winebyrenee.com
            """,
            page_metadata={
                "title": "About Renee Sferrazza | Wine Expert",
                "url": "https://reneesferrazza.com/about-renee-sferrazza",
                "description": "Renee Sferrazza - Wine Expert in Toronto"
            },
            claimed_identity=renee_identity,
        )
        
        assert result.confidence_level == ConfidenceLevel.HIGH
        assert result.is_auto_confirm() is True
        assert result.is_auto_reject() is False
    
    def test_medium_confidence_range(self, scorer, renee_identity):
        """Score between 0.5 and 0.8 should be medium confidence."""
        # Moderate signals: name in content, partial indicators
        result = scorer.score_page(
            page_content="Renee Sferrazza is mentioned in this article about wine.",
            page_metadata={
                "title": "Wine Article",
                "url": "https://example.com/article"
            },
            claimed_identity=renee_identity,
        )
        
        # Should be in medium range or low, but definitely not auto-confirm
        assert not result.is_auto_confirm()
    
    def test_low_confidence_threshold(self, scorer, renee_identity):
        """Score < 0.5 should be low confidence."""
        result = scorer.score_page(
            page_content="This page is about wine in general.",
            page_metadata={"title": "Wine Article", "url": "https://example.com"},
            claimed_identity=renee_identity,
        )
        
        assert result.confidence_level == ConfidenceLevel.LOW
        assert result.is_auto_reject() is True
        assert result.is_auto_confirm() is False
    
    def test_pending_confirmation_range(self, scorer, renee_identity):
        """Medium scores should indicate pending confirmation."""
        result = scorer.score_page(
            page_content="Renee Sferrazza is a wine expert.",
            page_metadata={
                "title": "Article mentioning Renee",
                "url": "https://example.com/article"
            },
            claimed_identity=renee_identity,
        )
        
        if result.score >= 0.5 and result.score < 0.8:
            assert result.is_pending_confirmation() is True


# ============================================================================
# Edge Case Tests
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_content(self, scorer, renee_identity):
        """Empty content should handle gracefully."""
        result = scorer.score_page(
            page_content="",
            page_metadata={"title": "", "url": "https://example.com"},
            claimed_identity=renee_identity,
        )
        
        assert result.score == 0.0
        assert result.confidence_level == ConfidenceLevel.LOW
    
    def test_empty_identity(self, scorer):
        """Empty identity should handle gracefully."""
        result = scorer.score_page(
            page_content="Some content",
            page_metadata={"title": "Page", "url": "https://example.com"},
            claimed_identity={},
        )
        
        assert result.score == 0.0
    
    def test_no_submitted_links(self, scorer):
        """Identity without submitted links should work fine."""
        identity = {"full_name": "Jane Doe", "location": "Boston, MA"}
        
        result = scorer.score_page(
            page_content="Jane Doe is a developer in Boston.",
            page_metadata={"title": "About Jane Doe", "url": "https://janedoe.com"},
            claimed_identity=identity,
        )
        
        assert result.score > 0
        # Social handle should just be 0, not error
        assert result.details["component_scores"]["social_handle_match"] == 0.0
    
    def test_unicode_normalization(self, scorer):
        """Should handle unicode names with accents."""
        identity = {"full_name": "José García", "location": "Madrid, España"}
        
        result = scorer.score_page(
            page_content="Jose Garcia is a developer based in Madrid.",
            page_metadata={"title": "About Jose Garcia", "url": "https://example.com"},
            claimed_identity=identity,
        )
        
        # Should match despite accent differences
        assert result.score > 0
        assert "name_in_content" in result.matched_signals
    
    def test_case_insensitivity(self, scorer, renee_identity):
        """Matching should be case insensitive."""
        result = scorer.score_page(
            page_content="RENEE SFERRAZZA is a wine expert. renee sferrazza founded the company.",
            page_metadata={"title": "RENEE SFERRAZZA", "url": "https://example.com"},
            claimed_identity=renee_identity,
        )
        
        assert result.score >= 0.4  # Name in title + content + indicators


# ============================================================================
# Custom Weights Tests
# ============================================================================

class TestCustomWeights:
    """Test custom scoring weights."""
    
    def test_custom_weights_validation(self):
        """Weights that don't sum to 1.0 should raise error."""
        with pytest.raises(ValueError):
            ScoringWeights(
                name_in_title=0.5,
                name_in_content=0.5,
                location_match=0.5,  # Too much
                url_slug_match=0.0,
                social_handle_match=0.0,
                profile_indicators=0.0,
            )
    
    def test_custom_weights_affect_score(self, renee_identity):
        """Custom weights should affect scoring."""
        # Create scorer that heavily weights URL slug
        custom_weights = ScoringWeights(
            name_in_title=0.1,
            name_in_content=0.1,
            location_match=0.1,
            url_slug_match=0.5,  # Heavy weight
            social_handle_match=0.1,
            profile_indicators=0.1,
        )
        scorer = IdentityConfidenceScorer(weights=custom_weights)
        
        result = scorer.score_page(
            page_content="Generic content",
            page_metadata={
                "title": "About",
                "url": "https://reneesferrazza.com/about"  # Strong URL match
            },
            claimed_identity=renee_identity,
        )
        
        # URL slug should contribute more with custom weights
        assert result.details["component_scores"]["url_slug_match"] > 0


# ============================================================================
# Convenience Function Tests
# ============================================================================

class TestConvenienceFunction:
    """Test the score_identity_confidence convenience function."""
    
    def test_convenience_function_works(self, renee_identity):
        """Convenience function should work without instantiating scorer."""
        result = score_identity_confidence(
            page_content="Renee Sferrazza is a wine expert in Toronto.",
            page_metadata={
                "title": "About Renee Sferrazza",
                "url": "https://reneesferrazza.com"
            },
            claimed_identity=renee_identity,
        )
        
        assert isinstance(result, IdentityScoreResult)
        assert result.score > 0
    
    def test_convenience_function_with_quality(self, renee_identity):
        """Convenience function should accept content quality."""
        result = score_identity_confidence(
            page_content="Renee Sferrazza",
            page_metadata={"title": "Renee", "url": "https://example.com"},
            claimed_identity=renee_identity,
            content_quality="partial"
        )
        
        assert result.details["content_quality"] == "partial"
        assert result.details["quality_penalty"] == 0.1


# ============================================================================
# Result Structure Tests
# ============================================================================

class TestResultStructure:
    """Test result object structure and methods."""
    
    def test_result_has_all_fields(self, scorer, renee_identity):
        """Result should have all expected fields."""
        result = scorer.score_page(
            page_content="Renee Sferrazza is a wine expert.",
            page_metadata={"title": "About", "url": "https://example.com"},
            claimed_identity=renee_identity,
        )
        
        assert hasattr(result, "score")
        assert hasattr(result, "confidence_level")
        assert hasattr(result, "details")
        assert hasattr(result, "matched_signals")
        assert hasattr(result, "unmatched_signals")
        assert hasattr(result, "reasons")
        assert hasattr(result, "normalized_identity")
    
    def test_reasons_are_human_readable(self, scorer, renee_identity):
        """Reasons should be human-readable strings."""
        result = scorer.score_page(
            page_content="Renee Sferrazza is a wine expert in Toronto.",
            page_metadata={
                "title": "About Renee Sferrazza",
                "url": "https://reneesferrazza.com/about"
            },
            claimed_identity=renee_identity,
        )
        
        assert len(result.reasons) > 0
        for reason in result.reasons:
            assert isinstance(reason, str)
            assert len(reason) > 0
    
    def test_component_scores_sum_check(self, scorer, renee_identity):
        """Component scores should be individually valid."""
        result = scorer.score_page(
            page_content="Renee Sferrazza is a wine expert.",
            page_metadata={"title": "About", "url": "https://example.com"},
            claimed_identity=renee_identity,
        )
        
        scores = result.details["component_scores"]
        for key, value in scores.items():
            assert 0.0 <= value <= 1.0, f"{key} score {value} out of range"


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
