"""
Research Orchestrator State Machine Fix

Fixes the COMPLETED state issue:
- If Deep Research OFF: BIO_GENERATED → FINALIZING → COMPLETED (terminal)
- If Deep Research ON: BIO_GENERATED → FINALIZING → CLAIMS_ENRICHMENT → ... → RUNTIME_PUBLISHED → COMPLETED

Usage:
    Import and call the patched functions instead of the original.
    Or use patch_research_orchestrator() to monkey-patch at runtime.
"""

import logging
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class ResearchRunStatus(str, Enum):
    """Fixed state machine with proper terminal states."""
    PLANNING = "planning"
    QUEUED = "queued"
    CRAWLING = "crawling"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    TIMED_OUT = "timed_out"
    READY_FOR_INGESTION = "ready_for_ingestion"
    INGESTING = "ingesting"
    INGESTION_COMPLETED = "ingestion_completed"
    GENERATING_BIO = "generating_bio"
    BIO_GENERATED = "bio_generated"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    
    # Deep Research Phases
    CLAIMS_ENRICHMENT = "claims_enrichment"
    CLAIMS_COMPLETED = "claims_completed"
    WEB_VERIFICATION = "web_verification"
    WEB_VERIFIED = "web_verified"
    CLAIMS_FINALIZATION = "claims_finalization"
    CLAIMS_FINALIZED = "claims_finalized"
    ADJUDICATION = "adjudication"
    ADJUDICATED = "adjudicated"
    RUNTIME_PUBLICATION = "runtime_publication"
    RUNTIME_PUBLISHED = "runtime_published"
    
    FAILED = "failed"


def is_deep_research_enabled(run_data: Dict[str, Any]) -> bool:
    """
    Check if deep research is enabled for this research run.
    
    Deep research is enabled if:
    1. Explicitly enabled in run metadata
    2. Not explicitly disabled in run metadata and the always-on runtime config is active
    """
    checkpoint = run_data.get("checkpoint_data", {})
    metadata = checkpoint.get("metadata", {})
    
    # Explicit enable in metadata
    if metadata.get("deep_research_enabled") is True:
        return True
    
    # Explicit disable
    if metadata.get("deep_research_enabled") is False:
        return False
    
    # Check global config (always on for new runs unless metadata disables it)
    from modules.deep_research_config import get_config
    config = get_config()

    return config.is_enabled()


