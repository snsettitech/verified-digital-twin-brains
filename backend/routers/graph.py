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
        nodes_res = supabase.rpc("get_nodes_system", {
            "t_id": twin_id,
            "limit_val": limit
        }).execute()
            
        # Fetch edges via RPC
        edges = []
        if nodes_res.data:
            edges_res = supabase.rpc("get_edges_system", {
                "t_id": twin_id, 
                "limit_val": limit * 2
            }).execute()
            edges = edges_res.data

        return {
            "nodes": nodes_res.data,
            "edges": edges,
            "stats": {
                "node_count": len(nodes_res.data),
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
