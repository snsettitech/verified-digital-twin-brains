"""
Research Claim Finalization Service (Phase 10)

Orchestrates finalization for research runs:
1. Fetch all claims with Phase 8 + 9 data
2. Apply finalization rules to each
3. Persist final decisions
4. Run consistency checker
5. Persist issues
6. Track finalization progress

Usage:
    service = ResearchClaimFinalizationService()
    summary = await service.finalize_research_run(run_id, twin_id)
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from modules.observability import supabase
from modules.research_claim_extractor import ResearchClaim, VerificationStatus
from modules.research_claim_web_verifier import WebVerificationStatus
from modules.research_claim_finalization_engine import (
    FinalizationEngine,
    FinalClaimStatus,
    FinalizationDecision,
)
from modules.research_claim_consistency_checker import (
    ConsistencyChecker,
    ConsistencyIssue,
    FinalizedClaim,
    get_issue_summary,
)

logger = logging.getLogger(__name__)


class FinalizationRunStatus(str, Enum):
    """Status of finalization for a research run."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"  # Some claims/issues failed


@dataclass
class FinalizationSummary:
    """Summary of claim finalization results."""
    research_run_id: str
    twin_id: str
    status: FinalizationRunStatus
    total_claims: int = 0
    finalized_count: int = 0
    issues_found: int = 0
    by_final_status: Dict[str, int] = field(default_factory=dict)
    by_issue_type: Dict[str, int] = field(default_factory=dict)
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "research_run_id": self.research_run_id,
            "twin_id": self.twin_id,
            "status": self.status.value,
            "total_claims": self.total_claims,
            "finalized_count": self.finalized_count,
            "issues_found": self.issues_found,
            "by_final_status": self.by_final_status,
            "by_issue_type": self.by_issue_type,
            "error_message": self.error_message,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass
class FinalizedClaimView:
    """Complete view of a finalized claim."""
    # Claim data
    claim_id: str
    claim_text: str
    claim_type: str
    
    # Phase 8 local verification
    local_status: str
    local_confidence: float
    
    # Phase 9 web verification
    web_status: Optional[str]
    web_confidence: float
    
    # Phase 10 finalization
    final_status: str
    final_confidence: float
    final_reason_codes: List[str]
    resolution_source: str
    finalized_at: Optional[str]
    notes: Optional[str]


