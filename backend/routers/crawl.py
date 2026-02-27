"""
Crawl Router (Phase 1A.6)

REST API endpoints for Deep Research crawl management.

Deep Research routes are always enabled.
"""

import logging
import asyncio
import uuid
import re
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from modules.auth_guard import get_current_user, verify_twin_ownership, require_admin
from modules.observability import supabase
from modules.schemas import CrawlRunSchema

logger = logging.getLogger(__name__)

router = APIRouter(tags=["crawl"])

# Deep Research is always enabled. Keep helper for backward compatibility.
def _check_feature_enabled():
    """No-op compatibility check."""
    return None


# Tracks in-flight research crawl tasks keyed by research_run_id.
_ACTIVE_RESEARCH_CRAWL_TASKS: Dict[str, asyncio.Task[Any]] = {}


async def _run_research_crawl_pipeline(
    research_run_id: str,
    twin_id: str,
    crawl_id: str,
    claimed_identity: Optional[Dict[str, Any]],
) -> None:
    """
    Execute crawl processing for a research run and advance orchestrator status.

    Flow:
    1) Crawl pages with CrawlJobProcessor.
    2) On success, generate confirmations + transition via on_crawl_completed.
    3) On failure, transition run to failed.
    """
    from modules.crawl_job_processor import process_crawl_job
    from modules.research_orchestrator import ResearchOrchestrator, ResearchRunStatus

    orchestrator = ResearchOrchestrator()
    crawl_job_id = str(uuid.uuid4())

    try:
        crawl_result = await process_crawl_job(
            job_id=crawl_job_id,
            crawl_id=crawl_id,
            twin_id=twin_id,
            claimed_identity=claimed_identity or {},
        )

        crawl_status = getattr(getattr(crawl_result, "status", None), "value", None) or str(
            getattr(crawl_result, "status", "")
        )

        if crawl_status == "failed":
            error_message = getattr(crawl_result, "error_message", None) or "Crawl failed"
            failure_checkpoint = orchestrator._build_checkpoint(
                phase="crawl_failed",
                crawl_id=crawl_id,
                summary=None,
            )
            failure_checkpoint.warnings.append(error_message)
            await orchestrator._transition(
                research_run_id=research_run_id,
                twin_id=twin_id,
                to_status=ResearchRunStatus.FAILED,
                reason=f"Crawl failed: {error_message}",
                checkpoint=failure_checkpoint,
                crawl_id=crawl_id,
            )
            logger.error(
                "Research crawl failed: research_run_id=%s crawl_id=%s error=%s",
                research_run_id,
                crawl_id,
                error_message,
            )
            return

        transition = await orchestrator.on_crawl_completed(
            research_run_id=research_run_id,
            twin_id=twin_id,
            crawl_id=crawl_id,
        )
        if not transition.success:
            transition_error = transition.error or "on_crawl_completed returned unsuccessful result"
            failure_checkpoint = orchestrator._build_checkpoint(
                phase="crawl_transition_failed",
                crawl_id=crawl_id,
                summary=None,
            )
            failure_checkpoint.warnings.append(transition_error)
            await orchestrator._transition(
                research_run_id=research_run_id,
                twin_id=twin_id,
                to_status=ResearchRunStatus.FAILED,
                reason=f"Crawl completion transition failed: {transition_error}",
                checkpoint=failure_checkpoint,
                crawl_id=crawl_id,
            )
            logger.error(
                "Research crawl completion transition failed: research_run_id=%s crawl_id=%s error=%s",
                research_run_id,
                crawl_id,
                transition_error,
            )
            return

        logger.info(
            "Research crawl completed: research_run_id=%s crawl_id=%s transitioned=%s",
            research_run_id,
            crawl_id,
            transition.new_status,
        )

    except Exception as e:
        logger.exception(
            "Unhandled error in research crawl pipeline: research_run_id=%s crawl_id=%s err=%s",
            research_run_id,
            crawl_id,
            e,
        )
        try:
            failure_checkpoint = orchestrator._build_checkpoint(
                phase="crawl_pipeline_exception",
                crawl_id=crawl_id,
                summary=None,
            )
            failure_checkpoint.warnings.append(str(e))
            await orchestrator._transition(
                research_run_id=research_run_id,
                twin_id=twin_id,
                to_status=ResearchRunStatus.FAILED,
                reason=f"Crawl pipeline exception: {e}",
                checkpoint=failure_checkpoint,
                crawl_id=crawl_id,
            )
        except Exception:
            logger.exception(
                "Failed to transition research run to failed after pipeline exception: research_run_id=%s",
                research_run_id,
            )


# ============================================================================
# Request/Response Schemas
# ============================================================================

class CreateCrawlRequest(BaseModel):
    """Request to create a new crawl run."""
    seed_urls: List[str] = Field(..., description="Starting URLs for crawl")
    max_pages: int = Field(default=50, ge=1, le=500, description="Maximum pages to crawl")
    max_depth: int = Field(default=2, ge=1, le=5, description="Maximum crawl depth")
    include_patterns: Optional[List[str]] = Field(default=None, description="URL patterns to include")
    exclude_patterns: Optional[List[str]] = Field(default=None, description="URL patterns to exclude")
    
    @field_validator('seed_urls')
    def validate_urls(cls, v):
        """Ensure at least one seed URL is provided."""
        if not v:
            raise ValueError('At least one seed URL is required')
        for url in v:
            if not url.startswith(('http://', 'https://')):
                raise ValueError(f'Invalid URL: {url}. Must start with http:// or https://')
        return v


class CreateCrawlResponse(BaseModel):
    """Response from crawl creation."""
    crawl_id: str
    status: str
    message: str
    twin_id: str
    created_at: str


class CrawlStatusResponse(BaseModel):
    """Crawl status response."""
    crawl_id: str
    twin_id: str
    status: str
    seed_urls: List[str]
    progress: dict
    started_at: Optional[str]
    completed_at: Optional[str]
    error_message: Optional[str]
    manifest_artifact_path: Optional[str]


class CrawlListResponse(BaseModel):
    """List of crawls response."""
    crawls: List[CrawlRunSchema]
    total: int


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    code: str
    message: str


# ============================================================================
# Helper Functions
# ============================================================================

def _get_crawl_or_404(crawl_id: str, twin_id: str) -> dict:
    """
    Get crawl run by ID, validating twin scope.
    
    Args:
        crawl_id: Crawl run ID
        twin_id: Expected twin ID
    
    Returns:
        Crawl run data
    
    Raises:
        HTTPException: 404 if not found, 403 if twin mismatch
    """
    try:
        response = supabase.table("crawl_runs").select("*").eq("id", crawl_id).single().execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "Crawl not found",
                    "code": "NOT_FOUND",
                    "message": f"No crawl found with ID: {crawl_id}"
                }
            )
        
        crawl = response.data
        
        # Verify twin scoping
        if crawl.get("twin_id") != twin_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "Access denied",
                    "code": "TWIN_MISMATCH",
                    "message": "Crawl does not belong to this twin"
                }
            )
        
        return crawl
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Database error",
                "code": "DB_ERROR",
                "message": str(e)
            }
        )


