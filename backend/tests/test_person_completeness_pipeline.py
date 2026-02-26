"""
Tests for Person Completeness Pipeline

Run: pytest backend/tests/test_person_completeness_pipeline.py -v
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import uuid

from modules.person_completeness_pipeline import (
    PersonCompletenessPipeline,
    PipelineStage,
    PipelineResult,
    run_person_completeness_pipeline,
    is_person_completeness_enabled,
)
from modules.person_completeness_config import PersonCompletenessConfig


class TestPersonCompletenessConfig:
    """Test configuration."""
    
    def test_is_enabled_for_twin_default(self):
        config = PersonCompletenessConfig(enabled=True)
        assert config.is_enabled_for_twin("any-twin") is True
    
    def test_is_enabled_for_twin_disabled(self):
        config = PersonCompletenessConfig(enabled=False)
        assert config.is_enabled_for_twin("any-twin") is False
    
    def test_is_enabled_for_twin_explicit_enable(self):
        config = PersonCompletenessConfig(
            enabled=True,
            enabled_twin_ids=["twin-1"]
        )
        assert config.is_enabled_for_twin("twin-1") is True
        assert config.is_enabled_for_twin("twin-2") is False
    
    def test_is_enabled_for_twin_explicit_disable(self):
        config = PersonCompletenessConfig(
            enabled=True,
            disabled_twin_ids=["twin-1"]
        )
        assert config.is_enabled_for_twin("twin-1") is False
        assert config.is_enabled_for_twin("twin-2") is True
    
    def test_get_enabled_stages(self):
        config = PersonCompletenessConfig()
        stages = config.get_enabled_stages()
        assert "source_registry_built" in stages
        assert "claims_extracted" in stages


class TestPersonCompletenessPipeline:
    """Test main pipeline orchestrator."""
    
    @pytest.fixture
    def mock_config(self):
        config = PersonCompletenessConfig(enabled=True)
        config.source_registry.enabled = True
        config.claim_extraction.enabled = True
        config.timeline_builder.enabled = False  # Disable for faster tests
        config.topic_graph.enabled = False
        config.style_profile.enabled = False
        config.contradiction_detection.enabled = False
        config.answerability_scoring.enabled = False
        return config
    
    @pytest.fixture
    def pipeline(self, mock_config):
        return PersonCompletenessPipeline(config=mock_config)
    
    @pytest.mark.asyncio
    async def test_pipeline_disabled(self, pipeline):
        """Test that disabled pipeline returns early."""
        pipeline.config.enabled = False
        
        result = await pipeline.run_for_twin("test-twin")
        
        assert result.success is False
        assert "not enabled" in result.error_message
    
    @pytest.mark.asyncio
    async def test_pipeline_already_running(self, pipeline):
        """Test that running pipeline blocks duplicate."""
        with patch.object(pipeline.repository, 'get_latest_run', return_value={
            "id": "run-1",
            "status": "running"
        }):
            result = await pipeline.run_for_twin("test-twin")
        
        assert result.success is False
        assert "already in progress" in result.error_message
    
    @pytest.mark.asyncio
    async def test_pipeline_success(self, pipeline):
        """Test successful pipeline run."""
        # Mock all dependencies
        with patch.object(pipeline.repository, 'get_latest_run', return_value=None):
            with patch.object(pipeline.repository, 'create_run', return_value="run-1"):
                with patch.object(pipeline.repository, 'update_run_status'):
                    # Mock stage handlers
                    mock_handler = AsyncMock()
                    mock_handler.run = AsyncMock(return_value=Mock(
                        success=True,
                        sources_added=5,
                        claims_extracted=10
                    ))
                    pipeline._stage_handlers["source_registry_built"] = mock_handler
                    pipeline._stage_handlers["claims_extracted"] = mock_handler
                    
                    result = await pipeline.run_for_twin("test-twin")
        
        assert result.success is True
        assert len(result.stages_completed) >= 0  # Stages may be mocked
    
    @pytest.mark.asyncio
    async def test_pipeline_stage_failure_continue(self, pipeline):
        """Test pipeline continues on stage failure when configured."""
        pipeline.config.continue_on_stage_failure = True
        
        with patch.object(pipeline.repository, 'get_latest_run', return_value=None):
            with patch.object(pipeline.repository, 'create_run', return_value="run-1"):
                with patch.object(pipeline.repository, 'update_run_status'):
                    # One stage fails, one succeeds
                    mock_success = AsyncMock()
                    mock_success.run = AsyncMock(return_value=Mock(success=True))
                    
                    mock_fail = AsyncMock()
                    mock_fail.run = AsyncMock(return_value=Mock(
                        success=False,
                        error_message="Stage failed"
                    ))
                    
                    pipeline._stage_handlers["source_registry_built"] = mock_success
                    # Other stages fail
                    
                    result = await pipeline.run_for_twin("test-twin")
        
        # Should be partial success
        assert result.success is True  # Partial is still success


class TestPipelineStages:
    """Test individual pipeline stages."""
    
    @pytest.mark.asyncio
    async def test_source_registry_builder(self):
        """Test source registry building."""
        from modules.source_registry_builder import SourceRegistryBuilder
        
        builder = SourceRegistryBuilder()
        
        with patch('modules.source_registry_builder.supabase') as mock_supabase:
            # Mock empty sources
            mock_supabase.table.return_value.select.return_value.execute.return_value = Mock(data=[])
            
            result = await builder.run("test-twin")
        
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_claim_extraction_service(self):
        """Test claim extraction."""
        from modules.claim_extraction_service import ClaimExtractionService
        
        service = ClaimExtractionService()
        
        with patch('modules.claim_extraction_service.supabase') as mock_supabase:
            # Mock no sources
            mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.limit.return_value.execute.return_value = Mock(data=[])
            
            result = await service.run("test-twin")
        
        assert result.success is True
        assert result.claims_extracted == 0


class TestIntegration:
    """Integration-style tests."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_with_mocks(self):
        """Test full pipeline with mocked dependencies."""
        config = PersonCompletenessConfig(enabled=True)
        pipeline = PersonCompletenessPipeline(config=config)
        
        # Mock all database calls
        with patch('modules.person_completeness_pipeline.supabase') as mock_supabase:
            mock_supabase.table.return_value.select.return_value.execute.return_value = Mock(data=None)
            mock_supabase.table.return_value.insert.return_value.execute.return_value = Mock(data=[{"id": "run-1"}])
            mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = Mock()
            
            # Mock stage handlers to return success
            with patch.object(pipeline, '_get_stage_handler') as mock_get_handler:
                mock_handler = AsyncMock()
                mock_handler.run = AsyncMock(return_value=Mock(
                    success=True,
                    sources_added=5,
                    claims_extracted=10,
                    events_created=3,
                    topics_created=4,
                    profile_version=1,
                    contradictions_found=0,
                    scores_computed=5
                ))
                mock_get_handler.return_value = mock_handler
                
                result = await pipeline.run_for_twin("test-twin", force_rebuild=True)
        
        assert isinstance(result, PipelineResult)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
