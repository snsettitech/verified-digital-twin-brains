# backend/api/vc_routes.py
"""FastAPI routes for VC specialization.

VC routes are only available when ENABLE_VC_ROUTES=true.
These routes provide VC-specific functionality like artifact upload.

This module demonstrates how specialization-specific routes are conditionally
loaded and how they verify that the twin uses VC specialization before processing.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from modules.auth_guard import get_current_user, verify_twin_ownership
from modules._core.registry_loader import get_specialization_manifest
from pathlib import Path

router = APIRouter(tags=["vc"])


@router.post("/vc/artifact/upload/{twin_id}")
async def upload_vc_artifact(
    twin_id: str,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user)
):
    """
    Upload an artifact for the VC specialization.
    
    This endpoint is only available for twins with specialization_id='vc'.
    It validates ownership, checks specialization, and processes VC-specific artifacts.
    
    Args:
        twin_id: The twin ID (must have specialization_id='vc')
        file: Uploaded file (PDF, DOCX, TXT, MD)
        user: Authenticated user (from JWT)
        
    Returns:
        Structured extraction result (placeholder - implementation pending)
        
    Raises:
        400: If twin does not use VC specialization
        404: If twin not found
        500: If VC manifest or schema loading fails
    """
    # Verify user has access to twin
    verify_twin_ownership(twin_id, user)
    
    # Verify twin uses VC specialization
    from modules.observability import supabase
    try:
        response = supabase.table("twins").select("specialization_id").eq("id", twin_id).single().execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Twin not found")
        
        specialization_id = response.data.get("specialization_id")
        if specialization_id != "vc":
            raise HTTPException(
                status_code=400, 
                detail=f"This endpoint is only available for VC specialization. Twin uses: {specialization_id or 'vanilla'}"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Twin not found: {e}")
    
    # Load VC manifest (with validation to detect silent fallback)
    try:
        manifest = get_specialization_manifest("vc")
        # Validate that we actually got a VC manifest, not a vanilla fallback
        manifest_id = manifest.get("id")
        if manifest_id != "vc":
            raise HTTPException(
                status_code=500,
                detail=f"VC specialization not available (got {manifest_id} instead). Ensure VC routes are enabled and VC files are properly configured."
            )
        scribe_schema_path = manifest.get("prompts", {}).get("scribe_schema")
        if not scribe_schema_path:
            raise HTTPException(status_code=500, detail="VC manifest missing scribe_schema path")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load VC manifest: {e}")
    
    # Load scribe schema JSON
    try:
        import json
        schema_path = Path(__file__).parents[2] / scribe_schema_path
        if not schema_path.is_file():
            raise HTTPException(status_code=500, detail=f"Scribe schema file not found: {scribe_schema_path}")
        with schema_path.open("r", encoding="utf-8") as f:
            scribe_schema = json.load(f)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load scribe schema: {e}")
    
    # TODO: Implement artifact processing
    # This is a placeholder - actual implementation would:
    # 1. Save uploaded file temporarily
    # 2. Extract text from file (PDF, DOCX, etc.)
    # 3. Process with VC-specific schema using Scribe engine
    # 4. Return structured extraction (nodes, edges)
    
    return {
        "status": "success",
        "message": "Artifact upload endpoint (placeholder - implementation pending)",
        "filename": file.filename,
        "twin_id": twin_id,
        "specialization": "vc",
        "note": "This endpoint will process artifacts using VC-specific schema when implemented"
    }
