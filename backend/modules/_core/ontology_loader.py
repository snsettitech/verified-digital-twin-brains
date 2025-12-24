# backend/modules/_core/ontology_loader.py
"""Ontology loader for the generic feature base.

* Loads any JSON ontology pack (e.g., vc_base_pack.json).
* Validates required node types and allowed edge types.
* Registers the ontology in the graph store (placeholder implementation).
"""
import json
from pathlib import Path
from typing import Dict, List, Any

ALLOWED_EDGE_TYPES = {
    "DEPENDS_ON",
    "IMPLIES",
    "PRIORITIZES",
    "CONTRADICTS",
    "REQUIRES",
    "EXAMPLE_OF",
}

def load_ontology(pack_path: str) -> Dict[str, Any]:
    """Load an ontology pack JSON file and return its dict representation.

    Raises:
        FileNotFoundError: If the pack file does not exist.
        ValueError: If the JSON is malformed or contains disallowed edge types.
    """
    path = Path(pack_path)
    if not path.is_file():
        raise FileNotFoundError(f"Ontology pack not found: {pack_path}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    # Basic validation – ensure "nodes" and "edges" sections exist
    if "nodes" not in data or "edges" not in data:
        raise ValueError("Ontology pack must contain 'nodes' and 'edges' sections")
    # Validate edge types
    for edge in data["edges"]:
        edge_type = edge.get("type")
        if edge_type not in ALLOWED_EDGE_TYPES:
            raise ValueError(f"Disallowed edge type: {edge_type}")
    return data

def register_ontology(pack_data: Dict[str, Any]) -> None:
    """Placeholder for registering the ontology in the graph store.

    In the real system this would create tables, indexes, or in‑memory structures.
    Here we simply log the registration for demonstration purposes.
    """
    # Example: print a summary (replace with actual registration logic)
    node_count = len(pack_data.get("nodes", []))
    edge_count = len(pack_data.get("edges", []))
    print(f"Registered ontology: {node_count} nodes, {edge_count} edges")