def _build_progress(crawl: dict) -> dict:
    """Build progress summary from crawl data."""
    return {
        "pages_found": crawl.get("pages_found", 0),
        "pages_ingested": crawl.get("pages_ingested", 0),
        "pages_unchanged": crawl.get("pages_unchanged", 0),
        "pages_failed": crawl.get("pages_failed", 0),
        "failed_authentications": crawl.get("failed_authentications", 0),
    }


_URL_IN_TEXT_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)


def _extract_http_urls_from_text(content: str) -> List[str]:
    """Extract likely absolute URLs from free text."""
    if not content:
        return []
    urls: List[str] = []
    for raw in _URL_IN_TEXT_PATTERN.findall(content):
        candidate = str(raw).strip().rstrip(").,;]")
        if candidate.startswith(("http://", "https://")):
            urls.append(candidate)
    return urls


def _normalize_seed_urls(urls: List[str], max_urls: int = 50) -> List[str]:
    """
    Normalize and dedupe URLs for crawl seeding.

    Uses canonicalization for consistency with deep-research pipelines.
    """
    if not urls:
        return []
    deduped: List[str] = []
    seen: set[str] = set()
    try:
        from modules.url_canonicalizer import canonicalize_url
    except Exception:
        canonicalize_url = None

    for raw in urls:
        candidate = str(raw or "").strip()
        if not candidate:
            continue
        if not candidate.startswith(("http://", "https://")):
            continue
        try:
            normalized = canonicalize_url(candidate) if canonicalize_url else candidate
        except Exception:
            normalized = candidate
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
        if len(deduped) >= max_urls:
            break
    return deduped


def _collect_seed_urls_from_latest_link_compile_job(twin_id: str) -> List[str]:
    """
    Collect URL signals from latest link-compile jobs (Mode A/B/C).

    - Mode C contributes explicit source_urls.
    - Mode A/B may include URLs inside parsed content; extract them.
    """
    try:
        result = (
            supabase.table("link_compile_jobs")
            .select("source_urls,source_files")
            .eq("twin_id", twin_id)
            .order("created_at", desc=True)
            .limit(3)
            .execute()
        )
    except Exception as exc:
        logger.warning("Failed to load link-compile jobs for twin=%s: %s", twin_id, exc)
        return []

    candidates: List[str] = []
    for job in result.data or []:
        for url in job.get("source_urls") or []:
            if isinstance(url, str):
                candidates.append(url)

        for source_file in job.get("source_files") or []:
            if not isinstance(source_file, dict):
                continue
            maybe_url = source_file.get("url")
            if isinstance(maybe_url, str) and maybe_url.strip():
                candidates.append(maybe_url)
            content = source_file.get("content")
            if isinstance(content, str) and content.strip():
                candidates.extend(_extract_http_urls_from_text(content))

    return candidates


def _collect_seed_urls_from_request_inputs(
    twin_id: str,
    claimed_identity: Optional[Dict[str, Any]],
    request_seed_urls: List[str],
) -> List[str]:
    """
    Build initial seed URLs from all onboarding mode inputs.

    Sources:
    - explicit request.seed_urls
    - claimed_identity.submitted_links
    - latest Mode A/B/C link-compile job payloads for this twin
    """
    candidates: List[str] = list(request_seed_urls or [])

    identity = claimed_identity or {}
    submitted_links = identity.get("submitted_links")
    if isinstance(submitted_links, list):
        for link in submitted_links:
            if isinstance(link, str):
                candidates.append(link)
    elif isinstance(submitted_links, str):
        candidates.append(submitted_links)

    candidates.extend(_collect_seed_urls_from_latest_link_compile_job(twin_id))
    return _normalize_seed_urls(candidates, max_urls=60)


def _build_name_research_hints(
    claimed_identity: Optional[Dict[str, Any]],
    seed_urls: List[str],
) -> Dict[str, Optional[str]]:
    """Map onboarding identity payload to name-research hint schema."""
    identity = claimed_identity or {}
    website = None
    for url in seed_urls:
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            website = url
            break

    company = (
        identity.get("company")
        or identity.get("organization")
        or identity.get("org")
        or identity.get("employer")
    )
    if not company:
        headline_or_role = str(identity.get("headline") or identity.get("role") or "").strip()
        marker = " at "
        if marker in headline_or_role.lower():
            lower_value = headline_or_role.lower()
            idx = lower_value.find(marker)
            extracted = headline_or_role[idx + len(marker):].strip(" -|,")
            company = extracted or None
    location = identity.get("location")

    return {
        "location": str(location).strip() if location else None,
        "company": str(company).strip() if company else None,
        "website": str(website).strip() if website else None,
    }


async def _discover_seed_urls_with_name_research_tools(
    full_name: str,
    hints: Dict[str, Optional[str]],
) -> List[str]:
    """
    Reuse name-only deep research discovery stack for onboarding.

    This gives /twins/{id}/research the same query expansion + provider fallback
    behavior used by /deep-research/runs.
    """
    try:
        from modules.name_deep_research_service import get_name_deep_research_service

        service = get_name_deep_research_service()
        return await service.discover_urls_for_identity(
            name=full_name,
            hints=hints,
            max_queries=8,
            max_urls=50,
        )
    except Exception as exc:
        logger.warning("Name-research URL discovery failed for '%s': %s", full_name, exc)
        return []


# ============================================================================
# Endpoints
# ============================================================================

@router.post(
    "/twins/{twin_id}/crawls",
    response_model=CreateCrawlResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def create_crawl(
    twin_id: str,
    request: CreateCrawlRequest,
    user: dict = Depends(get_current_user)
):
    """
    Create a new crawl run for the specified twin.
    
    The crawl will be queued and processed asynchronously.
    Use GET /twins/{twin_id}/crawls/{crawl_id} to check status.
    
    Deep Research routes are always enabled.
    """
    # Check feature flag
    _check_feature_enabled()
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    try:
        # Create crawl run record
        crawl_id = _create_crawl_run(
            twin_id=twin_id,
            seed_urls=request.seed_urls,
            max_pages=request.max_pages,
            max_depth=request.max_depth,
            include_patterns=request.include_patterns,
            exclude_patterns=request.exclude_patterns,
        )
        
        # TODO: In Phase 1B+, enqueue crawl job for background processing
        # For now, crawl is created in 'queued' status
        
        return CreateCrawlResponse(
            crawl_id=crawl_id,
            status="queued",
            message="Crawl created successfully. Use GET endpoint to check status.",
            twin_id=twin_id,
            created_at=datetime.utcnow().isoformat(),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to create crawl",
                "code": "CREATE_FAILED",
                "message": str(e)
            }
        )


