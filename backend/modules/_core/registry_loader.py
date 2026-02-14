# backend/modules/_core/registry_loader.py
"""Utility to load the specialization registry and retrieve manifests.

The registry is located at `backend/modules/specializations/registry.json`.
The Digital Twin uses a standardized 'Vanilla' platform for all implementations.
"""
import json
from pathlib import Path
from typing import Dict, Any, List

REGISTRY_PATH = Path(__file__).parents[2] / "modules" / "specializations" / "registry.json"

def load_registry() -> Dict[str, Any]:
    """Load the specialization registry JSON file."""
    if not REGISTRY_PATH.is_file():
        raise FileNotFoundError(f"Specialization registry not found at {REGISTRY_PATH}")
    with REGISTRY_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)

def get_specialization_manifest(specialization_id: str = "vanilla") -> Dict[str, Any]:
    """Retrieve the manifest for the specialization.
    
    Args:
        specialization_id: Specialization identifier (defaults to "vanilla").
    Returns:
        The parsed manifest JSON as a dict.
    """
    try:
        registry = load_registry()
        specs: List[Dict[str, Any]] = registry.get("specializations", [])
        
        # Standardize on vanilla
        target_id = specialization_id if specialization_id == "vanilla" else "vanilla"
        spec = next((s for s in specs if s.get("id") == target_id), None)
        
        if not spec and target_id == "vanilla":
             # Last ditch effort if vanilla missing from registry
             spec = {"manifest_path": "modules/specializations/vanilla/manifest.json"}
        
        manifest_path = Path(__file__).parents[2] / spec["manifest_path"]
        with manifest_path.open("r", encoding="utf-8") as f:
            return json.load(f)
            
    except Exception as e:
        print(f"Error loading manifest: {e}")
        # Return empty or default manifest to prevent crash
        return {"id": "vanilla", "display_name": "Digital Twin", "packs": []}