def get_valid_transitions(
    from_status: ResearchRunStatus,
    run_data: Optional[Dict[str, Any]] = None
) -> set:
    """
    Get valid transitions from a status, considering deep research enablement.
    
    Args:
        from_status: Current status
        run_data: Optional run data to check deep research enablement
        
    Returns:
        Set of valid next statuses
    """
    # Base transitions (always valid)
    base_transitions = {
        ResearchRunStatus.PLANNING: {
            ResearchRunStatus.QUEUED, ResearchRunStatus.FAILED
        },
        ResearchRunStatus.QUEUED: {
            ResearchRunStatus.CRAWLING, ResearchRunStatus.FAILED
        },
        ResearchRunStatus.CRAWLING: {
            ResearchRunStatus.AWAITING_CONFIRMATION,
            ResearchRunStatus.READY_FOR_INGESTION,
            ResearchRunStatus.FAILED,
        },
        ResearchRunStatus.AWAITING_CONFIRMATION: {
            ResearchRunStatus.AWAITING_CONFIRMATION,
            ResearchRunStatus.READY_FOR_INGESTION,
            ResearchRunStatus.TIMED_OUT,
            ResearchRunStatus.FAILED,
        },
        ResearchRunStatus.TIMED_OUT: {
            ResearchRunStatus.READY_FOR_INGESTION, ResearchRunStatus.FAILED
        },
        ResearchRunStatus.READY_FOR_INGESTION: {
            ResearchRunStatus.INGESTING, ResearchRunStatus.FAILED
        },
        ResearchRunStatus.INGESTING: {
            ResearchRunStatus.INGESTION_COMPLETED, ResearchRunStatus.FAILED
        },
        ResearchRunStatus.INGESTION_COMPLETED: {
            ResearchRunStatus.GENERATING_BIO, ResearchRunStatus.FAILED
        },
        ResearchRunStatus.GENERATING_BIO: {
            ResearchRunStatus.BIO_GENERATED, ResearchRunStatus.FAILED
        },
        ResearchRunStatus.BIO_GENERATED: {
            ResearchRunStatus.FINALIZING, ResearchRunStatus.FAILED
        },
        ResearchRunStatus.FINALIZING: {
            ResearchRunStatus.COMPLETED, ResearchRunStatus.FAILED
        },
        ResearchRunStatus.CLAIMS_ENRICHMENT: {
            ResearchRunStatus.CLAIMS_COMPLETED,
            ResearchRunStatus.FAILED,
            ResearchRunStatus.CLAIMS_ENRICHMENT,
        },
        ResearchRunStatus.CLAIMS_COMPLETED: {
            ResearchRunStatus.WEB_VERIFICATION,
            ResearchRunStatus.CLAIMS_COMPLETED,
        },
        ResearchRunStatus.WEB_VERIFICATION: {
            ResearchRunStatus.WEB_VERIFIED,
            ResearchRunStatus.FAILED,
            ResearchRunStatus.WEB_VERIFICATION,
        },
        ResearchRunStatus.WEB_VERIFIED: {
            ResearchRunStatus.CLAIMS_FINALIZATION,
            ResearchRunStatus.WEB_VERIFIED,
        },
        ResearchRunStatus.CLAIMS_FINALIZATION: {
            ResearchRunStatus.CLAIMS_FINALIZED,
            ResearchRunStatus.FAILED,
            ResearchRunStatus.CLAIMS_FINALIZATION,
        },
        ResearchRunStatus.CLAIMS_FINALIZED: {
            ResearchRunStatus.ADJUDICATION,
            ResearchRunStatus.RUNTIME_PUBLICATION,
            ResearchRunStatus.CLAIMS_FINALIZED,
        },
        ResearchRunStatus.ADJUDICATION: {
            ResearchRunStatus.ADJUDICATED,
            ResearchRunStatus.FAILED,
            ResearchRunStatus.ADJUDICATION,
        },
        ResearchRunStatus.ADJUDICATED: {
            ResearchRunStatus.RUNTIME_PUBLICATION,
            ResearchRunStatus.ADJUDICATED,
        },
        ResearchRunStatus.RUNTIME_PUBLICATION: {
            ResearchRunStatus.RUNTIME_PUBLISHED,
            ResearchRunStatus.FAILED,
            ResearchRunStatus.RUNTIME_PUBLICATION,
        },
        ResearchRunStatus.RUNTIME_PUBLISHED: {
            ResearchRunStatus.COMPLETED,  # Final transition to completed
            ResearchRunStatus.RUNTIME_PUBLISHED,
        },
        ResearchRunStatus.FAILED: set(),
    }
    
    transitions = base_transitions.get(from_status, set()).copy()
    
    # Handle COMPLETED transitions based on deep research setting
    if from_status == ResearchRunStatus.COMPLETED:
        # Check if we should continue to deep research
        if run_data and is_deep_research_enabled(run_data):
            transitions.add(ResearchRunStatus.CLAIMS_ENRICHMENT)
        # COMPLETED is terminal if deep research is off
    
    return transitions


def get_next_auto_status(
    current_status: ResearchRunStatus,
    run_data: Dict[str, Any]
) -> Optional[ResearchRunStatus]:
    """
    Get the next automatic status after completing a stage.
    
    This handles the conditional logic:
    - After FINALIZING → COMPLETED (if no deep research) or CLAIMS_ENRICHMENT (if deep research)
    - After CLAIMS_FINALIZED → ADJUDICATION (if enabled) or RUNTIME_PUBLICATION
    - After RUNTIME_PUBLISHED → COMPLETED (always)
    
    Args:
        current_status: Current completed status
        run_data: Run data for context
        
    Returns:
        Next status or None if terminal
    """
    deep_research = is_deep_research_enabled(run_data)
    
    transitions = {
        # Standard pipeline (no deep research)
        ResearchRunStatus.FINALIZING: (
            ResearchRunStatus.CLAIMS_ENRICHMENT if deep_research 
            else ResearchRunStatus.COMPLETED
        ),
        
        # Deep research pipeline
        ResearchRunStatus.CLAIMS_COMPLETED: ResearchRunStatus.WEB_VERIFICATION,
        ResearchRunStatus.WEB_VERIFIED: ResearchRunStatus.CLAIMS_FINALIZATION,
        ResearchRunStatus.CLAIMS_FINALIZED: ResearchRunStatus.RUNTIME_PUBLICATION,
        ResearchRunStatus.ADJUDICATED: ResearchRunStatus.RUNTIME_PUBLICATION,
        ResearchRunStatus.RUNTIME_PUBLISHED: ResearchRunStatus.COMPLETED,
    }
    
    return transitions.get(current_status)


