from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from modules.observability import supabase
from modules._core.tenant_guard import verify_tenant_access, verify_twin_access

router = APIRouter(tags=["graph"])

class NodeCreate(BaseModel):
    name: str
    type: str
    description: Optional[str] = None
    properties: Dict[str, Any] = {}

class EdgeCreate(BaseModel):
    from_node_id: str
    to_node_id: str
    type: str
    description: Optional[str] = None

@router.get("/twins/{twin_id}/graph")
async def get_twin_graph(
    twin_id: str,
    limit: int = Query(100, le=500),
    user=Depends(verify_tenant_access),
    authorized=Depends(verify_twin_access)
):
    """Retrieve the cognitive graph for visualization."""
    try:
        # Fetch nodes via RPC (System Privileges)
        nodes = []
        edges = []
        try:
            nodes_res = supabase.rpc("get_nodes_system", {
                "t_id": twin_id,
                "limit_val": limit
            }).execute()
            if getattr(nodes_res, "error", None):
                raise Exception(nodes_res.error)
            nodes = nodes_res.data or []
        except Exception as e:
            # Fallback: direct table query if RPC is missing/out of date
            nodes_res = supabase.table("nodes").select("*").eq("twin_id", twin_id).limit(limit).execute()
            nodes = nodes_res.data or []

        # Fetch edges via RPC
        if nodes:
            try:
                edges_res = supabase.rpc("get_edges_system", {
                    "t_id": twin_id,
                    "limit_val": limit * 2
                }).execute()
                if getattr(edges_res, "error", None):
                    raise Exception(edges_res.error)
                edges = edges_res.data or []
            except Exception as e:
                edges_res = supabase.table("edges").select("*").eq("twin_id", twin_id).limit(limit * 2).execute()
                edges = edges_res.data or []

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "node_count": len(nodes),
                "edge_count": len(edges)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/twins/{twin_id}/nodes")
async def create_node(
    twin_id: str,
    node: NodeCreate,
    user=Depends(verify_tenant_access),
    authorized=Depends(verify_twin_access)
):
    """Create a new node manually."""
    try:
        data = {
            "twin_id": twin_id,
            "name": node.name,
            "type": node.type,
            "description": node.description,
            "properties": node.properties
        }
        res = supabase.table("nodes").insert(data).execute()
        return res.data[0]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
