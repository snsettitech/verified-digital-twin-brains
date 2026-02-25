"""
Research Orchestrator Module (Phase 3.4)

State machine and checkpointing for onboarding-driven research workflow.

Orchestrates the lifecycle:
planning -> queued -> crawling -> awaiting_confirmation -> ready_for_ingestion

Pauses at awaiting_confirmation gate until user resolves all confirmations.
Transitions to ready_for_ingestion when confirmed or timed out.

Phase 3.4 stops at ready_for_ingestion (no ingestion continuation).
Phase 3.5 will implement ingestion continuation.

Usage:
    orchestrator = ResearchOrchestrator()
    
    # Create research run from onboarding
    run = await orchestrator.create_research_run(
        twin_id="twin-123",
        actor_user_id="user-456",
        claimed_identity={"full_name": "Test User", ...},
        seed_urls=["https://example.com"]
    )
    
    # After crawl completes
    result = await orchestrator.on_crawl_completed(
        research_run_id=run.research_run_id,
        twin_id="twin-123",
        crawl_id="crawl-789"
    )
    
    # After user confirms/rejects
    result = await orchestrator.on_confirmations_updated(
        research_run_id=run.research_run_id,
        twin_id="twin-123"
    )
"""

import uuid
import logging
from typing import Optional, Dict, Any, List, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