@router.get(
    "/twins/{twin_id}/crawls/{crawl_id}",
    response_model=CrawlStatusResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        404: {"model": ErrorResponse, "description": "Crawl not found"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def get_crawl_status(
    twin_id: str,
    crawl_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Get crawl run status and progress.
    
    Returns metadata-only response (no page content).
    """
    # Check feature flag
    _check_feature_enabled()
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    # Get crawl (validates twin scoping internally)
    crawl = _get_crawl_or_404(crawl_id, twin_id)
    
    return CrawlStatusResponse(
        crawl_id=crawl["id"],
        twin_id=crawl["twin_id"],
        status=crawl["status"],
        seed_urls=crawl.get("seed_urls", []),
        progress=_build_progress(crawl),
        started_at=crawl.get("started_at"),
        completed_at=crawl.get("completed_at"),
        error_message=crawl.get("error_message"),
        manifest_artifact_path=crawl.get("manifest_artifact_path"),
    )


@router.get(
    "/twins/{twin_id}/crawls",
    response_model=CrawlListResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def list_crawls(
    twin_id: str,
    status: Optional[str] = None,
    limit: int = 20,
    user: dict = Depends(get_current_user)
):
    """
    List crawl runs for the specified twin.
    
    Optional status filter: queued, running, completed, failed
    """
    # Check feature flag
    _check_feature_enabled()
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    try:
        query = (
            supabase.table("crawl_runs")
            .select("*")
            .eq("twin_id", twin_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        
        if status:
            query = query.eq("status", status)
        
        response = query.execute()
        crawls = response.data or []
        
        # Map to schema
        crawl_schemas = [
            CrawlRunSchema(
                id=c["id"],
                twin_id=c["twin_id"],
                status=c["status"],
                pages_found=c.get("pages_found", 0),
                pages_ingested=c.get("pages_ingested", 0),
                pages_failed=c.get("pages_failed", 0),
                started_at=c.get("started_at"),
                completed_at=c.get("completed_at"),
                created_at=c.get("created_at"),
            )
            for c in crawls
        ]
        
        return CrawlListResponse(
            crawls=crawl_schemas,
            total=len(crawl_schemas)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to list crawls",
                "code": "LIST_FAILED",
                "message": str(e)
            }
        )


@router.delete(
    "/twins/{twin_id}/crawls/{crawl_id}",
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        404: {"model": ErrorResponse, "description": "Crawl not found"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def cancel_crawl(
    twin_id: str,
    crawl_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Cancel a running or queued crawl.
    
    Note: Cannot cancel completed or failed crawls.
    """
    # Check feature flag
    _check_feature_enabled()
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    # Get crawl (validates twin scoping internally)
    crawl = _get_crawl_or_404(crawl_id, twin_id)
    
    # Check if cancelable
    if crawl["status"] not in ("queued", "running"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Cannot cancel crawl",
                "code": "INVALID_STATE",
                "message": f"Cannot cancel crawl with status: {crawl['status']}"
            }
        )
    
    try:
        # Update status to cancelled
        supabase.table("crawl_runs").update({
            "status": "cancelled",
            "completed_at": datetime.utcnow().isoformat(),
        }).eq("id", crawl_id).execute()
        
        return {
            "crawl_id": crawl_id,
            "status": "cancelled",
            "message": "Crawl cancelled successfully"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to cancel crawl",
                "code": "CANCEL_FAILED",
                "message": str(e)
            }
        )


@router.get(
    "/twins/{twin_id}/crawls/{crawl_id}/changes",
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        404: {"model": ErrorResponse, "description": "Crawl not found"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def get_crawl_changes(
    twin_id: str,
    crawl_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Get crawl changes summary (diff since prior crawl).
    
    Returns counts and list of changes:
    - unchanged_pages: Same content as prior crawl
    - changed_pages: Different content from prior crawl
    - new_pages: Not present in prior crawl
    - removed_pages: In prior crawl but not this one (best-effort)
    
    Note: Removed page detection requires explicit recrawl closeout logic
    that compares against previous crawl's complete page list. Currently
    returns 0 with a note that full removal detection is pending.
    """
    # Check feature flag
    _check_feature_enabled()
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    # Get crawl (validates twin scoping internally)
    crawl = _get_crawl_or_404(crawl_id, twin_id)
    
    # Get pages for this crawl
    try:
        from backend.modules.crawl_repository import CrawlRepository
        pages = CrawlRepository.get_pages_by_crawl(crawl_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to fetch crawl pages",
                "code": "DB_ERROR",
                "message": str(e)
            }
        )
    
    # Calculate changes
    changes_summary = _calculate_changes(pages)
    
    return {
        "crawl_id": crawl_id,
        "twin_id": twin_id,
        "unchanged_pages": changes_summary["unchanged"],
        "changed_pages": changes_summary["changed"],
        "new_pages": changes_summary["new"],
        "removed_pages": 0,  # Placeholder: Full removal detection pending
        "removed_pages_note": "Full removed-page detection requires recrawl closeout comparison against previous crawl. Currently returns 0.",
        "total_pages": len(pages),
        "changes": changes_summary["changes_list"],
    }


def _calculate_changes(pages: list) -> dict:
    """
    Calculate changes summary from crawl pages.
    
    Args:
        pages: List of page records
    
    Returns:
        Dict with counts and changes list
    """
    unchanged = 0
    changed = 0
    new_pages = 0
    changes_list = []
    
    for page in pages:
        status = page.get("status")
        canonical_url = page.get("canonical_url", "")
        content_hash = page.get("content_hash")
        previous_content_hash = page.get("metadata", {}).get("previous_content_hash")
        
        if status == "unchanged":
            unchanged += 1
            changes_list.append({
                "canonical_url": canonical_url,
                "classification": "unchanged",
                "previous_hash": content_hash,
                "current_hash": content_hash,
            })
        elif status == "changed":
            changed += 1
            changes_list.append({
                "canonical_url": canonical_url,
                "classification": "changed",
                "previous_hash": previous_content_hash,
                "current_hash": content_hash,
            })
        elif status in ("ingested", "discovered"):
            # New page (no prior classification means new)
            new_pages += 1
            changes_list.append({
                "canonical_url": canonical_url,
                "classification": "new",
                "previous_hash": None,
                "current_hash": content_hash,
            })
    
    return {
        "unchanged": unchanged,
        "changed": changed,
        "new": new_pages,
        "changes_list": changes_list,
    }


# ============================================================================
# Phase 3.3: Source Confirmation Endpoints
# ============================================================================

class ResolveConfirmationRequest(BaseModel):
    """Request to resolve a confirmation."""
    action: str = Field(..., description="Action to take: 'confirm' or 'reject'")
    feedback: Optional[str] = Field(default=None, description="Optional feedback/reason")
    
    @field_validator('action')
    def validate_action(cls, v):
        """Ensure action is valid."""
        if v not in ('confirm', 'reject'):
            raise ValueError("Action must be 'confirm' or 'reject'")
        return v


class BulkResolveRequest(BaseModel):
    """Request to bulk resolve confirmations."""
    confirmation_ids: List[str] = Field(..., description="List of confirmation IDs")
    action: str = Field(..., description="Action to take: 'confirm' or 'reject'")
    feedback: Optional[str] = Field(default=None, description="Optional feedback/reason")
    
    @field_validator('action')
    def validate_action(cls, v):
        """Ensure action is valid."""
        if v not in ('confirm', 'reject'):
            raise ValueError("Action must be 'confirm' or 'reject'")
        return v


@router.post(
    "/twins/{twin_id}/research/{research_run_id}/confirmations/create",
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        404: {"model": ErrorResponse, "description": "Research run not found"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def create_confirmations(
    twin_id: str,
    research_run_id: str,
    crawl_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Create confirmation records from crawl pages (Phase 3.3).
    
    Idempotent: Safe to call multiple times - will skip existing confirmations.
    """
    # Check feature flag
    _check_feature_enabled()
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    try:
        from modules.source_confirmation import SourceConfirmationManager
        
        manager = SourceConfirmationManager()
        result = await manager.create_confirmations_for_crawl(
            research_run_id=research_run_id,
            crawl_id=crawl_id,
            twin_id=twin_id,
            user_id=user.get("id"),
        )
        
        if result.error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "Failed to create confirmations",
                    "code": "CREATION_FAILED",
                    "message": result.error
                }
            )
        
        return {
            "research_run_id": result.research_run_id,
            "crawl_id": result.crawl_id,
            "total_pages": result.total_pages,
            "created": result.created,
            "skipped": result.skipped,
            "by_status": result.by_status,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to create confirmations",
                "code": "CREATION_FAILED",
                "message": str(e)
            }
        )


@router.get(
    "/twins/{twin_id}/research/{research_run_id}/pending-confirmations",
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def list_pending_confirmations(
    twin_id: str,
    research_run_id: str,
    limit: int = 100,
    offset: int = 0,
    user: dict = Depends(get_current_user)
):
    """
    List pending confirmations awaiting user review (Phase 3.3).
    
    Returns items that need user action:
    - pending: Medium confidence, needs decision
    - manual_review: Blocked/manual-needed quality
    - auto_rejected: Low confidence, user can override
    """
    # Check feature flag
    _check_feature_enabled()
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    try:
        from modules.source_confirmation import SourceConfirmationManager
        
        manager = SourceConfirmationManager()
        result = await manager.list_pending_confirmations(
            research_run_id=research_run_id,
            twin_id=twin_id,
            limit=limit,
            offset=offset,
        )
        
        return {
            "items": [
                {
                    "confirmation_id": item.confirmation_id,
                    "crawl_page_id": item.crawl_page_id,
                    "url": item.url,
                    "canonical_url": item.canonical_url,
                    "title": item.title,
                    "snippet": item.snippet,
                    "content_quality": item.content_quality,
                    "identity_confidence_score": item.identity_confidence_score,
                    "identity_confidence_percent": item.identity_confidence_percent,
                    "match_details": item.match_details,
                    "submitted_root_url": item.submitted_root_url,
                    "status": item.status,
                    "created_at": item.created_at,
                }
                for item in result.items
            ],
            "total": result.total,
            "limit": result.limit,
            "offset": result.offset,
            "has_more": result.has_more,
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to list confirmations",
                "code": "LIST_FAILED",
                "message": str(e)
            }
        )


@router.post(
    "/twins/{twin_id}/research/{research_run_id}/confirmations/{confirmation_id}",
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        404: {"model": ErrorResponse, "description": "Confirmation not found"},
        403: {"model": ErrorResponse, "description": "Access denied"},
        400: {"model": ErrorResponse, "description": "Invalid action or already resolved"},
    }
)
async def resolve_confirmation_endpoint(
    twin_id: str,
    research_run_id: str,
    confirmation_id: str,
    request: ResolveConfirmationRequest,
    user: dict = Depends(get_current_user)
):
    """
    Resolve a single confirmation (confirm or reject) (Phase 3.3 + 3.4).
    
    Phase 3.4: After resolving, triggers orchestrator to check if all
    confirmations are resolved and potentially transition to ready_for_ingestion.
    """
    # Check feature flag
    _check_feature_enabled()
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    try:
        from modules.source_confirmation import SourceConfirmationManager
        from modules.research_orchestrator import ResearchOrchestrator
        
        # Resolve the confirmation
        manager = SourceConfirmationManager()
        result = await manager.resolve_confirmation(
            research_run_id=research_run_id,
            confirmation_id=confirmation_id,
            twin_id=twin_id,
            actor_user_id=user.get("id"),
            action=request.action,
            feedback=request.feedback,
        )
        
        if result.error:
            status_code = status.HTTP_400_BAD_REQUEST
            error_text = result.error.lower()
            if "not found" in error_text:
                status_code = status.HTTP_404_NOT_FOUND
            elif "server disconnected" in error_text or "connection" in error_text or "temporar" in error_text:
                status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            raise HTTPException(
                status_code=status_code,
                detail={
                    "error": "Failed to resolve confirmation",
                    "code": "RESOLVE_FAILED",
                    "message": result.error
                }
            )
        
        # Phase 3.4: Notify orchestrator of confirmation update
        # This may trigger state transition to ready_for_ingestion
        orchestrator = ResearchOrchestrator()
        transition_result = await orchestrator.on_confirmations_updated(
            research_run_id=research_run_id,
            twin_id=twin_id,
        )
        
        return {
            "confirmation_id": result.confirmation_id,
            "research_run_id": result.research_run_id,
            "previous_status": result.previous_status,
            "new_status": result.new_status,
            "action": result.action,
            "resolved_at": result.resolved_at,
            "user_override": result.user_override,
            "run_status": transition_result.new_status if transition_result.success else None,
            "run_transition": transition_result.transition_reason if transition_result.success else None,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to resolve confirmation",
                "code": "RESOLVE_FAILED",
                "message": str(e)
            }
        )


