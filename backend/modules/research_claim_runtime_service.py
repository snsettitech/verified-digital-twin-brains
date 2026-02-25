"""
Research Claim Runtime Service (Phase 12)

Runtime Publication + Deployment Readiness

Provides:
- Publication of claims to runtime layer
- Deterministic publication rules
- Backfill service for historical runs
- Export functionality
- Observability and audit trail

Usage:
    service = ResearchClaimRuntimeService()
    
    # Publish runtime claims
    result = await service.publish_runtime_claims(
        research_run_id="run-abc",
        twin_id="twin-456"
    )
    
    # Get published claims
    claims = await service.get_runtime_claims(
        twin_id="twin-456",
        filters={"published": True}
    )
    
    # Backfill historical runs
    result = await service.backfill_publication(
        twin_id="twin-456",
        dry_run=True
    )
"""

import uuid
import hashlib
import json
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from modules.observability import supabase as _supabase
from modules.deep_research_config import get_config as get_dr_config
from modules.research_claim_adjudication_service import (
    ResearchClaimAdjudicationService,
    CanonicalStatus,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Constants
# ============================================================================

class PublicationStatus(str, Enum):
    """Publication run statuses."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


class RuntimeStatus(str, Enum):
    """Runtime claim statuses."""
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"
    UNPUBLISHED = "unpublished"


class SuppressionReason(str, Enum):
    """Reasons for claim suppression."""
    UNRESOLVED_STATUS = "unresolved_status"
    REJECTED_CLAIM = "rejected_claim"
    OPEN_CONSISTENCY_ISSUE = "open_consistency_issue"
    LOW_CONFIDENCE = "low_confidence"
    MANUAL_HOLD = "manual_hold"
    RULE_VIOLATION = "rule_violation"


class PublicationAction(str, Enum):
    """Publication audit actions."""
    PUBLISHED = "published"
    SUPPRESSED = "suppressed"
    UPDATED = "updated"
    UNPUBLISHED = "unpublished"
    REPUBLISHED = "republished"
    BATCH_PUBLISH = "batch_publish"
    BACKFILL = "backfill"


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class PublicationRule:
    """A publication rule with condition and outcome."""
    name: str
    condition: str  # Description of the condition
    publishable: bool
    priority: int
    suppression_reason: Optional[str] = None


@dataclass
class PublicationResult:
    """Result of a publication run."""
    success: bool
    research_run_id: str
    status: str
    total_claims: int
    published_count: int
    suppressed_count: int
    skipped_count: int
    errors: List[str] = field(default_factory=list)


@dataclass
class RuntimeClaim:
    """A claim in the runtime publication layer."""
    id: str
    claim_id: str
    research_run_id: str
    twin_id: str
    publishable: bool
    published: bool
    suppressed: bool
    suppression_reason: Optional[str]
    runtime_claim_text: str
    runtime_status: str
    runtime_confidence: float
    runtime_issue_flags: List[str]
    runtime_citations: List[Dict[str, Any]]
    source_canonical_id: Optional[str]
    source_finalization_id: Optional[str]
    published_at: Optional[str]
    published_version: int
    content_hash: Optional[str]
    created_at: str
    updated_at: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "claim_id": self.claim_id,
            "research_run_id": self.research_run_id,
            "twin_id": self.twin_id,
            "publishable": self.publishable,
            "published": self.published,
            "suppressed": self.suppressed,
            "suppression_reason": self.suppression_reason,
            "runtime_claim_text": self.runtime_claim_text,
            "runtime_status": self.runtime_status,
            "runtime_confidence": self.runtime_confidence,
            "runtime_issue_flags": self.runtime_issue_flags,
            "runtime_citations": self.runtime_citations,
            "source_canonical_id": self.source_canonical_id,
            "source_finalization_id": self.source_finalization_id,
            "published_at": self.published_at,
            "published_version": self.published_version,
            "content_hash": self.content_hash,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class BackfillResult:
    """Result of a backfill operation."""
    success: bool
    total_runs: int
    processed_runs: int
    failed_runs: int
    total_claims: int
    published_count: int
    suppressed_count: int
    errors: List[str] = field(default_factory=list)
    resume_token: Optional[str] = None


@dataclass
class ExportResult:
    """Result of an export operation."""
    success: bool
    format: str
    record_count: int
    data: Any
    error: Optional[str] = None


# ============================================================================
# Publication Rule Engine
# ============================================================================

class PublicationRuleEngine:
    """
    Engine for applying publication rules to claims.
    
    Rules are applied in priority order, with the first matching rule
    determining the publishability of a claim.
    """
    
    DEFAULT_RULES = [
        PublicationRule(
            name="accept_canonical_accepted",
            condition="canonical_status == 'accepted'",
            publishable=True,
            priority=1,
        ),
        PublicationRule(
            name="suppress_canonical_rejected",
            condition="canonical_status == 'rejected'",
            publishable=False,
            priority=2,
            suppression_reason=SuppressionReason.REJECTED_CLAIM.value,
        ),
        PublicationRule(
            name="suppress_unresolved",
            condition="canonical_status == 'unresolved' AND suppress_unresolved_default",
            publishable=False,
            priority=3,
            suppression_reason=SuppressionReason.UNRESOLVED_STATUS.value,
        ),
        PublicationRule(
            name="suppress_needs_review",
            condition="canonical_status == 'needs_review' AND require_human_review",
            publishable=False,
            priority=4,
            suppression_reason=SuppressionReason.UNRESOLVED_STATUS.value,
        ),
        PublicationRule(
            name="suppress_open_high_severity",
            condition="has_open_issues AND max_severity == 'high'",
            publishable=False,
            priority=5,
            suppression_reason=SuppressionReason.OPEN_CONSISTENCY_ISSUE.value,
        ),
        PublicationRule(
            name="suppress_low_confidence",
            condition="confidence < min_confidence_threshold",
            publishable=False,
            priority=6,
            suppression_reason=SuppressionReason.LOW_CONFIDENCE.value,
        ),
        PublicationRule(
            name="default_accept",
            condition="default",
            publishable=True,
            priority=100,
        ),
    ]
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the rule engine.
        
        Args:
            config: Optional configuration overrides
        """
        self.rules = self.DEFAULT_RULES.copy()
        self.config = config or {}
    
    def evaluate_claim(
        self,
        claim_data: Dict[str, Any],
        canonical_data: Optional[Dict[str, Any]],
        issue_data: List[Dict[str, Any]],
    ) -> Tuple[bool, Optional[str], List[str]]:
        """
        Evaluate a claim against publication rules.
        
        Args:
            claim_data: The claim record
            canonical_data: The canonical claim record
            issue_data: List of open issues for this claim
            
        Returns:
            Tuple of (publishable, suppression_reason, issue_flags)
        """
        context = self._build_context(claim_data, canonical_data, issue_data)
        
        for rule in sorted(self.rules, key=lambda r: r.priority):
            if self._matches_rule(rule, context):
                issue_flags = self._get_issue_flags(context)
                if rule.publishable:
                    return True, None, issue_flags
                else:
                    return False, rule.suppression_reason, issue_flags
        
        # Default: not publishable
        return False, SuppressionReason.RULE_VIOLATION.value, []
    
    def _build_context(
        self,
        claim_data: Dict[str, Any],
        canonical_data: Optional[Dict[str, Any]],
        issue_data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Build evaluation context from claim data."""
        dr_config = get_dr_config()
        
        max_severity = None
        has_open_issues = False
        if issue_data:
            has_open_issues = True
            severities = [i.get("severity", "medium") for i in issue_data]
            if "high" in severities:
                max_severity = "high"
            elif "medium" in severities:
                max_severity = "medium"
            else:
                max_severity = "low"
        
        return {
            "claim_status": claim_data.get("verification_status"),
            "canonical_status": canonical_data.get("canonical_status") if canonical_data else None,
            "locked": canonical_data.get("locked") if canonical_data else False,
            "confidence": canonical_data.get("adjudication_confidence", 0.0) if canonical_data else 0.0,
            "has_open_issues": has_open_issues,
            "max_severity": max_severity,
            "issue_count": len(issue_data),
            "suppress_unresolved_default": dr_config.phase_12_suppress_unresolved_by_default,
            "require_human_review": not dr_config.phase_12_auto_publish,
            "min_confidence_threshold": self.config.get("min_confidence_threshold", 0.0),
        }
    
    def _matches_rule(self, rule: PublicationRule, context: Dict[str, Any]) -> bool:
        """Check if a rule matches the context."""
        # For simplicity, we use basic condition evaluation
        # In production, consider using a proper expression evaluator
        
        if rule.condition == "default":
            return True
        
        condition = rule.condition
        
        # Replace placeholders with context values
        for key, value in context.items():
            if isinstance(value, bool):
                condition = condition.replace(key, str(value))
            elif isinstance(value, str):
                condition = condition.replace(f"{key} == '{value}'", "True")
                condition = condition.replace(f"{key} != '{value}'", "False")
            elif isinstance(value, (int, float)):
                condition = condition.replace(key, str(value))
        
        try:
            # Evaluate the condition
            result = eval(condition, {"__builtins__": {}}, {})
            return bool(result)
        except Exception:
            # If evaluation fails, assume no match
            return False
    
    def _get_issue_flags(self, context: Dict[str, Any]) -> List[str]:
        """Get list of issue flags based on context."""
        flags = []
        if context.get("has_open_issues"):
            flags.append("has_open_issues")
        if context.get("max_severity") == "high":
            flags.append("high_severity_conflict")
        if context.get("canonical_status") == "needs_review":
            flags.append("needs_review")
        if context.get("canonical_status") == "unresolved":
            flags.append("unresolved")
        if context.get("locked"):
            flags.append("locked")
        return flags


# ============================================================================
# Main Service Class
# ============================================================================

class ResearchClaimRuntimeService:
    """
    Service for runtime publication of claims.
    
    Responsibilities:
    - Publish claims to runtime layer based on rules
    - Manage publication runs and backfill
    - Provide export functionality
    - Maintain audit trail
    """
    
    def __init__(self, supabase_client=None):
        """
        Initialize the runtime service.
        
        Args:
            supabase_client: Optional Supabase client for dependency injection
        """
        self.supabase = supabase_client or _supabase
        self.config = get_dr_config()
        self.rule_engine = PublicationRuleEngine()
        self.adjudication_service = ResearchClaimAdjudicationService(supabase_client)
    
    # ========================================================================
    # Core Publication Methods
    # ========================================================================
    
    async def publish_runtime_claims(
        self,
        research_run_id: str,
        twin_id: str,
        auto_publish: bool = False,
        correlation_id: Optional[str] = None,
    ) -> PublicationResult:
        """
        Publish claims to the runtime layer.
        
        Args:
            research_run_id: The research run to publish
            twin_id: Twin scope
            auto_publish: Whether to auto-publish without manual review
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            PublicationResult with counts and status
        """
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        
        try:
            # Create publication run record
            run_id = await self._create_publication_run(
                research_run_id=research_run_id,
                twin_id=twin_id,
                correlation_id=correlation_id,
            )
            
            # Update status to running
            await self._update_publication_run_status(
                run_id, PublicationStatus.RUNNING.value
            )
            
            # Get all claims for this research run
            claims_response = self.supabase.table("research_claims").select(
                "*"
            ).eq("research_run_id", research_run_id).eq("twin_id", twin_id).execute()
            
            if not claims_response.data:
                await self._update_publication_run_status(
                    run_id, PublicationStatus.COMPLETED.value, completed=True
                )
                return PublicationResult(
                    success=True,
                    research_run_id=research_run_id,
                    status=PublicationStatus.COMPLETED.value,
                    total_claims=0,
                    published_count=0,
                    suppressed_count=0,
                    skipped_count=0,
                )
            
            total = len(claims_response.data)
            published = 0
            suppressed = 0
            skipped = 0
            errors = []
            
            for claim in claims_response.data:
                try:
                    result = await self._process_claim(
                        claim=claim,
                        research_run_id=research_run_id,
                        twin_id=twin_id,
                        auto_publish=auto_publish or self.config.phase_12_auto_publish,
                        correlation_id=correlation_id,
                    )
                    
                    if result["published"]:
                        published += 1
                    elif result["suppressed"]:
                        suppressed += 1
                    else:
                        skipped += 1
                        
                except Exception as e:
                    logger.error(f"Error processing claim {claim.get('id')}: {e}")
                    errors.append(str(e))
                    skipped += 1
            
            # Update publication run
            status = PublicationStatus.COMPLETED.value if not errors else PublicationStatus.PARTIAL.value
            await self._update_publication_run_status(
                run_id, status, completed=True,
                total=total, published=published, suppressed=suppressed
            )
            
            return PublicationResult(
                success=True,
                research_run_id=research_run_id,
                status=status,
                total_claims=total,
                published_count=published,
                suppressed_count=suppressed,
                skipped_count=skipped,
                errors=errors,
            )
            
        except Exception as e:
            logger.error(f"Error publishing runtime claims: {e}")
            return PublicationResult(
                success=False,
                research_run_id=research_run_id,
                status=PublicationStatus.FAILED.value,
                total_claims=0,
                published_count=0,
                suppressed_count=0,
                skipped_count=0,
                errors=[str(e)],
            )
    
    async def _process_claim(
        self,
        claim: Dict[str, Any],
        research_run_id: str,
        twin_id: str,
        auto_publish: bool,
        correlation_id: str,
    ) -> Dict[str, Any]:
        """Process a single claim for runtime publication."""
        claim_id = claim["id"]
        
        # Get canonical data
        canonical_response = self.supabase.table("research_claim_canonical").select(
            "*"
        ).eq("claim_id", claim_id).is_("superseded_at", None).limit(1).execute()
        
        canonical = canonical_response.data[0] if canonical_response.data else None
        
        # Get open issues
        issues_response = self.supabase.table("research_claim_consistency_issues").select(
            "*"
        ).eq("research_run_id", research_run_id).contains("claim_ids", [claim_id]).eq("status", "open").execute()
        
        issues = issues_response.data if issues_response.data else []
        
        # Apply publication rules
        publishable, suppression_reason, issue_flags = self.rule_engine.evaluate_claim(
            claim_data=claim,
            canonical_data=canonical,
            issue_data=issues,
        )
        
        # Determine runtime status
        if canonical:
            runtime_status = self._map_canonical_to_runtime(canonical["canonical_status"])
            confidence = canonical.get("adjudication_confidence", 0.0)
        else:
            runtime_status = RuntimeStatus.UNPUBLISHED.value
            confidence = 0.0
        
        # Check for existing runtime publication
        existing = await self._get_existing_runtime_publication(claim_id)
        
        # Generate content hash
        content_hash = self._generate_content_hash(claim)
        
        now = datetime.utcnow().isoformat()
        
        if existing:
            # Update existing
            update_data = {
                "publishable": publishable,
                "suppressed": not publishable and suppression_reason is not None,
                "suppression_reason": suppression_reason,
                "runtime_status": runtime_status,
                "runtime_confidence": confidence,
                "runtime_issue_flags": issue_flags,
                "source_canonical_id": canonical["id"] if canonical else None,
                "source_finalization_id": None,  # Will be populated later
                "content_hash": content_hash,
                "updated_at": now,
            }
            
            # Auto-publish if enabled and publishable
            if auto_publish and publishable and not existing["published"]:
                update_data["published"] = True
                update_data["published_at"] = now
                update_data["published_version"] = existing["published_version"] + 1
            
            self.supabase.table("research_claim_runtime_publication").update(
                update_data
            ).eq("id", existing["id"]).execute()
            
            # Record audit
            await self._record_publication_audit(
                publication_id=existing["id"],
                claim_id=claim_id,
                research_run_id=research_run_id,
                twin_id=twin_id,
                action=PublicationAction.UPDATED.value,
                correlation_id=correlation_id,
            )
            
        else:
            # Create new
            new_id = str(uuid.uuid4())
            insert_data = {
                "id": new_id,
                "claim_id": claim_id,
                "research_run_id": research_run_id,
                "twin_id": twin_id,
                "publishable": publishable,
                "published": auto_publish and publishable,
                "suppressed": not publishable and suppression_reason is not None,
                "suppression_reason": suppression_reason,
                "runtime_claim_text": claim.get("claim_text", ""),
                "runtime_status": runtime_status,
                "runtime_confidence": confidence,
                "runtime_issue_flags": issue_flags,
                "runtime_citations": claim.get("citations", []),
                "source_canonical_id": canonical["id"] if canonical else None,
                "source_finalization_id": None,
                "published_at": now if (auto_publish and publishable) else None,
                "published_version": 1,
                "content_hash": content_hash,
                "created_at": now,
                "updated_at": now,
            }
            
            self.supabase.table("research_claim_runtime_publication").insert(insert_data).execute()
            
            # Record audit
            await self._record_publication_audit(
                publication_id=new_id,
                claim_id=claim_id,
                research_run_id=research_run_id,
                twin_id=twin_id,
                action=PublicationAction.PUBLISHED.value if (auto_publish and publishable) else PublicationAction.SUPPRESSED.value,
                correlation_id=correlation_id,
            )
        
        return {
            "published": auto_publish and publishable,
            "suppressed": not publishable and suppression_reason is not None,
            "publishable": publishable,
        }
    
    # ========================================================================
    # Query Methods
    # ========================================================================
    
    async def get_runtime_claims(
        self,
        twin_id: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[RuntimeClaim]:
        """
        Get runtime claims for a twin.
        
        Args:
            twin_id: Twin scope
            filters: Optional filters (published, suppressed, status, etc.)
            limit: Max items to return
            offset: Pagination offset
            
        Returns:
            List of RuntimeClaim
        """
        try:
            query = self.supabase.table("research_claim_runtime_publication").select(
                "*"
            ).eq("twin_id", twin_id)
            
            if filters:
                if "published" in filters:
                    query = query.eq("published", filters["published"])
                if "suppressed" in filters:
                    query = query.eq("suppressed", filters["suppressed"])
                if "publishable" in filters:
                    query = query.eq("publishable", filters["publishable"])
                if "status" in filters:
                    query = query.eq("runtime_status", filters["status"])
                if "research_run_id" in filters:
                    query = query.eq("research_run_id", filters["research_run_id"])
            
            response = query.order("created_at", desc=True).limit(limit).offset(offset).execute()
            
            return [
                RuntimeClaim(
                    id=record["id"],
                    claim_id=record["claim_id"],
                    research_run_id=record["research_run_id"],
                    twin_id=record["twin_id"],
                    publishable=record.get("publishable", False),
                    published=record.get("published", False),
                    suppressed=record.get("suppressed", False),
                    suppression_reason=record.get("suppression_reason"),
                    runtime_claim_text=record.get("runtime_claim_text", ""),
                    runtime_status=record.get("runtime_status", RuntimeStatus.UNPUBLISHED.value),
                    runtime_confidence=record.get("runtime_confidence", 0.0),
                    runtime_issue_flags=record.get("runtime_issue_flags", []),
                    runtime_citations=record.get("runtime_citations", []),
                    source_canonical_id=record.get("source_canonical_id"),
                    source_finalization_id=record.get("source_finalization_id"),
                    published_at=record.get("published_at"),
                    published_version=record.get("published_version", 1),
                    content_hash=record.get("content_hash"),
                    created_at=record["created_at"],
                    updated_at=record["updated_at"],
                )
                for record in response.data
            ]
            
        except Exception as e:
            logger.error(f"Error getting runtime claims: {e}")
            return []
    
    async def get_publication_status(
        self,
        research_run_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get the publication status for a research run."""
        try:
            response = self.supabase.table("research_claim_publication_runs").select(
                "*"
            ).eq("research_run_id", research_run_id).limit(1).execute()
            
            return response.data[0] if response.data else None
            
        except Exception as e:
            logger.error(f"Error getting publication status: {e}")
            return None
    
    # ========================================================================
    # Backfill Methods
    # ========================================================================
    
    async def backfill_publication(
        self,
        twin_id: Optional[str] = None,
        research_run_ids: Optional[List[str]] = None,
        dry_run: bool = False,
        batch_size: int = 100,
        resume_token: Optional[str] = None,
    ) -> BackfillResult:
        """
        Backfill runtime publication for historical research runs.
        
        Args:
            twin_id: Optional twin to limit scope
            research_run_ids: Optional specific runs to backfill
            dry_run: If True, don't actually publish
            batch_size: Number of runs to process per batch
            resume_token: Optional token to resume from previous run
            
        Returns:
            BackfillResult with statistics
        """
        try:
            # Get runs to backfill
            if research_run_ids:
                runs = research_run_ids
            else:
                query = self.supabase.table("research_runs").select("id")
                if twin_id:
                    query = query.eq("twin_id", twin_id)
                
                # Only include runs in terminal states
                query = query.in_("status", [
                    "claims_finalized", "adjudicated", "runtime_published"
                ])
                
                if resume_token:
                    query = query.gt("id", resume_token)
                
                response = query.order("id").limit(batch_size).execute()
                runs = [r["id"] for r in response.data]
            
            total_runs = len(runs)
            processed = 0
            failed = 0
            total_claims = 0
            published_count = 0
            suppressed_count = 0
            errors = []
            
            for run_id in runs:
                try:
                    if not dry_run:
                        result = await self.publish_runtime_claims(
                            research_run_id=run_id,
                            twin_id=twin_id or await self._get_twin_for_run(run_id),
                            auto_publish=True,
                        )
                        
                        if result.success:
                            total_claims += result.total_claims
                            published_count += result.published_count
                            suppressed_count += result.suppressed_count
                        else:
                            failed += 1
                            errors.extend(result.errors)
                    
                    processed += 1
                    
                except Exception as e:
                    logger.error(f"Error backfilling run {run_id}: {e}")
                    failed += 1
                    errors.append(str(e))
            
            # Generate resume token for next batch
            next_resume_token = runs[-1] if runs and len(runs) == batch_size else None
            
            return BackfillResult(
                success=True,
                total_runs=total_runs,
                processed_runs=processed,
                failed_runs=failed,
                total_claims=total_claims,
                published_count=published_count,
                suppressed_count=suppressed_count,
                errors=errors,
                resume_token=next_resume_token,
            )
            
        except Exception as e:
            logger.error(f"Error in backfill operation: {e}")
            return BackfillResult(
                success=False,
                total_runs=0,
                processed_runs=0,
                failed_runs=0,
                total_claims=0,
                published_count=0,
                suppressed_count=0,
                errors=[str(e)],
            )
    
    # ========================================================================
    # Export Methods
    # ========================================================================
    
    async def export_runtime_claims(
        self,
        twin_id: str,
        format: str = "json",
        filters: Optional[Dict[str, Any]] = None,
    ) -> ExportResult:
        """
        Export runtime claims in various formats.
        
        Args:
            twin_id: Twin scope
            format: Export format (json, csv)
            filters: Optional filters
            
        Returns:
            ExportResult with data
        """
        try:
            claims = await self.get_runtime_claims(
                twin_id=twin_id,
                filters=filters,
                limit=10000,  # High limit for exports
            )
            
            if format == "json":
                data = [claim.to_dict() for claim in claims]
                return ExportResult(
                    success=True,
                    format=format,
                    record_count=len(data),
                    data=data,
                )
            
            elif format == "csv":
                import csv
                import io
                
                if not claims:
                    return ExportResult(
                        success=True,
                        format=format,
                        record_count=0,
                        data="",
                    )
                
                output = io.StringIO()
                fieldnames = [
                    "claim_id", "runtime_claim_text", "runtime_status",
                    "published", "suppressed", "suppression_reason",
                    "runtime_confidence", "published_at"
                ]
                
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                
                for claim in claims:
                    writer.writerow({
                        "claim_id": claim.claim_id,
                        "runtime_claim_text": claim.runtime_claim_text,
                        "runtime_status": claim.runtime_status,
                        "published": claim.published,
                        "suppressed": claim.suppressed,
                        "suppression_reason": claim.suppression_reason,
                        "runtime_confidence": claim.runtime_confidence,
                        "published_at": claim.published_at,
                    })
                
                return ExportResult(
                    success=True,
                    format=format,
                    record_count=len(claims),
                    data=output.getvalue(),
                )
            
            else:
                return ExportResult(
                    success=False,
                    format=format,
                    record_count=0,
                    data=None,
                    error=f"Unsupported format: {format}",
                )
            
        except Exception as e:
            logger.error(f"Error exporting runtime claims: {e}")
            return ExportResult(
                success=False,
                format=format,
                record_count=0,
                data=None,
                error=str(e),
            )
    
    # ========================================================================
    # Private Helper Methods
    # ========================================================================
    
    async def _create_publication_run(
        self,
        research_run_id: str,
        twin_id: str,
        correlation_id: str,
    ) -> str:
        """Create a publication run record."""
        run_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        # Check if publication run already exists
        existing = self.supabase.table("research_claim_publication_runs").select(
            "id"
        ).eq("research_run_id", research_run_id).limit(1).execute()
        
        if existing.data:
            # Update existing
            self.supabase.table("research_claim_publication_runs").update({
                "status": PublicationStatus.PENDING.value,
                "started_at": None,
                "completed_at": None,
                "updated_at": now,
            }).eq("id", existing.data[0]["id"]).execute()
            return existing.data[0]["id"]
        
        # Create new
        self.supabase.table("research_claim_publication_runs").insert({
            "id": run_id,
            "research_run_id": research_run_id,
            "twin_id": twin_id,
            "status": PublicationStatus.PENDING.value,
            "created_at": now,
            "updated_at": now,
        }).execute()
        
        return run_id
    
    async def _update_publication_run_status(
        self,
        run_id: str,
        status: str,
        completed: bool = False,
        total: int = 0,
        published: int = 0,
        suppressed: int = 0,
    ):
        """Update publication run status."""
        now = datetime.utcnow().isoformat()
        update_data = {
            "status": status,
            "updated_at": now,
        }
        
        if status == PublicationStatus.RUNNING.value:
            update_data["started_at"] = now
        
        if completed:
            update_data["completed_at"] = now
            update_data["total_claims"] = total
            update_data["published_count"] = published
            update_data["suppressed_count"] = suppressed
            update_data["skipped_count"] = total - published - suppressed
        
        self.supabase.table("research_claim_publication_runs").update(
            update_data
        ).eq("id", run_id).execute()
    
    async def _get_existing_runtime_publication(self, claim_id: str) -> Optional[Dict[str, Any]]:
        """Get existing runtime publication record for a claim."""
        try:
            response = self.supabase.table("research_claim_runtime_publication").select(
                "*"
            ).eq("claim_id", claim_id).limit(1).execute()
            return response.data[0] if response.data else None
        except Exception:
            return None
    
    def _generate_content_hash(self, claim: Dict[str, Any]) -> str:
        """Generate a hash of claim content for change detection."""
        content = json.dumps({
            "text": claim.get("claim_text", ""),
            "type": claim.get("claim_type", ""),
            "citations": claim.get("citations", []),
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:32]
    
    def _map_canonical_to_runtime(self, canonical_status: str) -> str:
        """Map canonical status to runtime status."""
        status_map = {
            CanonicalStatus.ACCEPTED.value: RuntimeStatus.ACCEPTED.value,
            CanonicalStatus.REJECTED.value: RuntimeStatus.REJECTED.value,
            CanonicalStatus.NEEDS_REVIEW.value: RuntimeStatus.NEEDS_REVIEW.value,
            CanonicalStatus.UNRESOLVED.value: RuntimeStatus.UNPUBLISHED.value,
        }
        return status_map.get(canonical_status, RuntimeStatus.UNPUBLISHED.value)
    
    async def _record_publication_audit(
        self,
        publication_id: str,
        claim_id: str,
        research_run_id: str,
        twin_id: str,
        action: str,
        correlation_id: str,
        actor_id: Optional[str] = None,
        actor_type: str = "system",
    ):
        """Record a publication action in the audit table."""
        self.supabase.table("research_claim_publication_audit").insert({
            "id": str(uuid.uuid4()),
            "publication_id": publication_id,
            "claim_id": claim_id,
            "research_run_id": research_run_id,
            "twin_id": twin_id,
            "action": action,
            "actor_id": actor_id,
            "actor_type": actor_type,
            "correlation_id": correlation_id,
            "created_at": datetime.utcnow().isoformat(),
        }).execute()
    
    async def _get_twin_for_run(self, research_run_id: str) -> str:
        """Get the twin ID for a research run."""
        response = self.supabase.table("research_runs").select(
            "twin_id"
        ).eq("id", research_run_id).single().execute()
        return response.data["twin_id"] if response.data else ""


# ============================================================================
# Convenience Functions
# ============================================================================

async def publish_runtime_claims(
    research_run_id: str,
    twin_id: str,
    **kwargs
) -> PublicationResult:
    """Convenience function to publish runtime claims."""
    service = ResearchClaimRuntimeService()
    return await service.publish_runtime_claims(
        research_run_id=research_run_id,
        twin_id=twin_id,
        **kwargs
    )
