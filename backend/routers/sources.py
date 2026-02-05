from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from modules.auth_guard import verify_owner, get_current_user, verify_twin_ownership
from modules.observability import supabase
from modules.ingestion import delete_source

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



@router.post("/sources/{source_id}/re-extract")
async def re_extract_source(source_id: str, user=Depends(verify_owner)):
    """Re-extract content from a source (triggers re-processing)."""
    try:
        # Reset status to trigger re-processing
        supabase.table("sources").update({
            "staging_status": "processing",
            "status": "processing"
        }).eq("id", source_id).execute()

        return {"status": "success", "message": "Re-extraction queued"}
    except Exception as e:
        print(f"Error re-extracting source: {e}")
        raise HTTPException(status_code=500, detail=str(e))


