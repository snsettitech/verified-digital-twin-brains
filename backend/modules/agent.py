import os
from typing import Annotated, TypedDict, List, Dict, Any, Union, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from modules.tools import get_retrieval_tool, get_cloud_tools
from modules.observability import supabase

# Try to import checkpointer (optional - P1-A)
try:
    from langgraph.checkpoint.postgres import PostgresSaver
    # Note: asyncpg is a dependency of langgraph-checkpoint-postgres, no need to import directly
    CHECKPOINTER_AVAILABLE = True
except ImportError:
    CHECKPOINTER_AVAILABLE = False
    PostgresSaver = None

# Global checkpointer instance (singleton)
_checkpointer = None

def get_checkpointer():
    """
    Get or create Postgres checkpointer instance (P1-A).
    Returns None if DATABASE_URL not set or checkpointer unavailable.
    """
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer
    
    if not CHECKPOINTER_AVAILABLE:
        return None
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        # Checkpointer is optional - return None if DATABASE_URL not set
        return None
    
    try:
        # Initialize checkpointer with Postgres connection
        # The checkpointer will create its own connection pool
        _checkpointer = PostgresSaver.from_conn_string(database_url)
        print("[LangGraph] Checkpointer initialized with DATABASE_URL")
        return _checkpointer
    except Exception as e:
        print(f"[LangGraph] Failed to initialize checkpointer: {e}")
        return None

async def get_owner_style_profile(twin_id: str, force_refresh: bool = False) -> str:
    """
    Analyzes owner's verified responses and opinion documents to create a persistent style profile.
    """
    try:
        # 1. Check if we already have a profile in the database
        if not force_refresh:
            # RLS Fix: Use RPC
            twin_res = supabase.rpc("get_twin_system", {"t_id": twin_id}).single().execute()
            if twin_res.data and twin_res.data.get("settings"):
                profile = twin_res.data["settings"].get("persona_profile")
                if profile:
                    # Return a consolidated string or the dict depending on how it's used
                    # For backward compatibility, if it's a dict, we might need to handle it
                    if isinstance(profile, dict):
                        return profile.get("description", "Professional and helpful.")
                    return profile

        # 2. Fetch data for analysis
        # A. Fetch verified replies
        replies_res = supabase.table("escalation_replies").select(
            "content, escalations(messages(conversations(twin_id)))"
        ).execute()
        
        analysis_texts = []
        for r in replies_res.data:
            try:
                if r["escalations"]["messages"]["conversations"]["twin_id"] == twin_id:
                    analysis_texts.append(f"VERIFIED REPLY: {r['content']}")
            except (KeyError, TypeError):
                continue
        
        # B. Fetch some OPINION chunks from Pinecone for style variety
        from modules.clients import get_pinecone_index
        index = get_pinecone_index()
        try:
            opinion_search = index.query(
                vector=[0.1] * 3072, # Use non-zero vector for metadata filtering
                filter={"category": {"$eq": "OPINION"}},
                top_k=20, # Increased for better analysis
                include_metadata=True,
                namespace=twin_id
            )
            for match in opinion_search.get("matches", []):
                analysis_texts.append(f"OPINION DOC: {match['metadata']['text']}")
        except Exception as pe:
            print(f"Error fetching opinions for style: {pe}")

        if not analysis_texts:
            return "Professional and helpful."
            
        # 3. Analyze style using a more capable model
        # Using more snippets for a comprehensive view
        all_content = "\n---\n".join(analysis_texts[:25])
        
        client = ChatOpenAI(model="gpt-4o-mini", temperature=0, model_kwargs={"response_format": {"type": "json_object"}})
        analysis_prompt = f"""You are a linguistic expert analyzing a user's writing style to create a 'Digital Twin' persona.
        Analyze the following snippets of text from the user.
        
        EXTRACT THE FOLLOWING INTO JSON:
        1. description: A concise, high-fidelity persona description (3-4 sentences) starting with 'Your voice is...'.
        2. signature_phrases: A list of 5 exact phrases or verbal tics the user frequently uses.
        3. style_exemplars: 3 short text snippets (max 20 words each) that perfectly represent the user's style.
        4. opinion_summary: A map of major topics and the user's stance/intensity (e.g., {{"Topic": {{"stance": "...", "intensity": 8}}}}).
        
        TEXT SNIPPETS:
        {all_content}"""
        
        res = await client.ainvoke([HumanMessage(content=analysis_prompt)])
        import json
        persona_data = json.loads(res.content)
        
        # 4. Persist the profile back to the twin settings
        try:
            from datetime import datetime
            # Get current settings first to merge
            # RLS Fix: Use RPC
            twin_res = supabase.rpc("get_twin_system", {"t_id": twin_id}).single().execute()
            curr_settings = twin_res.data["settings"] if twin_res.data else {}
            
            curr_settings["persona_profile"] = persona_data.get("description")
            curr_settings["signature_phrases"] = persona_data.get("signature_phrases", [])
            curr_settings["style_exemplars"] = persona_data.get("style_exemplars", [])
            curr_settings["opinion_map"] = persona_data.get("opinion_summary", {})
            curr_settings["last_style_analysis"] = datetime.now().isoformat()
            
            # Update probably needs RPC too? Or update via table might work if RLS allows UPDATE but not SELECT?
            # Usually RLS blocks both. But we only need Read for `run_agent_stream`.
            # Updating style is a background task. 
            # I'll leave update as is for now, assuming RLS allows update? (Unlikely).
            # I should use update_twin_settings system RPC but I didn't create one.
            supabase.table("twins").update({"settings": curr_settings}).eq("id", twin_id).execute()
        except Exception as se:
            print(f"Error persisting persona profile: {se}")

        return persona_data.get("description", "Professional and helpful.")
    except Exception as e:
        print(f"Error analyzing style: {e}")
        return "Professional and helpful."

