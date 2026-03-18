"""
Pinecone knowledge base search tool.

Replaces the LangChain @tool-decorated search_knowledge_base function
with a plain async function. Same logic, no framework dependency.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional


def _normalize(value):
    """Recursively normalize numpy/exotic types to JSON-serializable Python types."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items()}
    return str(value)


async def search_knowledge_base(
    query: str,
    twin_id: str,
    group_id: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, Any]]] = None,
    resolve_default_group: bool = True,
) -> str:
    """
    Search the digital twin's knowledge base.

    Returns a JSON string of context snippets with metadata.
    Checks verified QnA first, then vector search, with optional
    graph fallback.
    """
    from modules.retrieval import retrieve_context_with_intent

    history = conversation_history or []

    # Auto-expand ambiguous queries using conversation history
    expanded_query = _expand_ambiguous_query(query, history)

    # Convert history to dict format for intent classification
    history_dicts = []
    for msg in history[-5:]:
        if isinstance(msg, dict) and msg.get("content"):
            role = msg.get("role", "user")
            history_dicts.append({"role": role, "content": str(msg["content"])})

    # Intent-aware retrieval
    retrieval_result = await retrieve_context_with_intent(
        query=expanded_query,
        twin_id=twin_id,
        group_id=group_id,
        conversation_history=history_dicts,
        resolve_default_group=resolve_default_group,
    )

    contexts = retrieval_result.get("contexts", [])

    intent = retrieval_result.get("intent")
    if intent:
        print(f"[ADK Tool] Intent: {intent.intent_type.value}, contexts: {len(contexts)}")

    # Graph fallback (optional)
    graph_results = []
    if os.getenv("ENABLE_GRAPH_RETRIEVAL_FALLBACK", "false").lower() == "true" and not contexts:
        graph_results = _graph_fallback_search(expanded_query, twin_id)

    all_results = contexts + graph_results
    return json.dumps(_normalize(all_results))


def _expand_ambiguous_query(
    query: str,
    history: List[Dict[str, Any]],
) -> str:
    """Expand vague queries using conversation history."""
    if not history:
        return query

    recent_context = []
    for msg in history[-10:]:
        content = ""
        if isinstance(msg, dict):
            content = str(msg.get("content", ""))
        if len(content) > 10:
            recent_context.append(content)

    if not recent_context:
        return query

    generic_terms = {
        "reflection", "document", "summary", "that", "this",
        "it", "above", "below", "deal",
    }
    query_lower = query.lower().strip()

    if query_lower not in generic_terms and len(query.split()) > 2:
        return query

    context_text = " ".join(recent_context).lower()
    expanded_parts = [query]

    if any(t in context_text for t in ["m&a", "mergers", "acquisitions", "merger", "acquisition"]):
        if "m&a" not in query_lower and "merger" not in query_lower:
            expanded_parts.insert(0, "M&A")

    if any(t in context_text for t in ["sgmt", "6050"]):
        if "6050" not in query_lower and "sgmt" not in query_lower:
            expanded_parts.append("SGMT 6050")

    if "reflection" in context_text and query_lower == "reflection":
        if any(t in context_text for t in ["m&a", "mergers", "acquisitions"]):
            return "M&A reflection SGMT 6050"

    return " ".join(expanded_parts)


def _graph_fallback_search(query: str, twin_id: str) -> List[Dict[str, Any]]:
    """Optional graph-based fallback when vector search returns nothing."""
    try:
        from modules.observability import supabase

        stop_words = {
            "the", "and", "for", "with", "that", "this", "from", "have",
            "what", "when", "where", "which", "who", "whom", "know",
            "does", "your", "about", "into", "just", "like", "they",
            "them", "their", "would", "could", "should", "you", "are",
            "was", "were", "has", "had", "can", "did", "not",
        }
        query_terms = [
            t for t in re.findall(r"[a-z0-9]{4,}", query.lower())
            if t not in stop_words
        ]
        if not query_terms:
            return []

        nodes_res = supabase.rpc("get_nodes_system", {"t_id": twin_id, "limit_val": 20}).execute()
        results = []
        for node in (nodes_res.data or []):
            name = node.get("name") or ""
            desc = node.get("description") or ""
            haystack = f"{name} {desc}".lower()
            matched = [t for t in query_terms if re.search(rf"\\b{re.escape(t)}\\b", haystack)]
            if not matched:
                continue
            results.append({
                "text": f"{name}: {desc}",
                "source_id": f"graph-{str(node.get('id', ''))[:8]}",
                "score": min(0.9, 0.65 + 0.1 * len(matched)),
                "is_graph": True,
                "category": node.get("type", "KNOWLEDGE"),
                "matched_terms": matched,
            })
        return results
    except Exception as e:
        print(f"Graph search error: {e}")
        return []
