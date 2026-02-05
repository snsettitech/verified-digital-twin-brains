from langchain.tools import tool
from modules.retrieval import retrieve_context
from typing import List, Dict, Any, Optional
import os

def get_retrieval_tool(twin_id: str, group_id: Optional[str] = None, conversation_history: list = None):
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
        contexts = await retrieve_context(expanded_query, twin_id, group_id=group_id)
        
        # Graph search (Supabase nodes table)
        graph_results = []
        try:
            from modules.observability import supabase
            nodes_res = supabase.rpc("get_nodes_system", {"t_id": twin_id, "limit_val": 20}).execute()
            if nodes_res.data:
                query_words = set(expanded_query.lower().split())
                for node in nodes_res.data:
                    name = (node.get("name") or "").lower()
                    desc = (node.get("description") or "").lower()
                    # Check if any query word matches node name or description
                    if any(word in name or word in desc for word in query_words if len(word) > 2):
                        graph_results.append({
                            "text": f"{node['name']}: {node['description']}",
                            "source_id": f"graph-{node['id'][:8]}",
                            "score": 0.85,  # High confidence for graph knowledge
                            "is_graph": True,
                            "category": node.get("type", "KNOWLEDGE")
                        })
        except Exception as e:
            print(f"Graph search error: {e}")
        
        # Merge: Graph results first (higher priority), then vector results
        all_results = graph_results + contexts
        return json.dumps(all_results)
    
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