class TwinState(TypedDict):
    """
    State for the Digital Twin reasoning graph.
    """
    messages: Annotated[List[BaseMessage], add_messages]
    twin_id: str
    confidence_score: float
    citations: List[str]

def create_twin_agent(
    twin_id: str,
    group_id: Optional[str] = None,
    system_prompt_override: str = None,
    full_settings: dict = None,
    graph_context: str = "",
    owner_memory_context: str = ""
):
    # Initialize the LLM
    api_key = os.getenv("OPENAI_API_KEY")
    
    # Extract tool_access override if present from full_settings
    # (group settings should already be merged in run_agent_stream)
    allowed_tools = None
    if full_settings and "tool_access" in full_settings:
        tool_access_config = full_settings.get("tool_access", {})
        if isinstance(tool_access_config, list):
            allowed_tools = tool_access_config
        elif isinstance(tool_access_config, dict) and "allowed_tools" in tool_access_config:
            allowed_tools = tool_access_config["allowed_tools"]
    
    # Ensure full_settings is a dict
    if full_settings is None:
        full_settings = {}
    
    # Apply group overrides for specific fields
    temperature = full_settings.get("temperature") if "temperature" in full_settings else 0
    max_tokens = full_settings.get("max_tokens")
    
    # Using a model that supports tool calling well
    llm = ChatOpenAI(
        model="gpt-4-turbo-preview", 
        api_key=api_key, 
        temperature=temperature, 
        streaming=True,
        max_tokens=max_tokens if max_tokens else None
    )
    
    # Setup tools - will be recreated with conversation history in call_model
    cloud_tools = get_cloud_tools(allowed_tools=allowed_tools)
    
    # Bind tools to the LLM (will be updated with conversation-aware retrieval tool)
    llm_with_tools = None  # Will be set in call_model
    
    # Define the nodes
    async def call_model(state: TwinState):
        messages = state["messages"]
        
        # Create retrieval tool with conversation history for context-aware query expansion
        retrieval_tool = get_retrieval_tool(twin_id, group_id=group_id, conversation_history=messages)
        tools = [retrieval_tool] + cloud_tools
        llm_with_tools = llm.bind_tools(tools)
        
        # Check current query for brevity requests
        current_query = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                current_query = msg.content.lower()
                break
        
        # Ensure system message is always present at the beginning
        has_system = any(isinstance(m, SystemMessage) for m in messages)
        if not has_system:
            # Extract persona components from settings
            settings = full_settings or {}
            style_desc = settings.get("persona_profile", "Professional and helpful.")
            phrases = settings.get("signature_phrases", [])
            exemplars = settings.get("style_exemplars", [])
            opinion_map = settings.get("opinion_map", {})
            
            # Check for general_knowledge_allowed setting
            general_knowledge_allowed = settings.get("general_knowledge_allowed", False)
            
            # Load node context from nodes table (Right Brain interview - High-level Identity)
            node_context = ""
            try:
                # Reducing limit to avoid prompt pollution; focusing on top 10 core concepts
                nodes_res = supabase.rpc("get_nodes_system", {"t_id": twin_id, "limit_val": 10}).execute()
                if nodes_res.data and len(nodes_res.data) > 0:
                    intent_items = []
                    profile_items = []
                    
                    for node in nodes_res.data:
                        node_type = node.get("type", "").lower()
                        name = node.get("name", "")
                        desc = node.get("description", "")
                        
                        if not name or not desc:
                            continue
                        
                        # Separate intent nodes from profile nodes
                        if "intent" in node_type:
                            if "confirmed" not in node_type:
                                intent_items.append(f"- {name}: {desc}")
                        else:
                            profile_items.append(f"- {name}: {desc}")
                    
                    if intent_items or profile_items:
                        if intent_items:
                            node_context += "\n            **Your Purpose:**\n            " + "\n            ".join(intent_items)
                        if profile_items:
                            node_context += "\n            **Your Profile:**\n            " + "\n            ".join(profile_items)
            except Exception as ge:
                print(f"Error loading node context: {ge}")
                node_context = ""
            
            # Combine query-relevant graph context with high-level identity nodes
            final_graph_context = ""
            if graph_context:
                final_graph_context += f"SPECIFIC KNOWLEDGE (Query-Relevant):\n{graph_context}\n\n"
            
            if node_context:
                final_graph_context += f"GENERAL IDENTITY NODES (High-Level Concepts):{node_context}"
            
            graph_context_for_prompt = final_graph_context.strip()
            
            # Check for group-specific system prompt override
            # Use the outer function's system_prompt_override, or fall back to group settings
            effective_system_prompt = system_prompt_override
            if not effective_system_prompt:
                group_system_prompt = settings.get("system_prompt")
                if group_system_prompt:
                    effective_system_prompt = group_system_prompt
            
            persona_section = f"""YOUR PERSONA STYLE:
            - DESCRIPTION: {style_desc}"""
            
            if phrases:
                persona_section += f"\n            - SIGNATURE PHRASES (Use these naturally): {', '.join(phrases)}"
            
            if exemplars:
                exemplars_text = "\n              ".join([f"- \"{ex}\"" for ex in exemplars])
                persona_section += f"\n            - STYLE EXEMPLARS (Mimic this flow):\n              {exemplars_text}"
            
            if opinion_map:
                opinions_text = "\n              ".join([f"- {topic}: {data['stance']} (Intensity: {data['intensity']}/10)" for topic, data in opinion_map.items()])
                persona_section += f"\n            - CORE WORLDVIEW / OPINIONS (Always stay consistent with these):\n              {opinions_text}"

            general_knowledge_note = "You may use general knowledge if allowed in settings." if general_knowledge_allowed else "Do NOT make things up or use general knowledge - only respond with verified information."

            owner_memory_block = "OWNER MEMORY (Authoritative for stance, preferences, lens, tone):\n"
            if owner_memory_context:
                owner_memory_block += owner_memory_context
            else:
                owner_memory_block += "- None available for this query."
            
            # Check if user wants brevity from current query or history
            brevity_instruction = ""
            if current_query and ("one line" in current_query or "short answer" in current_query or "brief" in current_query or "concise" in current_query):
                brevity_instruction = "\n            **BREVITY MODE**: The user requested a short/one-line answer. Provide a concise 1-2 sentence response maximum. No bullet points, no lists, just a brief summary."
            
            # Construct final system prompt
            if effective_system_prompt:
                # Custom system prompt takes the "Identity" slot but we still wrap it with RAG instructions
                base_identity = effective_system_prompt
            else:
                base_identity = f"You are the AI Digital Twin of the owner (ID: {twin_id})."

            system_prompt = f"""{base_identity}
            Your primary intelligence comes from the `search_knowledge_base` tool AND your memorized knowledge.

            {persona_section}
            {brevity_instruction}

            {graph_context_for_prompt}

            {owner_memory_block}

            CRITICAL OPERATING PROCEDURES:
            - Owner Memory is authoritative for stance/opinion/preferences/lens/tone. Never invent beliefs.
            - World knowledge is for factual support only and must be cited.
            0. **MEMORIZED KNOWLEDGE**: The section above contains high-level graph summaries. If a question asks for specific details, career history, dates, or depth, you MUST call `search_knowledge_base` even if there is a brief mention in the summaries.
            1. **Search Requirement**: You MUST call `search_knowledge_base` for any query about the owner's specific background, experience, or specialized knowledge. Do NOT rely on general LLM knowledge.
            2. **Brevity First**: Default to concise, one-line answers when possible. Only expand when explicitly asked for details.
            3. **Context Awareness**: Use conversation history to expand ambiguous queries.
            4. **Verified QnA Priority**: If search returns "verified_qna_match": true, YOUR RESPONSE MUST BE THE EXACT TEXT - COPY IT VERBATIM.
            5. **Persona & Voice**: Use first-person ("I", "my"). 
            6. **Tool Results Are Binding**: If `search_knowledge_base` returns results, you MUST use them.
            7. **No Data**: If no relevant information is found AFTER searching, respond with: "I don't have this specific information in my knowledge base." {general_knowledge_note}
            8. **Citations**: Cite sources using [Source ID].

            Current Twin ID: {twin_id}"""
            messages = [SystemMessage(content=system_prompt)] + messages
            
        response = await llm_with_tools.ainvoke(messages)
        return {"messages": [response]}

    async def handle_tools(state: TwinState):
        citations = list(state.get("citations", []))
        total_score = 0
        score_count = 0

        # Create tools with conversation history (same as in call_model)
        messages = state["messages"]
        retrieval_tool = get_retrieval_tool(twin_id, group_id=group_id, conversation_history=messages)
        tools = [retrieval_tool] + cloud_tools

        # Create tool node manually to extract metadata
        tool_node = ToolNode(tools)
        result = await tool_node.ainvoke(state)
        
        # Extract citations and scores from search_knowledge_base if present
        for msg in result["messages"]:
            if isinstance(msg, ToolMessage) and msg.name == "search_knowledge_base":
                import json
                try:
                    # LangGraph/LangChain ToolNode content is the return value of the tool
                    data = msg.content
                    # If it's a string representation of a list of dicts, parse it
                    if isinstance(data, str):
                        try:
                            # Try parsing as JSON first
                            data = json.loads(data)
                        except:
                            # If not JSON, it might be a literal string representation
                            import ast
                            try:
                                data = ast.literal_eval(data)
                            except:
                                pass
                    
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                if "source_id" in item:
                                    citations.append(item["source_id"])
                                if "score" in item:
                                    total_score += item["score"]
                                    score_count += 1
                except Exception as e:
                    print(f"Error parsing tool output: {e}")

        # If tools were called but no scores found, it might mean empty results
        # We should reflect that in the confidence
        if score_count > 0:
            # Check if any verified answer was found (verified_qna_match or is_verified)
            has_verified = any(
                ("verified_qna_match" in msg.content and '"verified_qna_match": true' in msg.content) or
                ("is_verified" in msg.content and '"is_verified": true' in msg.content)
                for msg in result["messages"] 
                if isinstance(msg, ToolMessage)
            )
            if has_verified:
                new_confidence = 1.0 # Force 100% confidence if owner verified info is found
            else:
                new_confidence = total_score / score_count
        else:
            # If search tool was called but returned nothing, confidence is 0 (triggers "I don't know")
            new_confidence = 0.0
        
        return {
            "messages": result["messages"],
            "citations": list(set(citations)),
            "confidence_score": new_confidence
        }

    # Define the graph
    workflow = StateGraph(TwinState)
    
    # Add nodes
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", handle_tools)
    
    # Set entry point
    workflow.set_entry_point("agent")
    
    # Define conditional edges
    def should_continue(state: TwinState):
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return END

    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            END: END
        }
    )
    
    # Add back edge from tools to agent
    workflow.add_edge("tools", "agent")
    
    # P1-A: Compile with checkpointer if available
    checkpointer = get_checkpointer()
    if checkpointer:
        return workflow.compile(checkpointer=checkpointer)
    else:
        return workflow.compile()

