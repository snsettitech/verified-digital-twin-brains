from fastapi import APIRouter, Depends
from modules.auth_guard import get_current_user
import json
from pathlib import Path
from modules.specializations import get_specialization
from modules.specializations.registry import list_specializations
from modules._core.registry_loader import get_specialization_manifest

router = APIRouter(tags=["config"])


def _load_json_file(relative_path: str) -> dict:
    """Load a JSON file given a path relative to backend or repo root."""
    # Try backend folder first (for modules/... paths)
    backend_base = Path(__file__).parent.parent  # backend/routers -> backend
    full_path = backend_base / relative_path
    if full_path.is_file():
        with full_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    # Fall back to repo root (for frontend/... paths)
    repo_root = backend_base.parent
    full_path = repo_root / relative_path
    if full_path.is_file():
        with full_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {}


@router.get("/config/specialization")
async def get_specialization_config():
    """Get current specialization configuration for frontend.

    Returns:
        - name, display_name, description
        - sidebar (menu config)
        - features (feature flags from manifest inline)
        - default_settings
        - ui_clusters (cluster definitions for graph/cards)
        - host_policy (slot-priority, ordering, follow-up behavior)
    """
    spec = get_specialization()

    # Load manifest to get extended config
    try:
        manifest = get_specialization_manifest(spec.name)
    except Exception:
        manifest = {}

    # Load UI clusters from manifest path if present
    ui_clusters = {}
    if manifest.get("ui_config"):
        ui_clusters = _load_json_file(manifest["ui_config"])

    # Load host policy from manifest path if present
    host_policy = {}
    if manifest.get("host_policy"):
        host_policy = _load_json_file(manifest["host_policy"])

    # Feature flags: prefer inline manifest over class method
    feature_flags = manifest.get("feature_flags") or spec.get_feature_flags()

    return {
        "name": spec.name,
        "display_name": spec.display_name,
        "description": spec.description,
        "sidebar": spec.get_sidebar_config(),
        "features": feature_flags,
        "default_settings": spec.get_default_settings(),
        "ui_clusters": ui_clusters,
        "host_policy": host_policy,
    }


@router.get("/twins/{twin_id}/specialization")
async def get_twin_specialization_config(twin_id: str, user=Depends(get_current_user)):
    """Get specialization configuration for a specific twin.
    
    This replaces the global /config/specialization endpoint.
    Retrieves the specialization_id from the twins table (defaulting to 'vanilla')
    and returns its configuration.
    """
    from modules.auth_guard import verify_twin_ownership
    from modules.observability import supabase
    
    # SECURITY: Verify user has access to this twin
    verify_twin_ownership(twin_id, user)
    
    # 1. Get twin's specialization preference
    spec_id = "vanilla"  # Default
    try:
        # Direct query with proper error handling
        response = supabase.table("twins").select("specialization").eq("id", twin_id).maybe_single().execute()
        if response.data:
            spec_id = response.data.get("specialization") or "vanilla"
    except Exception as e:
        print(f"Warning: Could not fetch specialization for twin {twin_id}: {e}")
        spec_id = "vanilla"

    
    # 2. Load the specialization instance
    spec = get_specialization(spec_id)

    # 3. Load manifest-based config (same logic as before)
    manifest = {}
    try:
        manifest = get_specialization_manifest(spec.name)
    except Exception:
        pass

    # Load UI clusters
    ui_clusters = {}
    if manifest.get("ui_config"):
        ui_clusters = _load_json_file(manifest["ui_config"])

    # Load host policy
    host_policy = {}
    if manifest.get("host_policy"):
        host_policy = _load_json_file(manifest["host_policy"])

    # Feature flags
    feature_flags = manifest.get("feature_flags") or spec.get_feature_flags()

    return {
        "id": spec.name,
        "name": spec.name,
        "display_name": spec.display_name,
        "description": spec.description,
        "sidebar": spec.get_sidebar_config(),
        "features": feature_flags,
        "default_settings": spec.get_default_settings(),
        "ui_clusters": ui_clusters,
        "host_policy": host_policy,
    }


@router.get("/config/specializations")
async def list_all_specializations():
    """List all available specializations."""
    return list_specializations()