class ResearchClaimFinalizationService:
    """
    Service for claim finalization operations (Phase 10).
    
    Orchestrates:
    1. Fetch claims with Phase 8 + 9 data
    2. Apply finalization rules
    3. Persist final decisions
    4. Run consistency checks
    5. Persist issues
    6. Update finalization status
    
    Idempotent: Safe to retry without duplication.
    """
    
    def __init__(self, supabase_client=None):
        """
        Initialize service.
        
        Args:
            supabase_client: Optional Supabase client (for testing)
        """
        self.db = supabase_client or supabase
        self.finalization_engine = FinalizationEngine()
        self.consistency_checker = ConsistencyChecker()
    
    async def get_finalization_status(
        self,
        research_run_id: str,
        twin_id: str,
    ) -> Optional[FinalizationSummary]:
        """
        Get current finalization status for a research run.
        
        Args:
            research_run_id: Research run ID
            twin_id: Twin ID for scoping
            
        Returns:
            FinalizationSummary or None if not started
        """
        try:
            result = self.db.table("research_claim_finalization_runs").select(
                "*"
            ).eq("research_run_id", research_run_id).eq("twin_id", twin_id).single().execute()
            
            if not result.data:
                return None
            
            data = result.data
            
            # Get status breakdown
            status_result = self.db.table("research_claim_finalizations").select(
                "final_status"
            ).eq("research_run_id", research_run_id).execute()
            
            by_status = {}
            if status_result.data:
                for row in status_result.data:
                    status = row.get("final_status", "unknown")
                    by_status[status] = by_status.get(status, 0) + 1
            
            # Get issue breakdown
            issue_result = self.db.table("research_claim_consistency_issues").select(
                "issue_type"
            ).eq("research_run_id", research_run_id).execute()
            
            by_issue = {}
            if issue_result.data:
                for row in issue_result.data:
                    itype = row.get("issue_type", "unknown")
                    by_issue[itype] = by_issue.get(itype, 0) + 1
            
            return FinalizationSummary(
                research_run_id=data["research_run_id"],
                twin_id=data["twin_id"],
                status=FinalizationRunStatus(data.get("status", "pending")),
                total_claims=data.get("total_claims", 0),
                finalized_count=data.get("finalized_count", 0),
                issues_found=data.get("issues_found", 0),
                by_final_status=by_status,
                by_issue_type=by_issue,
                error_message=data.get("error_message"),
                started_at=data.get("started_at"),
                completed_at=data.get("completed_at"),
            )
            
        except Exception as e:
            logger.error(f"Error getting finalization status: {e}")
            return None
    
    async def finalize_research_run(
        self,
        research_run_id: str,
        twin_id: str,
    ) -> FinalizationSummary:
        """
        Start or continue finalization for a research run.
        
        Idempotent:
        - If already completed, returns existing summary
        - If in progress, returns current status
        - If not started, begins finalization process
        
        Args:
            research_run_id: Research run ID
            twin_id: Twin ID
            
        Returns:
            FinalizationSummary
        """
        # Check current status
        existing = await self.get_finalization_status(research_run_id, twin_id)
        
        if existing:
            if existing.status == FinalizationRunStatus.COMPLETED:
                logger.info(f"Finalization already completed for {research_run_id}")
                return existing
            
            if existing.status == FinalizationRunStatus.RUNNING:
                logger.info(f"Finalization already in progress for {research_run_id}")
                return existing
        
        # Set status to running
        await self._update_run_status(
            research_run_id, twin_id, FinalizationRunStatus.RUNNING
        )
        
        try:
            # Fetch claims with Phase 8 + 9 data
            claims_data = await self._get_claims_with_verification(research_run_id, twin_id)
            
            if not claims_data:
                logger.warning(f"No claims found for {research_run_id}")
                summary = await self._complete_finalization(
                    research_run_id, twin_id, [], [], "No claims available"
                )
                return summary
            
            logger.info(f"Finalizing {len(claims_data)} claims for {research_run_id}")
            
            # Finalize each claim
            finalized_claims: List[FinalizedClaim] = []
            
            for claim, local_status, local_conf, web_status, web_conf in claims_data:
                try:
                    # Apply finalization rules
                    decision = self.finalization_engine.finalize_claim(
                        claim=claim,
                        local_status=local_status,
                        local_confidence=local_conf,
                        web_status=web_status,
                        web_confidence=web_conf,
                    )
                    
                    # Persist finalization
                    await self._persist_finalization(
                        research_run_id,
                        twin_id,
                        claim,
                        local_status,
                        local_conf,
                        web_status,
                        web_conf,
                        decision,
                    )
                    
                    # Add to list for consistency check
                    finalized_claims.append(FinalizedClaim(
                        claim=claim,
                        final_status=decision.final_status,
                        final_confidence=decision.final_confidence,
                        local_status=local_status.value,
                        web_status=web_status.value if web_status else None,
                    ))
                    
                except Exception as e:
                    logger.error(f"Failed to finalize claim {claim.id}: {e}")
                    # Continue with other claims
            
            # Run consistency check
            issues = self.consistency_checker.check_consistency(finalized_claims)
            
            # Persist issues
            for issue in issues:
                await self._persist_consistency_issue(research_run_id, twin_id, issue)
            
            # Complete finalization
            summary = await self._complete_finalization(
                research_run_id,
                twin_id,
                finalized_claims,
                issues,
            )
            
            logger.info(f"Finalization completed for {research_run_id}: "
                       f"{summary.finalized_count} claims, {summary.issues_found} issues")
            
            return summary
            
        except Exception as e:
            logger.error(f"Finalization failed for {research_run_id}: {e}")
            await self._update_run_status(
                research_run_id,
                twin_id,
                FinalizationRunStatus.FAILED,
                error_message=str(e),
            )
            return FinalizationSummary(
                research_run_id=research_run_id,
                twin_id=twin_id,
                status=FinalizationRunStatus.FAILED,
                error_message=str(e),
            )
    
    async def _get_claims_with_verification(
        self,
        research_run_id: str,
        twin_id: str,
    ) -> List[tuple]:
        """
        Fetch claims with Phase 8 and Phase 9 verification data.
        
        Returns:
            List of tuples: (claim, local_status, local_conf, web_status, web_conf)
        """
        try:
            # Fetch claims from Phase 8
            claims_result = self.db.table("research_claims").select(
                "*"
            ).eq("research_run_id", research_run_id).eq("twin_id", twin_id).execute()
            
            if not claims_result.data:
                return []
            
            claims_data = []
            for row in claims_result.data:
                claim = ResearchClaim.from_dict(row)
                local_status = VerificationStatus(row.get("verification_status", "pending"))
                local_conf = row.get("confidence", 0.5)
                
                # Fetch Phase 9 web verification if available
                web_result = self.db.table("research_claim_web_verifications").select(
                    "*"
                ).eq("claim_id", claim.id).single().execute()
                
                if web_result.data:
                    web_data = web_result.data
                    web_status = WebVerificationStatus(
                        web_data.get("web_verification_status", "pending")
                    )
                    web_conf = web_data.get("web_verification_confidence", 0.0)
                else:
                    web_status = None
                    web_conf = 0.0
                
                claims_data.append((claim, local_status, local_conf, web_status, web_conf))
            
            return claims_data
            
        except Exception as e:
            logger.error(f"Error fetching claims with verification: {e}")
            return []
    
    async def _persist_finalization(
        self,
        research_run_id: str,
        twin_id: str,
        claim: ResearchClaim,
        local_status: VerificationStatus,
        local_conf: float,
        web_status: Optional[WebVerificationStatus],
        web_conf: float,
        decision: FinalizationDecision,
    ) -> None:
        """Persist finalization decision to database."""
        try:
            data = {
                "claim_id": claim.id,
                "research_run_id": research_run_id,
                "twin_id": twin_id,
                "final_status": decision.final_status.value,
                "final_confidence": decision.final_confidence,
                "final_reason_codes": decision.reason_codes,
                "resolution_source": "system_rule",
                "local_verification_status": local_status.value,
                "local_confidence": local_conf,
                "web_verification_status": web_status.value if web_status else None,
                "web_confidence": web_conf,
                "notes": decision.notes,
                "finalized_at": datetime.utcnow().isoformat(),
            }
            
            # Upsert with claim_id as unique key
            self.db.table("research_claim_finalizations").upsert(
                data,
                on_conflict="claim_id"
            ).execute()
            
        except Exception as e:
            logger.error(f"Error persisting finalization: {e}")
            raise
    
    async def _persist_consistency_issue(
        self,
        research_run_id: str,
        twin_id: str,
        issue: ConsistencyIssue,
    ) -> None:
        """Persist consistency issue to database."""
        try:
            data = {
                "research_run_id": research_run_id,
                "twin_id": twin_id,
                "issue_type": issue.issue_type.value,
                "severity": issue.severity.value,
                "status": "open",
                "claim_ids": issue.claim_ids,
                "title": issue.title,
                "description": issue.description,
                "detection_rule": issue.detection_rule,
                "confidence": issue.confidence,
                "issue_hash": issue.issue_hash,
            }
            
            # Upsert with issue_hash for deduplication
            self.db.table("research_claim_consistency_issues").upsert(
                data,
                on_conflict="issue_hash"
            ).execute()
            
        except Exception as e:
            logger.error(f"Error persisting consistency issue: {e}")
            # Don't raise - continue with other issues
    
    async def _update_run_status(
        self,
        research_run_id: str,
        twin_id: str,
        status: FinalizationRunStatus,
        error_message: Optional[str] = None,
    ) -> None:
        """Update finalization run status."""
        data = {
            "research_run_id": research_run_id,
            "twin_id": twin_id,
            "status": status.value,
        }
        
        if status == FinalizationRunStatus.RUNNING:
            data["started_at"] = datetime.utcnow().isoformat()
        
        if error_message:
            data["error_message"] = error_message
        
        try:
            self.db.table("research_claim_finalization_runs").upsert(
                data,
                on_conflict="research_run_id"
            ).execute()
        except Exception as e:
            logger.error(f"Error updating run status: {e}")
    
    async def _complete_finalization(
        self,
        research_run_id: str,
        twin_id: str,
        finalized_claims: List[FinalizedClaim],
        issues: List[ConsistencyIssue],
        error_message: Optional[str] = None,
    ) -> FinalizationSummary:
        """Complete finalization and update database."""
        # Count by status
        by_status = {}
        for fc in finalized_claims:
            s = fc.final_status.value
            by_status[s] = by_status.get(s, 0) + 1
        
        # Count by issue type
        by_issue = {}
        for issue in issues:
            t = issue.issue_type.value
            by_issue[t] = by_issue.get(t, 0) + 1
        
        # Determine overall status
        if error_message:
            status = FinalizationRunStatus.FAILED
        else:
            status = FinalizationRunStatus.COMPLETED
        
        # Update database
        data = {
            "research_run_id": research_run_id,
            "twin_id": twin_id,
            "status": status.value,
            "total_claims": len(finalized_claims),
            "finalized_count": len(finalized_claims),
            "issues_found": len(issues),
            "error_message": error_message,
            "completed_at": datetime.utcnow().isoformat(),
        }
        
        try:
            self.db.table("research_claim_finalization_runs").upsert(
                data,
                on_conflict="research_run_id"
            ).execute()
        except Exception as e:
            logger.error(f"Error completing finalization: {e}")
        
        return FinalizationSummary(
            research_run_id=research_run_id,
            twin_id=twin_id,
            status=status,
            total_claims=len(finalized_claims),
            finalized_count=len(finalized_claims),
            issues_found=len(issues),
            by_final_status=by_status,
            by_issue_type=by_issue,
            error_message=error_message,
            completed_at=datetime.utcnow().isoformat(),
        )
    
    async def list_finalized_claims(
        self,
        research_run_id: str,
        twin_id: str,
        final_status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[FinalizedClaimView]:
        """
        List finalized claims with complete Phase 8/9/10 data.
        """
        try:
            # Join claims with finalizations
            query = """
                SELECT 
                    rc.id as claim_id,
                    rc.claim_text,
                    rc.claim_type,
                    rc.verification_status as local_status,
                    rc.confidence as local_confidence,
                    rcw.web_verification_status as web_status,
                    rcw.web_verification_confidence as web_confidence,
                    rcf.final_status,
                    rcf.final_confidence,
                    rcf.final_reason_codes,
                    rcf.resolution_source,
                    rcf.finalized_at,
                    rcf.notes
                FROM research_claims rc
                LEFT JOIN research_claim_finalizations rcf ON rc.id = rcf.claim_id
                LEFT JOIN research_claim_web_verifications rcw ON rc.id = rcw.claim_id
                WHERE rc.research_run_id = %s AND rc.twin_id = %s
            """
            
            result = self.db.rpc("execute_sql", {"sql": query, "params": [research_run_id, twin_id]}).execute()
            
            views = []
            for row in (result.data or []):
                if final_status and row.get("final_status") != final_status:
                    continue
                views.append(FinalizedClaimView(
                    claim_id=row["claim_id"],
                    claim_text=row["claim_text"],
                    claim_type=row["claim_type"],
                    local_status=row["local_status"],
                    local_confidence=row["local_confidence"],
                    web_status=row.get("web_status"),
                    web_confidence=row.get("web_confidence") or 0.0,
                    final_status=row.get("final_status") or "unresolved",
                    final_confidence=row.get("final_confidence") or 0.0,
                    final_reason_codes=row.get("final_reason_codes") or [],
                    resolution_source=row.get("resolution_source") or "system_rule",
                    finalized_at=row.get("finalized_at"),
                    notes=row.get("notes"),
                ))
            
            return views[offset:offset + limit]
            
        except Exception as e:
            logger.error(f"Error listing finalized claims: {e}")
            return []
    
    async def list_consistency_issues(
        self,
        research_run_id: str,
        twin_id: str,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List consistency issues for a research run."""
        try:
            query = self.db.table("research_claim_consistency_issues").select(
                "*"
            ).eq("research_run_id", research_run_id).eq("twin_id", twin_id)
            
            if status:
                query = query.eq("status", status)
            if severity:
                query = query.eq("severity", severity)
            
            query = query.order("created_at", desc=True).limit(limit).offset(offset)
            result = query.execute()
            
            return result.data or []
            
        except Exception as e:
            logger.error(f"Error listing consistency issues: {e}")
            return []
    
    async def resolve_consistency_issue(
        self,
        issue_id: str,
        research_run_id: str,
        twin_id: str,
        action: str,
        notes: str,
        user_id: str,
    ) -> bool:
        """
        Resolve a consistency issue.
        
        Args:
            issue_id: Issue ID
            research_run_id: Research run ID
            twin_id: Twin ID
            action: 'dismissed', 'claims_updated', 'manual_override'
            notes: Resolution notes
            user_id: User ID
            
        Returns:
            True if successful
        """
        try:
            data = {
                "status": "resolved" if action != "dismissed" else "dismissed",
                "resolved_by": user_id,
                "resolved_at": datetime.utcnow().isoformat(),
                "resolution_notes": notes,
                "resolution_action": action,
            }
            
            self.db.table("research_claim_consistency_issues").update(data).eq(
                "id", issue_id
            ).eq("research_run_id", research_run_id).eq("twin_id", twin_id).execute()
            
            return True
            
        except Exception as e:
            logger.error(f"Error resolving consistency issue: {e}")
            return False
    
    async def manual_override_final_status(
        self,
        claim_id: str,
        research_run_id: str,
        twin_id: str,
        new_status: FinalClaimStatus,
        reason: str,
        user_id: str,
    ) -> bool:
        """
        Manually override a claim's final status.
        
        Args:
            claim_id: Claim ID
            research_run_id: Research run ID
            twin_id: Twin ID
            new_status: New final status
            reason: Override reason
            user_id: User ID
            
        Returns:
            True if successful
        """
        try:
            data = {
                "final_status": new_status.value,
                "resolution_source": "manual_override",
                "finalized_by": user_id,
                "finalized_at": datetime.utcnow().isoformat(),
                "notes": f"[MANUAL OVERRIDE] {reason}",
            }
            
            self.db.table("research_claim_finalizations").update(data).eq(
                "claim_id", claim_id
            ).eq("research_run_id", research_run_id).eq("twin_id", twin_id).execute()
            
            return True
            
        except Exception as e:
            logger.error(f"Error overriding final status: {e}")
            return False


# =============================================================================
# Convenience Functions
# =============================================================================

async def finalize_research_run_claims(
    research_run_id: str,
    twin_id: str,
) -> FinalizationSummary:
    """
    Main entry point: finalize claims for a research run.
    
    Args:
        research_run_id: Research run ID
        twin_id: Twin ID
        
    Returns:
        FinalizationSummary
    """
    service = ResearchClaimFinalizationService()
    return await service.finalize_research_run(research_run_id, twin_id)
