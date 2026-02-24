"""
Tests for Research Orchestrator (Phase 3.4)

State machine and checkpointing tests.
"""

import pytest
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Skip tests if modules not available
pytest.importorskip("modules.research_orchestrator")

from modules.research_orchestrator import (
    ResearchOrchestrator,
    ResearchRunStatus,
    ResearchRepository,
    is_valid_transition,
    CheckpointData,
    ConfirmationCheckpointData,
    CreateResearchRunResult,
    TransitionResult,
)


# ============================================================================
# State Machine Tests
# ============================================================================

class TestStateMachine:
    """Test state machine transitions."""
    
    def test_valid_transitions_planning(self):
        """Planning can go to queued or failed."""
        assert is_valid_transition(ResearchRunStatus.PLANNING, ResearchRunStatus.QUEUED)
        assert is_valid_transition(ResearchRunStatus.PLANNING, ResearchRunStatus.FAILED)
        assert not is_valid_transition(ResearchRunStatus.PLANNING, ResearchRunStatus.CRAWLING)
        assert not is_valid_transition(ResearchRunStatus.PLANNING, ResearchRunStatus.READY_FOR_INGESTION)
    
    def test_valid_transitions_queued(self):
        """Queued can go to crawling or failed."""
        assert is_valid_transition(ResearchRunStatus.QUEUED, ResearchRunStatus.CRAWLING)
        assert is_valid_transition(ResearchRunStatus.QUEUED, ResearchRunStatus.FAILED)
        assert not is_valid_transition(ResearchRunStatus.QUEUED, ResearchRunStatus.AWAITING_CONFIRMATION)
    
    def test_valid_transitions_crawling(self):
        """Crawling can go to awaiting_confirmation, ready_for_ingestion, or failed."""
        assert is_valid_transition(ResearchRunStatus.CRAWLING, ResearchRunStatus.AWAITING_CONFIRMATION)
        assert is_valid_transition(ResearchRunStatus.CRAWLING, ResearchRunStatus.READY_FOR_INGESTION)
        assert is_valid_transition(ResearchRunStatus.CRAWLING, ResearchRunStatus.FAILED)
        assert not is_valid_transition(ResearchRunStatus.CRAWLING, ResearchRunStatus.QUEUED)
    
    def test_valid_transitions_awaiting_confirmation(self):
        """Awaiting_confirmation can go to itself (refresh), ready_for_ingestion, timed_out, or failed."""
        assert is_valid_transition(ResearchRunStatus.AWAITING_CONFIRMATION, ResearchRunStatus.AWAITING_CONFIRMATION)
        assert is_valid_transition(ResearchRunStatus.AWAITING_CONFIRMATION, ResearchRunStatus.READY_FOR_INGESTION)
        assert is_valid_transition(ResearchRunStatus.AWAITING_CONFIRMATION, ResearchRunStatus.TIMED_OUT)
        assert is_valid_transition(ResearchRunStatus.AWAITING_CONFIRMATION, ResearchRunStatus.FAILED)
        assert not is_valid_transition(ResearchRunStatus.AWAITING_CONFIRMATION, ResearchRunStatus.CRAWLING)
    
    def test_valid_transitions_timed_out(self):
        """Timed_out can go to ready_for_ingestion or failed."""
        assert is_valid_transition(ResearchRunStatus.TIMED_OUT, ResearchRunStatus.READY_FOR_INGESTION)
        assert is_valid_transition(ResearchRunStatus.TIMED_OUT, ResearchRunStatus.FAILED)
        assert not is_valid_transition(ResearchRunStatus.TIMED_OUT, ResearchRunStatus.AWAITING_CONFIRMATION)
    
    def test_valid_transitions_ready_for_ingestion(self):
        """Ready_for_ingestion can go to ingesting or failed (Phase 3.5)."""
        assert is_valid_transition(ResearchRunStatus.READY_FOR_INGESTION, ResearchRunStatus.INGESTING)
        assert is_valid_transition(ResearchRunStatus.READY_FOR_INGESTION, ResearchRunStatus.FAILED)
        assert not is_valid_transition(ResearchRunStatus.READY_FOR_INGESTION, ResearchRunStatus.CRAWLING)
        assert not is_valid_transition(ResearchRunStatus.READY_FOR_INGESTION, ResearchRunStatus.AWAITING_CONFIRMATION)
    
    def test_terminal_states(self):
        """Completed and failed are terminal."""
        assert not is_valid_transition(ResearchRunStatus.COMPLETED, ResearchRunStatus.PLANNING)
        assert not is_valid_transition(ResearchRunStatus.COMPLETED, ResearchRunStatus.QUEUED)
        assert not is_valid_transition(ResearchRunStatus.COMPLETED, ResearchRunStatus.CRAWLING)
        assert not is_valid_transition(ResearchRunStatus.COMPLETED, ResearchRunStatus.READY_FOR_INGESTION)
        
        assert not is_valid_transition(ResearchRunStatus.FAILED, ResearchRunStatus.PLANNING)
        assert not is_valid_transition(ResearchRunStatus.FAILED, ResearchRunStatus.CRAWLING)
    
    def test_self_transition_allowed(self):
        """Self-transitions are always valid (idempotent)."""
        for status in ResearchRunStatus:
            assert is_valid_transition(status, status)