@router.post(
    "/twins/{twin_id}/research/{research_run_id}/bulk-confirm",
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def bulk_resolve_confirmations_endpoint(
    twin_id: str,
    research_run_id: str,
    request: BulkResolveRequest,
    user: dict = Depends(get_current_user)
):
    """
    Bulk resolve multiple confirmations (Phase 3.3 + 3.4).
    
    Phase 3.4: After resolving, triggers orchestrator to check if all
    confirmations are resolved and potentially transition to ready_for_ingestion.
    """
    # Check feature flag
    _check_feature_enabled()
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    try:
        from modules.source_confirmation import SourceConfirmationManager
        from modules.research_orchestrator import ResearchOrchestrator
        
        # Bulk resolve confirmations
        manager = SourceConfirmationManager()
        result = await manager.bulk_resolve_confirmations(
            research_run_id=research_run_id,
            twin_id=twin_id,
            actor_user_id=user.get("id"),
            confirmation_ids=request.confirmation_ids,
            action=request.action,
            feedback=request.feedback,
        )
        
        # Phase 3.4: Notify orchestrator of confirmation update
        # This may trigger state transition to ready_for_ingestion
        orchestrator = ResearchOrchestrator()
        transition_result = await orchestrator.on_confirmations_updated(
            research_run_id=research_run_id,
            twin_id=twin_id,
        )
        
        return {
            "research_run_id": result.research_run_id,
            "action": result.action,
            "requested": result.requested,
            "succeeded": result.succeeded,
            "failed": result.failed,
            "errors": result.errors,
            "run_status": transition_result.new_status if transition_result.success else None,
            "run_transition": transition_result.transition_reason if transition_result.success else None,
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to bulk resolve confirmations",
                "code": "BULK_RESOLVE_FAILED",
                "message": str(e)
            }
        )


