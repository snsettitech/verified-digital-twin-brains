"""
Research Claim Adjudication Service (Phase 11)

Human Adjudication + Canonical Claim Review Workflow

Provides:
- Adjudication of claims by owner/admin (approve/reject/override)
- Canonical claim store with versioning
- Review queue management
- Audit trail for all actions
- Lock/unlock mechanism for claim editing

Usage:
    service = ResearchClaimAdjudicationService()
    
    # Adjudicate a claim
    result = await service.adjudicate_claim(
        claim_id="claim-123",
        twin_id="twin-456",
        action="approve",
        actor_id="user-789",
        notes="Verified through manual review"
    )
    
    # Get review queue
    queue = await service.get_review_queue(
        research_run_id="run-abc",
        twin_id="twin-456",
        filters={"status": "needs_review"}
    )
"""

import uuid
import hashlib
import json
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from modules.observability import supabase as _supabase
from modules.deep_research_config import get_config as get_dr_config

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Constants
# ============================================================================

class AdjudicationAction(str, Enum):
    """Valid adjudication actions."""
    APPROVE = "approve"
    REJECT = "reject"
    MARK_NEEDS_REVIEW = "mark_needs_review"
    MARK_UNRESOLVED = "mark_unresolved"
    LOCK = "lock"
    UNLOCK = "unlock"
    OVERRIDE_STATUS = "override_status"
    OVERRIDE_CANONICAL = "override_canonical"


class CanonicalStatus(str, Enum):
    """Canonical claim statuses."""
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"
    UNRESOLVED = "unresolved"
    SUPERSEDED = "superseded"


class SourceOfTruth(str, Enum):
    """How the canonical state was determined."""
    SYSTEM_RULE = "system_rule"
    HUMAN_REVIEW = "human_review"
    OVERRIDE = "override"
    CONSENSUS = "consensus"


class ActorType(str, Enum):
    """Actor types for audit trail."""
    USER = "user"
    SYSTEM = "system"
    ADMIN = "admin"


class IssueAction(str, Enum):
    """Valid actions on consistency issues."""
    CONFIRM_CONFLICT = "confirm_conflict"
    DISMISS = "dismiss"
    MERGE_DUPLICATE = "merge_duplicate"
    SPLIT_CONTEXT = "split_context"
    DEFER = "defer"


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class AdjudicationResult:
    """Result of an adjudication action."""
    success: bool
    claim_id: str
    action: str
    previous_status: Optional[str]
    new_status: Optional[str]
    canonical_id: Optional[str]
    is_new_canonical: bool
    error: Optional[str] = None


@dataclass
class CanonicalClaim:
    """Canonical claim record."""
    id: str
    claim_id: str
    research_run_id: str
    twin_id: str
    canonical_status: str
    canonical_text: Optional[str]
    source_of_truth: str
    locked: bool
    locked_by: Optional[str]
    locked_at: Optional[str]
    lock_reason: Optional[str]
    adjudication_confidence: float
    version: int
    superseded_by: Optional[str]
    effective_at: str
    superseded_at: Optional[str]
    created_at: str
    updated_at: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "claim_id": self.claim_id,
            "research_run_id": self.research_run_id,
            "twin_id": self.twin_id,
            "canonical_status": self.canonical_status,
            "canonical_text": self.canonical_text,
            "source_of_truth": self.source_of_truth,
            "locked": self.locked,
            "locked_by": self.locked_by,
            "locked_at": self.locked_at,
            "lock_reason": self.lock_reason,
            "adjudication_confidence": self.adjudication_confidence,
            "version": self.version,
            "superseded_by": self.superseded_by,
            "effective_at": self.effective_at,
            "superseded_at": self.superseded_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class ReviewQueueItem:
    """Item in the review queue."""
    claim_id: str
    claim_text: str
    claim_type: str
    research_run_id: str
    twin_id: str
    finalization_status: Optional[str]
    canonical_status: Optional[str]
    locked: bool
    locked_by: Optional[str]
    has_open_issues: bool
    issue_count: int
    adjudication_count: int
    created_at: str