def is_terminal_status(
    status: ResearchRunStatus,
    run_data: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Check if a status is terminal (no further transitions possible).
    
    Args:
        status: Status to check
        run_data: Optional run data for deep research check
        
    Returns:
        True if terminal
    """
    if status == ResearchRunStatus.FAILED:
        return True
    
    if status == ResearchRunStatus.COMPLETED:
        # COMPLETED is terminal only if deep research is not enabled
        if run_data:
            return not is_deep_research_enabled(run_data)
        return True  # Assume terminal if no data
    
    if status == ResearchRunStatus.RUNTIME_PUBLISHED:
        # RUNTIME_PUBLISHED is always terminal - must transition to COMPLETED explicitly
        return False  # Allow transition to COMPLETED
    
    return False


# Skip adjudication helper
def should_skip_adjudication(run_data: Dict[str, Any]) -> bool:
    """
    Check if adjudication phase should be skipped.
    
    Skipped if:
    1. Explicitly disabled in metadata
    2. No claims requiring review
    3. Auto-publish enabled
    """
    checkpoint = run_data.get("checkpoint_data", {})
    metadata = checkpoint.get("metadata", {})
    
    # Explicit skip
    if metadata.get("skip_adjudication") is True:
        return True
    
    # Check config
    from modules.deep_research_config import get_config
    config = get_config()
    
    if getattr(config, 'phase_12_auto_publish', False):
        return True
    
    return False


def get_adjudication_path(
    current_status: ResearchRunStatus,
    run_data: Dict[str, Any]
) -> ResearchRunStatus:
    """
    Get the next status after CLAIMS_FINALIZED, considering adjudication skip.
    
    Args:
        current_status: Should be CLAIMS_FINALIZED
        run_data: Run data
        
    Returns:
        ADJUDICATION or RUNTIME_PUBLICATION
    """
    if current_status != ResearchRunStatus.CLAIMS_FINALIZED:
        raise ValueError(f"Expected CLAIMS_FINALIZED, got {current_status}")
    
    if should_skip_adjudication(run_data):
        return ResearchRunStatus.RUNTIME_PUBLICATION
    
    return ResearchRunStatus.ADJUDICATION


# Patch function for runtime use
def patch_research_orchestrator():
    """
    Monkey-patch the research_orchestrator module with fixed state machine.
    Call this at application startup.
    """
    try:
        from modules import research_orchestrator as ro
        
        # Store original functions
        ro._original_is_valid_transition = ro.is_valid_transition
        ro._original_VALID_TRANSITIONS = ro.VALID_TRANSITIONS.copy()
        
        # Replace with fixed versions
        def fixed_is_valid_transition(from_status, to_status, run_data=None):
            """Fixed transition check with deep research awareness."""
            if from_status == to_status:
                return True
            valid = get_valid_transitions(from_status, run_data)
            return to_status in valid
        
        # Update module
        ro.is_valid_transition = fixed_is_valid_transition
        ro.get_next_auto_status = get_next_auto_status
        ro.is_terminal_status = is_terminal_status
        ro.is_deep_research_enabled = is_deep_research_enabled
        ro.should_skip_adjudication = should_skip_adjudication
        ro.get_adjudication_path = get_adjudication_path
        
        logger.info("Research orchestrator state machine patched")
        
    except Exception as e:
        logger.error(f"Failed to patch research orchestrator: {e}")


def unpatch_research_orchestrator():
    """Restore original state machine (for testing)."""
    try:
        from modules import research_orchestrator as ro
        
        if hasattr(ro, '_original_is_valid_transition'):
            ro.is_valid_transition = ro._original_is_valid_transition
            ro.VALID_TRANSITIONS = ro._original_VALID_TRANSITIONS
            delattr(ro, '_original_is_valid_transition')
            delattr(ro, '_original_VALID_TRANSITIONS')
        
        logger.info("Research orchestrator state machine restored")
        
    except Exception as e:
        logger.error(f"Failed to unpatch research orchestrator: {e}")