@router.get(
    "/twins/{twin_id}/research/{research_run_id}/confirmation-summary",
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def get_confirmation_summary_endpoint(
    twin_id: str,
    research_run_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Get summary of confirmation statuses (Phase 3.3).
    
    Returns counts and resolution status for the research run.
    """
    # Check feature flag
    _check_feature_enabled()
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    try:
        from modules.source_confirmation import SourceConfirmationManager
        
        manager = SourceConfirmationManager()
        result = await manager.get_confirmation_summary(
            research_run_id=research_run_id,
            twin_id=twin_id,
        )
        
        return {
            "research_run_id": result.research_run_id,
            "twin_id": result.twin_id,
            "total": result.total,
            "pending": result.pending,
            "auto_confirmed": result.auto_confirmed,
            "auto_rejected": result.auto_rejected,
            "manual_review": result.manual_review,
            "confirmed": result.confirmed,
            "rejected": result.rejected,
            "all_resolved": result.all_resolved,
            "resolution_percent": result.resolution_percent,
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to get confirmation summary",
                "code": "SUMMARY_FAILED",
                "message": str(e)
            }
        )


# ============================================================================
# Phase 3.4: Research Orchestrator Endpoints
# ============================================================================

class CreateResearchRunRequest(BaseModel):
    """Request to create a research run."""
    claimed_identity: dict = Field(..., description="Identity info: {full_name, location, submitted_links, ...}")
    seed_urls: List[str] = Field(default_factory=list, description="URLs to crawl (optional; use Firecrawl search when empty + full_name)")
    onboarding_session_id: Optional[str] = Field(default=None, description="Optional onboarding session link")
    metadata: Optional[dict] = Field(default=None, description="Additional config")


class CreateResearchRunResponse(BaseModel):
    """Response from creating research run."""
    research_run_id: str
    twin_id: str
    status: str
    created_at: str


class ResearchRunStatusResponse(BaseModel):
    """Research run status response."""
    research_run_id: str
    twin_id: str
    status: str
    crawl_id: Optional[str]
    checkpoint_data: dict
    confirmation_summary: Optional[dict]
    next_actions: List[str]  # Phase 6: Canonical plural field
    warnings: List[str]
    created_at: str
    updated_at: str
    
    @property
    def next_action(self) -> str:
        """Backward compatibility alias for next_actions[0] or empty string."""
        return self.next_actions[0] if self.next_actions else ""


@router.post(
    "/twins/{twin_id}/research",
    response_model=CreateResearchRunResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def create_research_run_endpoint(
    twin_id: str,
    request: CreateResearchRunRequest,
    user: dict = Depends(get_current_user)
):
    """
    Create a new research run (Phase 3.4).
    
    Initializes research run with claimed identity and seed URLs.
    Seed URL collection is mode-aware:
    - direct seed_urls in request
    - claimed_identity.submitted_links
    - latest Mode A/B/C link-compile payloads (URLs extracted from content)
    Then augments discovery using the same name-research URL discovery tools.
    Transitions through state machine:
    planning -> queued -> crawling -> awaiting_confirmation -> ready_for_ingestion
    """
    # Check feature flag
    _check_feature_enabled()
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    claimed_identity = request.claimed_identity or {}
    full_name = str(claimed_identity.get("full_name") or "").strip()

    # 1) Collect explicit seed URLs from all onboarding mode inputs.
    seed_urls = _collect_seed_urls_from_request_inputs(
        twin_id=twin_id,
        claimed_identity=claimed_identity,
        request_seed_urls=list(request.seed_urls or []),
    )

    # 2) Augment discovery with name-research stack when identity is available.
    # We do this even when some URLs exist so onboarding can "lock on" identity
    # and still discover additional corroborating sources.
    if full_name:
        hints = _build_name_research_hints(claimed_identity, seed_urls)
        discovered_urls = await _discover_seed_urls_with_name_research_tools(
            full_name=full_name,
            hints=hints,
        )
        if discovered_urls:
            before_count = len(seed_urls)
            seed_urls = _normalize_seed_urls(seed_urls + discovered_urls, max_urls=60)
            logger.info(
                "Research seed URL expansion: twin_id=%s base=%s discovered=%s final=%s",
                twin_id,
                before_count,
                len(discovered_urls),
                len(seed_urls),
            )
    
    # Require at least one URL to proceed
    if not seed_urls:
        if not full_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "No sources for research",
                    "code": "NO_SOURCES",
                    "message": "Provide seed_urls, submitted links, or full_name for discovery."
                }
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "No URLs discovered",
                "code": "SEARCH_EMPTY",
                "message": "No crawlable URLs discovered from onboarding inputs and name-based discovery. Try adding explicit URLs."
            }
        )
    
    try:
        from modules.research_orchestrator import ResearchOrchestrator
        from modules.deep_research_config import get_config as get_deep_research_config
        
        orchestrator = ResearchOrchestrator()
        result = await orchestrator.create_research_run(
            twin_id=twin_id,
            actor_user_id=user.get("id"),
            claimed_identity=claimed_identity,
            seed_urls=seed_urls,
            onboarding_session_id=request.onboarding_session_id,
            metadata=request.metadata,
        )
        
        if result.error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "Failed to create research run",
                    "code": "CREATION_FAILED",
                    "message": result.error
                }
            )
        
        # Create crawl run and transition research status to crawling immediately.
        # This ensures polling sees active progress instead of a queued dead-end.
        config = get_deep_research_config()
        crawl_id = _create_crawl_run(
            twin_id=twin_id,
            seed_urls=seed_urls,
            max_pages=config.firecrawl.website_crawl_limit,
            max_depth=config.firecrawl.website_max_depth,
            include_patterns=None,
            exclude_patterns=None,
        )

        crawl_start = await orchestrator.mark_crawl_started(
            research_run_id=result.research_run_id,
            twin_id=twin_id,
            crawl_id=crawl_id,
        )
        if not crawl_start.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "Failed to start crawl",
                    "code": "CRAWL_START_FAILED",
                    "message": crawl_start.error or "Could not transition research run to crawling",
                },
            )

        # Process crawl asynchronously and continue orchestrator transitions
        # (crawling -> awaiting_confirmation/ready_for_ingestion).
        crawl_task = asyncio.create_task(
            _run_research_crawl_pipeline(
                research_run_id=result.research_run_id,
                twin_id=twin_id,
                crawl_id=crawl_id,
                claimed_identity=claimed_identity,
            )
        )
        _ACTIVE_RESEARCH_CRAWL_TASKS[result.research_run_id] = crawl_task

        def _cleanup_crawl_task(task: asyncio.Task[Any]) -> None:
            _ACTIVE_RESEARCH_CRAWL_TASKS.pop(result.research_run_id, None)
            if task.cancelled():
                logger.warning("Research crawl task cancelled: research_run_id=%s", result.research_run_id)
                return
            exc = task.exception()
            if exc:
                logger.exception(
                    "Research crawl task crashed: research_run_id=%s err=%s",
                    result.research_run_id,
                    exc,
                )

        crawl_task.add_done_callback(_cleanup_crawl_task)

        return CreateResearchRunResponse(
            research_run_id=result.research_run_id,
            twin_id=result.twin_id,
            status=crawl_start.new_status,
            created_at=result.created_at,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to create research run",
                "code": "CREATION_FAILED",
                "message": str(e)
            }
        )


@router.get(
    "/twins/{twin_id}/research/{research_run_id}",
    response_model=ResearchRunStatusResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        404: {"model": ErrorResponse, "description": "Research run not found"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def get_research_run_status(
    twin_id: str,
    research_run_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Get research run status and checkpoint (Phase 3.4).
    
    Returns full status including:
    - Current state in state machine
    - Checkpoint data for resume capability
    - Confirmation summary (if applicable)
    - Next action hint for polling
    """
    # Check feature flag
    _check_feature_enabled()
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    try:
        from modules.research_orchestrator import ResearchOrchestrator
        
        orchestrator = ResearchOrchestrator()
        result = await orchestrator.get_run_status(
            research_run_id=research_run_id,
            twin_id=twin_id,
        )
        
        # Build confirmation summary dict
        confirmation_summary = None
        if result.confirmation_summary:
            confirmation_summary = {
                "research_run_id": result.confirmation_summary.research_run_id,
                "twin_id": result.confirmation_summary.twin_id,
                "total": result.confirmation_summary.total,
                "pending": result.confirmation_summary.pending,
                "auto_confirmed": result.confirmation_summary.auto_confirmed,
                "auto_rejected": result.confirmation_summary.auto_rejected,
                "manual_review": result.confirmation_summary.manual_review,
                "confirmed": result.confirmation_summary.confirmed,
                "rejected": result.confirmation_summary.rejected,
                "all_resolved": result.confirmation_summary.all_resolved,
                "resolution_percent": result.confirmation_summary.resolution_percent,
            }
        
        return ResearchRunStatusResponse(
            research_run_id=result.research_run_id,
            twin_id=result.twin_id,
            status=result.status,
            crawl_id=result.crawl_id,
            checkpoint_data=result.checkpoint_data,
            confirmation_summary=confirmation_summary,
            next_actions=result.next_actions,
            warnings=result.warnings,
            created_at=result.created_at,
            updated_at=result.updated_at,
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "Research run not found",
                "code": "NOT_FOUND",
                "message": str(e)
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to get research run status",
                "code": "STATUS_FAILED",
                "message": str(e)
            }
        )


class ContinueIngestionResponse(BaseModel):
    """Response from continue ingestion endpoint."""
    research_run_id: str
    twin_id: str
    previous_status: str
    new_status: str
    ingestion_summary: Optional[dict]
    transition_reason: Optional[str]


@router.post(
    "/twins/{twin_id}/research/{research_run_id}/continue-ingestion",
    response_model=ContinueIngestionResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        404: {"model": ErrorResponse, "description": "Research run not found"},
        403: {"model": ErrorResponse, "description": "Access denied"},
        400: {"model": ErrorResponse, "description": "Invalid state for ingestion"},
        409: {"model": ErrorResponse, "description": "Already completed"},
    }
)
async def continue_ingestion_endpoint(
    twin_id: str,
    research_run_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Continue research run from ready_for_ingestion to ingestion completion (Phase 3.5).
    
    This endpoint:
    1. Validates run is in ready_for_ingestion state
    2. Transitions to ingesting
    3. Performs confirmation-gated ingestion (only confirmed/auto_confirmed sources)
    4. Transitions to ingestion_completed
    5. Returns ingestion summary
    
    Idempotent: If already in ingestion_completed, returns success with current state.
    
    Phase 3.5 stops here - no bio generation, no mind score updates.
    """
    # Check feature flag
    _check_feature_enabled()
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    try:
        from modules.research_orchestrator import ResearchOrchestrator, ResearchRunStatus
        
        orchestrator = ResearchOrchestrator()
        
        # First check current status for idempotency
        try:
            current_status_result = await orchestrator.get_run_status(
                research_run_id=research_run_id,
                twin_id=twin_id,
            )
            
            # Idempotent: already completed
            if current_status_result.status == ResearchRunStatus.INGESTION_COMPLETED.value:
                return ContinueIngestionResponse(
                    research_run_id=research_run_id,
                    twin_id=twin_id,
                    previous_status=current_status_result.status,
                    new_status=current_status_result.status,
                    ingestion_summary=current_status_result.checkpoint_data.get("ingestion"),
                    transition_reason="Already in ingestion_completed state (idempotent)",
                )
            
            # Validate state
            if current_status_result.status != ResearchRunStatus.READY_FOR_INGESTION.value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "Invalid state for ingestion",
                        "code": "INVALID_STATE",
                        "message": f"Research run must be in ready_for_ingestion state, current: {current_status_result.status}"
                    }
                )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "Research run not found",
                    "code": "NOT_FOUND",
                    "message": str(e)
                }
            )
        
        # Continue to ingestion
        result = await orchestrator.continue_to_ingestion(
            research_run_id=research_run_id,
            twin_id=twin_id,
        )
        
        if not result.success:
            status_code = status.HTTP_400_BAD_REQUEST
            if "already" in (result.error or "").lower():
                status_code = status.HTTP_409_CONFLICT
            
            raise HTTPException(
                status_code=status_code,
                detail={
                    "error": "Ingestion continuation failed",
                    "code": "INGESTION_FAILED",
                    "message": result.error or "Unknown error"
                }
            )
        
        # Get updated status for ingestion summary
        updated_status = await orchestrator.get_run_status(
            research_run_id=research_run_id,
            twin_id=twin_id,
        )
        
        return ContinueIngestionResponse(
            research_run_id=research_run_id,
            twin_id=twin_id,
            previous_status=result.previous_status,
            new_status=result.new_status,
            ingestion_summary=updated_status.checkpoint_data.get("ingestion"),
            transition_reason=result.transition_reason,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Ingestion continuation failed",
                "code": "INGESTION_FAILED",
                "message": str(e)
            }
        )


class ContinueBioResponse(BaseModel):
    """Response from continue bio endpoint."""
    research_run_id: str
    twin_id: str
    previous_status: str
    new_status: str
    bio_generation_summary: Optional[dict]
    transition_reason: Optional[str]


@router.post(
    "/twins/{twin_id}/research/{research_run_id}/continue-bio",
    response_model=ContinueBioResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        404: {"model": ErrorResponse, "description": "Research run not found"},
        403: {"model": ErrorResponse, "description": "Access denied"},
        400: {"model": ErrorResponse, "description": "Invalid state for bio generation"},
        409: {"model": ErrorResponse, "description": "Already completed"},
    }
)
async def continue_bio_endpoint(
    twin_id: str,
    research_run_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Continue research run from ingestion_completed to bio generation completion (Phase 4).
    
    This endpoint:
    1. Validates run is in ingestion_completed state
    2. Transitions to generating_bio
    3. Collects confirmed source URLs (confirmed + auto_confirmed only)
    4. Triggers persona bio generation using existing pipeline
    5. Transitions to bio_generated
    6. Returns bio generation summary
    
    Idempotent: If already in bio_generated, returns success with current state.
    
    Phase 4 stops here - no mind score updates, no readiness checks.
    """
    # Check feature flag
    _check_feature_enabled()
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    try:
        from modules.research_orchestrator import ResearchOrchestrator, ResearchRunStatus
        
        orchestrator = ResearchOrchestrator()
        
        # First check current status for idempotency
        try:
            current_status_result = await orchestrator.get_run_status(
                research_run_id=research_run_id,
                twin_id=twin_id,
            )
            
            # Idempotent: already completed
            if current_status_result.status == ResearchRunStatus.BIO_GENERATED.value:
                return ContinueBioResponse(
                    research_run_id=research_run_id,
                    twin_id=twin_id,
                    previous_status=current_status_result.status,
                    new_status=current_status_result.status,
                    bio_generation_summary=current_status_result.checkpoint_data.get("bio_generation"),
                    transition_reason="Already in bio_generated state (idempotent)",
                )
            
            # Validate state
            if current_status_result.status != ResearchRunStatus.INGESTION_COMPLETED.value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "Invalid state for bio generation",
                        "code": "INVALID_STATE",
                        "message": f"Research run must be in ingestion_completed state, current: {current_status_result.status}"
                    }
                )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "Research run not found",
                    "code": "NOT_FOUND",
                    "message": str(e)
                }
            )
        
        # Continue to bio generation
        result = await orchestrator.continue_to_bio_generation(
            research_run_id=research_run_id,
            twin_id=twin_id,
        )
        
        if not result.success:
            status_code = status.HTTP_400_BAD_REQUEST
            if "already" in (result.error or "").lower():
                status_code = status.HTTP_409_CONFLICT
            
            raise HTTPException(
                status_code=status_code,
                detail={
                    "error": "Bio generation continuation failed",
                    "code": "BIO_GENERATION_FAILED",
                    "message": result.error or "Unknown error"
                }
            )
        
        # Get updated status for bio generation summary
        updated_status = await orchestrator.get_run_status(
            research_run_id=research_run_id,
            twin_id=twin_id,
        )
        
        return ContinueBioResponse(
            research_run_id=research_run_id,
            twin_id=twin_id,
            previous_status=result.previous_status,
            new_status=result.new_status,
            bio_generation_summary=updated_status.checkpoint_data.get("bio_generation"),
            transition_reason=result.transition_reason,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Bio generation continuation failed",
                "code": "BIO_GENERATION_FAILED",
                "message": str(e)
            }
        )


