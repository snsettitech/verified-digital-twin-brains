import os
from typing import Annotated, TypedDict, List, Dict, Any, Union, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from modules.tools import get_retrieval_tool, get_cloud_tools
from modules.observability import supabase

async def get_owner_style_profile(twin_id: str, force_refresh: bool = False) -> str:
    """
    Analyzes owner's verified responses and opinion documents to create a persistent style profile.
    """
    try:
        # 1. Check if we already have a profile in the database
        if not force_refresh:
            twin_res = supabase.table("twins").select("settings").eq("id", twin_id).single().execute()
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
            twin_res = supabase.table("twins").select("settings").eq("id", twin_id).single().execute()
            curr_settings = twin_res.data["settings"] if twin_res.data else {}
            
            curr_settings["persona_profile"] = persona_data.get("description")
            curr_settings["signature_phrases"] = persona_data.get("signature_phrases", [])
            curr_settings["style_exemplars"] = persona_data.get("style_exemplars", [])
            curr_settings["opinion_map"] = persona_data.get("opinion_summary", {})
            curr_settings["last_style_analysis"] = datetime.now().isoformat()
            
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

def create_twin_agent(twin_id: str, group_id: Optional[str] = None, system_prompt_override: str = None, full_settings: dict = None):
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
            
            # Check if user wants brevity from current query or history
            brevity_instruction = ""
            if current_query and ("one line" in current_query or "short answer" in current_query or "brief" in current_query or "concise" in current_query):
                brevity_instruction = "\n            **BREVITY MODE**: The user requested a short/one-line answer. Provide a concise 1-2 sentence response maximum. No bullet points, no lists, just a brief summary."
            
            system_prompt = effective_system_prompt or f"""You are the AI Digital Twin of the owner (ID: {twin_id}). 
            Your primary intelligence comes from the `search_knowledge_base` tool.

            {persona_section}
            {brevity_instruction}

            CRITICAL OPERATING PROCEDURES:
            0. **Brevity First**: Default to concise, one-line answers when possible. Only expand when explicitly asked for details. If the user asks for "one line", "short answer", "brief", or "concise", provide exactly that - a single sentence or maximum 2 sentences.
            1. **Context Awareness**: If the user's query is ambiguous (e.g., "the reflection", "that document", "the summary above"), use conversation history to understand what they're referring to. Look at previous messages to identify the specific topic (e.g., "M&A reflection", "SGMT 6050", etc.) and include those keywords in your search query.
            2. Factual Questions: For ANY question about facts, opinions, history, or documents, you MUST FIRST call `search_knowledge_base`. When queries are ambiguous, expand them using context from the conversation (e.g., "reflection" → "M&A reflection SGMT 6050" if that was discussed).
            3. Verified QnA Priority: If search returns ANY result with "verified_qna_match": true or "is_verified": true, this is a verified answer from the owner. YOUR RESPONSE MUST BE THE EXACT TEXT FROM THE "text" FIELD - COPY IT VERBATIM. Do not paraphrase, modify, add to, or rephrase it in any way. Just return the exact "text" value as your complete response.
            4. Verified Info: If search returns "is_verified": true, copy the exact "text" field value as your response. No modifications allowed.
            5. Persona & Voice:
               - Sources have a 'category' (FACT or OPINION), a 'tone', and potentially an 'opinion_topic' and 'opinion_stance'.
               - If a source is an 'OPINION', use first-person framing like 'In my view' or 'I personally believe'.
               - If an 'opinion_stance' is provided for an 'OPINION', strictly adhere to that stance.
               - If a source is a 'FACT', state it directly as objective information.
               - Adopt the 'tone' (e.g., Thoughtful, Assertive) found in the relevant source to match the owner's style.
            6. No Data: If the tool returns no relevant information OR returns empty results with weak retrieval scores (< 0.5), you MUST respond with: "I don't have this specific information in my knowledge base." {general_knowledge_note}
            7. Citations: Always cite your sources using [Source ID] when using tool results. For verified QnA, use the citations provided.
            8. Personal Identity: Speak in the first person ("I", "my") as if you are the owner, but grounded in the verified data.
            9. ALWAYS SEARCH: Always call search_knowledge_base first, even for simple greetings. If a verified answer exists, use it exactly. When queries are vague, use conversation context to make them more specific before searching.

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
    
    # Compile the graph
    return workflow.compile()

async def run_agent_stream(twin_id: str, query: str, history: List[BaseMessage] = None, system_prompt: str = None, group_id: Optional[str] = None):
    """
    Runs the agent and yields events from the graph.
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
    twin_res = supabase.table("twins").select("settings").eq("id", twin_id).single().execute()
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
        twin_res = supabase.table("twins").select("settings").eq("id", twin_id).single().execute()
        settings = twin_res.data["settings"] if twin_res.data else {}
        # Re-merge group settings if needed
        if group_id:
            try:
                from modules.access_groups import get_group_settings
                group_settings = await get_group_settings(group_id)
                settings = {**settings, **group_settings}
            except Exception:
                pass

    agent = create_twin_agent(twin_id, group_id=group_id, system_prompt_override=system_prompt, full_settings=settings)
    
    initial_messages = history or []
    initial_messages.append(HumanMessage(content=query))
    
    state = {
        "messages": initial_messages,
        "twin_id": twin_id,
        "confidence_score": 1.0, # Start with high confidence (e.g. for greetings)
        "citations": []
    }
    
    # We use astream to get events
    async for event in agent.astream(state, stream_mode="updates"):
        yield event

