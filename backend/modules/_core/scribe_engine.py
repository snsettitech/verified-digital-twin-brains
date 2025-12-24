# backend/modules/_core/scribe_engine.py
"""Scribe Engine: Extracts structured knowledge from conversation.

Integrates with OpenAI Structured Outputs (beta) to parse user/assistant
messages into Graph Nodes and Edges, then persists them to Supabase
using secure RPCs.

Refactored to support Strict Mode (extra="forbid") and explicit Property models.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import logging
import json

from modules.clients import get_async_openai_client
from modules.observability import supabase

logger = logging.getLogger(__name__)

# --- Structured Output Schema (Strict Mode) ---

class Property(BaseModel):
    key: str = Field(description="Property name (e.g., 'value', 'unit', 'sector').")
    value: str = Field(description="Property value as string.")
    
    # Strict mode requires forbidding extra fields
    # Using model_config for Pydantic v2 or class Config for v1. 
    # Assumes environment supports standard Pydantic.
    class Config:
        extra = "forbid"

class NodeUpdate(BaseModel):
    name: str = Field(description="Unique name of the concept, entity, or topic. Use Title Case.")
    type: str = Field(description="Type of entity (e.g., Company, Person, Statistic, Market, Product, Concept, Goal).")
    description: str = Field(description="Concise description or definition based on the context.")
    # OpenAI Strict Mode does NOT support Dict[str, Any]. Must use List of objects.
    properties: List[Property] = Field(default_factory=list, description="List of key-value properties.")

    class Config:
        extra = "forbid"

class EdgeUpdate(BaseModel):
    from_node: str = Field(description="Name of the source node.")
    to_node: str = Field(description="Name of the target node.")
    type: str = Field(description="Relationship type (e.g., FOUNDED, LOCATED_IN, HAS_METRIC, TARGETS, MENTIONS).")
    description: Optional[str] = Field(None, description="Context for why this relationship exists.")

    class Config:
        extra = "forbid"

class GraphUpdates(BaseModel):
    nodes: List[NodeUpdate] = Field(default_factory=list, description="List of nodes to create or update.")
    edges: List[EdgeUpdate] = Field(default_factory=list, description="List of relationships to create.")
    confidence: float = Field(description="Confidence score (0.0 to 1.0) in the extraction accuracy.")

    class Config:
        extra = "forbid"

# --- Core Functions ---

async def process_interaction(
    twin_id: str, 
    user_message: str, 
    assistant_message: str,
    history: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    analyzes the interaction and updates the cognitive graph.
    """
    try:
        client = get_async_openai_client()
        
        # Construct context
        messages = [
            {"role": "system", "content": (
                "You are an expert Knowledge Graph Scribe. "
                "Your goal is to extract structured entities (Nodes) and relationships (Edges) "
                "from the latest user-assistant interaction. "
                "Focus on factual claims, metrics, definitions, and proper nouns. "
                "Do NOT create generic nodes like 'User' or 'Assistant'. "
                "Ensure node names are canonical (Title Case)."
            )}
        ]
        
        if history:
            # Flatten history (limit last 6 turns)
            for msg in history[-6:]: 
                if hasattr(msg, "content"): # LangChain Object
                    role = "user"
                    if hasattr(msg, "type") and msg.type == "ai":
                         role = "assistant"
                    elif hasattr(msg, "role"):
                         role = msg.role
                    content = msg.content
                elif isinstance(msg, dict): # Check dict last
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                else:
                    continue
                
                messages.append({"role": role, "content": content})
                
        # Add current turn
        messages.append({"role": "user", "content": user_message})
        messages.append({"role": "assistant", "content": assistant_message})

        # Call OpenAI with Pydantic Schema
        response = await client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=messages,
            response_format=GraphUpdates,
            temperature=0.0
        )
        
        updates = response.choices[0].message.parsed
        
        if not updates:
            logger.warning("Scribe returned no parsed structure.")
            return {"nodes": [], "edges": []}
            
        logger.info(f"Scribe extracted: {len(updates.nodes)} nodes, {len(updates.edges)} edges, conf={updates.confidence}")
        
        # Persist to Supabase
        created_nodes = await _persist_nodes(twin_id, updates.nodes)
        
        # Create map for Edges
        node_map = {n['name']: n['id'] for n in created_nodes}
        
        # Persist Edges
        valid_edges = []
        for edge in updates.edges:
            from_id = node_map.get(edge.from_node)
            to_id = node_map.get(edge.to_node)
            
            if from_id and to_id:
                valid_edges.append(edge)
            else:
                # In strict mode, we might want to log this or handle partial edges
                pass
        
        created_edges = await _persist_edges(twin_id, valid_edges, node_map)
        
        return {
            "nodes": created_nodes, 
            "edges": created_edges,
            "confidence": updates.confidence
        }

    except Exception as e:
        logger.error(f"Scribe Engine Error: {e}", exc_info=True)
        # Log to stderr/stdout as well for visibility
        print(f"Scribe Engine Critical Failure: {e}")
        return {"nodes": [], "edges": [], "error": str(e)}


async def _persist_nodes(twin_id: str, nodes: List[NodeUpdate]) -> List[Dict[str, Any]]:
    """Persist nodes using system RPC."""
    results = []
    for node in nodes:
        try:
            # Convert List[Property] back to Dict for JSON storage
            props_dict = {p.key: p.value for p in node.properties}
            
            res = supabase.rpc("create_node_system", {
                "t_id": twin_id,
                "n_name": node.name,
                "n_type": node.type,
                "n_desc": node.description,
                "n_props": props_dict
            }).execute()
            
            if res.data:
                results.append(res.data[0])
                
        except Exception as e:
            logger.error(f"Failed to create node {node.name}: {e}")
            
    return results

async def _persist_edges(twin_id: str, edges: List[EdgeUpdate], node_map: Dict[str, str]) -> List[Dict[str, Any]]:
    """Persist edges using system RPC."""
    results = []
    for edge in edges:
        try:
            from_id = node_map.get(edge.from_node)
            to_id = node_map.get(edge.to_node)
            
            res = supabase.rpc("create_edge_system", {
                "t_id": twin_id,
                "from_id": from_id,
                "to_id": to_id,
                "e_type": edge.type,
                "e_desc": edge.description,
                "e_props": {}
            }).execute()
            
            if res.data:
                results.append(res.data[0])
                
        except Exception as e:
            logger.error(f"Failed to create edge {edge.from_node}->{edge.to_node}: {e}")
            
    return results


# --- Legacy Support ---

def extract_structured_output(text: str, schema: dict) -> dict:
    return {}

def score_confidence(data: dict) -> float:
    return data.get("confidence", 0.0)

def detect_contradictions(new_data: dict, existing_data: dict) -> list:
    return []
