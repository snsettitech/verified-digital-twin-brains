from langchain.tools import tool
from modules.retrieval import retrieve_context
from typing import List, Dict, Any, Optional
import os
import re
import inspect

def get_retrieval_tool(
    twin_id: str,
    group_id: Optional[str] = None,
    conversation_history: list = None,
    resolve_default_group: bool = True,
):
    """
    Creates a tool for retrieving context from the digital twin's knowledge base.
    If group_id is provided, filters results by group permissions.
    If conversation_history is provided, uses it to expand ambiguous queries.
    """
    # Capture conversation_history in closure
    history = conversation_history or []
    
    @tool
    async def search_knowledge_base(query: str) -> str:
        """
        Searches the digital twin's knowledge base for information relevant to the query.
        This tool checks verified QnA entries first (highest priority), then vector search.
        If a verified QnA match is found (verified_qna_match: true), use it exactly as provided.
        Use this tool when you need information from documents uploaded by the owner.
        
        CRITICAL: If the query is ambiguous or vague (e.g., "reflection", "that document", "the summary above"),
        you MUST expand it using conversation history. Look at previous messages to find specific keywords.
        For example:
        - "reflection" → "M&A reflection SGMT 6050" (if previous messages mentioned M&A or SGMT 6050)
        - "that document" → Use keywords from the document that was just discussed
        - "the summary above" → Use keywords from the summary that was just provided
        
        ALWAYS expand vague queries before searching. Never search for generic terms like "reflection" alone
        if the conversation context suggests a specific document (e.g., "M&A reflection").
        
        Returns a JSON string containing the relevant context snippets with metadata.
        """
        import json
        def _normalize(value):
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
        
        # Auto-expand ambiguous queries using conversation history
        expanded_query = query
        if history and len(history) > 0:
            # Extract keywords from recent conversation (last 10 messages for better context)
            recent_context = []
            for msg in history[-10:]:
                if hasattr(msg, 'content') and msg.content:
                    content = str(msg.content)
                    # Skip system messages and very short messages
                    if len(content) > 10:
                        recent_context.append(content)
            
            if recent_context:
                # If query is too generic (single word, common terms), try to expand it
                generic_terms = ['reflection', 'document', 'summary', 'that', 'this', 'it', 'above', 'below', 'deal']
                query_lower = query.lower().strip()
                
                if query_lower in generic_terms or len(query.split()) <= 2:
                    # Look for specific keywords in conversation history
                    context_text = " ".join(recent_context).lower()
                    
                    # Common patterns to extract - build expanded query progressively
                    expanded_parts = [query]
                    
                    # Check for M&A related terms
                    if any(term in context_text for term in ['m&a', 'mergers', 'acquisitions', 'merger', 'acquisition']):
                        if 'm&a' not in query_lower and 'merger' not in query_lower and 'acquisition' not in query_lower:
                            expanded_parts.insert(0, "M&A")
                    
                    # Check for SGMT 6050
                    if any(term in context_text for term in ['sGMT', '6050', 'sGMT 6050']):
                        if '6050' not in query_lower and 'sGMT' not in query_lower:
                            expanded_parts.append("SGMT 6050")
                    
                    # Check for reflection specifically
                    if 'reflection' in context_text and query_lower == 'reflection':
                        # Make sure we include M&A if it was mentioned
                        if any(term in context_text for term in ['m&a', 'mergers', 'acquisitions']):
                            expanded_query = "M&A reflection SGMT 6050"
                        else:
                            expanded_query = " ".join(expanded_parts)
                    else:
                        expanded_query = " ".join(expanded_parts)
        
        # Vector search (Pinecone)
        retrieval_kwargs = {"group_id": group_id}
        try:
            sig = inspect.signature(retrieve_context)
            if "resolve_default_group" in sig.parameters:
                retrieval_kwargs["resolve_default_group"] = resolve_default_group
        except (TypeError, ValueError):
            # Fallback for mocked/non-inspectable callables used in tests.
            pass

        contexts = await retrieve_context(
            expanded_query,
            twin_id,
            **retrieval_kwargs,
        )
        
        # Graph fallback (optional): disabled by default to avoid broad, low-precision matches.
        graph_results = []
        graph_fallback_enabled = os.getenv("ENABLE_GRAPH_RETRIEVAL_FALLBACK", "false").lower() == "true"
        if graph_fallback_enabled and not contexts:
            try:
                from modules.observability import supabase

                stop_words = {
                    "the", "and", "for", "with", "that", "this", "from", "have", "what", "when",
                    "where", "which", "who", "whom", "know", "does", "your", "about", "into",
                    "just", "like", "they", "them", "their", "would", "could", "should", "you",
                    "are", "was", "were", "has", "had", "can", "did", "not"
                }
                query_terms = [
                    term for term in re.findall(r"[a-z0-9]{4,}", expanded_query.lower())
                    if term not in stop_words
                ]

                if query_terms:
                    nodes_res = supabase.rpc("get_nodes_system", {"t_id": twin_id, "limit_val": 20}).execute()
                    for node in (nodes_res.data or []):
                        name = (node.get("name") or "")
                        desc = (node.get("description") or "")
                        haystack = f"{name} {desc}".lower()
                        matched_terms = [
                            term for term in query_terms
                            if re.search(rf"\\b{re.escape(term)}\\b", haystack)
                        ]
                        if not matched_terms:
                            continue

                        score = min(0.9, 0.65 + (0.1 * len(matched_terms)))
                        graph_results.append({
                            "text": f"{name}: {desc}",
                            "source_id": f"graph-{str(node.get('id', ''))[:8]}",
                            "score": score,
                            "is_graph": True,
                            "category": node.get("type", "KNOWLEDGE"),
                            "matched_terms": matched_terms,
                        })
            except Exception as e:
                print(f"Graph search error: {e}")

        # Keep source-grounded vector retrieval as primary. Graph fallback is additive only when enabled.
        all_results = contexts + graph_results
        return json.dumps(_normalize(all_results))
    
    return search_knowledge_base

def get_cloud_tools(allowed_tools: Optional[List[str]] = None):
    """
    Returns a list of cloud-based tools (e.g., Gmail, Slack) via Composio or fallback tools.
    If allowed_tools is provided, only returns tools whose names are in that list.
    """
    tools = []
    
    # 1. Try to load Composio tools if API key is present
    if os.getenv("COMPOSIO_API_KEY"):
        try:
            from composio_langchain import ComposioToolSet, App
            toolset = ComposioToolSet()
            # Default to some useful apps if configured
            # tools.extend(toolset.get_tools(apps=[App.GMAIL, App.SLACK]))
            pass
        except ImportError:
            print("Composio not installed, skipping cloud tools.")

    # 2. Add fallback/utility tools if allowed
    # Note: In a production "Verified" brain, we might want to restrict external search
    # unless explicitly allowed in twin settings.
    try:
        from langchain_community.tools import DuckDuckGoSearchRun
        # Only add if specifically enabled in env or for certain twins
        if os.getenv("ENABLE_WEB_SEARCH") == "true":
            tools.append(DuckDuckGoSearchRun())
    except ImportError:
        pass
    
    # Filter tools by allowed_tools if provided
    if allowed_tools is not None:
        filtered_tools = []
        for tool in tools:
            tool_name = getattr(tool, "name", None) or str(tool)
            if tool_name in allowed_tools or any(allowed in tool_name for allowed in allowed_tools):
                filtered_tools.append(tool)
        tools = filtered_tools

    return tools