class ContinueFinalizeResponse(BaseModel):
    """Response from continue finalization endpoint."""
    research_run_id: str
    twin_id: str
    previous_status: str
    new_status: str
    mind_score_summary: Optional[dict]
    readiness_summary: Optional[dict]
    transition_reason: Optional[str]


@router.post(
    "/twins/{twin_id}/research/{research_run_id}/continue-finalize",
    response_model=ContinueFinalizeResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        404: {"model": ErrorResponse, "description": "Research run not found"},
        403: {"model": ErrorResponse, "description": "Access denied"},
        400: {"model": ErrorResponse, "description": "Invalid state for finalization"},
        409: {"model": ErrorResponse, "description": "Already completed"},
    }
)
async def continue_finalize_endpoint(
    twin_id: str,
    research_run_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Continue research run from bio_generated to completed (Phase 5 finalization).
    
    This endpoint:
    1. Validates run is in bio_generated state
    2. Transitions to finalizing
    3. Updates mind score using existing training_metrics hook
    4. Evaluates twin readiness
    5. Transitions to completed
    6. Returns mind score and readiness summaries
    
    Idempotent: If already in completed, returns success with current state.
    
    Phase 5 stops here - no frontend changes, no chat changes.
    """
    # Check feature flag
    _check_feature_enabled()
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    try:
        from modules.research_orchestrator import ResearchOrchestrator, ResearchRunStatus
        
        orchestrator = ResearchOrchestrator()
        
        # First check current status for idempotency
        try:
            current_status_result = await orchestrator.get_run_status(
                research_run_id=research_run_id,
                twin_id=twin_id,
            )
            
            # Idempotent: already completed
            if current_status_result.status == ResearchRunStatus.COMPLETED.value:
                return ContinueFinalizeResponse(
                    research_run_id=research_run_id,
                    twin_id=twin_id,
                    previous_status=current_status_result.status,
                    new_status=current_status_result.status,
                    mind_score_summary=current_status_result.checkpoint_data.get("mind_score"),
                    readiness_summary=current_status_result.checkpoint_data.get("readiness"),
                    transition_reason="Already in completed state (idempotent)",
                )
            
            # Validate state
            if current_status_result.status != ResearchRunStatus.BIO_GENERATED.value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "Invalid state for finalization",
                        "code": "INVALID_STATE",
                        "message": f"Research run must be in bio_generated state, current: {current_status_result.status}"
                    }
                )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "Research run not found",
                    "code": "NOT_FOUND",
                    "message": str(e)
                }
            )
        
        # Continue to finalization
        result = await orchestrator.continue_to_finalize_research_run(
            research_run_id=research_run_id,
            twin_id=twin_id,
        )
        
        if not result.success:
            status_code = status.HTTP_400_BAD_REQUEST
            if "already" in (result.error or "").lower():
                status_code = status.HTTP_409_CONFLICT
            
            raise HTTPException(
                status_code=status_code,
                detail={
                    "error": "Finalization failed",
                    "code": "FINALIZATION_FAILED",
                    "message": result.error or "Unknown error"
                }
            )
        
        # Get updated status for summaries
        updated_status = await orchestrator.get_run_status(
            research_run_id=research_run_id,
            twin_id=twin_id,
        )
        
        return ContinueFinalizeResponse(
            research_run_id=research_run_id,
            twin_id=twin_id,
            previous_status=result.previous_status,
            new_status=result.new_status,
            mind_score_summary=updated_status.checkpoint_data.get("mind_score"),
            readiness_summary=updated_status.checkpoint_data.get("readiness"),
            transition_reason=result.transition_reason,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Finalization failed",
                "code": "FINALIZATION_FAILED",
                "message": str(e)
            }
        )


class ResearchSummaryResponse(BaseModel):
    """Response from research summary endpoint."""
    twin_id: str
    research_run_id: Optional[str]
    status: Optional[str]
    sources: Dict[str, List[Any]]
    bio_generation: Optional[dict]
    mind_score: Optional[dict]
    readiness: Optional[dict]
    next_actions: List[str]
    checkpoint_updated_at: Optional[str]


@router.get(
    "/twins/{twin_id}/research-summary",
    response_model=ResearchSummaryResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        404: {"model": ErrorResponse, "description": "Twin not found"},
        403: {"model": ErrorResponse, "description": "Access denied"},
    }
)
async def get_research_summary_endpoint(
    twin_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Get research summary for a twin (Phase 5 backend contract).
    
    This endpoint:
    1. Returns the latest research run status
    2. Groups sources by confirmation status
    3. Includes bio generation, mind score, and readiness summaries (if available)
    4. Provides next actions for UI integration
    
    No frontend changes in this phase - this is the backend contract only.
    """
    # Check feature flag
    _check_feature_enabled()
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    try:
        from modules.research_orchestrator import ResearchOrchestrator
        from modules.twin_readiness import TwinReadinessChecker
        
        # Get latest research run
        orchestrator = ResearchOrchestrator()
        
        # Query latest research run
        response = supabase.table("research_runs").select(
            "*"
        ).eq("twin_id", twin_id).not_.eq("status", "failed").order(
            "created_at", desc=True
        ).limit(1).execute()
        
        if not response.data:
            # No research run found - return empty summary
            return ResearchSummaryResponse(
                twin_id=twin_id,
                research_run_id=None,
                status=None,
                sources={
                    "confirmed": [],
                    "auto_confirmed": [],
                    "pending": [],
                    "manual_review": [],
                    "rejected": [],
                },
                bio_generation=None,
                mind_score=None,
                readiness=None,
                next_actions=["start_onboarding"],
                checkpoint_updated_at=None,
            )
        
        run = response.data[0]
        research_run_id = run["id"]
        status = run.get("status")
        checkpoint_data = run.get("checkpoint_data", {})
        
        # Get sources grouped by confirmation status
        sources = await _get_sources_by_status(research_run_id, twin_id)
        
        # Get full run status for complete picture
        try:
            run_status = await orchestrator.get_run_status(
                research_run_id=research_run_id,
                twin_id=twin_id,
            )
            next_actions = run_status.next_actions  # Phase 6: Use canonical plural field
        except Exception:
            next_actions = []
        
        # Build response
        return ResearchSummaryResponse(
            twin_id=twin_id,
            research_run_id=research_run_id,
            status=status,
            sources=sources,
            bio_generation=checkpoint_data.get("bio_generation"),
            mind_score=checkpoint_data.get("mind_score"),
            readiness=checkpoint_data.get("readiness"),
            next_actions=next_actions,
            checkpoint_updated_at=checkpoint_data.get("last_transition_at"),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to get research summary",
                "code": "SUMMARY_FAILED",
                "message": str(e)
            }
        )


