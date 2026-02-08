from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from modules.auth_guard import verify_owner, get_current_user, verify_twin_ownership
from modules.observability import supabase
from modules.ingestion import delete_source
from modules.training_jobs import create_training_job
from modules.ingestion import detect_url_provider
from modules.ingestion_diagnostics import diagnostics_schema_status

router = APIRouter(tags=["sources"])

def _normalize_source(source: dict):
    if not source:
        return source
    status = source.get("status")
    if status == "approved":
        source["status"] = "live"
    elif status in ("staged", "training"):
        source["status"] = "processing"
    source.pop("staging_status", None)
    return source


@router.get("/sources/{twin_id}")
async def list_sources(twin_id: str, status: Optional[str] = None, user=Depends(get_current_user)):
    """
    List all sources for a twin.
    Optional status filter: 'processing', 'processed', 'error', 'live'
    """
    # Verify user has access to this twin
    verify_twin_ownership(twin_id, user)

    try:
        query = supabase.table("sources").select("*").eq("twin_id", twin_id).order("created_at", desc=True)

        if status:
            query = query.eq("status", status)

        response = query.execute()
        data = response.data or []
        return [_normalize_source(item) for item in data]
    except Exception as e:
        print(f"Error listing sources: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sources/{source_id}/health")
async def get_source_health(source_id: str, user=Depends(get_current_user)):
    """Get health check results for a source."""
    try:
        # First get source to verify ownership
        source = supabase.table("sources").select("twin_id, health_status").eq("id", source_id).single().execute()
        if not source.data:
            raise HTTPException(status_code=404, detail="Source not found")

        # Verify user owns this twin
        verify_twin_ownership(source.data["twin_id"], user)

        # Get health checks from ingestion_logs
        response = supabase.table("ingestion_logs").select("*").eq("source_id", source_id).order("created_at", desc=True).limit(20).execute()
        logs = response.data or []
        checks = [
            {
                "id": log.get("id"),
                "check_type": "ingestion_log",
                "status": log.get("log_level", "info"),
                "message": log.get("message"),
                "metadata": log.get("metadata"),
                "created_at": log.get("created_at")
            }
            for log in logs
        ]

        return {
            "health_status": source.data.get("health_status"),
            "logs": logs,
            "checks": checks
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting source health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sources/{twin_id}/{source_id}")
async def get_source(twin_id: str, source_id: str, user=Depends(get_current_user)):
    """Get a specific source with its details."""
    verify_twin_ownership(twin_id, user)

    try:
        response = supabase.table("sources").select("*").eq("id", source_id).eq("twin_id", twin_id).single().execute()

        if not response.data:
            raise HTTPException(status_code=404, detail="Source not found")

        return _normalize_source(response.data)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting source: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sources/{twin_id}/{source_id}")
async def delete_source_endpoint(twin_id: str, source_id: str, user=Depends(verify_owner)):
    """Delete a source and its associated vectors."""
    try:
        await delete_source(source_id, twin_id)
        return {"status": "success", "message": "Source deleted"}
    except Exception as e:
        print(f"Error deleting source: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sources/{source_id}/logs")
async def get_source_logs(source_id: str, user=Depends(get_current_user)):
    """Get ingestion logs for a source."""
    try:
        # First get source to verify ownership
        source = supabase.table("sources").select("twin_id").eq("id", source_id).single().execute()
        if not source.data:
            raise HTTPException(status_code=404, detail="Source not found")

        # Verify user owns this twin
        verify_twin_ownership(source.data["twin_id"], user)

        response = supabase.table("ingestion_logs").select("*").eq("source_id", source_id).order("created_at", desc=True).limit(50).execute()
        return response.data or []
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting source logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sources/{source_id}/events")
async def get_source_events(source_id: str, user=Depends(get_current_user)):
    """Get step timeline events for a source."""
    try:
        source = supabase.table("sources").select("twin_id").eq("id", source_id).single().execute()
        if not source.data:
            raise HTTPException(status_code=404, detail="Source not found")

        verify_twin_ownership(source.data["twin_id"], user)

        res = supabase.table("source_events").select("*").eq("source_id", source_id).order("created_at", desc=False).limit(200).execute()
        return res.data or []
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting source events: {e}")
        msg = str(e)
        if "source_events" in msg and ("schema cache" in msg or "PGRST205" in msg):
            raise HTTPException(
                status_code=503,
                detail=(
                    "Ingestion diagnostics schema is not installed (missing source_events/last_error columns). "
                    "Apply backend/database/migrations/20260207_ingestion_diagnostics.sql in Supabase SQL editor, "
                    "then redeploy/restart the backend."
                ),
            )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sources/{source_id}/re-extract")
async def re_extract_source(source_id: str, user=Depends(verify_owner)):
    """Compatibility shim: re-queue processing for a source (use /sources/{source_id}/retry)."""
    try:
        # Delegate to the canonical retry logic.
        return await retry_source(source_id, user)
    except Exception as e:
        print(f"Error re-extracting source: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sources/{source_id}/retry")
async def retry_source(source_id: str, user=Depends(verify_owner)):
    """
    Retry ingestion/indexing for a source.

    - If `citation_url` exists, re-runs URL ingestion.
    - Otherwise, re-runs indexing over existing `content_text`.
    """
    try:
        source_res = supabase.table("sources").select("id, twin_id, citation_url, content_text").eq("id", source_id).single().execute()
        if not source_res.data:
            raise HTTPException(status_code=404, detail="Source not found")

        twin_id = source_res.data["twin_id"]
        verify_twin_ownership(twin_id, user)

        citation_url = source_res.data.get("citation_url")
        provider = detect_url_provider(citation_url) if citation_url else "file"

        # Clear last error and reset status to queued/pending. Diagnostics fields are best-effort
        # and may not exist until the migration is applied.
        update = {
            "status": "pending",
            "staging_status": "staged",
            "health_status": "healthy",
        }
        available, _err = diagnostics_schema_status()
        if available:
            update.update(
                {
                    "last_error": None,
                    "last_error_at": None,
                    "last_provider": provider,
                    "last_step": "queued",
                    "last_event_at": None,
                }
            )
        try:
            supabase.table("sources").update(update).eq("id", source_id).execute()
        except Exception as e:
            # If some deployments have staging_status removed, retry without it.
            msg = str(e)
            if "staging_status" in msg:
                update.pop("staging_status", None)
                supabase.table("sources").update(update).eq("id", source_id).execute()
            else:
                raise

        job_id = create_training_job(
            source_id=source_id,
            twin_id=twin_id,
            job_type="ingestion",
            priority=0,
            metadata={
                "provider": provider,
                "url": citation_url,
                "ingest_mode": "retry",
            }
        )

        return {"status": "queued", "source_id": source_id, "job_id": job_id}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error retrying source {source_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
