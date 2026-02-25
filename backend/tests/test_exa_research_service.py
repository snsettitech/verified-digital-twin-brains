"""
Tests for ExaResearchService

Covers:
- Person query building
- Two-pass retrieval
- Freshness controls
- Quality filtering
- Integration with existing Phase 9
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import asyncio

from modules.exa_research_service import (
    ExaResearchService,
    PersonSearchQuery,
    ResearchResult,
    SearchMetadata,
    ExaCategory,
    SourceFreshness,
    FRESHNESS_DEFAULTS,
)


# ============================================================================
# Person Query Builder Tests
# ============================================================================

class TestPersonSearchQuery:
    """Test person search query building."""
    
    def test_basic_name_only(self):
        """Query with just name."""
        query = PersonSearchQuery(name="John Doe")
        assert query.build_query() == "John Doe"
    
    def test_name_with_company(self):
        """Query with name and company."""
        query = PersonSearchQuery(
            name="John Doe",
            company="Acme Corp"
        )
        result = query.build_query()
        assert "John Doe" in result
        assert "Acme Corp" in result
    
    def test_name_with_aliases(self):
        """Query with aliases."""
        query = PersonSearchQuery(
            name="John Doe",
            aliases=["J. Doe", "Johnny Doe"]
        )
        result = query.build_query()
        assert "John Doe" in result
        assert '"J. Doe"' in result
        assert '"Johnny Doe"' in result
    
    def test_name_with_social_handles(self):
        """Query with social handles (cleaned)."""
        query = PersonSearchQuery(
            name="John Doe",
            social_handles=["@johndoe", "@jdoe"]
        )
        result = query.build_query()
        assert '"johndoe"' in result  # @ removed
        assert '"jdoe"' in result
    
    def test_name_with_topics(self):
        """Query with expertise topics."""
        query = PersonSearchQuery(
            name="John Doe",
            topics=["AI", "machine learning", "robotics"]
        )
        result = query.build_query()
        assert "John Doe" in result
        assert "AI" in result
        assert "machine learning" in result
        assert "robotics" in result
    
    def test_name_with_geography(self):
        """Query with location."""
        query = PersonSearchQuery(
            name="John Doe",
            geography="San Francisco"
        )
        result = query.build_query()
        assert "John Doe" in result
        assert "San Francisco" in result
    
    def test_complex_person_query(self):
        """Complex query with all fields."""
        query = PersonSearchQuery(
            name="Sarah Chen",
            aliases=["S. Chen"],
            company="OpenAI",
            social_handles=["@sarahchen"],
            topics=["AI safety", "research"],
            geography="San Francisco"
        )
        result = query.build_query()
        
        # Should include core elements
        assert "Sarah Chen" in result
        assert "OpenAI" in result
        assert "AI safety" in result
        
        # Should not over-constrain (no assertion on exact format)
        assert len(result.split()) >= 4  # Multiple components
    
    def test_domain_filters(self):
        """Domain filter building."""
        query = PersonSearchQuery(
            name="John Doe",
            website_domains=["johndoe.com", "linkedin.com/in/johndoe"]
        )
        domains = query.build_domain_filters()
        assert "johndoe.com" in domains
        assert "linkedin.com/in/johndoe" in domains


# ============================================================================
# Freshness Controls Tests
# ============================================================================

class TestFreshnessControls:
    """Test freshness configuration."""
    
    def test_freshness_defaults(self):
        """Freshness preset defaults."""
        assert FRESHNESS_DEFAULTS[SourceFreshness.NEWS] == 24
        assert FRESHNESS_DEFAULTS[SourceFreshness.SOCIAL] == 48
        assert FRESHNESS_DEFAULTS[SourceFreshness.COMPANY] == 168
        assert FRESHNESS_DEFAULTS[SourceFreshness.EVERGREEN] == 720
        assert FRESHNESS_DEFAULTS[SourceFreshness.ARCHIVE] == -1
    
    @pytest.mark.asyncio
    async def test_resolve_freshness_explicit_override(self):
        """Explicit max_age_hours overrides freshness preset."""
        service = ExaResearchService(api_key="test")
        
        result = service._resolve_freshness(
            freshness=SourceFreshness.NEWS,  # Would be 24
            max_age_hours=12  # But we want 12
        )
        assert result == 12
    
    @pytest.mark.asyncio
    async def test_resolve_freshness_preset_only(self):
        """Freshness preset used when no explicit override."""
        service = ExaResearchService(api_key="test")
        
        result = service._resolve_freshness(
            freshness=SourceFreshness.EVERGREEN,
            max_age_hours=None
        )
        assert result == 720
    
    @pytest.mark.asyncio
    async def test_resolve_freshness_none(self):
        """None returns None (use Exa default)."""
        service = ExaResearchService(api_key="test")
        
        result = service._resolve_freshness(None, None)
        assert result is None


# ============================================================================
# Quality Filtering Tests
# ============================================================================

class TestQualityFiltering:
    """Test quality filtering and deduplication."""
    
    @pytest.mark.asyncio
    async def test_high_authority_domain_assessment(self):
        """High authority domains correctly identified."""
        service = ExaResearchService(api_key="test")
        
        quality = service._assess_domain_quality("linkedin.com")
        assert quality == "high"
        
        quality = service._assess_domain_quality("github.com")
        assert quality == "high"
    
    @pytest.mark.asyncio
    async def test_low_quality_domain_assessment(self):
        """Low quality domains correctly identified."""
        service = ExaResearchService(api_key="test")
        
        quality = service._assess_domain_quality("pinterest.com")
        assert quality == "low"
    
    @pytest.mark.asyncio
    async def test_medium_quality_domain_assessment(self):
        """Unknown domains default to medium."""
        service = ExaResearchService(api_key="test")
        
        quality = service._assess_domain_quality("example.com")
        assert quality == "medium"
    
    @pytest.mark.asyncio
    async def test_filter_quality_removes_low(self):
        """Low quality results are filtered out."""
        service = ExaResearchService(api_key="test")
        
        results = [
            ResearchResult(url="https://linkedin.com/in/john", title="John", source_quality="high"),
            ResearchResult(url="https://pinterest.com/pin", title="Pin", source_quality="low"),
            ResearchResult(url="https://example.com", title="Example", source_quality="medium"),
        ]
        
        filtered = service._filter_quality(results)
        
        assert len(filtered) == 2
        assert all(r.source_quality != "low" for r in filtered)
    
    @pytest.mark.asyncio
    async def test_deduplicate_by_domain(self):
        """Results deduplicated by domain."""
        service = ExaResearchService(api_key="test")
        
        results = [
            ResearchResult(url="https://linkedin.com/in/john1", title="John 1"),
            ResearchResult(url="https://linkedin.com/in/john2", title="John 2"),
            ResearchResult(url="https://linkedin.com/in/john3", title="John 3"),
            ResearchResult(url="https://github.com/john", title="GitHub"),
        ]
        
        deduplicated = service._deduplicate_by_domain(results, max_per_domain=2)
        
        # Should keep max 2 from linkedin.com
        linkedin_count = sum(1 for r in deduplicated if "linkedin.com" in r.url)
        assert linkedin_count == 2
        # Should keep github
        assert any("github.com" in r.url for r in deduplicated)


# ============================================================================
# ResearchResult Tests
# ============================================================================

class TestResearchResult:
    """Test ResearchResult data class."""
    
    def test_to_dict_serialization(self):
        """ResearchResult serializes to dict correctly."""
        metadata = SearchMetadata(
            query="test query",
            category="people",
            search_type="auto",
            num_results_requested=10,
            num_results_returned=5,
        )
        
        result = ResearchResult(
            url="https://example.com",
            title="Example",
            text="Full text content",
            highlights=["Highlight 1", "Highlight 2"],
            score=0.95,
            source_quality="high",
            verified=True,
            search_metadata=metadata,
        )
        
        data = result.to_dict()
        
        assert data["url"] == "https://example.com"
        assert data["title"] == "Example"
        assert data["text"] == "Full text content"
        assert len(data["highlights"]) == 2
        assert data["score"] == 0.95
        assert data["source_quality"] == "high"
        assert data["verified"] is True
        assert data["search_metadata"]["query"] == "test query"


# ============================================================================
# Service Integration Tests
# ============================================================================

class TestExaResearchService:
    """Test ExaResearchService integration."""
    
    @pytest.mark.asyncio
    async def test_service_initialization_without_key(self):
        """Service warns but doesn't fail without API key."""
        with patch.dict('os.environ', {}, clear=True):
            service = ExaResearchService()
            assert service.api_key == ""
    
    @pytest.mark.asyncio
    async def test_service_initialization_with_key(self):
        """Service initializes with provided key."""
        service = ExaResearchService(api_key="test_key_123")
        assert service.api_key == "test_key_123"
    
    @pytest.mark.asyncio
    async def test_service_initialization_from_env(self):
        """Service reads API key from environment."""
        with patch.dict('os.environ', {'EXA_API_KEY': 'env_key_456'}):
            service = ExaResearchService()
            assert service.api_key == "env_key_456"
    
    @pytest.mark.asyncio
    @patch('exa_py.Exa')
    async def test_search_highlights_mock(self, mock_exa_class):
        """Search highlights with mocked Exa client."""
        # Setup mock
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.url = "https://example.com/article"
        mock_result.title = "Example Article"
        mock_result.highlights = ["This is a highlight"]
        mock_result.score = 0.9
        mock_result.published_date = "2024-01-15"
        mock_result.author = "John Doe"
        
        mock_response = MagicMock()
        mock_response.results = [mock_result]
        mock_client.search.return_value = mock_response
        mock_exa_class.return_value = mock_client
        
        # Execute
        service = ExaResearchService(api_key="test")
        results = await service.search_highlights(
            query="test query",
            num_results=5,
            category=ExaCategory.PEOPLE,
        )
        
        # Verify
        assert len(results) == 1
        assert results[0].url == "https://example.com/article"
        assert results[0].title == "Example Article"
        assert results[0].source_quality == "medium"  # example.com
        
        # Verify call
        mock_client.search.assert_called_once()
        call_kwargs = mock_client.search.call_args.kwargs
        assert call_kwargs["query"] == "test query"
        assert call_kwargs["category"] == "people"
        assert call_kwargs["type"] == "auto"
    
    @pytest.mark.asyncio
    @patch('exa_py.Exa')
    async def test_fetch_full_contents_mock(self, mock_exa_class):
        """Fetch full contents with mocked client."""
        # Setup mock
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.url = "https://example.com"
        mock_result.title = "Full Article"
        mock_result.text = "This is the full article content..."
        mock_result.published_date = "2024-01-15"
        
        mock_response = MagicMock()
        mock_response.results = [mock_result]
        mock_client.get_contents.return_value = mock_response
        mock_exa_class.return_value = mock_client
        
        # Execute
        service = ExaResearchService(api_key="test")
        results = await service.fetch_full_contents(
            urls=["https://example.com"],
            max_characters=5000,
        )
        
        # Verify
        assert len(results) == 1
        assert results[0].text == "This is the full article content..."
        assert results[0].text_length == len("This is the full article content...")
        
        # Verify call
        mock_client.get_contents.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('exa_py.Exa')
    async def test_discover_person_integration(self, mock_exa_class):
        """Person discovery with mocked client."""
        # Setup mock
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.url = "https://linkedin.com/in/john"
        mock_result.title = "John Doe - LinkedIn"
        mock_result.highlights = ["CEO at Acme Corp"]
        mock_result.score = 0.95
        
        mock_response = MagicMock()
        mock_response.results = [mock_result]
        mock_client.search.return_value = mock_response
        mock_exa_class.return_value = mock_client
        
        # Execute
        service = ExaResearchService(api_key="test")
        results = await service.discover_person(
            name="John Doe",
            company="Acme Corp",
            topics=["leadership"],
            fetch_full_content=False,  # Skip second pass for test
        )
        
        # Verify
        assert len(results) == 1
        assert results[0].url == "https://linkedin.com/in/john"
        assert any("John Doe" in note for note in results[0].verification_notes)
        
        # Verify category=people was used
        call_kwargs = mock_client.search.call_args.kwargs
        assert call_kwargs["category"] == "people"


