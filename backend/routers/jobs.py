"""
Jobs Router

REST API endpoints for viewing and managing background jobs.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from modules.auth_guard import get_current_user
from modules.jobs import (
    Job, JobLog, JobStatus, JobType, LogLevel,
    create_job, get_job, list_jobs, list_job_logs,
    start_job, complete_job, fail_job, append_log
)
from modules.observability import supabase

router = APIRouter(prefix="/jobs", tags=["jobs"])


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateJobRequest(BaseModel):
    job_type: JobType
    twin_id: Optional[str] = None
    source_id: Optional[str] = None
    priority: int = 0
    metadata: dict = {}


class JobResponse(BaseModel):
    id: str
    twin_id: Optional[str] = None
    source_id: Optional[str] = None
    status: str
    job_type: str
    priority: int
    error_message: Optional[str] = None
    metadata: dict
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class JobLogResponse(BaseModel):
    id: str
    job_id: str
    log_level: str
    message: str
    metadata: dict
    created_at: str


# ============================================================================
# Helper Functions
# ============================================================================

def get_user_twin_ids(user_id: str) -> List[str]:
    """Get list of twin IDs owned by the user."""
    result = supabase.table("twins").select("id").eq("tenant_id", user_id).execute()
    return [row["id"] for row in result.data] if result.data else []


def job_to_response(job: Job) -> JobResponse:
    """Convert Job model to response."""
    return JobResponse(
        id=job.id,
        twin_id=job.twin_id,
        source_id=job.source_id,
        status=job.status.value if isinstance(job.status, JobStatus) else job.status,
        job_type=job.job_type.value if isinstance(job.job_type, JobType) else job.job_type,
        priority=job.priority,
        error_message=job.error_message,
        metadata=job.metadata,
        created_at=job.created_at.isoformat() if hasattr(job.created_at, 'isoformat') else str(job.created_at),
        updated_at=job.updated_at.isoformat() if hasattr(job.updated_at, 'isoformat') else str(job.updated_at),
        started_at=job.started_at.isoformat() if job.started_at and hasattr(job.started_at, 'isoformat') else str(job.started_at) if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at and hasattr(job.completed_at, 'isoformat') else str(job.completed_at) if job.completed_at else None
    )


def log_to_response(log: JobLog) -> JobLogResponse:
    """Convert JobLog model to response."""
    return JobLogResponse(
        id=log.id,
        job_id=log.job_id,
        log_level=log.log_level.value if isinstance(log.log_level, LogLevel) else log.log_level,
        message=log.message,
        metadata=log.metadata,
        created_at=log.created_at.isoformat() if hasattr(log.created_at, 'isoformat') else str(log.created_at)
    )


# ============================================================================
# Endpoints
# ============================================================================

@router.get("", response_model=List[JobResponse])
async def list_user_jobs(
    status: Optional[str] = Query(None, description="Filter by status"),
    job_type: Optional[str] = Query(None, description="Filter by job type"),
    twin_id: Optional[str] = Query(None, description="Filter by twin ID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(get_current_user)
):
    """
    List jobs visible to the current user.
    
    Filters jobs to only show those belonging to the user's twins.
    """
    user_id = user.get("user_id")
    user_twin_ids = get_user_twin_ids(user_id)
    
    # Build query
    query = supabase.table("jobs").select("*")
    
    # Filter by user's twins (or show jobs with no twin_id for system jobs)
    if twin_id:
        if twin_id not in user_twin_ids:
            raise HTTPException(status_code=403, detail="Not authorized to view jobs for this twin")
        query = query.eq("twin_id", twin_id)
    else:
        # Show jobs for user's twins OR system jobs (twin_id is null)
        query = query.or_(f"twin_id.is.null,twin_id.in.({','.join(user_twin_ids)})" if user_twin_ids else "twin_id.is.null")
    
    if status:
        query = query.eq("status", status)
    if job_type:
        query = query.eq("job_type", job_type)
    
    query = query.order("created_at", desc=True).range(offset, offset + limit - 1)
    result = query.execute()
    
    jobs = [Job(**row) for row in result.data] if result.data else []
    return [job_to_response(job) for job in jobs]


@router.get("/{job_id}", response_model=JobResponse)
async def get_job_details(
    job_id: str,
    user=Depends(get_current_user)
):
    """Get details of a specific job."""
    user_id = user.get("user_id")
    user_twin_ids = get_user_twin_ids(user_id)
    
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check authorization
    if job.twin_id and job.twin_id not in user_twin_ids:
        raise HTTPException(status_code=403, detail="Not authorized to view this job")
    
    return job_to_response(job)


@router.get("/{job_id}/logs", response_model=List[JobLogResponse])
async def get_job_logs(
    job_id: str,
    log_level: Optional[str] = Query(None, description="Filter by log level"),
    limit: int = Query(100, ge=1, le=500),
    user=Depends(get_current_user)
):
    """Get logs for a specific job."""
    user_id = user.get("user_id")
    user_twin_ids = get_user_twin_ids(user_id)
    
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check authorization
    if job.twin_id and job.twin_id not in user_twin_ids:
        raise HTTPException(status_code=403, detail="Not authorized to view this job")
    
    level = LogLevel(log_level) if log_level else None
    logs = list_job_logs(job_id, log_level=level, limit=limit)
    
    return [log_to_response(log) for log in logs]


@router.post("", response_model=JobResponse)
async def create_new_job(
    request: CreateJobRequest,
    user=Depends(get_current_user)
):
    """
    Create a new job.
    
    Note: This is primarily for internal/admin use. Most jobs are created
    automatically by the system (e.g., during ingestion).
    """
    user_id = user.get("user_id")
    user_twin_ids = get_user_twin_ids(user_id)
    
    # Check authorization for twin_id
    if request.twin_id and request.twin_id not in user_twin_ids:
        raise HTTPException(status_code=403, detail="Not authorized to create jobs for this twin")
    
    job = create_job(
        job_type=request.job_type,
        twin_id=request.twin_id,
        source_id=request.source_id,
        priority=request.priority,
        metadata=request.metadata
    )
    
    return job_to_response(job)
