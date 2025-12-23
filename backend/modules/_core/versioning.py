"""
Versioning Module for Cognitive Profile Approval

Provides diff computation and snapshot management for profile versions.
"""
from typing import Dict, List, Any, Optional
from datetime import datetime


def compute_diff(old_snapshot: Dict, new_snapshot: Dict) -> Dict:
    """
    Compute what changed between two profile snapshots.
    
    Returns a diff object showing added, removed, and modified nodes/edges.
    """
    # Handle first version case
    if not old_snapshot:
        return {
            "added_nodes": new_snapshot.get("nodes", []),
            "removed_nodes": [],
            "modified_nodes": [],
            "added_edges": new_snapshot.get("edges", []),
            "removed_edges": [],
            "modified_edges": [],
            "is_initial": True
        }
    
    # Index nodes by ID for comparison
    old_nodes = {n["id"]: n for n in old_snapshot.get("nodes", [])}
    new_nodes = {n["id"]: n for n in new_snapshot.get("nodes", [])}
    
    old_edges = {e["id"]: e for e in old_snapshot.get("edges", [])}
    new_edges = {e["id"]: e for e in new_snapshot.get("edges", [])}
    
    # Compute node changes
    added_nodes = [n for id, n in new_nodes.items() if id not in old_nodes]
    removed_nodes = [n for id, n in old_nodes.items() if id not in new_nodes]
    
    modified_nodes = []
    for id in set(old_nodes) & set(new_nodes):
        old = old_nodes[id]
        new = new_nodes[id]
        changes = _diff_dict(old, new)
        if changes:
            modified_nodes.append({
                "id": id,
                "name": new.get("name"),
                "changes": changes
            })
    
    # Compute edge changes
    added_edges = [e for id, e in new_edges.items() if id not in old_edges]
    removed_edges = [e for id, e in old_edges.items() if id not in new_edges]
    
    modified_edges = []
    for id in set(old_edges) & set(new_edges):
        old = old_edges[id]
        new = new_edges[id]
        changes = _diff_dict(old, new)
        if changes:
            modified_edges.append({
                "id": id,
                "changes": changes
            })
    
    return {
        "added_nodes": added_nodes,
        "removed_nodes": removed_nodes,
        "modified_nodes": modified_nodes,
        "added_edges": added_edges,
        "removed_edges": removed_edges,
        "modified_edges": modified_edges,
        "is_initial": False
    }


def _diff_dict(old: Dict, new: Dict) -> Dict:
    """
    Compare two dicts and return changes.
    """
    changes = {}
    all_keys = set(old.keys()) | set(new.keys())
    
    # Skip certain fields that change frequently
    skip_fields = {"created_at", "updated_at", "id"}
    
    for key in all_keys:
        if key in skip_fields:
            continue
        old_val = old.get(key)
        new_val = new.get(key)
        if old_val != new_val:
            changes[key] = {
                "old": old_val,
                "new": new_val
            }
    
    return changes


def create_snapshot(nodes: List[Dict], edges: List[Dict]) -> Dict:
    """
    Create a snapshot object from current graph state.
    """
    return {
        "nodes": nodes,
        "edges": edges,
        "timestamp": datetime.utcnow().isoformat(),
        "node_count": len(nodes),
        "edge_count": len(edges)
    }


def summarize_diff(diff: Dict) -> str:
    """
    Create a human-readable summary of changes.
    """
    parts = []
    
    if diff.get("is_initial"):
        return f"Initial version with {len(diff.get('added_nodes', []))} nodes"
    
    if diff.get("added_nodes"):
        parts.append(f"+{len(diff['added_nodes'])} nodes")
    if diff.get("removed_nodes"):
        parts.append(f"-{len(diff['removed_nodes'])} nodes")
    if diff.get("modified_nodes"):
        parts.append(f"~{len(diff['modified_nodes'])} modified")
    if diff.get("added_edges"):
        parts.append(f"+{len(diff['added_edges'])} edges")
    
    return ", ".join(parts) if parts else "No changes"
