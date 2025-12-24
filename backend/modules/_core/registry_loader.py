# backend/modules/_core/registry_loader.py
"""Utility to load specialization registry and retrieve manifests.

The registry is a JSON file located at
`backend/modules/specializations/registry.json`. Each entry contains:
- id: specialization identifier (e.g., "vc")
- display_name
- description
- manifest_path: path to the specialization's manifest.json

The loader provides two helper functions:
1. `load_registry()` – returns the parsed registry dict.
2. `get_specialization_manifest(specialization_id)` – loads and returns the
   specialization manifest as a dict.
"""
import json
from pathlib import Path
from typing import Dict, Any, List

REGISTRY_PATH = Path(__file__).parents[2] / "modules" / "specializations" / "registry.json"

def load_registry() -> Dict[str, Any]:
    """Load the specialization registry JSON file.

    Returns:
        A dictionary with a top‑level key "specializations" containing a list of
        specialization entries.
    """
    if not REGISTRY_PATH.is_file():
        raise FileNotFoundError(f"Specialization registry not found at {REGISTRY_PATH}")
    with REGISTRY_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)

def get_specialization_manifest(specialization_id: str) -> Dict[str, Any]:
    """Retrieve the manifest for a given specialization.

    Args:
        specialization_id: The identifier from the registry (e.g., "vc").
    Returns:
        The parsed manifest JSON as a dict.
    Raises:
        KeyError: If the specialization_id is not present in the registry.
        FileNotFoundError: If the manifest file cannot be found.
    """
    registry = load_registry()
    specs: List[Dict[str, Any]] = registry.get("specializations", [])
    spec = next((s for s in specs if s.get("id") == specialization_id), None)
    if not spec:
        raise KeyError(f"Specialization '{specialization_id}' not found in registry")
    manifest_path = Path(__file__).parents[2] / spec["manifest_path"]
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifest file not found: {manifest_path}")
    with manifest_path.open("r", encoding="utf-8") as f:
        return json.load(f)

# Example usage (to be called from API endpoints or services):
# manifest = get_specialization_manifest("vc")
# print(manifest["packs"])  # list of ontology pack paths
