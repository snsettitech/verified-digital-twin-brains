
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from modules.retrieval import retrieve_context
from modules.auth_guard import get_current_user, verify_twin_ownership, ensure_twin_active
from modules.observability import supabase
import asyncio

router = APIRouter(
    prefix="/debug",
    tags=["debug"]
)

class RetrievalDebugRequest(BaseModel):
    query: str
    twin_id: str
    top_k: int = 10

@router.post("/retrieval")
async def debug_retrieval(
    request: RetrievalDebugRequest,
    current_user: dict = Depends(get_current_user)
):
    print(f"[Debug Retrieval] Query: {request.query}, Twin: {request.twin_id}")
    
    try:
        verify_twin_ownership(request.twin_id, current_user)
        ensure_twin_active(request.twin_id)

        # Call the actual retrieval function
        contexts = await retrieve_context(request.query, request.twin_id, top_k=request.top_k)
        
        # Diagnostics: Check Group ID
        from modules.access_groups import get_default_group
        diagnostics = {}
        try:
            default_group = await get_default_group(request.twin_id)
            diagnostics["default_group_id"] = default_group["id"] if default_group else "None"
        except Exception as e:
            diagnostics["default_group_error"] = str(e)
            
        # Enrich with source filenames
        source_ids = list(set([c.get("source_id") for c in contexts if c.get("source_id") and c.get("source_id") != "verified_memory"]))
        
        source_map = {}
        if source_ids:
            try:
                # Use in_ filter for multiple IDs
                res = supabase.table("sources").select("id, filename").in_("id", source_ids).execute()
                for item in res.data:
                    source_map[item["id"]] = item["filename"]
            except Exception as e:
                print(f"[Debug Retrieval] Error fetching sources: {e}")
                
        # Add filenames and raw metadata to contexts for inspection
        for c in contexts:
            sid = c.get("source_id")
            if sid in source_map:
                c["source_filename"] = source_map[sid]
            
            # If verified memory, add virtual filename
            if c.get("is_verified") and not c.get("source_filename"):
                 c["source_filename"] = "🧠 Verified Memory (Q&A)"

        return {
            "query": request.query,
            "twin_id": request.twin_id,
            "results_count": len(contexts),
            "diagnostics": diagnostics,
            "contexts": contexts
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