async def _get_sources_by_status(
    research_run_id: str,
    twin_id: str,
) -> Dict[str, List[Any]]:
    """
    Get sources grouped by confirmation status.
    
    Args:
        research_run_id: Research run ID
        twin_id: Twin ID
        
    Returns:
        Dict with sources grouped by status
    """
    try:
        # Query source_confirmations with crawl_page metadata
        response = supabase.table("source_confirmations").select(
            "*, crawl_pages(canonical_url, title, metadata)"
        ).eq("research_run_id", research_run_id).eq("twin_id", twin_id).execute()
        
        sources = {
            "confirmed": [],
            "auto_confirmed": [],
            "pending": [],
            "manual_review": [],
            "rejected": [],
        }
        
        if not response.data:
            return sources
        
        for row in response.data:
            status = row.get("confirmation_status", row.get("status", ""))
            source_data = {
                "confirmation_id": row.get("id"),
                "crawl_page_id": row.get("crawl_page_id"),
                "url": row.get("url"),
                "title": row.get("title"),
                "canonical_url": row.get("canonical_url"),
                "identity_confidence_score": row.get("identity_confidence_score"),
                "content_quality": row.get("content_quality"),
                "created_at": row.get("created_at"),
            }
            
            # Add to appropriate group
            if status in ("confirmed", "auto_confirmed"):
                sources["confirmed" if status == "confirmed" else "auto_confirmed"].append(source_data)
            elif status == "pending":
                sources["pending"].append(source_data)
            elif status == "manual_review":
                sources["manual_review"].append(source_data)
            elif status in ("rejected", "auto_rejected"):
                sources["rejected"].append(source_data)
        
        return sources
        
    except Exception as e:
        logger.error(f"Phase 5: Error getting sources by status: {e}")
        return {
            "confirmed": [],
            "auto_confirmed": [],
            "pending": [],
            "manual_review": [],
            "rejected": [],
        }