# ============================================================================
# Claim Verification Tests
# ============================================================================

class TestClaimVerification:
    """Test claim verification features."""
    
    @pytest.mark.asyncio
    async def test_build_claim_query_removes_first_person(self):
        """First-person pronouns removed from claim queries."""
        service = ExaResearchService(api_key="test")
        
        query = service._build_claim_query("I prefer remote work", "preference")
        assert "I " not in query
        assert "prefer" in query
        assert "remote work" in query
    
    @pytest.mark.asyncio
    async def test_build_claim_query_adds_context(self):
        """Context added for experience claims."""
        service = ExaResearchService(api_key="test")
        
        query = service._build_claim_query("Led engineering teams", "experience")
        assert "experience" in query or "background" in query
    
    @pytest.mark.asyncio
    @patch('exa_py.Exa')
    async def test_verify_claim_assesses_quality(self, mock_exa_class):
        """Verification quality assessed and marked."""
        # Setup mock
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.url = "https://linkedin.com/in/john"
        mock_result.title = "Profile"
        mock_result.highlights = ["Led teams"]
        mock_result.score = 0.9
        
        mock_response = MagicMock()
        mock_response.results = [mock_result]
        mock_client.search.return_value = mock_response
        mock_exa_class.return_value = mock_client
        
        # Execute
        service = ExaResearchService(api_key="test")
        results = await service.verify_claim(
            claim_text="Led engineering teams",
            claim_type="experience",
        )
        
        # Verify quality assessment
        assert len(results) == 1
        assert results[0].source_quality == "high"  # linkedin.com
        assert results[0].verified is True  # High authority = verified
        assert any("High authority" in note for note in results[0].verification_notes)


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Test error handling."""
    
    @pytest.mark.asyncio
    async def test_search_without_api_key_returns_empty(self):
        """Graceful handling when API key missing."""
        service = ExaResearchService(api_key="")
        results = await service.search_highlights("test")
        assert results == []
    
    @pytest.mark.asyncio
    @patch('exa_py.Exa')
    async def test_search_error_returns_empty(self, mock_exa_class):
        """Errors return empty list, don't crash."""
        mock_client = MagicMock()
        mock_client.search.side_effect = Exception("API Error")
        mock_exa_class.return_value = mock_client
        
        service = ExaResearchService(api_key="test")
        results = await service.search_highlights("test")
        
        assert results == []


# ============================================================================
# API Contract Tests
# ============================================================================

class TestAPIContracts:
    """Test API contracts and enums."""
    
    def test_exa_category_values(self):
        """ExaCategory enum has correct values."""
        assert ExaCategory.PEOPLE.value == "people"
        assert ExaCategory.COMPANY.value == "company"
        assert ExaCategory.NEWS.value == "news"
        assert ExaCategory.RESEARCH_PAPER.value == "research paper"
        assert ExaCategory.TWEET.value == "tweet"
    
    def test_source_freshness_values(self):
        """SourceFreshness enum has correct values."""
        assert SourceFreshness.NEWS.value == "news"
        assert SourceFreshness.SOCIAL.value == "social"
        assert SourceFreshness.COMPANY.value == "company"
        assert SourceFreshness.EVERGREEN.value == "evergreen"
        assert SourceFreshness.ARCHIVE.value == "archive"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
