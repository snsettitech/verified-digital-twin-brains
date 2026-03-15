"""
Tests for Phase 3: Claim Extraction

Verifies:
1. Claim extraction correctness
2. Idempotency of claim storage
3. Proper tenant/twin scoping via group_id
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from modules.graph_claim_extractor import (
    GraphClaimExtractor,
    ExtractedClaim,
    process_extract_claims_job
)


class TestClaimExtraction:
    """Test claim extraction from text."""
    
    @pytest.mark.asyncio
    async def test_extract_claims_from_text(self):
        """Should extract structured claims from text."""
        with patch('modules.graph_claim_extractor.get_graph_memory_config') as mock_config:
            mock_config.return_value = MagicMock()
            mock_config.return_value.is_write_allowed.return_value = True
            mock_config.return_value.make_group_id.return_value = "tenant1__twin1"
            
            extractor = GraphClaimExtractor(
                tenant_id="tenant1",
                twin_id="twin1"
            )
            
            # Mock LLM extraction
            extractor._llm_extract_claims = AsyncMock(return_value=[
                {"text": "Owner prefers direct communication", "confidence": 0.95, "type": "preference"},
                {"text": "Response time should be under 24 hours", "confidence": 0.88, "type": "fact"}
            ])
            
            claims = await extractor.extract_claims(
                text="I prefer direct communication and expect responses within 24 hours.",
                source_type="escalation_resolution",
                source_ref="esc-123"
            )
            
            assert len(claims) == 2
            assert claims[0].text == "Owner prefers direct communication"
            assert claims[0].claim_type == "preference"
            assert claims[0].confidence == 0.95
            assert claims[0].source_ref == "esc-123"
    
    @pytest.mark.asyncio
    async def test_claims_tenant_scoped(self):
        """Claims should include tenant/twin scope in ID."""
        with patch('modules.graph_claim_extractor.get_graph_memory_config') as mock_config:
            mock_config.return_value = MagicMock()
            mock_config.return_value.is_write_allowed.return_value = True
            mock_config.return_value.make_group_id.return_value = "tenant1__twin1"
            
            extractor = GraphClaimExtractor(
                tenant_id="tenant1",
                twin_id="twin1"
            )
            
            extractor._llm_extract_claims = AsyncMock(return_value=[
                {"text": "Test claim", "confidence": 0.9, "type": "fact"}
            ])
            
            claims = await extractor.extract_claims(
                text="Test claim",
                source_type="test",
                source_ref="test-1"
            )
            
            # Claim ID should be deterministic based on content + scope
            claim = claims[0]
            assert claim.claim_id is not None
            assert len(claim.claim_id) == 16  # SHA-256 truncated
    
    @pytest.mark.asyncio
    async def test_extraction_disabled_when_graph_off(self):
        """Should return empty list when graph writes disabled."""
        with patch('modules.graph_claim_extractor.get_graph_memory_config') as mock_config:
            mock_config.return_value = MagicMock()
            mock_config.return_value.is_write_allowed.return_value = False
            
            extractor = GraphClaimExtractor(
                tenant_id="tenant1",
                twin_id="twin1"
            )
            
            claims = await extractor.extract_claims(
                text="Some text",
                source_type="test",
                source_ref="test-1"
            )
            
            assert claims == []


class TestClaimIdempotency:
    """Test idempotency of claim storage."""
    
    @pytest.mark.asyncio
    async def test_same_claim_same_idempotency_key(self):
        """Same claim should generate same idempotency key."""
        with patch('modules.graph_claim_extractor.get_graph_memory_config') as mock_config:
            mock_config.return_value = MagicMock()
            mock_config.return_value.is_write_allowed.return_value = True
            mock_config.return_value.make_group_id.return_value = "tenant1__twin1"
            
            mock_outbox = MagicMock()
            mock_outbox.submit = MagicMock(return_value="job-123")
            
            mock_client = MagicMock()
            mock_client.outbox = mock_outbox
            
            with patch('modules.graph_claim_extractor.GraphMemoryCore') as mock_core:
                mock_core.return_value = mock_client
                
                extractor = GraphClaimExtractor(
                    tenant_id="tenant1",
                    twin_id="twin1"
                )
                
                claim = ExtractedClaim(
                    claim_id="claim123",
                    text="Test claim",
                    confidence=0.9,
                    claim_type="fact",
                    source_ref="esc-123",
                    source_type="escalation_resolution",
                    extracted_at="2024-01-01T00:00:00Z",
                    content_hash="abc123"
                )
                
                # Store twice
                await extractor.store_claims([claim], async_write=True)
                await extractor.store_claims([claim], async_write=True)
                
                # Should have same idempotency key
                calls = mock_outbox.submit.call_args_list
                assert len(calls) == 2
                assert calls[0][1]['idempotency_key'] == calls[1][1]['idempotency_key']
    
    @pytest.mark.asyncio
    async def test_different_claims_different_keys(self):
        """Different claims should have different idempotency keys."""
        with patch('modules.graph_claim_extractor.get_graph_memory_config') as mock_config:
            mock_config.return_value = MagicMock()
            mock_config.return_value.is_write_allowed.return_value = True
            mock_config.return_value.make_group_id.return_value = "tenant1__twin1"
            
            mock_outbox = MagicMock()
            mock_outbox.submit = MagicMock(return_value="job-123")
            
            mock_client = MagicMock()
            mock_client.outbox = mock_outbox
            
            with patch('modules.graph_claim_extractor.GraphMemoryCore') as mock_core:
                mock_core.return_value = mock_client
                
                extractor = GraphClaimExtractor(
                    tenant_id="tenant1",
                    twin_id="twin1"
                )
                
                claim1 = ExtractedClaim(
                    claim_id="claim1",
                    text="Claim one",
                    confidence=0.9,
                    claim_type="fact",
                    source_ref="esc-123",
                    source_type="escalation",
                    extracted_at="2024-01-01T00:00:00Z",
                    content_hash="hash1"
                )
                
                claim2 = ExtractedClaim(
                    claim_id="claim2",
                    text="Claim two",
                    confidence=0.8,
                    claim_type="opinion",
                    source_ref="esc-123",
                    source_type="escalation",
                    extracted_at="2024-01-01T00:00:00Z",
                    content_hash="hash2"
                )
                
                await extractor.store_claims([claim1, claim2], async_write=True)
                
                calls = mock_outbox.submit.call_args_list
                assert len(calls) == 2
                assert calls[0][1]['idempotency_key'] != calls[1][1]['idempotency_key']


class TestWorkerJobProcessing:
    """Test worker job processing."""
    
    @pytest.mark.asyncio
    async def test_process_extract_job_success(self):
        """Worker should process extraction job successfully."""
        with patch('modules.graph_claim_extractor.GraphClaimExtractor') as mock_extractor_class:
            mock_extractor = MagicMock()
            mock_extractor.extract_claims = AsyncMock(return_value=[
                ExtractedClaim(
                    claim_id="c1",
                    text="Test claim",
                    confidence=0.9,
                    claim_type="fact",
                    source_ref="esc-123",
                    source_type="escalation",
                    extracted_at="2024-01-01T00:00:00Z",
                    content_hash="hash1"
                )
            ])
            mock_extractor.store_claims = AsyncMock(return_value=["job-1"])
            mock_extractor_class.return_value = mock_extractor
            
            result = await process_extract_claims_job(
                tenant_id="tenant1",
                twin_id="twin1",
                payload={
                    "text": "Test text",
                    "source_type": "escalation_resolution",
                    "source_ref": "esc-123",
                    "context": {"question": "What?"}
                }
            )
            
            assert result is True
            mock_extractor.extract_claims.assert_called_once()
            mock_extractor.store_claims.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_extract_job_failure_graceful(self):
        """Worker should handle failures gracefully."""
        with patch('modules.graph_claim_extractor.GraphClaimExtractor') as mock_extractor_class:
            mock_extractor = MagicMock()
            mock_extractor.extract_claims = AsyncMock(side_effect=Exception("LLM error"))
            mock_extractor_class.return_value = mock_extractor
            
            result = await process_extract_claims_job(
                tenant_id="tenant1",
                twin_id="twin1",
                payload={"text": "Test"}
            )
            
            assert result is False  # Returns False to trigger retry


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