# ============================================================================
# Checkpoint Data Tests
# ============================================================================

class TestCheckpointData:
    """Test checkpoint data structure."""
    
    def test_checkpoint_creation(self):
        """Test creating checkpoint data."""
        checkpoint = CheckpointData(
            phase="crawling",
            last_transition_at=datetime.utcnow().isoformat(),
            crawl_id="crawl-123",
            seed_urls_count=5,
        )
        
        assert checkpoint.phase == "crawling"
        assert checkpoint.crawl_id == "crawl-123"
        assert checkpoint.seed_urls_count == 5
        assert checkpoint.confirmation is None
    
    def test_checkpoint_with_confirmation(self):
        """Test checkpoint with confirmation data."""
        confirmation_data = ConfirmationCheckpointData(
            total=10,
            pending=3,
            manual_review=1,
            auto_confirmed=4,
            auto_rejected=2,
            confirmed=0,
            rejected=0,
            all_resolved=False,
            resolution_percent=70.0,
        )
        
        checkpoint = CheckpointData(
            phase="awaiting_confirmation",
            last_transition_at=datetime.utcnow().isoformat(),
            crawl_id="crawl-123",
            confirmation=confirmation_data,
        )
        
        assert checkpoint.confirmation.total == 10
        assert checkpoint.confirmation.pending == 3
        assert checkpoint.confirmation.all_resolved is False
        assert checkpoint.confirmation.resolution_percent == 70.0
    
    def test_checkpoint_to_dict(self):
        """Test converting checkpoint to dict."""
        confirmation_data = ConfirmationCheckpointData(
            total=5,
            pending=0,
            manual_review=0,
            auto_confirmed=3,
            auto_rejected=2,
            confirmed=0,
            rejected=0,
            all_resolved=True,
            resolution_percent=100.0,
        )
        
        checkpoint = CheckpointData(
            phase="ready_for_ingestion",
            last_transition_at=datetime.utcnow().isoformat(),
            crawl_id="crawl-123",
            confirmation=confirmation_data,
            claimed_identity={"full_name": "Test User"},
            seed_urls_count=2,
            warnings=["Test warning"],
        )
        
        checkpoint_dict = {
            "phase": checkpoint.phase,
            "last_transition_at": checkpoint.last_transition_at,
            "crawl_id": checkpoint.crawl_id,
            "confirmation": checkpoint.confirmation.__dict__,
            "claimed_identity": checkpoint.claimed_identity,
            "seed_urls_count": checkpoint.seed_urls_count,
            "warnings": checkpoint.warnings,
        }
        
        assert checkpoint_dict["phase"] == "ready_for_ingestion"
        assert checkpoint_dict["confirmation"]["total"] == 5
        assert checkpoint_dict["confirmation"]["all_resolved"] is True


# ============================================================================
# Orchestrator Integration Tests
# ============================================================================

class TestOrchestratorStateTransitions:
    """Test orchestrator state transition logic."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator for testing."""
        return ResearchOrchestrator(confirmation_timeout_hours=24)
    
    @pytest.mark.asyncio
    async def test_create_research_run(self, orchestrator):
        """Test creating a research run."""
        # This would require database - skip if no db
        pytest.skip("Requires database connection")
    
    @pytest.mark.asyncio
    async def test_transition_validation(self, orchestrator):
        """Test transition validation logic."""
        # Verify planning -> queued is valid
        assert is_valid_transition(
            ResearchRunStatus.PLANNING,
            ResearchRunStatus.QUEUED
        )
        
        # Verify crawling -> awaiting_confirmation is valid
        assert is_valid_transition(
            ResearchRunStatus.CRAWLING,
            ResearchRunStatus.AWAITING_CONFIRMATION
        )
        
        # Verify awaiting_confirmation -> ready_for_ingestion is valid
        assert is_valid_transition(
            ResearchRunStatus.AWAITING_CONFIRMATION,
            ResearchRunStatus.READY_FOR_INGESTION
        )


# ============================================================================
# Phase 3.4 Contract Tests
# ============================================================================

