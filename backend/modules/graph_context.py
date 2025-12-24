"""
Graph Context Module

Provides utilities for fetching cognitive graph data for chat context
and UI display.
"""

from typing import Dict, Any, List, Optional
from modules.observability import supabase


def get_graph_stats(twin_id: str) -> Dict[str, Any]:
    """
    Get summary statistics about a twin's cognitive graph.
    Returns node count and top nodes for UI display.
    """
    try:
        # Fetch nodes via RPC
        nodes_res = supabase.rpc("get_nodes_system", {
            "t_id": twin_id,
            "limit_val": 50
        }).execute()
        
        nodes = nodes_res.data if nodes_res.data else []
        
        # Categorize nodes
        intent_nodes = []
        profile_nodes = []
        
        for node in nodes:
            node_type = node.get("type", "").lower()
            name = node.get("name", "")
            description = node.get("description", "")
            
            if not name:
                continue
            
            node_summary = {
                "name": name,
                "type": node.get("type", ""),
                "description": description[:100] + "..." if len(description) > 100 else description
            }
            
            if "intent" in node_type:
                intent_nodes.append(node_summary)
            else:
                profile_nodes.append(node_summary)
        
        # Get top nodes for display (max 5 each category)
        top_nodes = intent_nodes[:3] + profile_nodes[:5]
        
        return {
            "node_count": len(nodes),
            "has_graph": len(nodes) > 0,
            "intent_count": len(intent_nodes),
            "profile_count": len(profile_nodes),
            "top_nodes": top_nodes
        }
    except Exception as e:
        print(f"Error fetching graph stats: {e}")
        return {
            "node_count": 0,
            "has_graph": False,
            "intent_count": 0,
            "profile_count": 0,
            "top_nodes": []
        }


def get_graph_context_for_chat(twin_id: str, limit: int = 20) -> Dict[str, Any]:
    """
    Get graph context formatted for chat injection.
    Returns both the text context and metadata.
    """
    try:
        nodes_res = supabase.rpc("get_nodes_system", {
            "t_id": twin_id,
            "limit_val": limit
        }).execute()
        
        nodes = nodes_res.data if nodes_res.data else []
        
        if not nodes:
            return {
                "context_text": "",
                "node_count": 0,
                "nodes_used": []
            }
        
        # Build context string
        node_summaries = []
        nodes_used = []
        
        for n in nodes:
            name = n.get("name", "")
            node_type = n.get("type", "")
            description = n.get("description", "")
            props = n.get("properties", {}) or {}
            
            if not name or not description:
                continue
            
            # Format properties
            props_str = ""
            if props:
                props_items = [f"{k}: {v}" for k, v in props.items() 
                              if isinstance(v, (str, int, float))]
                if props_items:
                    props_str = f" [{', '.join(props_items[:3])}]"
            
            node_summaries.append(f"- {name} ({node_type}): {description}{props_str}")
            nodes_used.append({
                "name": name,
                "type": node_type
            })
        
        context_text = ""
        if node_summaries:
            context_text = "MEMORIZED KNOWLEDGE (High Priority - Answer from here if relevant):\n" + "\n".join(node_summaries)
        
        return {
            "context_text": context_text,
            "node_count": len(nodes_used),
            "nodes_used": nodes_used
        }
    except Exception as e:
        print(f"Error fetching graph context: {e}")
        return {
            "context_text": "",
            "node_count": 0,
            "nodes_used": []
        }