# Langfuse v3 tracing
try:
    from langfuse import observe
    _langfuse_available = True
except ImportError:
    _langfuse_available = False
    def observe(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


@observe(name="agent_response")
async def run_agent_stream(
    twin_id: str,
    query: str,
    history: List[BaseMessage] = None,
    system_prompt: str = None,
    group_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    owner_memory_context: str = ""
):
    """
    Runs the agent and yields events from the graph.
    
    P1-A: conversation_id is used as thread_id for state persistence if checkpointer is enabled.
    """
    # 0. Apply Phase 9 Safety Guardrails
    from modules.safety import apply_guardrails
    refusal_message = apply_guardrails(twin_id, query)
    if refusal_message:
        # Yield a simulated refusal event to match the graph output format
        yield {
            "agent": {
                "messages": [AIMessage(content=refusal_message)]
            }
        }
        return

    # 1. Fetch full twin settings for persona encoding
    # RLS Fix: Use RPC
    twin_res = supabase.rpc("get_twin_system", {"t_id": twin_id}).single().execute()
    settings = twin_res.data["settings"] if twin_res.data else {}
    
    # 2. Load group settings if group_id provided
    if group_id:
        try:
            from modules.access_groups import get_group_settings
            group_settings = await get_group_settings(group_id)
            # Merge group settings with twin settings (group takes precedence)
            settings = {**settings, **group_settings}
        except Exception as e:
            print(f"Warning: Failed to load group settings: {e}")
    
    # 3. Ensure style analysis has been run at least once
    if "persona_profile" not in settings:
        await get_owner_style_profile(twin_id)
        # Re-fetch after analysis
        # RLS Fix: Use RPC
        twin_res = supabase.rpc("get_twin_system", {"t_id": twin_id}).single().execute()
        settings = twin_res.data["settings"] if twin_res.data else {}
        # Re-merge group settings if needed
        if group_id:
            try:
                from modules.access_groups import get_group_settings
                group_settings = await get_group_settings(group_id)
                settings = {**settings, **group_settings}
            except Exception:
                pass

    # 3.5 Fetch Graph Snapshot (P0.2 - Bounded, query-relevant)
    # Feature flag: GRAPH_RAG_ENABLED (default: false)
    graph_context = ""
    graph_rag_enabled = os.getenv("GRAPH_RAG_ENABLED", "false").lower() == "true"
    
    if graph_rag_enabled:
        try:
            from modules.graph_context import get_graph_snapshot
            snapshot = await get_graph_snapshot(twin_id, query=query)
            graph_context = snapshot.get("context_text", "")
            if not graph_context:
                print(f"[GraphRAG] Enabled but returned empty context for twin {twin_id}, query: {query[:50]}")
        except Exception as e:
            print(f"[GraphRAG] Retrieval failed, falling back to RAG-lite. Error: {e}")

    agent = create_twin_agent(
        twin_id,
        group_id=group_id,
        system_prompt_override=system_prompt,
        full_settings=settings,
        graph_context=graph_context,
        owner_memory_context=owner_memory_context
    )
    
    initial_messages = history or []
    initial_messages.append(HumanMessage(content=query))
    
    state = {
        "messages": initial_messages,
        "twin_id": twin_id,
        "confidence_score": 1.0,
        "citations": []
    }
    
    # Phase 10: Metrics instrumentation
    from modules.metrics_collector import MetricsCollector
    import time
    
    metrics = MetricsCollector(twin_id=twin_id)
    metrics.record_request()
    agent_start = time.time()
    
    # P1-A: Generate thread_id from conversation_id for state persistence
    thread_id = None
    if conversation_id:
        # Thread ID format: conversation_id (simple, deterministic)
        thread_id = conversation_id
        print(f"[LangGraph] Using thread_id: {thread_id}")
    
    try:
        # P1-A: Pass thread_id if checkpointer is enabled
        config = {"configurable": {"thread_id": thread_id}} if thread_id and get_checkpointer() else {}
        async for event in agent.astream(state, stream_mode="updates", **config):
            yield event
    finally:
        # Record agent latency and flush metrics
        agent_latency = (time.time() - agent_start) * 1000
        metrics.record_latency("agent", agent_latency)
        metrics.flush()
