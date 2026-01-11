# backend/api/vc_routes.py
"""FastAPI routes for VC specialization.

This module demonstrates how the generic core components are wired together
for a specific specialization (VC). It provides a placeholder `/artifact/upload`
endpoint that:
1. Enforces tenant isolation via `@require_tenant`.
2. Loads the VC specialization manifest to obtain the scribe schema.
3. Calls the generic `artifact_pipeline.process_artifact` stub.
4. Returns the structured extraction result.

Real implementations will replace the stub logic with actual file handling,
text extraction, and LLM calls.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from backend.modules._core.tenant_guard import verify_tenant_access
from backend.modules._core.registry_loader import get_specialization_manifest
from backend.modules._core.artifact_pipeline import process_artifact

router = APIRouter()

@router.post("/vc/artifact/upload")
async def upload_vc_artifact(
    file: UploadFile = File(...), 
    user: dict = Depends(verify_tenant_access)
):
    """Upload an artifact for the VC specialization.

    Args:
        file: Uploaded file (PDF, DOCX, TXT, MD).
        tenant_id: Tenant identifier (validated by `require_tenant`).
    Returns:
        Structured extraction dict (node_updates, edge_updates, ...).
    """
    # Load VC manifest to get the scribe schema path
    try:
        manifest = get_specialization_manifest("vc")
        scribe_schema_path = manifest["prompts"]["scribe_schema"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load VC manifest: {e}")

    # Load the scribe schema JSON
    try:
        import json
        from pathlib import Path
        schema_path = Path(__file__).parents[3] / scribe_schema_path
        with schema_path.open("r", encoding="utf-8") as f:
            scribe_schema = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load scribe schema: {e}")

    # Save uploaded file to a temporary location (placeholder)
    temp_path = Path("/tmp") / file.filename
    with temp_path.open("wb") as out:
        content = await file.read()
        out.write(content)

    # Process the artifact using the generic pipeline (stub implementation)
    result = process_artifact(str(temp_path), scribe_schema)
    return result