@router.post(
    "/twins/{twin_id}/research/{research_run_id}/transition/{new_status}",
    responses={
        503: {"model": ErrorResponse, "description": "Feature disabled"},
        404: {"model": ErrorResponse, "description": "Research run not found"},
        403: {"model": ErrorResponse, "description": "Access denied"},
        400: {"model": ErrorResponse, "description": "Invalid transition"},
    }
)
async def force_status_transition(
    twin_id: str,
    research_run_id: str,
    new_status: str,
    reason: Optional[str] = None,
    user: dict = Depends(require_admin)
):
    """
    Force a status transition (admin/debug only) (Phase 3.4).
    
    Use with caution - bypasses normal state machine validation.
    Primarily for testing, debugging, and recovery scenarios.
    
    Valid statuses: planning, queued, crawling, awaiting_confirmation,
    timed_out, ready_for_ingestion, completed, failed
    """
    # Check feature flag
    _check_feature_enabled()
    
    # Verify twin ownership
    verify_twin_ownership(twin_id, user)
    
    try:
        from modules.research_orchestrator import ResearchOrchestrator
        
        # Validate status
        try:
            to_status = ResearchRunStatus(new_status)
        except ValueError:
            valid = [s.value for s in ResearchRunStatus]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid status",
                    "code": "INVALID_STATUS",
                    "message": f"Valid statuses: {valid}"
                }
            )
        
        orchestrator = ResearchOrchestrator()
        
        # Use internal transition method (requires admin/debug privileges)
        result = await orchestrator._transition(
            research_run_id=research_run_id,
            twin_id=twin_id,
            to_status=to_status,
            reason=reason or "Admin forced transition",
        )
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Transition failed",
                    "code": "TRANSITION_FAILED",
                    "message": result.error or "Unknown error"
                }
            )
        
        return {
            "research_run_id": research_run_id,
            "previous_status": result.previous_status,
            "new_status": result.new_status,
            "transition_reason": result.transition_reason,
            "checkpoint_updated": result.checkpoint_updated,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Transition failed",
                "code": "TRANSITION_FAILED",
                "message": str(e)
            }
        )


# ============================================================================
# Private Helper Functions
# ============================================================================

def _create_crawl_run(
    twin_id: str,
    seed_urls: List[str],
    max_pages: int,
    max_depth: int,
    include_patterns: Optional[List[str]],
    exclude_patterns: Optional[List[str]],
) -> str:
    """
    Create crawl run record in database.
    
    Returns:
        Crawl run ID
    """
    import uuid
    from backend.modules.deep_research_config import get_config as get_dr_config
    
    crawl_id = str(uuid.uuid4())
    config = get_dr_config()
    
    try:
        result = supabase.table("crawl_runs").insert({
            "id": crawl_id,
            "twin_id": twin_id,
            "status": "queued",
            "seed_urls": seed_urls,
            "max_pages": max_pages,
            "max_depth": max_depth,
            "include_patterns": include_patterns or [],
            "exclude_patterns": exclude_patterns or [],
            "safety_config": config.safety.dict(),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }).execute()
        
        return crawl_id
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Database error",
                "code": "DB_INSERT_FAILED",
                "message": str(e)
            }
        )