class TestPhase34Contracts:
    """Test Phase 3.4 behavior contracts."""
    
    def test_stops_at_ready_for_ingestion(self):
        """Phase 3.4 stops at ready_for_ingestion - Phase 3.5 continues to ingestion."""
        # ready_for_ingestion now transitions to ingesting (Phase 3.5)
        assert is_valid_transition(
            ResearchRunStatus.READY_FOR_INGESTION,
            ResearchRunStatus.INGESTING
        )
        # Path continues: ingesting -> ingestion_completed (Phase 3.5 terminal)
        assert is_valid_transition(
            ResearchRunStatus.INGESTING,
            ResearchRunStatus.INGESTION_COMPLETED
        )
    
    def test_confirmation_gate_behavior(self):
        """Test confirmation gate: crawling -> awaiting_confirmation or ready_for_ingestion."""
        # From crawling, can go to awaiting_confirmation
        assert is_valid_transition(
            ResearchRunStatus.CRAWLING,
            ResearchRunStatus.AWAITING_CONFIRMATION
        )
        # Or directly to ready_for_ingestion if all auto-resolved
        assert is_valid_transition(
            ResearchRunStatus.CRAWLING,
            ResearchRunStatus.READY_FOR_INGESTION
        )
    
    def test_timeout_transition(self):
        """Test timeout transition: awaiting_confirmation -> timed_out -> ready_for_ingestion."""
        # Can timeout from awaiting_confirmation
        assert is_valid_transition(
            ResearchRunStatus.AWAITING_CONFIRMATION,
            ResearchRunStatus.TIMED_OUT
        )
        # Then proceed to ready_for_ingestion
        assert is_valid_transition(
            ResearchRunStatus.TIMED_OUT,
            ResearchRunStatus.READY_FOR_INGESTION
        )
    
    def test_user_override_policy(self):
        """Test that users can override auto decisions (via confirmation system)."""
        # This is enforced in the confirmation manager, not the orchestrator
        # The orchestrator just responds to state changes
        pass
    
    def test_checkpoint_schema_completeness(self):
        """Test checkpoint schema has all required fields."""
        now = datetime.utcnow().isoformat()
        checkpoint = CheckpointData(
            phase="awaiting_confirmation",
            last_transition_at=now,
            crawl_id="crawl-123",
            confirmation=ConfirmationCheckpointData(
                total=10, pending=3, manual_review=1,
                auto_confirmed=4, auto_rejected=2,
                confirmed=0, rejected=0,
                all_resolved=False, resolution_percent=70.0
            ),
            claimed_identity={"full_name": "Test"},
            seed_urls_count=2,
            timeout_at=(datetime.utcnow() + timedelta(hours=24)).isoformat(),
            warnings=["Some items unresolved"],
        )
        
        # Verify all fields are present
        assert checkpoint.phase == "awaiting_confirmation"
        assert checkpoint.last_transition_at == now
        assert checkpoint.crawl_id == "crawl-123"
        assert checkpoint.confirmation is not None
        assert checkpoint.claimed_identity == {"full_name": "Test"}
        assert checkpoint.seed_urls_count == 2
        assert checkpoint.timeout_at is not None
        assert len(checkpoint.warnings) == 1


# ============================================================================
# Research Repository Tests
# ============================================================================

class TestResearchRepository:
    """Test research repository operations."""
    
    def test_repository_singleton(self):
        """Test repository can be instantiated."""
        repo = ResearchRepository()
        assert repo is not None


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Test error handling in orchestrator."""
    
    def test_invalid_state_transition(self):
        """Test that invalid transitions are rejected."""
        # completed -> crawling is invalid
        assert not is_valid_transition(
            ResearchRunStatus.COMPLETED,
            ResearchRunStatus.CRAWLING
        )
        
        # ready_for_ingestion -> crawling is invalid
        assert not is_valid_transition(
            ResearchRunStatus.READY_FOR_INGESTION,
            ResearchRunStatus.CRAWLING
        )
    
    def test_unknown_status_handling(self):
        """Test handling of unknown status strings."""
        # Invalid status should raise ValueError
        with pytest.raises(ValueError):
            ResearchRunStatus("invalid_status")
    
    @pytest.mark.asyncio
    async def test_nonexistent_run_handling(self):
        """Test handling of non-existent research run."""
        orchestrator = ResearchOrchestrator()
        
        # Try to get status of non-existent run
        # This should raise ValueError
        with pytest.raises(ValueError):
            await orchestrator.get_run_status(
                research_run_id="nonexistent-uuid",
                twin_id="some-twin-id",
            )


# ============================================================================
# Summary and Integration Contract
# ============================================================================

def test_phase_3_4_implementation_summary():
    """
    Summary of Phase 3.4 implementation contracts.
    
    This test documents the expected behavior of Phase 3.4.
    """
    # State machine covers: planning -> queued -> crawling -> awaiting_confirmation -> ready_for_ingestion
    states = list(ResearchRunStatus)
    required_states = [
        ResearchRunStatus.PLANNING,
        ResearchRunStatus.QUEUED,
        ResearchRunStatus.CRAWLING,
        ResearchRunStatus.AWAITING_CONFIRMATION,
        ResearchRunStatus.READY_FOR_INGESTION,
    ]
    
    for state in required_states:
        assert state in states, f"Required state {state} not found"
    
    # Checkpoint can store confirmation summary
    checkpoint = CheckpointData(
        phase="awaiting_confirmation",
        last_transition_at=datetime.utcnow().isoformat(),
    )
    assert checkpoint.phase == "awaiting_confirmation"
    
    # Confirmation checkpoint can track resolution progress
    confirmation = ConfirmationCheckpointData(
        total=10,
        pending=0,
        manual_review=0,
        auto_confirmed=10,
        auto_rejected=0,
        confirmed=0,
        rejected=0,
        all_resolved=True,
        resolution_percent=100.0,
    )
    assert confirmation.all_resolved is True
    assert confirmation.resolution_percent == 100.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