@dataclass
class ReviewQueueSummary:
    """Summary statistics for the review queue."""
    total_claims: int
    needs_review: int
    unresolved: int
    accepted: int
    rejected: int
    locked: int
    has_open_issues: int


@dataclass
class AdjudicationHistoryItem:
    """Single adjudication record from history."""
    id: str
    action: str
    previous_status: Optional[str]
    new_status: Optional[str]
    actor_id: Optional[str]
    actor_type: str
    reason_code: Optional[str]
    notes: Optional[str]
    created_at: str


@dataclass
class IssueActionResult:
    """Result of an issue action."""
    success: bool
    issue_id: str
    action: str
    previous_status: Optional[str]
    new_status: Optional[str]
    error: Optional[str] = None


# ============================================================================
# Main Service Class
# ============================================================================

class ResearchClaimAdjudicationService:
    """
    Service for human adjudication and canonical claim management.
    
    Responsibilities:
    - Apply adjudication actions to claims
    - Manage canonical claim store with versioning
    - Maintain audit trail of all actions
    - Handle claim locking
    - Build review queues
    """
    
    def __init__(self, supabase_client=None):
        """
        Initialize the adjudication service.
        
        Args:
            supabase_client: Optional Supabase client for dependency injection
        """
        self.supabase = supabase_client or _supabase
        self.config = get_dr_config()
    
    # ========================================================================
    # Core Adjudication Methods
    # ========================================================================
    
    async def adjudicate_claim(
        self,
        claim_id: str,
        twin_id: str,
        action: str,
        actor_id: str,
        notes: Optional[str] = None,
        reason_code: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        actor_type: str = "user",
    ) -> AdjudicationResult:
        """
        Apply an adjudication action to a claim.
        
        Args:
            claim_id: The claim to adjudicate
            twin_id: Twin scope
            action: One of approve, reject, mark_needs_review, mark_unresolved, override_status
            actor_id: User performing the action
            notes: Optional notes about the decision
            reason_code: Optional reason code
            idempotency_key: Optional key for idempotency
            actor_type: 'user', 'admin', or 'system'
            
        Returns:
            AdjudicationResult with success status and details
        """
        try:
            # Generate idempotency key if not provided
            if not idempotency_key:
                idempotency_key = self._generate_idempotency_key(
                    claim_id, action, actor_id
                )
            
            # Check for existing adjudication (idempotency)
            existing = await self._check_existing_adjudication(idempotency_key)
            if existing:
                logger.info(f"Adjudication already exists for key {idempotency_key}")
                return AdjudicationResult(
                    success=True,
                    claim_id=claim_id,
                    action=action,
                    previous_status=existing.get("previous_status"),
                    new_status=existing.get("new_status"),
                    canonical_id=existing.get("canonical_id"),
                    is_new_canonical=False,
                )
            
            # Get current canonical claim
            current_canonical = await self._get_current_canonical(claim_id)
            previous_status = current_canonical.canonical_status if current_canonical else None
            
            # Determine new status based on action
            new_status = self._determine_new_status(action, previous_status)
            
            # Get claim details for research_run_id
            claim_details = await self._get_claim_details(claim_id)
            if not claim_details:
                return AdjudicationResult(
                    success=False,
                    claim_id=claim_id,
                    action=action,
                    previous_status=previous_status,
                    new_status=None,
                    canonical_id=None,
                    is_new_canonical=False,
                    error="Claim not found",
                )
            
            research_run_id = claim_details["research_run_id"]
            
            # Check if claim is locked (prevent modification)
            if current_canonical and current_canonical.locked:
                if actor_type != "admin":
                    return AdjudicationResult(
                        success=False,
                        claim_id=claim_id,
                        action=action,
                        previous_status=previous_status,
                        new_status=None,
                        canonical_id=None,
                        is_new_canonical=False,
                        error=f"Claim is locked by {current_canonical.locked_by}",
                    )
            
            # Create new canonical version (supersede old if exists)
            new_canonical = await self._create_canonical_version(
                claim_id=claim_id,
                research_run_id=research_run_id,
                twin_id=twin_id,
                canonical_status=new_status,
                source_of_truth=self._determine_source_of_truth(action, actor_type),
                previous_canonical=current_canonical,
                confidence=1.0 if actor_type in ("user", "admin") else 0.8,
            )
            
            # Record adjudication
            await self._record_adjudication(
                claim_id=claim_id,
                research_run_id=research_run_id,
                twin_id=twin_id,
                action=action,
                previous_status=previous_status,
                new_status=new_status,
                actor_id=actor_id,
                actor_type=actor_type,
                reason_code=reason_code,
                notes=notes,
                idempotency_key=idempotency_key,
            )
            
            return AdjudicationResult(
                success=True,
                claim_id=claim_id,
                action=action,
                previous_status=previous_status,
                new_status=new_status,
                canonical_id=new_canonical.id,
                is_new_canonical=True,
            )
            
        except Exception as e:
            logger.error(f"Error adjudicating claim {claim_id}: {e}")
            return AdjudicationResult(
                success=False,
                claim_id=claim_id,
                action=action,
                previous_status=None,
                new_status=None,
                canonical_id=None,
                is_new_canonical=False,
                error=str(e),
            )
    
    async def lock_claim(
        self,
        claim_id: str,
        twin_id: str,
        actor_id: str,
        reason: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> AdjudicationResult:
        """
        Lock a claim to prevent modification.
        
        Args:
            claim_id: The claim to lock
            twin_id: Twin scope
            actor_id: User locking the claim
            reason: Reason for locking
            idempotency_key: Optional idempotency key
            
        Returns:
            AdjudicationResult
        """
        return await self.adjudicate_claim(
            claim_id=claim_id,
            twin_id=twin_id,
            action=AdjudicationAction.LOCK.value,
            actor_id=actor_id,
            notes=reason,
            idempotency_key=idempotency_key,
            actor_type="admin",
        )
    
    async def unlock_claim(
        self,
        claim_id: str,
        twin_id: str,
        actor_id: str,
        idempotency_key: Optional[str] = None,
    ) -> AdjudicationResult:
        """
        Unlock a previously locked claim.
        
        Args:
            claim_id: The claim to unlock
            twin_id: Twin scope
            actor_id: User unlocking the claim
            idempotency_key: Optional idempotency key
            
        Returns:
            AdjudicationResult
        """
        return await self.adjudicate_claim(
            claim_id=claim_id,
            twin_id=twin_id,
            action=AdjudicationAction.UNLOCK.value,
            actor_id=actor_id,
            idempotency_key=idempotency_key,
            actor_type="admin",
        )
    
    # ========================================================================
    # Review Queue Methods
    # ========================================================================
    
    async def get_review_queue(
        self,
        research_run_id: str,
        twin_id: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ReviewQueueItem]:
        """
        Get the review queue for a research run.
        
        Args:
            research_run_id: The research run
            twin_id: Twin scope
            filters: Optional filters (status, has_issues, etc.)
            limit: Max items to return
            offset: Pagination offset
            
        Returns:
            List of ReviewQueueItem
        """
        try:
            # Get all claims for this research run
            claims_response = self.supabase.table("research_claims").select(
                "*"
            ).eq("research_run_id", research_run_id).eq("twin_id", twin_id).execute()
            
            if not claims_response.data:
                return []
            
            items = []
            for claim in claims_response.data:
                # Get canonical status
                canonical = await self._get_current_canonical(claim["id"])
                
                # Check for open issues
                issues_response = self.supabase.table("research_claim_consistency_issues").select(
                    "*"
                ).eq("research_run_id", research_run_id).contains("claim_ids", [claim["id"]]).eq("status", "open").execute()
                
                # Get adjudication count
                adj_response = self.supabase.table("research_claim_adjudications").select(
                    "id"
                ).eq("claim_id", claim["id"]).execute()
                
                # Apply filters
                if filters:
                    status_filter = filters.get("status")
                    if status_filter:
                        current_status = canonical.canonical_status if canonical else None
                        if current_status != status_filter:
                            continue
                    
                    if filters.get("has_issues") and not issues_response.data:
                        continue
                    
                    if filters.get("locked_only") and (not canonical or not canonical.locked):
                        continue
                
                items.append(ReviewQueueItem(
                    claim_id=claim["id"],
                    claim_text=claim.get("claim_text", ""),
                    claim_type=claim.get("claim_type", ""),
                    research_run_id=research_run_id,
                    twin_id=twin_id,
                    finalization_status=claim.get("verification_status"),
                    canonical_status=canonical.canonical_status if canonical else None,
                    locked=canonical.locked if canonical else False,
                    locked_by=canonical.locked_by if canonical else None,
                    has_open_issues=len(issues_response.data) > 0,
                    issue_count=len(issues_response.data),
                    adjudication_count=len(adj_response.data),
                    created_at=claim.get("created_at", ""),
                ))
            
            # Apply limit and offset
            return items[offset:offset + limit]
            
        except Exception as e:
            logger.error(f"Error getting review queue: {e}")
            return []
    
    async def get_review_queue_summary(
        self,
        research_run_id: str,
        twin_id: str,
    ) -> ReviewQueueSummary:
        """
        Get summary statistics for the review queue.
        
        Args:
            research_run_id: The research run
            twin_id: Twin scope
            
        Returns:
            ReviewQueueSummary
        """
        try:
            claims_response = self.supabase.table("research_claims").select(
                "*"
            ).eq("research_run_id", research_run_id).eq("twin_id", twin_id).execute()
            
            if not claims_response.data:
                return ReviewQueueSummary(
                    total_claims=0,
                    needs_review=0,
                    unresolved=0,
                    accepted=0,
                    rejected=0,
                    locked=0,
                    has_open_issues=0,
                )
            
            total = len(claims_response.data)
            needs_review_count = 0
            unresolved_count = 0
            accepted_count = 0
            rejected_count = 0
            locked_count = 0
            has_issues_count = 0
            
            for claim in claims_response.data:
                canonical = await self._get_current_canonical(claim["id"])
                
                if canonical:
                    if canonical.canonical_status == CanonicalStatus.NEEDS_REVIEW.value:
                        needs_review_count += 1
                    elif canonical.canonical_status == CanonicalStatus.UNRESOLVED.value:
                        unresolved_count += 1
                    elif canonical.canonical_status == CanonicalStatus.ACCEPTED.value:
                        accepted_count += 1
                    elif canonical.canonical_status == CanonicalStatus.REJECTED.value:
                        rejected_count += 1
                    
                    if canonical.locked:
                        locked_count += 1
                
                # Check for issues
                issues_response = self.supabase.table("research_claim_consistency_issues").select(
                    "id"
                ).eq("research_run_id", research_run_id).contains("claim_ids", [claim["id"]]).eq("status", "open").execute()
                
                if issues_response.data:
                    has_issues_count += 1
            
            return ReviewQueueSummary(
                total_claims=total,
                needs_review=needs_review_count,
                unresolved=unresolved_count,
                accepted=accepted_count,
                rejected=rejected_count,
                locked=locked_count,
                has_open_issues=has_issues_count,
            )
            
        except Exception as e:
            logger.error(f"Error getting review queue summary: {e}")
            return ReviewQueueSummary(
                total_claims=0,
                needs_review=0,
                unresolved=0,
                accepted=0,
                rejected=0,
                locked=0,
                has_open_issues=0,
            )
    
    # ========================================================================
    # Audit Trail Methods
    # ========================================================================
    
    async def get_adjudication_history(
        self,
        claim_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AdjudicationHistoryItem]:
        """
        Get the adjudication history for a claim.
        
        Args:
            claim_id: The claim
            limit: Max items to return
            offset: Pagination offset
            
        Returns:
            List of AdjudicationHistoryItem
        """
        try:
            response = self.supabase.table("research_claim_adjudications").select(
                "*"
            ).eq("claim_id", claim_id).order("created_at", desc=True).limit(limit).offset(offset).execute()
            
            return [
                AdjudicationHistoryItem(
                    id=record["id"],
                    action=record["action"],
                    previous_status=record.get("previous_status"),
                    new_status=record.get("new_status"),
                    actor_id=record.get("actor_id"),
                    actor_type=record.get("actor_type", "user"),
                    reason_code=record.get("reason_code"),
                    notes=record.get("notes"),
                    created_at=record["created_at"],
                )
                for record in response.data
            ]
            
        except Exception as e:
            logger.error(f"Error getting adjudication history: {e}")
            return []
    
    # ========================================================================
    # Consistency Issue Methods
    # ========================================================================
    
    async def apply_issue_action(
        self,
        issue_id: str,
        twin_id: str,
        action: str,
        actor_id: str,
        notes: Optional[str] = None,
        reason_code: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> IssueActionResult:
        """
        Apply an action to a consistency issue.
        
        Args:
            issue_id: The consistency issue
            twin_id: Twin scope
            action: One of confirm_conflict, dismiss, merge_duplicate, split_context, defer
            actor_id: User performing the action
            notes: Optional notes
            reason_code: Optional reason code
            idempotency_key: Optional idempotency key
            
        Returns:
            IssueActionResult
        """
        try:
            # Generate idempotency key if not provided
            if not idempotency_key:
                idempotency_key = self._generate_idempotency_key(
                    issue_id, action, actor_id
                )
            
            # Check for existing action (idempotency)
            existing = await self._check_existing_issue_action(idempotency_key)
            if existing:
                return IssueActionResult(
                    success=True,
                    issue_id=issue_id,
                    action=action,
                    previous_status=existing.get("previous_status"),
                    new_status=existing.get("new_status"),
                )
            
            # Get current issue
            issue_response = self.supabase.table("research_claim_consistency_issues").select(
                "*"
            ).eq("id", issue_id).single().execute()
            
            if not issue_response.data:
                return IssueActionResult(
                    success=False,
                    issue_id=issue_id,
                    action=action,
                    error="Issue not found",
                )
            
            issue = issue_response.data
            previous_status = issue.get("status")
            
            # Determine new status based on action
            new_status = self._determine_issue_status(action, previous_status)
            
            # Update issue status
            self.supabase.table("research_claim_consistency_issues").update({
                "status": new_status,
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("id", issue_id).execute()
            
            # Record the action
            self.supabase.table("research_claim_issue_actions").insert({
                "id": str(uuid.uuid4()),
                "issue_id": issue_id,
                "research_run_id": issue["research_run_id"],
                "twin_id": twin_id,
                "action": action,
                "previous_status": previous_status,
                "new_status": new_status,
                "actor_id": actor_id,
                "reason_code": reason_code,
                "notes": notes,
                "idempotency_key": idempotency_key,
                "created_at": datetime.utcnow().isoformat(),
            }).execute()
            
            return IssueActionResult(
                success=True,
                issue_id=issue_id,
                action=action,
                previous_status=previous_status,
                new_status=new_status,
            )
            
        except Exception as e:
            logger.error(f"Error applying issue action: {e}")
            return IssueActionResult(
                success=False,
                issue_id=issue_id,
                action=action,
                error=str(e),
            )
    
    # ========================================================================
    # Private Helper Methods
    # ========================================================================
    
    def _generate_idempotency_key(
        self,
        entity_id: str,
        action: str,
        actor_id: str,
    ) -> str:
        """Generate an idempotency key for an action."""
        content = f"{entity_id}:{action}:{actor_id}:{datetime.utcnow().strftime('%Y%m%d')}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]
    
    async def _check_existing_adjudication(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        """Check if an adjudication already exists for this key."""
        try:
            response = self.supabase.table("research_claim_adjudications").select(
                "*"
            ).eq("idempotency_key", idempotency_key).limit(1).execute()
            return response.data[0] if response.data else None
        except Exception:
            return None
    
    async def _check_existing_issue_action(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        """Check if an issue action already exists for this key."""
        try:
            response = self.supabase.table("research_claim_issue_actions").select(
                "*"
            ).eq("idempotency_key", idempotency_key).limit(1).execute()
            return response.data[0] if response.data else None
        except Exception:
            return None
    
    async def _get_current_canonical(self, claim_id: str) -> Optional[CanonicalClaim]:
        """Get the current (non-superseded) canonical claim."""
        try:
            response = self.supabase.table("research_claim_canonical").select(
                "*"
            ).eq("claim_id", claim_id).is_("superseded_at", None).limit(1).execute()
            
            if not response.data:
                return None
            
            record = response.data[0]
            return CanonicalClaim(
                id=record["id"],
                claim_id=record["claim_id"],
                research_run_id=record["research_run_id"],
                twin_id=record["twin_id"],
                canonical_status=record["canonical_status"],
                canonical_text=record.get("canonical_text"),
                source_of_truth=record["source_of_truth"],
                locked=record.get("locked", False),
                locked_by=record.get("locked_by"),
                locked_at=record.get("locked_at"),
                lock_reason=record.get("lock_reason"),
                adjudication_confidence=record.get("adjudication_confidence", 0.0),
                version=record.get("version", 1),
                superseded_by=record.get("superseded_by"),
                effective_at=record["effective_at"],
                superseded_at=record.get("superseded_at"),
                created_at=record["created_at"],
                updated_at=record["updated_at"],
            )
            
        except Exception as e:
            logger.error(f"Error getting canonical claim: {e}")
            return None
    
    async def _get_claim_details(self, claim_id: str) -> Optional[Dict[str, Any]]:
        """Get basic claim details."""
        try:
            response = self.supabase.table("research_claims").select(
                "*"
            ).eq("id", claim_id).limit(1).execute()
            return response.data[0] if response.data else None
        except Exception:
            return None
    
    def _determine_new_status(self, action: str, previous_status: Optional[str]) -> str:
        """Determine the new canonical status based on action."""
        action_map = {
            AdjudicationAction.APPROVE.value: CanonicalStatus.ACCEPTED.value,
            AdjudicationAction.REJECT.value: CanonicalStatus.REJECTED.value,
            AdjudicationAction.MARK_NEEDS_REVIEW.value: CanonicalStatus.NEEDS_REVIEW.value,
            AdjudicationAction.MARK_UNRESOLVED.value: CanonicalStatus.UNRESOLVED.value,
            AdjudicationAction.LOCK.value: previous_status or CanonicalStatus.UNRESOLVED.value,
            AdjudicationAction.UNLOCK.value: previous_status or CanonicalStatus.UNRESOLVED.value,
            AdjudicationAction.OVERRIDE_STATUS.value: CanonicalStatus.ACCEPTED.value,
            AdjudicationAction.OVERRIDE_CANONICAL.value: CanonicalStatus.ACCEPTED.value,
        }
        return action_map.get(action, previous_status or CanonicalStatus.UNRESOLVED.value)
    
    def _determine_source_of_truth(self, action: str, actor_type: str) -> str:
        """Determine the source of truth based on action and actor."""
        if action in (AdjudicationAction.OVERRIDE_STATUS.value, AdjudicationAction.OVERRIDE_CANONICAL.value):
            return SourceOfTruth.OVERRIDE.value
        elif actor_type in ("user", "admin"):
            return SourceOfTruth.HUMAN_REVIEW.value
        else:
            return SourceOfTruth.SYSTEM_RULE.value
    
    async def _create_canonical_version(
        self,
        claim_id: str,
        research_run_id: str,
        twin_id: str,
        canonical_status: str,
        source_of_truth: str,
        previous_canonical: Optional[CanonicalClaim],
        confidence: float = 0.0,
    ) -> CanonicalClaim:
        """
        Create a new canonical version, superseding the previous if exists.
        """
        now = datetime.utcnow().isoformat()
        new_version = 1
        
        # Supersede previous version if exists
        if previous_canonical:
            new_version = previous_canonical.version + 1
            self.supabase.table("research_claim_canonical").update({
                "superseded_at": now,
                "superseded_by": "pending",  # Will update after insert
                "updated_at": now,
            }).eq("id", previous_canonical.id).execute()
        
        # Create new canonical record
        new_id = str(uuid.uuid4())
        new_record = {
            "id": new_id,
            "claim_id": claim_id,
            "research_run_id": research_run_id,
            "twin_id": twin_id,
            "canonical_status": canonical_status,
            "source_of_truth": source_of_truth,
            "adjudication_confidence": confidence,
            "version": new_version,
            "effective_at": now,
            "created_at": now,
            "updated_at": now,
        }
        
        # Handle locking
        if canonical_status == AdjudicationAction.LOCK.value:
            new_record["locked"] = True
        elif canonical_status == AdjudicationAction.UNLOCK.value:
            new_record["locked"] = False
        elif previous_canonical:
            new_record["locked"] = previous_canonical.locked
        else:
            new_record["locked"] = False
        
        self.supabase.table("research_claim_canonical").insert(new_record).execute()
        
        # Update previous canonical's superseded_by if applicable
        if previous_canonical:
            self.supabase.table("research_claim_canonical").update({
                "superseded_by": new_id,
            }).eq("id", previous_canonical.id).execute()
        
        return CanonicalClaim(
            id=new_id,
            claim_id=claim_id,
            research_run_id=research_run_id,
            twin_id=twin_id,
            canonical_status=canonical_status,
            canonical_text=None,
            source_of_truth=source_of_truth,
            locked=new_record["locked"],
            locked_by=None,
            locked_at=None,
            lock_reason=None,
            adjudication_confidence=confidence,
            version=new_version,
            superseded_by=None,
            effective_at=now,
            superseded_at=None,
            created_at=now,
            updated_at=now,
        )
    
    async def _record_adjudication(
        self,
        claim_id: str,
        research_run_id: str,
        twin_id: str,
        action: str,
        previous_status: Optional[str],
        new_status: str,
        actor_id: str,
        actor_type: str,
        reason_code: Optional[str],
        notes: Optional[str],
        idempotency_key: str,
    ):
        """Record the adjudication action in the audit table."""
        self.supabase.table("research_claim_adjudications").insert({
            "id": str(uuid.uuid4()),
            "claim_id": claim_id,
            "research_run_id": research_run_id,
            "twin_id": twin_id,
            "action": action,
            "previous_status": previous_status,
            "new_status": new_status,
            "actor_id": actor_id,
            "actor_type": actor_type,
            "reason_code": reason_code,
            "notes": notes,
            "idempotency_key": idempotency_key,
            "created_at": datetime.utcnow().isoformat(),
        }).execute()
    
    def _determine_issue_status(self, action: str, previous_status: str) -> str:
        """Determine the new issue status based on action."""
        action_map = {
            IssueAction.CONFIRM_CONFLICT.value: "confirmed",
            IssueAction.DISMISS.value: "dismissed",
            IssueAction.MERGE_DUPLICATE.value: "merged",
            IssueAction.SPLIT_CONTEXT.value: "split",
            IssueAction.DEFER.value: "deferred",
        }
        return action_map.get(action, previous_status)


# ============================================================================
# Convenience Functions
# ============================================================================

async def adjudicate_claim(
    claim_id: str,
    twin_id: str,
    action: str,
    actor_id: str,
    **kwargs
) -> AdjudicationResult:
    """Convenience function to adjudicate a claim."""
    service = ResearchClaimAdjudicationService()
    return await service.adjudicate_claim(
        claim_id=claim_id,
        twin_id=twin_id,
        action=action,
        actor_id=actor_id,
        **kwargs
    )