from modules.observability import supabase
from modules.source_confirmation import (
    SourceConfirmationManager,
    ConfirmationSummary,
    ConfirmationStatus,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Research Run Status State Machine
# ============================================================================

class ResearchRunStatus(str, Enum):
    """
    Research run lifecycle statuses.
    
    State Machine Transitions:
    - planning -> queued
    - queued -> crawling
    - crawling -> awaiting_confirmation (if unresolved confirmations)
    - crawling -> ready_for_ingestion (if all auto-resolved)
    - awaiting_confirmation -> awaiting_confirmation (refresh, no-op)
    - awaiting_confirmation -> ready_for_ingestion (all resolved)
    - awaiting_confirmation -> timed_out (after timeout, policy decision)
    - timed_out -> ready_for_ingestion (proceed with what we have)
    - ready_for_ingestion -> ingesting (Phase 3.5)
    - ingesting -> ingestion_completed (Phase 3.5 terminal)
    - ingesting -> failed
    - ingestion_completed -> generating_bio (Phase 4)
    - generating_bio -> bio_generated (Phase 4 terminal)
    - generating_bio -> failed
    - bio_generated -> finalizing (Phase 5)
    - finalizing -> completed (Phase 5 terminal)
    - finalizing -> failed
    - completed -> (STOP - Phase 5 ends here)
    - * -> failed (error handling)
    
    Disallowed:
    - completed -> *
    - failed -> crawling
    - ready_for_ingestion -> crawling
    - awaiting_confirmation -> ingesting
    - awaiting_confirmation -> generating_bio
    - ready_for_ingestion -> generating_bio
    - ingestion_completed -> finalizing (must go through bio generation first)
    - bio_generated -> completed (must go through finalizing)
    """
    PLANNING = "planning"           # Initial setup
    QUEUED = "queued"               # Waiting to start crawl
    CRAWLING = "crawling"           # Crawl in progress
    AWAITING_CONFIRMATION = "awaiting_confirmation"  # Paused for user review
    TIMED_OUT = "timed_out"         # Confirmation window expired
    READY_FOR_INGESTION = "ready_for_ingestion"  # Phase 3.4 terminal
    INGESTING = "ingesting"         # Phase 3.5: Ingestion in progress
    INGESTION_COMPLETED = "ingestion_completed"  # Phase 3.5 terminal
    GENERATING_BIO = "generating_bio"  # Phase 4: Bio generation in progress
    BIO_GENERATED = "bio_generated"    # Phase 4 terminal
    FINALIZING = "finalizing"       # Phase 5: Mind score + readiness evaluation
    COMPLETED = "completed"         # Phase 5 terminal (non-terminal if Phase 8 enabled)
    
    # Phase 8: Claims Enrichment
    CLAIMS_ENRICHMENT = "claims_enrichment"
    CLAIMS_COMPLETED = "claims_completed"  # Phase 8 terminal (non-terminal if Phase 9 enabled)
    
    # Phase 9: Web Verification
    WEB_VERIFICATION = "web_verification"
    WEB_VERIFIED = "web_verified"   # Phase 9 terminal (non-terminal if Phase 10 enabled)
    
    # Phase 10: Claim Finalization
    CLAIMS_FINALIZATION = "claims_finalization"
    CLAIMS_FINALIZED = "claims_finalized"  # Phase 10 terminal (non-terminal if Phase 11 enabled)
    
    # Phase 11: Human Adjudication + Canonical Claim Review
    ADJUDICATION = "adjudication"
    ADJUDICATED = "adjudicated"  # Phase 11 terminal (non-terminal if Phase 12 enabled)
    
    # Phase 12: Runtime Publication + Deployment Readiness
    RUNTIME_PUBLICATION = "runtime_publication"
    RUNTIME_PUBLISHED = "runtime_published"  # Phase 12 terminal (pipeline complete)
    
    FAILED = "failed"               # Error state (terminal)


# Valid state transitions map
VALID_TRANSITIONS: Dict[ResearchRunStatus, Set[ResearchRunStatus]] = {
    ResearchRunStatus.PLANNING: {
        ResearchRunStatus.QUEUED,
        ResearchRunStatus.FAILED,
    },
    ResearchRunStatus.QUEUED: {
        ResearchRunStatus.CRAWLING,
        ResearchRunStatus.FAILED,
    },
    ResearchRunStatus.CRAWLING: {
        ResearchRunStatus.AWAITING_CONFIRMATION,
        ResearchRunStatus.READY_FOR_INGESTION,
        ResearchRunStatus.FAILED,
    },
    ResearchRunStatus.AWAITING_CONFIRMATION: {
        ResearchRunStatus.AWAITING_CONFIRMATION,  # Self-transition for refresh
        ResearchRunStatus.READY_FOR_INGESTION,
        ResearchRunStatus.TIMED_OUT,
        ResearchRunStatus.FAILED,
    },
    ResearchRunStatus.TIMED_OUT: {
        ResearchRunStatus.READY_FOR_INGESTION,
        ResearchRunStatus.FAILED,
    },
    ResearchRunStatus.READY_FOR_INGESTION: {
        ResearchRunStatus.INGESTING,  # Phase 3.5
        ResearchRunStatus.FAILED,
    },
    ResearchRunStatus.INGESTING: {
        ResearchRunStatus.INGESTION_COMPLETED,  # Phase 3.5
        ResearchRunStatus.FAILED,
    },
    ResearchRunStatus.INGESTION_COMPLETED: {
        ResearchRunStatus.GENERATING_BIO,  # Phase 4
        ResearchRunStatus.FAILED,
    },
    ResearchRunStatus.GENERATING_BIO: {
        ResearchRunStatus.BIO_GENERATED,  # Phase 4
        ResearchRunStatus.FAILED,
    },
    ResearchRunStatus.BIO_GENERATED: {
        ResearchRunStatus.FINALIZING,  # Phase 5
        ResearchRunStatus.FAILED,
    },
    ResearchRunStatus.FINALIZING: {
        ResearchRunStatus.COMPLETED,  # Phase 5
        ResearchRunStatus.FAILED,
    },
    # Phase 8: Claims Enrichment transitions
    ResearchRunStatus.COMPLETED: {
        ResearchRunStatus.CLAIMS_ENRICHMENT,  # Optional Phase 8
    },
    ResearchRunStatus.CLAIMS_ENRICHMENT: {
        ResearchRunStatus.CLAIMS_COMPLETED,
        ResearchRunStatus.FAILED,
        ResearchRunStatus.CLAIMS_ENRICHMENT,  # Self for idempotency
    },
    ResearchRunStatus.CLAIMS_COMPLETED: {
        ResearchRunStatus.WEB_VERIFICATION,  # Optional Phase 9
        ResearchRunStatus.CLAIMS_COMPLETED,   # Self for idempotency
    },
    
    # Phase 9: Web Verification transitions
    ResearchRunStatus.WEB_VERIFICATION: {
        ResearchRunStatus.WEB_VERIFIED,
        ResearchRunStatus.FAILED,
        ResearchRunStatus.WEB_VERIFICATION,  # Self for idempotency
    },
    ResearchRunStatus.WEB_VERIFIED: {
        ResearchRunStatus.CLAIMS_FINALIZATION,  # Optional Phase 10
        ResearchRunStatus.WEB_VERIFIED,  # Self for idempotency
    },
    
    # Phase 10: Claim Finalization transitions
    ResearchRunStatus.CLAIMS_FINALIZATION: {
        ResearchRunStatus.CLAIMS_FINALIZED,
        ResearchRunStatus.FAILED,
        ResearchRunStatus.CLAIMS_FINALIZATION,  # Self for idempotency
    },
    ResearchRunStatus.CLAIMS_FINALIZED: {
        ResearchRunStatus.ADJUDICATION,  # Optional Phase 11
        ResearchRunStatus.RUNTIME_PUBLICATION,  # Direct to Phase 12 if Phase 11 disabled
        ResearchRunStatus.CLAIMS_FINALIZED,  # Self for idempotency
    },
    
    # Phase 11: Human Adjudication transitions
    ResearchRunStatus.ADJUDICATION: {
        ResearchRunStatus.ADJUDICATED,
        ResearchRunStatus.FAILED,
        ResearchRunStatus.ADJUDICATION,  # Self for idempotency
    },
    ResearchRunStatus.ADJUDICATED: {
        ResearchRunStatus.RUNTIME_PUBLICATION,  # Optional Phase 12
        ResearchRunStatus.ADJUDICATED,  # Self for idempotency
    },
    
    # Phase 12: Runtime Publication transitions
    ResearchRunStatus.RUNTIME_PUBLICATION: {
        ResearchRunStatus.RUNTIME_PUBLISHED,
        ResearchRunStatus.FAILED,
        ResearchRunStatus.RUNTIME_PUBLICATION,  # Self for idempotency
    },
    ResearchRunStatus.RUNTIME_PUBLISHED: {
        ResearchRunStatus.RUNTIME_PUBLISHED,  # Self for idempotency (terminal)
    },
    
    ResearchRunStatus.FAILED: set(),     # Terminal
}


def is_valid_transition(from_status: ResearchRunStatus, to_status: ResearchRunStatus) -> bool:
    """Check if a state transition is valid."""
    if from_status == to_status:
        return True  # Self-transition is always valid (idempotent)
    return to_status in VALID_TRANSITIONS.get(from_status, set())


# ============================================================================
# Result Models
# ============================================================================

@dataclass
class CreateResearchRunResult:
    """Result of creating a research run."""
    research_run_id: str
    twin_id: str
    status: str
    created_at: str
    error: Optional[str] = None


@dataclass
class TransitionResult:
    """Result of a state transition."""
    success: bool
    research_run_id: str
    previous_status: str
    new_status: str
    checkpoint_updated: bool
    transition_reason: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ConfirmationCheckpointData:
    """Confirmation snapshot for checkpoint."""
    total: int
    pending: int
    manual_review: int
    auto_confirmed: int
    auto_rejected: int
    confirmed: int
    rejected: int
    all_resolved: bool
    resolution_percent: float


@dataclass
class IngestionCheckpointData:
    """Phase 3.5: Ingestion summary for checkpoint."""
    require_confirmation: bool
    pages_eligible: int
    pages_ingested: int
    pages_skipped: int
    rejected_skipped: int
    unresolved_skipped: int
    tombstone_actions: int
    errors: List[str]


@dataclass
class BioGenerationCheckpointData:
    """Phase 4: Bio generation summary for checkpoint."""
    triggered: bool
    source_url_count: int
    source_selection_policy: str
    persona_pipeline: str
    status: str  # success, failed, insufficient_data
    bio_variant_count: int
    selected_variant_id: Optional[str]
    result_refs: Dict[str, Any]  # job_id, session_id, etc.
    errors: List[str]


@dataclass
class MindScoreCheckpointData:
    """Phase 5: Mind score summary for checkpoint."""
    status: str  # success, failed
    score: int
    label: str
    words_processed: int
    questions_answerable_estimate: int
    updated_at: str
    errors: List[str]


@dataclass
class ReadinessCheckpointData:
    """Phase 5: Readiness evaluation summary for checkpoint."""
    status: str  # evaluated, failed
    is_ready: bool
    thresholds: Dict[str, int]
    requirements: Dict[str, bool]
    counts: Dict[str, int]
    errors: List[str]


@dataclass
class CheckpointData:
    """Full checkpoint payload for resume capability."""
    phase: str
    last_transition_at: str
    crawl_id: Optional[str] = None
    confirmation: Optional[ConfirmationCheckpointData] = None
    ingestion: Optional[IngestionCheckpointData] = None  # Phase 3.5
    bio_generation: Optional[BioGenerationCheckpointData] = None  # Phase 4
    mind_score: Optional[MindScoreCheckpointData] = None  # Phase 5
    readiness: Optional[ReadinessCheckpointData] = None  # Phase 5
    claimed_identity: Optional[Dict[str, Any]] = None
    seed_urls_count: int = 0
    timeout_at: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class ResearchRunStatusResult:
    """Full status response for polling."""
    research_run_id: str
    twin_id: str
    status: str
    crawl_id: Optional[str]
    checkpoint_data: Dict[str, Any]
    confirmation_summary: Optional[ConfirmationSummary]
    created_at: str
    updated_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    next_actions: List[str]  # Phase 6: Canonical field name (plural)
    warnings: List[str]
    
    @property
    def next_action(self) -> str:
        """Backward compatibility alias for next_actions[0] or 'none'."""
        return self.next_actions[0] if self.next_actions else "none"


# ============================================================================
# Research Repository
# ============================================================================

class ResearchRepository:
    """
    Data access layer for research runs.
    
    Responsibilities:
    - Create research run records
    - Update status/checkpoint safely
    - Fetch by (research_run_id, twin_id)
    - Store timestamps
    """
    
    @staticmethod
    def create_research_run(
        twin_id: str,
        actor_user_id: str,
        claimed_identity: Dict[str, Any],
        seed_urls: List[str],
        onboarding_session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create a new research run record.
        
        Returns:
            research_run_id
        """
        research_run_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        # Build initial checkpoint
        checkpoint = CheckpointData(
            phase=ResearchRunStatus.PLANNING.value,
            last_transition_at=now,
            claimed_identity=claimed_identity,
            seed_urls_count=len(seed_urls),
        )
        
        insert_data = {
            "id": research_run_id,
            "twin_id": twin_id,
            "input_question": f"Research for {claimed_identity.get('full_name', 'unknown')}",
            "status": ResearchRunStatus.PLANNING.value,
            "current_phase": ResearchRunStatus.PLANNING.value,
            "checkpoint_data": {
                "phase": checkpoint.phase,
                "last_transition_at": checkpoint.last_transition_at,
                "claimed_identity": checkpoint.claimed_identity,
                "seed_urls_count": checkpoint.seed_urls_count,
            },
            "created_at": now,
            "updated_at": now,
        }
        
        # Add optional metadata
        if onboarding_session_id:
            insert_data["onboarding_session_id"] = onboarding_session_id
        
        # Store full config in checkpoint
        if metadata:
            insert_data["checkpoint_data"]["metadata"] = metadata
        
        try:
            supabase.table("research_runs").insert(insert_data).execute()
            return research_run_id
        except Exception as e:
            logger.error(f"Error creating research run: {e}")
            raise
    
    @staticmethod
    def get_research_run(research_run_id: str, twin_id: str) -> Optional[Dict[str, Any]]:
        """Fetch research run by ID with twin scoping."""
        try:
            response = supabase.table("research_runs").select("*").eq(
                "id", research_run_id
            ).eq("twin_id", twin_id).single().execute()
            
            return response.data
        except Exception as e:
            logger.error(f"Error fetching research run: {e}")
            return None
    
    @staticmethod
    def update_status(
        research_run_id: str,
        new_status: str,
        checkpoint_data: Optional[Dict[str, Any]] = None,
        crawl_id: Optional[str] = None,
    ) -> bool:
        """Update research run status and checkpoint."""
        try:
            update_data = {
                "status": new_status,
                "current_phase": new_status,
                "updated_at": datetime.utcnow().isoformat(),
            }
            
            if checkpoint_data:
                update_data["checkpoint_data"] = checkpoint_data
            
            if crawl_id:
                update_data["crawl_id"] = crawl_id
            
            # Set started_at on first non-planning status
            if new_status not in (ResearchRunStatus.PLANNING.value,):
                # Only set if not already set
                existing = supabase.table("research_runs").select("started_at").eq(
                    "id", research_run_id
                ).single().execute()
                if existing.data and not existing.data.get("started_at"):
                    update_data["started_at"] = datetime.utcnow().isoformat()
            
            # Set completed_at for terminal statuses
            if new_status in (ResearchRunStatus.READY_FOR_INGESTION.value, ResearchRunStatus.COMPLETED.value, ResearchRunStatus.FAILED.value):
                update_data["completed_at"] = datetime.utcnow().isoformat()
            
            supabase.table("research_runs").update(update_data).eq(
                "id", research_run_id
            ).execute()
            
            return True
        except Exception as e:
            logger.error(f"Error updating research run status: {e}")
            return False


# ============================================================================
# Research Orchestrator
# ============================================================================

class ResearchOrchestrator:
    """
    Orchestrates research run lifecycle with state machine and checkpointing.
    
    Phase 3.4 responsibilities:
    - Create research runs from onboarding input
    - Track crawl progress
    - Pause at confirmation gate
    - Resume when confirmed or timed out
    - Stop at ready_for_ingestion (Phase 3.5 continues)
    """
    
    def __init__(
        self,
        repository: Optional[ResearchRepository] = None,
        confirmation_manager: Optional[SourceConfirmationManager] = None,
        confirmation_timeout_hours: int = 24,
    ):
        """
        Initialize orchestrator.
        
        Args:
            repository: Research run persistence layer
            confirmation_manager: Source confirmation workflow
            confirmation_timeout_hours: Hours to wait for confirmations
        """
        self.repository = repository or ResearchRepository()
        self.confirmation_manager = confirmation_manager or SourceConfirmationManager()
        self.confirmation_timeout_hours = confirmation_timeout_hours
    
    async def create_research_run(
        self,
        twin_id: str,
        actor_user_id: str,
        claimed_identity: Dict[str, Any],
        seed_urls: List[str],
        onboarding_session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CreateResearchRunResult:
        """
        Create a new research run from onboarding input.
        
        Args:
            twin_id: Twin ID
            actor_user_id: User creating the run
            claimed_identity: {full_name, location, submitted_links, ...}
            seed_urls: URLs to crawl
            onboarding_session_id: Optional onboarding session link
            metadata: Additional config/metadata
        
        Returns:
            CreateResearchRunResult
        """
        try:
            research_run_id = self.repository.create_research_run(
                twin_id=twin_id,
                actor_user_id=actor_user_id,
                claimed_identity=claimed_identity,
                seed_urls=seed_urls,
                onboarding_session_id=onboarding_session_id,
                metadata=metadata,
            )
            
            # Transition to queued immediately
            await self._transition(
                research_run_id=research_run_id,
                to_status=ResearchRunStatus.QUEUED,
                reason="Run created from onboarding",
            )
            
            run = self.repository.get_research_run(research_run_id, twin_id)
            
            return CreateResearchRunResult(
                research_run_id=research_run_id,
                twin_id=twin_id,
                status=ResearchRunStatus.QUEUED.value,
                created_at=run.get("created_at") if run else datetime.utcnow().isoformat(),
            )
            
        except Exception as e:
            logger.error(f"Error creating research run: {e}")
            return CreateResearchRunResult(
                research_run_id="",
                twin_id=twin_id,
                status="",
                created_at="",
                error=str(e),
            )
    
    async def mark_crawl_started(
        self,
        research_run_id: str,
        twin_id: str,
    ) -> TransitionResult:
        """
        Mark that crawl has started.
        
        Args:
            research_run_id: Research run ID
            twin_id: Twin ID for authorization
        
        Returns:
            TransitionResult
        """
        return await self._transition(
            research_run_id=research_run_id,
            twin_id=twin_id,
            to_status=ResearchRunStatus.CRAWLING,
            reason="Crawl job started",
        )
    
    async def on_crawl_completed(
        self,
        research_run_id: str,
        twin_id: str,
        crawl_id: str,
    ) -> TransitionResult:
        """
        Handle crawl completion.
        
        Phase 3.4 behavior:
        1. Create confirmations from crawl pages
        2. Inspect confirmation summary
        3. If unresolved items exist -> awaiting_confirmation
        4. If all resolved -> ready_for_ingestion
        
        Args:
            research_run_id: Research run ID
            twin_id: Twin ID for authorization
            crawl_id: Completed crawl ID
        
        Returns:
            TransitionResult
        """
        # Verify current status
        run = self.repository.get_research_run(research_run_id, twin_id)
        if not run:
            return TransitionResult(
                success=False,
                research_run_id=research_run_id,
                previous_status="",
                new_status="",
                checkpoint_updated=False,
                error="Research run not found",
            )
        
        current_status = ResearchRunStatus(run.get("status", "planning"))
        
        # Must be in CRAWLING status
        if current_status != ResearchRunStatus.CRAWLING:
            return TransitionResult(
                success=False,
                research_run_id=research_run_id,
                previous_status=current_status.value,
                new_status=current_status.value,
                checkpoint_updated=False,
                error=f"Cannot complete crawl from status: {current_status.value}",
            )
        
        # Create confirmations from crawl
        creation_result = await self.confirmation_manager.create_confirmations_for_crawl(
            research_run_id=research_run_id,
            crawl_id=crawl_id,
            twin_id=twin_id,
        )
        
        if creation_result.error:
            logger.error(f"Error creating confirmations: {creation_result.error}")
            # Still proceed to check summary (may have partial confirmations)
        
        # Get confirmation summary
        summary = await self.confirmation_manager.get_confirmation_summary(
            research_run_id=research_run_id,
            twin_id=twin_id,
        )
        
        # Build checkpoint with confirmation data
        checkpoint = self._build_checkpoint(
            phase="crawl_completed",
            crawl_id=crawl_id,
            summary=summary,
        )
        
        # Determine next status
        if summary.all_resolved:
            # All confirmations auto-resolved, proceed directly
            return await self._transition(
                research_run_id=research_run_id,
                twin_id=twin_id,
                to_status=ResearchRunStatus.READY_FOR_INGESTION,
                reason="All confirmations auto-resolved",
                checkpoint=checkpoint,
                crawl_id=crawl_id,
            )
        else:
            # Need user confirmation, pause at gate
            # Set timeout
            timeout_at = (datetime.utcnow() + timedelta(
                hours=self.confirmation_timeout_hours
            )).isoformat()
            checkpoint.timeout_at = timeout_at
            
            return await self._transition(
                research_run_id=research_run_id,
                twin_id=twin_id,
                to_status=ResearchRunStatus.AWAITING_CONFIRMATION,
                reason=f"Awaiting user confirmation: {summary.pending} pending, {summary.manual_review} manual_review, {summary.auto_rejected} auto_rejected",
                checkpoint=checkpoint,
                crawl_id=crawl_id,
            )
    
    async def on_confirmations_updated(
        self,
        research_run_id: str,
        twin_id: str,
    ) -> TransitionResult:
        """
        Handle confirmation updates (called after confirm/reject actions).
        
        Phase 3.4 behavior:
        - Check confirmation summary
        - If all resolved -> ready_for_ingestion
        - Else remain in awaiting_confirmation
        
        Args:
            research_run_id: Research run ID
            twin_id: Twin ID for authorization
        
        Returns:
            TransitionResult
        """
        # Verify current status
        run = self.repository.get_research_run(research_run_id, twin_id)
        if not run:
            return TransitionResult(
                success=False,
                research_run_id=research_run_id,
                previous_status="",
                new_status="",
                checkpoint_updated=False,
                error="Research run not found",
            )
        
        current_status = ResearchRunStatus(run.get("status", "planning"))
        
        # Can only be called from AWAITING_CONFIRMATION or TIMED_OUT
        if current_status not in (
            ResearchRunStatus.AWAITING_CONFIRMATION,
            ResearchRunStatus.TIMED_OUT,
        ):
            # Idempotent no-op if not in confirmation phase
            return TransitionResult(
                success=True,
                research_run_id=research_run_id,
                previous_status=current_status.value,
                new_status=current_status.value,
                checkpoint_updated=False,
                transition_reason=f"No-op: not in confirmation phase (status: {current_status.value})",
            )
        
        # Get updated summary
        summary = await self.confirmation_manager.get_confirmation_summary(
            research_run_id=research_run_id,
            twin_id=twin_id,
        )
        
        # Build checkpoint
        checkpoint = self._build_checkpoint(
            phase="confirmations_updated",
            crawl_id=run.get("crawl_id"),
            summary=summary,
        )
        
        # Check if all resolved
        if summary.all_resolved:
            return await self._transition(
                research_run_id=research_run_id,
                twin_id=twin_id,
                to_status=ResearchRunStatus.READY_FOR_INGESTION,
                reason="All confirmations resolved by user",
                checkpoint=checkpoint,
            )
        else:
            # Remain in awaiting_confirmation, update checkpoint
            return await self._transition(
                research_run_id=research_run_id,
                twin_id=twin_id,
                to_status=current_status,  # Self-transition
                reason=f"Still awaiting: {summary.pending} pending, {summary.manual_review} manual_review, {summary.auto_rejected} auto_rejected",
                checkpoint=checkpoint,
            )
    
    async def handle_confirmation_timeout(
        self,
        research_run_id: str,
        twin_id: str,
        timeout_hours: Optional[int] = None,
    ) -> TransitionResult:
        """
        Handle confirmation timeout.
        
        Phase 3.4 policy:
        - Transition to TIMED_OUT status
        - Then proceed to ready_for_ingestion
        - Preserve unresolved counts in checkpoint warnings
        - Do NOT ingest in this phase
        
        Args:
            research_run_id: Research run ID
            twin_id: Twin ID for authorization
            timeout_hours: Override default timeout
        
        Returns:
            TransitionResult
        """
        run = self.repository.get_research_run(research_run_id, twin_id)
        if not run:
            return TransitionResult(
                success=False,
                research_run_id=research_run_id,
                previous_status="",
                new_status="",
                checkpoint_updated=False,
                error="Research run not found",
            )
        
        current_status = ResearchRunStatus(run.get("status", "planning"))
        
        # Can only timeout from AWAITING_CONFIRMATION
        if current_status != ResearchRunStatus.AWAITING_CONFIRMATION:
            return TransitionResult(
                success=False,
                research_run_id=research_run_id,
                previous_status=current_status.value,
                new_status=current_status.value,
                checkpoint_updated=False,
                error=f"Cannot timeout from status: {current_status.value}",
            )
        
        # Get current summary for warnings
        summary = await self.confirmation_manager.get_confirmation_summary(
            research_run_id=research_run_id,
            twin_id=twin_id,
        )
        
        # Build warnings
        warnings = []
        if summary.pending > 0:
            warnings.append(f"{summary.pending} confirmations left pending on timeout")
        if summary.manual_review > 0:
            warnings.append(f"{summary.manual_review} manual_review confirmations unresolved")
        if summary.auto_rejected > 0:
            warnings.append(f"{summary.auto_rejected} auto_rejected confirmations not reviewed")
        
        # First transition to TIMED_OUT
        checkpoint = self._build_checkpoint(
            phase="confirmation_timeout",
            crawl_id=run.get("crawl_id"),
            summary=summary,
        )
        checkpoint.warnings = warnings
        
        timeout_result = await self._transition(
            research_run_id=research_run_id,
            twin_id=twin_id,
            to_status=ResearchRunStatus.TIMED_OUT,
            reason=f"Confirmation window expired after {timeout_hours or self.confirmation_timeout_hours} hours",
            checkpoint=checkpoint,
        )
        
        if not timeout_result.success:
            return timeout_result
        
        # Then proceed to ready_for_ingestion
        return await self._transition(
            research_run_id=research_run_id,
            twin_id=twin_id,
            to_status=ResearchRunStatus.READY_FOR_INGESTION,
            reason="Proceeding after timeout with unresolved confirmations",
            checkpoint=checkpoint,
        )
    
    async def continue_to_ingestion(
        self,
        research_run_id: str,
        twin_id: str,
    ) -> TransitionResult:
        """
        Phase 3.5: Continue from ready_for_ingestion to ingestion completion.
        
        Behavior:
        - Validate current state is ready_for_ingestion (or timeout-derived ready state)
        - Transition to ingesting
        - Call crawl_ingestion_bridge with require_confirmation=True
        - Persist ingestion stats in checkpoint_data
        - Transition to ingestion_completed (Phase 3.5 terminal)
        - Do NOT trigger bio generation or mind score updates
        
        Idempotent: If already in ingestion_completed, returns no-op success.
        
        Args:
            research_run_id: Research run ID
            twin_id: Twin ID for authorization
        
        Returns:
            TransitionResult with ingestion summary
        """
        # Verify current status
        run = self.repository.get_research_run(research_run_id, twin_id)
        if not run:
            return TransitionResult(
                success=False,
                research_run_id=research_run_id,
                previous_status="",
                new_status="",
                checkpoint_updated=False,
                error="Research run not found",
            )
        
        current_status = ResearchRunStatus(run.get("status", "planning"))
        crawl_id = run.get("crawl_id")
        
        # Idempotent: already completed
        if current_status == ResearchRunStatus.INGESTION_COMPLETED:
            return TransitionResult(
                success=True,
                research_run_id=research_run_id,
                previous_status=current_status.value,
                new_status=current_status.value,
                checkpoint_updated=False,
                transition_reason="Already in ingestion_completed state (idempotent)",
            )
        
        # Can only continue from READY_FOR_INGESTION
        if current_status != ResearchRunStatus.READY_FOR_INGESTION:
            return TransitionResult(
                success=False,
                research_run_id=research_run_id,
                previous_status=current_status.value,
                new_status=current_status.value,
                checkpoint_updated=False,
                error=f"Cannot continue to ingestion from status: {current_status.value}. Must be ready_for_ingestion.",
            )
        
        if not crawl_id:
            return TransitionResult(
                success=False,
                research_run_id=research_run_id,
                previous_status=current_status.value,
                new_status=current_status.value,
                checkpoint_updated=False,
                error="No crawl_id associated with research run",
            )
        
        # Get confirmation summary for checkpoint
        summary = await self.confirmation_manager.get_confirmation_summary(
            research_run_id=research_run_id,
            twin_id=twin_id,
        )
        
        # Build initial checkpoint (entering ingestion)
        initial_checkpoint = self._build_checkpoint(
            phase="ingesting",
            crawl_id=crawl_id,
            summary=summary,
        )
        
        # Transition to ingesting
        ingest_start_result = await self._transition(
            research_run_id=research_run_id,
            twin_id=twin_id,
            to_status=ResearchRunStatus.INGESTING,
            reason="Starting confirmation-gated ingestion",
            checkpoint=initial_checkpoint,
        )
        
        if not ingest_start_result.success:
            return ingest_start_result
        
        # Perform gated ingestion
        try:
            from modules.crawl_ingestion_bridge import CrawlIngestionBridge
            
            bridge = CrawlIngestionBridge()
            ingestion_stats = await bridge.process_crawl_for_ingestion(
                crawl_id=crawl_id,
                twin_id=twin_id,
                require_confirmation=True,
                research_run_id=research_run_id,
            )
            
            # Build ingestion checkpoint data
            ingestion_checkpoint = IngestionCheckpointData(
                require_confirmation=True,
                pages_eligible=ingestion_stats.get("pages_confirmed_eligible", 0),
                pages_ingested=ingestion_stats.get("sources_created", 0),
                pages_skipped=ingestion_stats.get("pages_skipped_not_confirmed", 0) + 
                             ingestion_stats.get("pages_skipped_rejected", 0),
                rejected_skipped=ingestion_stats.get("pages_skipped_rejected", 0),
                unresolved_skipped=ingestion_stats.get("pages_skipped_not_confirmed", 0),
                tombstone_actions=0,  # Placeholder: tombstone logic deferred
                errors=[],
            )
            
            # Build final checkpoint
            final_checkpoint = self._build_checkpoint(
                phase="ingestion_completed",
                crawl_id=crawl_id,
                summary=summary,
            )
            final_checkpoint.ingestion = ingestion_checkpoint
            
            # Transition to ingestion_completed
            return await self._transition(
                research_run_id=research_run_id,
                twin_id=twin_id,
                to_status=ResearchRunStatus.INGESTION_COMPLETED,
                reason=f"Ingestion complete: {ingestion_checkpoint.pages_ingested} pages ingested, {ingestion_checkpoint.pages_skipped} skipped",
                checkpoint=final_checkpoint,
            )
            
        except Exception as e:
            logger.error(f"Phase 3.5: Ingestion failed for run {research_run_id}: {e}")
            
            # Build failure checkpoint
            failure_checkpoint = self._build_checkpoint(
                phase="ingestion_failed",
                crawl_id=crawl_id,
                summary=summary,
            )
            failure_checkpoint.ingestion = IngestionCheckpointData(
                require_confirmation=True,
                pages_eligible=0,
                pages_ingested=0,
                pages_skipped=0,
                rejected_skipped=0,
                unresolved_skipped=0,
                tombstone_actions=0,
                errors=[str(e)],
            )
            failure_checkpoint.warnings.append(f"Ingestion failed: {e}")
            
            # Transition to failed
            return await self._transition(
                research_run_id=research_run_id,
                twin_id=twin_id,
                to_status=ResearchRunStatus.FAILED,
                reason=f"Ingestion failed: {e}",
                checkpoint=failure_checkpoint,
            )
    
    async def _get_confirmed_source_urls(
        self,
        research_run_id: str,
        twin_id: str,
        max_urls: int = 10,
    ) -> List[str]:
        """
        Phase 4: Get confirmed source URLs for bio generation.
        
        Selects only confirmed and auto_confirmed sources from source_confirmations.
        Deduplicates canonical URLs and applies stable ordering.
        
        Args:
            research_run_id: Research run ID
            twin_id: Twin ID for scoping
            max_urls: Maximum URLs to return (persona pipeline limit)
            
        Returns:
            List of canonical URLs (deduplicated, sorted by confidence desc, created_at asc)
        """
        try:
            # Query confirmed sources with their metadata
            response = supabase.table("source_confirmations").select(
                "crawl_page_id, status, identity_confidence_score, created_at"
            ).eq("research_run_id", research_run_id).eq("twin_id", twin_id).in_(
                "status", ["confirmed", "auto_confirmed"]
            ).order("identity_confidence_score", desc=True).order("created_at").execute()
            
            if not response.data:
                return []
            
            # Get crawl page IDs
            page_ids = [row["crawl_page_id"] for row in response.data if row.get("crawl_page_id")]
            
            if not page_ids:
                return []
            
            # Fetch canonical URLs from crawl_pages
            # Note: Using 'in' with a list - may need batching for large lists
            pages_response = supabase.table("crawl_pages").select(
                "id, canonical_url"
            ).in_("id", page_ids).execute()
            
            if not pages_response.data:
                return []
            
            # Build URL mapping preserving order from confirmation query
            url_map = {p["id"]: p.get("canonical_url", "") for p in pages_response.data}
            
            # Deduplicate URLs while preserving order (highest confidence first)
            seen_urls = set()
            unique_urls = []
            
            for row in response.data:
                page_id = row.get("crawl_page_id")
                url = url_map.get(page_id, "")
                
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    unique_urls.append(url)
                    
                    if len(unique_urls) >= max_urls:
                        break
            
            logger.info(f"Phase 4: Selected {len(unique_urls)} confirmed URLs for bio generation (max: {max_urls})")
            return unique_urls
            
        except Exception as e:
            logger.error(f"Phase 4: Error fetching confirmed source URLs: {e}")
            return []
    
    async def continue_to_bio_generation(
        self,
        research_run_id: str,
        twin_id: str,
    ) -> TransitionResult:
        """
        Phase 4: Continue from ingestion_completed to bio generation completion.
        
        Behavior:
        - Validate current state is ingestion_completed
        - Transition to generating_bio
        - Collect confirmed source URLs (confirmed + auto_confirmed only)
        - Trigger existing persona_link_compile bio generation flow
        - Persist bio generation result summary in checkpoint_data
        - Transition to bio_generated (Phase 4 terminal)
        - Do NOT update mind score
        - Do NOT compute twin readiness
        
        Idempotent: If already in bio_generated, returns no-op success.
        
        Args:
            research_run_id: Research run ID
            twin_id: Twin ID for authorization
        
        Returns:
            TransitionResult with bio generation summary
        """
        # Verify current status
        run = self.repository.get_research_run(research_run_id, twin_id)
        if not run:
            return TransitionResult(
                success=False,
                research_run_id=research_run_id,
                previous_status="",
                new_status="",
                checkpoint_updated=False,
                error="Research run not found",
            )
        
        current_status = ResearchRunStatus(run.get("status", "planning"))
        crawl_id = run.get("crawl_id")
        
        # Idempotent: already completed
        if current_status == ResearchRunStatus.BIO_GENERATED:
            return TransitionResult(
                success=True,
                research_run_id=research_run_id,
                previous_status=current_status.value,
                new_status=current_status.value,
                checkpoint_updated=False,
                transition_reason="Already in bio_generated state (idempotent)",
            )
        
        # Can only continue from INGESTION_COMPLETED
        if current_status != ResearchRunStatus.INGESTION_COMPLETED:
            return TransitionResult(
                success=False,
                research_run_id=research_run_id,
                previous_status=current_status.value,
                new_status=current_status.value,
                checkpoint_updated=False,
                error=f"Cannot continue to bio generation from status: {current_status.value}. Must be ingestion_completed.",
            )
        
        # Get existing checkpoint data
        existing_checkpoint = run.get("checkpoint_data", {})
        
        # Build initial checkpoint (entering bio generation)
        initial_bio_checkpoint = BioGenerationCheckpointData(
            triggered=True,
            source_url_count=0,
            source_selection_policy="confirmed_only",
            persona_pipeline="persona_link_compile",
            status="in_progress",
            bio_variant_count=0,
            selected_variant_id=None,
            result_refs={},
            errors=[],
        )
        
        initial_checkpoint = self._build_checkpoint(
            phase="generating_bio",
            crawl_id=crawl_id,
            summary=None,  # Will preserve existing confirmation data
        )
        initial_checkpoint.bio_generation = initial_bio_checkpoint
        
        # Preserve existing ingestion data from checkpoint
        if existing_checkpoint.get("ingestion"):
            # Reconstruct ingestion data from existing checkpoint
            ing_dict = existing_checkpoint["ingestion"]
            initial_checkpoint.ingestion = IngestionCheckpointData(
                require_confirmation=ing_dict.get("require_confirmation", True),
                pages_eligible=ing_dict.get("pages_eligible", 0),
                pages_ingested=ing_dict.get("pages_ingested", 0),
                pages_skipped=ing_dict.get("pages_skipped", 0),
                rejected_skipped=ing_dict.get("rejected_skipped", 0),
                unresolved_skipped=ing_dict.get("unresolved_skipped", 0),
                tombstone_actions=ing_dict.get("tombstone_actions", 0),
                errors=ing_dict.get("errors", []),
            )
        
        if existing_checkpoint.get("confirmation"):
            conf_dict = existing_checkpoint["confirmation"]
            initial_checkpoint.confirmation = ConfirmationCheckpointData(
                total=conf_dict.get("total", 0),
                pending=conf_dict.get("pending", 0),
                manual_review=conf_dict.get("manual_review", 0),
                auto_confirmed=conf_dict.get("auto_confirmed", 0),
                auto_rejected=conf_dict.get("auto_rejected", 0),
                confirmed=conf_dict.get("confirmed", 0),
                rejected=conf_dict.get("rejected", 0),
                all_resolved=conf_dict.get("all_resolved", False),
                resolution_percent=conf_dict.get("resolution_percent", 0.0),
            )
        
        # Transition to generating_bio
        bio_start_result = await self._transition(
            research_run_id=research_run_id,
            twin_id=twin_id,
            to_status=ResearchRunStatus.GENERATING_BIO,
            reason="Starting bio generation from confirmed sources",
            checkpoint=initial_checkpoint,
        )
        
        if not bio_start_result.success:
            return bio_start_result
        
        # Perform bio generation
        try:
            # Get confirmed source URLs
            confirmed_urls = await self._get_confirmed_source_urls(
                research_run_id=research_run_id,
                twin_id=twin_id,
                max_urls=10,
            )
            
            if not confirmed_urls:
                # No confirmed sources - mark as failed with insufficient data
                final_bio_checkpoint = BioGenerationCheckpointData(
                    triggered=True,
                    source_url_count=0,
                    source_selection_policy="confirmed_only",
                    persona_pipeline="persona_link_compile",
                    status="insufficient_data",
                    bio_variant_count=0,
                    selected_variant_id=None,
                    result_refs={},
                    errors=["No confirmed sources available for bio generation"],
                )
                
                final_checkpoint = self._build_checkpoint(
                    phase="bio_generated",
                    crawl_id=crawl_id,
                    summary=None,
                )
                final_checkpoint.bio_generation = final_bio_checkpoint
                final_checkpoint.ingestion = initial_checkpoint.ingestion
                final_checkpoint.confirmation = initial_checkpoint.confirmation
                
                return await self._transition(
                    research_run_id=research_run_id,
                    twin_id=twin_id,
                    to_status=ResearchRunStatus.BIO_GENERATED,
                    reason="Bio generation skipped: no confirmed sources",
                    checkpoint=final_checkpoint,
                )
            
            # Phase 4: Trigger existing persona bio generation
            # Using the existing persona_link_compile flow additively
            bio_result = await self._trigger_persona_bio_generation(
                twin_id=twin_id,
                source_urls=confirmed_urls,
            )
            
            # Build final checkpoint
            final_bio_checkpoint = BioGenerationCheckpointData(
                triggered=True,
                source_url_count=len(confirmed_urls),
                source_selection_policy="confirmed_only",
                persona_pipeline="persona_link_compile",
                status="success" if bio_result.get("success") else "failed",
                bio_variant_count=bio_result.get("variant_count", 0),
                selected_variant_id=bio_result.get("selected_variant_id"),
                result_refs={
                    "job_id": bio_result.get("job_id"),
                    "session_id": bio_result.get("session_id"),
                },
                errors=bio_result.get("errors", []),
            )
            
            final_checkpoint = self._build_checkpoint(
                phase="bio_generated",
                crawl_id=crawl_id,
                summary=None,
            )
            final_checkpoint.bio_generation = final_bio_checkpoint
            final_checkpoint.ingestion = initial_checkpoint.ingestion
            final_checkpoint.confirmation = initial_checkpoint.confirmation
            
            # Transition to bio_generated
            return await self._transition(
                research_run_id=research_run_id,
                twin_id=twin_id,
                to_status=ResearchRunStatus.BIO_GENERATED,
                reason=f"Bio generation complete: {final_bio_checkpoint.bio_variant_count} variants from {len(confirmed_urls)} sources",
                checkpoint=final_checkpoint,
            )
            
        except Exception as e:
            logger.error(f"Phase 4: Bio generation failed for run {research_run_id}: {e}")
            
            # Build failure checkpoint
            failure_bio_checkpoint = BioGenerationCheckpointData(
                triggered=True,
                source_url_count=0,
                source_selection_policy="confirmed_only",
                persona_pipeline="persona_link_compile",
                status="failed",
                bio_variant_count=0,
                selected_variant_id=None,
                result_refs={},
                errors=[str(e)],
            )
            
            failure_checkpoint = self._build_checkpoint(
                phase="bio_generation_failed",
                crawl_id=crawl_id,
                summary=None,
            )
            failure_checkpoint.bio_generation = failure_bio_checkpoint
            failure_checkpoint.ingestion = initial_checkpoint.ingestion
            failure_checkpoint.confirmation = initial_checkpoint.confirmation
            failure_checkpoint.warnings.append(f"Bio generation failed: {e}")
            
            # Transition to failed
            return await self._transition(
                research_run_id=research_run_id,
                twin_id=twin_id,
                to_status=ResearchRunStatus.FAILED,
                reason=f"Bio generation failed: {e}",
                checkpoint=failure_checkpoint,
            )
    
    async def _trigger_persona_bio_generation(
        self,
        twin_id: str,
        source_urls: List[str],
    ) -> Dict[str, Any]:
        """
        Phase 4: Trigger existing persona bio generation pipeline.
        
        This is an additive integration with the existing persona_link_compile flow.
        Uses Mode C (URL-based) ingestion and bio generation.
        
        Args:
            twin_id: Twin ID
            source_urls: List of confirmed source URLs
            
        Returns:
            Bio generation result summary
        """
        try:
            # Import here to avoid circular dependencies
            from modules.persona_bio_generator import generate_and_store_bios
            from modules.persona_claim_extractor import extract_and_store_claims, ClaimExtractor
            from modules.retrieval import retrieve_for_twin
            
            logger.info(f"Phase 4: Triggering persona bio generation for twin {twin_id} with {len(source_urls)} sources")
            
            # Step 1: Retrieve chunks for the confirmed sources
            # This uses the already-ingested content from Phase 3.5
            all_chunks = []
            for url in source_urls:
                try:
                    # Retrieve chunks for this URL
                    chunks = retrieve_for_twin(
                        twin_id=twin_id,
                        query=f"content from {url}",
                        top_k=10,
                        filters={"citation_url": url},
                    )
                    if chunks:
                        all_chunks.extend(chunks)
                except Exception as e:
                    logger.warning(f"Phase 4: Failed to retrieve chunks for {url}: {e}")
            
            if not all_chunks:
                return {
                    "success": False,
                    "variant_count": 0,
                    "errors": ["No chunks retrieved from confirmed sources"],
                }
            
            # Step 2: Extract claims from chunks
            logger.info(f"Phase 4: Extracting claims from {len(all_chunks)} chunks")
            extractor = ClaimExtractor()
            claims = await extractor.extract_from_chunks(all_chunks, twin_id)
            
            if not claims:
                return {
                    "success": False,
                    "variant_count": 0,
                    "errors": ["No claims extracted from sources"],
                }
            
            # Step 3: Generate bios from claims
            logger.info(f"Phase 4: Generating bios from {len(claims)} claims")
            bio_result = await generate_and_store_bios(
                twin_id=twin_id,
                claims=[c.to_dict() if hasattr(c, 'to_dict') else c for c in claims],
                supabase_client=supabase,
            )
            
            return {
                "success": bio_result.get("valid_count", 0) > 0,
                "variant_count": bio_result.get("valid_count", 0),
                "generated_count": bio_result.get("generated_count", 0),
                "variant_ids": bio_result.get("variant_ids", []),
                "job_id": None,  # Would be set if using async job
                "session_id": None,
                "errors": [],
            }
            
        except Exception as e:
            logger.error(f"Phase 4: Error in persona bio generation: {e}")
            return {
                "success": False,
                "variant_count": 0,
                "errors": [str(e)],
            }
    
    async def continue_to_finalize_research_run(
        self,
        research_run_id: str,
        twin_id: str,
    ) -> TransitionResult:
        """
        Phase 5: Continue from bio_generated to completed (finalization).
        
        Behavior:
        - Validate current state is bio_generated
        - Transition to finalizing
        - Call existing training_metrics update hook
        - Persist mind score summary in checkpoint_data
        - Evaluate twin readiness using TwinReadinessChecker
        - Persist readiness summary in checkpoint_data
        - Transition to completed (Phase 5 terminal)
        - Do NOT update mind score directly (training_metrics hook does this)
        
        Idempotent: If already in completed, returns no-op success.
        
        Args:
            research_run_id: Research run ID
            twin_id: Twin ID for authorization
        
        Returns:
            TransitionResult with finalization summary
        """
        # Verify current status
        run = self.repository.get_research_run(research_run_id, twin_id)
        if not run:
            return TransitionResult(
                success=False,
                research_run_id=research_run_id,
                previous_status="",
                new_status="",
                checkpoint_updated=False,
                error="Research run not found",
            )
        
        current_status = ResearchRunStatus(run.get("status", "planning"))
        crawl_id = run.get("crawl_id")
        
        # Idempotent: already completed
        if current_status == ResearchRunStatus.COMPLETED:
            return TransitionResult(
                success=True,
                research_run_id=research_run_id,
                previous_status=current_status.value,
                new_status=current_status.value,
                checkpoint_updated=False,
                transition_reason="Already in completed state (idempotent)",
            )
        
        # Can only continue from BIO_GENERATED
        if current_status != ResearchRunStatus.BIO_GENERATED:
            return TransitionResult(
                success=False,
                research_run_id=research_run_id,
                previous_status=current_status.value,
                new_status=current_status.value,
                checkpoint_updated=False,
                error=f"Cannot continue to finalization from status: {current_status.value}. Must be bio_generated.",
            )
        
        # Get existing checkpoint data
        existing_checkpoint = run.get("checkpoint_data", {})
        
        # Build initial checkpoint (entering finalization)
        initial_checkpoint = self._build_checkpoint(
            phase="finalizing",
            crawl_id=crawl_id,
            summary=None,
        )
        
        # Preserve existing checkpoint data
        if existing_checkpoint.get("ingestion"):
            ing_dict = existing_checkpoint["ingestion"]
            initial_checkpoint.ingestion = IngestionCheckpointData(
                require_confirmation=ing_dict.get("require_confirmation", True),
                pages_eligible=ing_dict.get("pages_eligible", 0),
                pages_ingested=ing_dict.get("pages_ingested", 0),
                pages_skipped=ing_dict.get("pages_skipped", 0),
                rejected_skipped=ing_dict.get("rejected_skipped", 0),
                unresolved_skipped=ing_dict.get("unresolved_skipped", 0),
                tombstone_actions=ing_dict.get("tombstone_actions", 0),
                errors=ing_dict.get("errors", []),
            )
        
        if existing_checkpoint.get("confirmation"):
            conf_dict = existing_checkpoint["confirmation"]
            initial_checkpoint.confirmation = ConfirmationCheckpointData(
                total=conf_dict.get("total", 0),
                pending=conf_dict.get("pending", 0),
                manual_review=conf_dict.get("manual_review", 0),
                auto_confirmed=conf_dict.get("auto_confirmed", 0),
                auto_rejected=conf_dict.get("auto_rejected", 0),
                confirmed=conf_dict.get("confirmed", 0),
                rejected=conf_dict.get("rejected", 0),
                all_resolved=conf_dict.get("all_resolved", False),
                resolution_percent=conf_dict.get("resolution_percent", 0.0),
            )
        
        if existing_checkpoint.get("bio_generation"):
            bio_dict = existing_checkpoint["bio_generation"]
            initial_checkpoint.bio_generation = BioGenerationCheckpointData(
                triggered=bio_dict.get("triggered", False),
                source_url_count=bio_dict.get("source_url_count", 0),
                source_selection_policy=bio_dict.get("source_selection_policy", "confirmed_only"),
                persona_pipeline=bio_dict.get("persona_pipeline", "persona_link_compile"),
                status=bio_dict.get("status", "unknown"),
                bio_variant_count=bio_dict.get("bio_variant_count", 0),
                selected_variant_id=bio_dict.get("selected_variant_id"),
                result_refs=bio_dict.get("result_refs", {}),
                errors=bio_dict.get("errors", []),
            )
        
        # Transition to finalizing
        finalize_start_result = await self._transition(
            research_run_id=research_run_id,
            twin_id=twin_id,
            to_status=ResearchRunStatus.FINALIZING,
            reason="Starting research run finalization (mind score + readiness)",
            checkpoint=initial_checkpoint,
        )
        
        if not finalize_start_result.success:
            return finalize_start_result
        
        # Perform finalization steps
        mind_score_checkpoint = None
        readiness_checkpoint = None
        mind_score_success = False
        readiness_success = False
        
        try:
            # Step 1: Update mind score using existing training_metrics hook
            logger.info(f"Phase 5: Updating mind score for twin {twin_id}")
            
            try:
                from modules.training_metrics import update_twin_training_metrics
                
                mind_score_updated = update_twin_training_metrics(twin_id)
                
                if mind_score_updated:
                    # Fetch updated mind score from twin settings
                    response = supabase.table("twins").select(
                        "settings"
                    ).eq("id", twin_id).single().execute()
                    
                    if response.data:
                        settings = response.data.get("settings") or {}
                        training_metrics = settings.get("training_metrics", {})
                        
                        mind_score_checkpoint = MindScoreCheckpointData(
                            status="success",
                            score=training_metrics.get("mind_score", 0),
                            label=training_metrics.get("mind_score_label", "Unknown"),
                            words_processed=training_metrics.get("words_processed", 0),
                            questions_answerable_estimate=training_metrics.get("questions_answerable_est", 0),
                            updated_at=training_metrics.get("last_computed_at", datetime.utcnow().isoformat()),
                            errors=[],
                        )
                        mind_score_success = True
                    else:
                        mind_score_checkpoint = MindScoreCheckpointData(
                            status="failed",
                            score=0,
                            label="Unknown",
                            words_processed=0,
                            questions_answerable_estimate=0,
                            updated_at=datetime.utcnow().isoformat(),
                            errors=["Could not fetch updated mind score"],
                        )
                else:
                    mind_score_checkpoint = MindScoreCheckpointData(
                        status="failed",
                        score=0,
                        label="Unknown",
                        words_processed=0,
                        questions_answerable_estimate=0,
                        updated_at=datetime.utcnow().isoformat(),
                        errors=["Mind score update failed"],
                    )
                    
            except Exception as e:
                logger.error(f"Phase 5: Error updating mind score: {e}")
                mind_score_checkpoint = MindScoreCheckpointData(
                    status="failed",
                    score=0,
                    label="Unknown",
                    words_processed=0,
                    questions_answerable_estimate=0,
                    updated_at=datetime.utcnow().isoformat(),
                    errors=[str(e)],
                )
            
            # Step 2: Evaluate twin readiness
            logger.info(f"Phase 5: Evaluating readiness for twin {twin_id}")
            
            try:
                from modules.twin_readiness import TwinReadinessChecker
                
                checker = TwinReadinessChecker()
                readiness_result = await checker.get_readiness_status(
                    twin_id=twin_id,
                    research_run_id=research_run_id,
                )
                
                readiness_checkpoint = ReadinessCheckpointData(
                    status=readiness_result.status,
                    is_ready=readiness_result.is_ready,
                    thresholds=readiness_result.thresholds,
                    requirements={
                        "has_confirmed_source": readiness_result.requirements.has_confirmed_source,
                        "has_bio_variant": readiness_result.requirements.has_bio_variant,
                        "mind_score_threshold_met": readiness_result.requirements.mind_score_threshold_met,
                        "no_pending_confirmations": readiness_result.requirements.no_pending_confirmations,
                    },
                    counts={
                        "confirmed": readiness_result.counts.confirmed,
                        "auto_confirmed": readiness_result.counts.auto_confirmed,
                        "pending": readiness_result.counts.pending,
                        "manual_review": readiness_result.counts.manual_review,
                        "rejected": readiness_result.counts.rejected,
                    },
                    errors=readiness_result.errors,
                )
                readiness_success = True
                
            except Exception as e:
                logger.error(f"Phase 5: Error evaluating readiness: {e}")
                readiness_checkpoint = ReadinessCheckpointData(
                    status="failed",
                    is_ready=False,
                    thresholds={},
                    requirements={},
                    counts={},
                    errors=[str(e)],
                )
            
            # Build final checkpoint
            final_checkpoint = self._build_checkpoint(
                phase="completed",
                crawl_id=crawl_id,
                summary=None,
            )
            final_checkpoint.ingestion = initial_checkpoint.ingestion
            final_checkpoint.confirmation = initial_checkpoint.confirmation
            final_checkpoint.bio_generation = initial_checkpoint.bio_generation
            final_checkpoint.mind_score = mind_score_checkpoint
            final_checkpoint.readiness = readiness_checkpoint
            
            # Determine final status
            if mind_score_success and readiness_success:
                final_reason = f"Research run finalized: mind_score={mind_score_checkpoint.score}, readiness={readiness_checkpoint.is_ready}"
            elif mind_score_success:
                final_reason = f"Research run finalized with readiness errors: mind_score={mind_score_checkpoint.score}"
            else:
                final_reason = "Research run finalized with mind score errors"
            
            # Transition to completed
            return await self._transition(
                research_run_id=research_run_id,
                twin_id=twin_id,
                to_status=ResearchRunStatus.COMPLETED,
                reason=final_reason,
                checkpoint=final_checkpoint,
            )
            
        except Exception as e:
            logger.error(f"Phase 5: Finalization failed for run {research_run_id}: {e}")
            
            # Build failure checkpoint with partial progress
            failure_checkpoint = self._build_checkpoint(
                phase="finalization_failed",
                crawl_id=crawl_id,
                summary=None,
            )
            failure_checkpoint.ingestion = initial_checkpoint.ingestion
            failure_checkpoint.confirmation = initial_checkpoint.confirmation
            failure_checkpoint.bio_generation = initial_checkpoint.bio_generation
            failure_checkpoint.mind_score = mind_score_checkpoint
            failure_checkpoint.readiness = readiness_checkpoint
            failure_checkpoint.warnings.append(f"Finalization failed: {e}")
            
            # Transition to failed
            return await self._transition(
                research_run_id=research_run_id,
                twin_id=twin_id,
                to_status=ResearchRunStatus.FAILED,
                reason=f"Finalization failed: {e}",
                checkpoint=failure_checkpoint,
            )
    
    async def get_run_status(
        self,
        research_run_id: str,
        twin_id: str,
    ) -> ResearchRunStatusResult:
        """
        Get full run status for polling.
        
        Args:
            research_run_id: Research run ID
            twin_id: Twin ID for authorization
        
        Returns:
            ResearchRunStatusResult
        """
        run = self.repository.get_research_run(research_run_id, twin_id)
        if not run:
            raise ValueError(f"Research run not found: {research_run_id}")
        
        status = run.get("status", "unknown")
        checkpoint_data = run.get("checkpoint_data", {})
        crawl_id = run.get("crawl_id")
        
        # Get confirmation summary if applicable
        summary = None
        if status in (
            ResearchRunStatus.AWAITING_CONFIRMATION.value,
            ResearchRunStatus.TIMED_OUT.value,
            ResearchRunStatus.READY_FOR_INGESTION.value,
            ResearchRunStatus.INGESTING.value,
            ResearchRunStatus.INGESTION_COMPLETED.value,
            ResearchRunStatus.GENERATING_BIO.value,
            ResearchRunStatus.BIO_GENERATED.value,
            ResearchRunStatus.FINALIZING.value,
            ResearchRunStatus.COMPLETED.value,
        ):
            try:
                summary = await self.confirmation_manager.get_confirmation_summary(
                    research_run_id=research_run_id,
                    twin_id=twin_id,
                )
            except Exception as e:
                logger.warning(f"Could not fetch confirmation summary: {e}")
        
        # Determine next_actions (Phase 6: canonical plural field)
        next_actions = []
        if status == ResearchRunStatus.AWAITING_CONFIRMATION.value:
            next_actions = ["wait_for_confirmation", "resolve_confirmations"]
        elif status == ResearchRunStatus.READY_FOR_INGESTION.value:
            next_actions = ["continue_to_ingestion"]
        elif status == ResearchRunStatus.CRAWLING.value:
            next_actions = ["wait_for_crawl"]
        elif status == ResearchRunStatus.INGESTING.value:
            next_actions = ["wait_for_ingestion"]
        elif status == ResearchRunStatus.INGESTION_COMPLETED.value:
            next_actions = ["continue_to_bio"]  # Phase 4
        elif status == ResearchRunStatus.GENERATING_BIO.value:
            next_actions = ["wait_for_bio"]  # Phase 4
        elif status == ResearchRunStatus.BIO_GENERATED.value:
            next_actions = ["continue_to_finalize"]  # Phase 5
        elif status == ResearchRunStatus.FINALIZING.value:
            next_actions = ["wait_for_finalization"]  # Phase 5
        elif status == ResearchRunStatus.COMPLETED.value:
            next_actions = ["research_complete"]  # Phase 5
        
        warnings = checkpoint_data.get("warnings", [])
        
        return ResearchRunStatusResult(
            research_run_id=research_run_id,
            twin_id=twin_id,
            status=status,
            crawl_id=crawl_id,
            checkpoint_data=checkpoint_data,
            confirmation_summary=summary,
            created_at=run.get("created_at", ""),
            updated_at=run.get("updated_at", ""),
            started_at=run.get("started_at"),
            completed_at=run.get("completed_at"),
            next_actions=next_actions,
            warnings=warnings,
        )
    
    async def _transition(
        self,
        research_run_id: str,
        to_status: ResearchRunStatus,
        reason: str,
        twin_id: Optional[str] = None,
        checkpoint: Optional[CheckpointData] = None,
        crawl_id: Optional[str] = None,
    ) -> TransitionResult:
        """
        Execute state transition with validation.
        
        Args:
            research_run_id: Research run ID
            to_status: Target status
            reason: Transition reason for logging
            twin_id: Optional twin ID (fetched if not provided)
            checkpoint: Optional checkpoint data
            crawl_id: Optional crawl ID
        
        Returns:
            TransitionResult
        """
        # Fetch run if twin_id not provided
        if twin_id is None:
            # Need to fetch without twin check first to get twin_id
            try:
                response = supabase.table("research_runs").select("*").eq(
                    "id", research_run_id
                ).single().execute()
                if not response.data:
                    return TransitionResult(
                        success=False,
                        research_run_id=research_run_id,
                        previous_status="",
                        new_status="",
                        checkpoint_updated=False,
                        error="Research run not found",
                    )
                run = response.data
                twin_id = run["twin_id"]
            except Exception as e:
                return TransitionResult(
                    success=False,
                    research_run_id=research_run_id,
                    previous_status="",
                    new_status="",
                    checkpoint_updated=False,
                    error=str(e),
                )
        else:
            run = self.repository.get_research_run(research_run_id, twin_id)
        
        if not run:
            return TransitionResult(
                success=False,
                research_run_id=research_run_id,
                previous_status="",
                new_status="",
                checkpoint_updated=False,
                error="Research run not found",
            )
        
        from_status = ResearchRunStatus(run.get("status", "planning"))
        
        # Validate transition
        if not is_valid_transition(from_status, to_status):
            return TransitionResult(
                success=False,
                research_run_id=research_run_id,
                previous_status=from_status.value,
                new_status=to_status.value,
                checkpoint_updated=False,
                error=f"Invalid transition: {from_status.value} -> {to_status.value}",
            )
        
        # Build checkpoint if not provided
        if checkpoint is None:
            checkpoint = CheckpointData(
                phase=to_status.value,
                last_transition_at=datetime.utcnow().isoformat(),
            )
        else:
            checkpoint.last_transition_at = datetime.utcnow().isoformat()
        
        # Update database
        checkpoint_dict = {
            "phase": checkpoint.phase,
            "last_transition_at": checkpoint.last_transition_at,
            "crawl_id": checkpoint.crawl_id,
            "confirmation": checkpoint.confirmation.__dict__ if checkpoint.confirmation else None,
            "ingestion": checkpoint.ingestion.__dict__ if checkpoint.ingestion else None,
            "bio_generation": checkpoint.bio_generation.__dict__ if checkpoint.bio_generation else None,
            "mind_score": checkpoint.mind_score.__dict__ if checkpoint.mind_score else None,
            "readiness": checkpoint.readiness.__dict__ if checkpoint.readiness else None,
            "claimed_identity": checkpoint.claimed_identity,
            "seed_urls_count": checkpoint.seed_urls_count,
            "timeout_at": checkpoint.timeout_at,
            "warnings": checkpoint.warnings,
        }
        
        success = self.repository.update_status(
            research_run_id=research_run_id,
            new_status=to_status.value,
            checkpoint_data=checkpoint_dict,
            crawl_id=crawl_id,
        )
        
        if success:
            logger.info(f"Research run {research_run_id}: {from_status.value} -> {to_status.value} ({reason})")
            return TransitionResult(
                success=True,
                research_run_id=research_run_id,
                previous_status=from_status.value,
                new_status=to_status.value,
                checkpoint_updated=True,
                transition_reason=reason,
            )
        else:
            return TransitionResult(
                success=False,
                research_run_id=research_run_id,
                previous_status=from_status.value,
                new_status=from_status.value,
                checkpoint_updated=False,
                error="Database update failed",
            )
    
    def _build_checkpoint(
        self,
        phase: str,
        crawl_id: Optional[str] = None,
        summary: Optional[ConfirmationSummary] = None,
    ) -> CheckpointData:
        """Build checkpoint data from confirmation summary."""
        checkpoint = CheckpointData(
            phase=phase,
            last_transition_at=datetime.utcnow().isoformat(),
            crawl_id=crawl_id,
        )
        
        if summary:
            checkpoint.confirmation = ConfirmationCheckpointData(
                total=summary.total,
                pending=summary.pending,
                manual_review=summary.manual_review,
                auto_confirmed=summary.auto_confirmed,
                auto_rejected=summary.auto_rejected,
                confirmed=summary.confirmed,
                rejected=summary.rejected,
                all_resolved=summary.all_resolved,
                resolution_percent=summary.resolution_percent,
            )
        
        return checkpoint


# ============================================================================
# Convenience Functions
# ============================================================================

async def create_research_run(
    twin_id: str,
    actor_user_id: str,
    claimed_identity: Dict[str, Any],
    seed_urls: List[str],
    onboarding_session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> CreateResearchRunResult:
    """Convenience function to create research run without instantiating orchestrator."""
    orchestrator = ResearchOrchestrator()
    return await orchestrator.create_research_run(
        twin_id=twin_id,
        actor_user_id=actor_user_id,
        claimed_identity=claimed_identity,
        seed_urls=seed_urls,
        onboarding_session_id=onboarding_session_id,
        metadata=metadata,
    )


async def get_run_status(
    research_run_id: str,
    twin_id: str,
) -> ResearchRunStatusResult:
    """Convenience function to get status without instantiating orchestrator."""
    orchestrator = ResearchOrchestrator()
    return await orchestrator.get_run_status(research_run_id, twin_id)
