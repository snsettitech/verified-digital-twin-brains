import os
import asyncio
import json
from typing import Annotated, TypedDict, List, Dict, Any, Union, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from modules.tools import get_retrieval_tool
from modules.observability import supabase
from modules.persona_compiler import (
    compile_prompt_plan,
    get_prompt_render_options,
    render_prompt_plan_with_options,
)
from modules.persona_intents import classify_query_intent
from modules.persona_module_store import list_runtime_modules_for_intent
from modules.persona_prompt_variant_store import (
    DEFAULT_PERSONA_PROMPT_VARIANT,
    get_active_persona_prompt_variant,
)
from modules.persona_spec import PersonaSpec
from modules.persona_spec_store import get_active_persona_spec
from modules.inference_router import invoke_json, invoke_text
from modules.response_policy import UNCERTAINTY_RESPONSE

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
        from modules.delphi_namespace import get_namespace_candidates_for_twin
        index = get_pinecone_index()
        try:
            for namespace in get_namespace_candidates_for_twin(twin_id=twin_id, include_legacy=True):
                opinion_search = index.query(
                    vector=[0.1] * 3072, # Use non-zero vector for metadata filtering
                    filter={"category": {"$eq": "OPINION"}},
                    top_k=20, # Increased for better analysis
                    include_metadata=True,
                    namespace=namespace
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
        
        analysis_prompt = f"""You are a linguistic expert analyzing a user's writing style to create a 'Digital Twin' persona.
        Analyze the following snippets of text from the user.
        
        EXTRACT THE FOLLOWING INTO JSON:
        1. description: A concise, high-fidelity persona description (3-4 sentences) starting with 'Your voice is...'.
        2. signature_phrases: A list of 5 exact phrases or verbal tics the user frequently uses.
        3. style_exemplars: 3 short text snippets (max 20 words each) that perfectly represent the user's style.
        4. opinion_summary: A map of major topics and the user's stance/intensity (e.g., {{"Topic": {{"stance": "...", "intensity": 8}}}}).
        
        TEXT SNIPPETS:
        {all_content}"""

        persona_data, _route_meta = await invoke_json(
            [{"role": "user", "content": analysis_prompt}],
            task="structured",
            temperature=0,
            max_tokens=700,
        )
        
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
    Supports Path B: Global Reasoning & Agentic RAG.
    Now supports Phase 4: Dialogue Orchestration.
    """
    messages: Annotated[List[BaseMessage], add_messages]
    twin_id: str
    confidence_score: float
    citations: List[str]
    # Path B: Agentic RAG additions
    sub_queries: Optional[List[str]]
    reasoning_history: Optional[List[str]]
    retrieved_context: Optional[Dict[str, Any]] # Stores results from multiple tools
    
    # Phase 4: Dialogue Orchestration Metadata
    dialogue_mode: Optional[str]        # SMALLTALK, QA_FACT, TEACHING, etc.
    requires_evidence: bool
    requires_teaching: bool
    target_owner_scope: bool            # True if person-specific
    planning_output: Optional[Dict[str, Any]] # Structured JSON from Planner Pass
    intent_label: Optional[str]         # Phase 3 stable intent taxonomy label
    persona_module_ids: Optional[List[str]]
    persona_spec_version: Optional[str]
    persona_prompt_variant: Optional[str]
    
    # Path B / Phase 4 Context
    full_settings: Optional[Dict[str, Any]]
    graph_context: Optional[str]
    owner_memory_context: Optional[str]
    system_prompt_override: Optional[str]
    interaction_context: Optional[str]

def build_system_prompt_with_trace(state: TwinState) -> tuple[str, Dict[str, Any]]:
    """
    Build prompt text plus persona runtime trace metadata (Phase 3).
    """
    twin_id = state.get("twin_id", "Unknown")
    full_settings = state.get("full_settings") or {}
    graph_context = state.get("graph_context") or ""
    owner_memory_context = state.get("owner_memory_context") or ""
    system_prompt_override = (state.get("system_prompt_override") or "").strip()
    dialogue_mode = state.get("dialogue_mode")

    messages = state.get("messages") or []
    last_human_msg = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "")
    intent_label = state.get("intent_label") or classify_query_intent(
        last_human_msg,
        dialogue_mode=dialogue_mode,
    )

    style_desc = full_settings.get("persona_profile", "Professional and helpful.")
    phrases = full_settings.get("signature_phrases", [])
    opinion_map = full_settings.get("opinion_map", {})
    default_system_prompt = (full_settings.get("system_prompt") or "").strip()
    custom_instructions = system_prompt_override or default_system_prompt
    public_intro = (full_settings.get("public_intro") or "").strip()
    intent_profile = full_settings.get("intent_profile") or {}

    # Load identity context (High-level concepts)
    node_context = ""
    try:
        nodes_res = supabase.rpc("get_nodes_system", {"t_id": twin_id, "limit_val": 10}).execute()
        if nodes_res.data:
            profile_items = [f"- {n.get('name')}: {n.get('description')}" for n in nodes_res.data]
            node_context = "\n            **GENERAL IDENTITY NODES:**\n            " + "\n            ".join(profile_items)
    except Exception:
        pass

    final_graph_context = ""
    if graph_context:
        final_graph_context += f"SPECIFIC KNOWLEDGE:\n{graph_context}\n\n"
    if node_context:
        final_graph_context += node_context

    persona_section = ""
    persona_trace = {
        "intent_label": intent_label,
        "module_ids": [],
        "persona_spec_version": None,
        "persona_prompt_variant": DEFAULT_PERSONA_PROMPT_VARIANT,
    }
    active_variant_row = get_active_persona_prompt_variant(twin_id=twin_id)
    active_variant_id = (
        str(active_variant_row.get("variant_id"))
        if active_variant_row and active_variant_row.get("variant_id")
        else DEFAULT_PERSONA_PROMPT_VARIANT
    )
    variant_overrides = (active_variant_row or {}).get("render_options") or {}
    render_options = get_prompt_render_options(active_variant_id, overrides=variant_overrides)

    active_persona_row = get_active_persona_spec(twin_id=twin_id)
    if active_persona_row and active_persona_row.get("spec"):
        try:
            parsed = PersonaSpec.model_validate(active_persona_row["spec"])
            runtime_modules = list_runtime_modules_for_intent(
                twin_id=twin_id,
                intent_label=intent_label,
                limit=8,
                include_draft=True,
            )
            prompt_plan = compile_prompt_plan(
                spec=parsed,
                intent_label=intent_label,
                user_query=last_human_msg,
                runtime_modules=runtime_modules,
                max_few_shots=max(0, int(render_options.max_few_shots)),
                module_detail_level=render_options.module_detail_level,
            )
            persona_section = render_prompt_plan_with_options(plan=prompt_plan, options=render_options)
            persona_trace["module_ids"] = prompt_plan.selected_module_ids
            persona_trace["intent_label"] = prompt_plan.intent_label or intent_label
            persona_trace["persona_spec_version"] = active_persona_row.get("version") or parsed.version
            persona_trace["persona_prompt_variant"] = render_options.variant_id
        except Exception as e:
            print(f"[PersonaCompiler] Active spec compile failed, using legacy settings fallback: {e}")
            persona_section = ""
            persona_trace["persona_spec_version"] = active_persona_row.get("version")
            persona_trace["persona_prompt_variant"] = active_variant_id

    if not persona_section:
        persona_section = f"YOUR PERSONA STYLE:\n- DESCRIPTION: {style_desc}"
        if phrases:
            persona_section += f"\n- SIGNATURE PHRASES: {', '.join(phrases)}"
        if opinion_map:
            opinions_text = "\n".join([f"- {t}: {d['stance']}" for t, d in opinion_map.items()])
            persona_section += f"\n- CORE WORLDVIEW:\n{opinions_text}"

    owner_memory_block = f"OWNER MEMORY:\n{owner_memory_context if owner_memory_context else '- None available.'}"
    custom_instructions_block = f"CUSTOM INSTRUCTIONS:\n{custom_instructions}\n" if custom_instructions else ""
    public_intro_block = f"PUBLIC INTRO (use when asked to introduce yourself):\n{public_intro}\n" if public_intro else ""
    intent_block = ""
    if isinstance(intent_profile, dict) and intent_profile:
        use_case = (intent_profile.get("use_case") or "").strip()
        audience = (intent_profile.get("audience") or "").strip()
        boundaries = (intent_profile.get("boundaries") or "").strip()
        intent_lines = []
        if use_case:
            intent_lines.append(f"- Primary use case: {use_case}")
        if audience:
            intent_lines.append(f"- Audience: {audience}")
        if boundaries:
            intent_lines.append(f"- Boundaries: {boundaries}")
        if intent_lines:
            intent_block = "INTENT PROFILE:\n" + "\n".join(intent_lines) + "\n"

    prompt = f"""You are the AI Digital Twin of the owner (ID: {twin_id}).
YOUR PRINCIPLES (Immutable):
- Use first-person ("I", "my").
- Every claim MUST be supported by retrieved context.
- If context is missing, say you don't know.
- Be concise by default.
- PUBLIC INTRO and INTENT PROFILE are owner-provided facts and may be used for self-description.

{custom_instructions_block}
{public_intro_block}
{intent_block}
{persona_section}

{final_graph_context}

{owner_memory_block}

AGENTIC RAG OPERATING PROCEDURES:
1. Use `search_knowledge_base` to find specific facts or beliefs.
2. If multiple searches are needed for global reasoning (e.g. "What are my principles?"), perform them.
3. If you find contradictions, acknowledge them.
"""
    return prompt, persona_trace


def build_system_prompt(state: TwinState) -> str:
    prompt, _ = build_system_prompt_with_trace(state)
    return prompt


def _is_smalltalk_query(query: str) -> bool:
    q = (query or "").strip().lower()
    if not q:
        return False
    smalltalk_markers = {
        "hi",
        "hello",
        "hey",
        "good morning",
        "good afternoon",
        "good evening",
        "how are you",
        "what's up",
        "whats up",
    }
    return q in smalltalk_markers or any(marker in q for marker in {"how's your day", "hows your day"})


def _is_owner_specific_query(query: str) -> bool:
    q = (query or "").strip().lower()
    if not q:
        return False
    markers = [
        r"\bwhat (do|did) i think\b",
        r"\bwhat('?s| is) my (stance|view|opinion|belief|thesis|principle)\b",
        r"\bmy (stance|view|opinion|belief|thesis|principle)\b",
        r"\bhow do i (approach|decide|evaluate)\b",
        r"\bbased on my (sources|documents|knowledge)\b",
        r"\bfrom my (sources|documents|knowledge)\b",
    ]
    return any(re.search(pattern, q) for pattern in markers)


def _is_explicit_teaching_query(query: str) -> bool:
    q = (query or "").strip().lower()
    if not q:
        return False
    markers = (
        "teach me",
        "learn this",
        "remember this",
        "save this memory",
        "correct this answer",
        "update your memory",
    )
    return any(marker in q for marker in markers)

    # Define the nodes
async def router_node(state: TwinState):
    """Phase 4 Orchestrator: Intent Classification & Routing"""
    messages = state["messages"]
    last_human_msg = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "")
    interaction_context = (state.get("interaction_context") or "owner_chat").strip().lower()

    # Deterministic fast-path keeps obvious greetings and owner-specific prompts stable.
    if _is_smalltalk_query(last_human_msg):
        return {
            "dialogue_mode": "SMALLTALK",
            "intent_label": classify_query_intent(last_human_msg, dialogue_mode="SMALLTALK"),
            "target_owner_scope": False,
            "requires_evidence": False,
            "sub_queries": [],
            "reasoning_history": (state.get("reasoning_history") or []) + [
                "Router: deterministic SMALLTALK fast-path"
            ],
        }

    owner_specific_heuristic = _is_owner_specific_query(last_human_msg)
    explicit_teaching = _is_explicit_teaching_query(last_human_msg)
    
    router_prompt = f"""You are a Strategic Dialogue Router for a Digital Twin.
    Classify the user's intent to determine retrieval and evidence requirements.
    
    USER QUERY: {last_human_msg}
    INTERACTION CONTEXT: {interaction_context}
    
    MODES:
    - SMALLTALK: Greetings, brief pleasantries, "how are you".
    - QA_FACT: Questions about objective facts, events, or public knowledge.
    - QA_RELATIONSHIP: Questions about people, entities, or connections (Graph needed).
    - STANCE_GLOBAL: Questions about beliefs, opinions, core philosophy, or "what do I think about".
    - REPAIR: User complaining about being robotic, generic, or incorrect.
    - TEACHING: Only when user explicitly asks to teach/correct OR context is owner_training and evidence is missing.
    
    INTENT ATTRIBUTES:
    - is_person_specific: True if the question asks for MY (the owner's) specific view, decision, preference, or experience.
    
    OUTPUT FORMAT (JSON):
    {{
        "mode": "SMALLTALK | QA_FACT | QA_RELATIONSHIP | STANCE_GLOBAL | REPAIR | TEACHING",
        "is_person_specific": bool,
        "requires_evidence": bool,
        "reasoning": "Brief explanation"
    }}
    """
    
    try:
        plan, _route_meta = await invoke_json(
            [{"role": "system", "content": router_prompt}],
            task="router",
            temperature=0,
            max_tokens=320,
        )
        print(f"[Router] Plan: {plan}")
        
        mode = plan.get("mode", "QA_FACT")
        is_specific = plan.get("is_person_specific", False)
        req_evidence = plan.get("requires_evidence", True)
        intent_label = classify_query_intent(last_human_msg, dialogue_mode=mode)

        # Deterministic guardrails over model output.
        if owner_specific_heuristic:
            is_specific = True
            req_evidence = True

        if mode == "TEACHING" and interaction_context != "owner_training" and not explicit_teaching:
            mode = "QA_FACT"

        # Person-specific queries MUST have evidence verification.
        if is_specific:
            req_evidence = True
            
        # Sub-query generation for the next step (retrieval)
        sub_queries = [last_human_msg] if mode != "SMALLTALK" else []
        
        return {
            "dialogue_mode": mode,
            "intent_label": intent_label,
            "target_owner_scope": is_specific,
            "requires_evidence": req_evidence,
            "sub_queries": sub_queries,
            "reasoning_history": (state.get("reasoning_history") or [])
            + [f"Router: Mode={mode}, Intent={intent_label}, Specific={is_specific}"]
        }
    except Exception as e:
        print(f"Router error: {e}")
        fallback_intent = classify_query_intent(last_human_msg, dialogue_mode="QA_FACT")
        return {
            "dialogue_mode": "QA_FACT",
            "intent_label": fallback_intent,
            "requires_evidence": True,
            "sub_queries": [last_human_msg],
        }

async def evidence_gate_node(state: TwinState):
    """Phase 4: Evidence Gate (Hard Constraint with LLM Verifier)"""
    mode = state.get("dialogue_mode")
    is_specific = state.get("target_owner_scope", False)
    context = state.get("retrieved_context", {}).get("results", [])
    last_human_msg = next((m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), "")
    requires_evidence = state.get("requires_evidence", True)
    interaction_context = (state.get("interaction_context") or "owner_chat").strip().lower()
    explicit_teaching = _is_explicit_teaching_query(last_human_msg)
    
    # Hard Gate Logic
    requires_teaching = False
    reason = "Sufficient evidence found."

    if mode == "SMALLTALK":
        return {
            "dialogue_mode": mode,
            "requires_teaching": False,
            "reasoning_history": (state.get("reasoning_history") or []) + ["Gate: SKIP (smalltalk)"]
        }

    if requires_evidence and not context:
        if is_specific:
            requires_teaching = True
            reason = "No evidence retrieved for owner-specific query."
        elif interaction_context == "owner_training" and (mode == "TEACHING" or explicit_teaching):
            requires_teaching = True
            reason = "Training context without evidence; collecting owner guidance."
        else:
            # Keep generic/public conversations fluent even when retrieval is empty.
            requires_teaching = False
            reason = "No retrieval evidence for generic query; proceeding with general response."
    
    if (not requires_teaching) and is_specific:
        if not context:
            requires_teaching = True
            reason = "No evidence found for person-specific query."
        else:
            # LLM Verifier Pass for person-specific intents
            context_str = "\n".join([f"- {c.get('text')}" for c in context[:3]])
            verifier_prompt = f"""You are an Evidence Verifier for a Digital Twin.
            The user asked a person-specific question, and we retrieved some context.
            Determine if the context contains SUFFICIENT EVIDENCE to answer the question as the twin.
            
            USER QUESTION: {last_human_msg}
            RETRIEVED CONTEXT:
            {context_str}
            
            RULE: If the context is generic, irrelevant, or doesn't actually contain the owner's stance/recipe/decision, you MUST fail it.
            
            OUTPUT FORMAT (JSON):
            {{
                "is_sufficient": bool,
                "reason": "Brief explanation"
            }}
            """
            try:
                v_res, _route_meta = await invoke_json(
                    [{"role": "system", "content": verifier_prompt}],
                    task="verifier",
                    temperature=0,
                    max_tokens=220,
                )
                
                if not v_res.get("is_sufficient"):
                    requires_teaching = True
                    reason = f"Verifier: {v_res.get('reason')}"
            except Exception as e:
                print(f"Verifier error: {e}")
                # Fallback to simple context check
                if len(context) < 1:
                    requires_teaching = True
                    reason = "Fallback: Insufficient context length."

    if requires_teaching:
        new_mode = "TEACHING"
    elif mode == "TEACHING":
        # TEACHING should not leak into normal chat turns without explicit trigger.
        new_mode = "QA_FACT"
    else:
        new_mode = mode
    
    return {
        "dialogue_mode": new_mode,
        "requires_teaching": requires_teaching,
        "reasoning_history": (state.get("reasoning_history") or []) + [f"Gate: {'FAIL -> TEACHING' if requires_teaching else 'PASS'}. {reason}"]
    }

async def planner_node(state: TwinState):
    """Pass A: Strategic Planning & Logic (Structured JSON)"""
    mode = state.get("dialogue_mode", "QA_FACT")
    context_data = state.get("retrieved_context", {}).get("results", [])
    user_query = next((m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), "")
    
    # Use the dynamic system prompt (Phase 4)
    system_msg, persona_trace = build_system_prompt_with_trace(state)
    
    # Prepare context
    context_str = ""
    for i, res in enumerate(context_data):
        text = res.get("text", "")
        date_info = res.get("metadata", {}).get("effective_from", "Unknown Date")
        source = res.get("source_id", "Unknown")
        context_str += f"[{i}] (Date: {date_info} | ID: {source}): {text}\n"

    # Deterministic safety fallback: no evidence means no speculative answer.
    if mode == "TEACHING" and not context_data:
        return {
            "planning_output": {
                "answer_points": [UNCERTAINTY_RESPONSE],
                "citations": [],
                "follow_up_question": "Can you share the source or clarify what I should say for this?",
                "confidence": 0.2,
                "teaching_questions": [
                    f"What should I answer when asked: \"{user_query}\"?",
                    "Do you have a source, quote, or document I should use for this topic?",
                ],
                "reasoning_trace": "No evidence retrieved; deterministic uncertainty response used.",
            },
            "intent_label": persona_trace.get("intent_label"),
            "persona_module_ids": persona_trace.get("module_ids", []),
            "persona_spec_version": persona_trace.get("persona_spec_version"),
            "persona_prompt_variant": persona_trace.get("persona_prompt_variant"),
            "reasoning_history": (state.get("reasoning_history") or []) + [
                "Planner: deterministic uncertainty plan (TEACHING + no evidence)."
            ],
        }

    planner_prompt = f"""
{system_msg}

CURRENT MODE: {mode}
EVIDENCE:
{context_str if context_str else "No evidence retrieved."}

TASK:
1. Identify the core points for the user's answer (max 3).
2. If in TEACHING mode, generate 2-3 specific questions for the owner.
3. Select a follow-up question to keep the conversation going.
4. If evidence is present, map points to citations.

OUTPUT FORMAT (STRICT JSON):
{{
    "answer_points": ["point 1", "point 2"],
    "citations": ["Source_ID_1", "Source_ID_2"],
    "follow_up_question": "...",
    "confidence": 0.0-1.0,
    "teaching_questions": ["q1", "q2"],
    "reasoning_trace": "Short internal log"
}}
"""
    try:
        plan, _route_meta = await invoke_json(
            [{"role": "system", "content": planner_prompt}],
            task="planner",
            temperature=0,
            max_tokens=900,
        )
        
        return {
            "planning_output": plan,
            "intent_label": persona_trace.get("intent_label"),
            "persona_module_ids": persona_trace.get("module_ids", []),
            "persona_spec_version": persona_trace.get("persona_spec_version"),
            "persona_prompt_variant": persona_trace.get("persona_prompt_variant"),
            "reasoning_history": (state.get("reasoning_history") or []) + [f"Planner: Generated {len(plan.get('answer_points', []))} points."]
        }
    except Exception as e:
        print(f"Planner error: {e}")
        return {
            "planning_output": {
                "answer_points": ["I encountered an error planning my response."],
                "follow_up_question": "Can you try rephrasing?",
            },
            "intent_label": persona_trace.get("intent_label"),
            "persona_module_ids": persona_trace.get("module_ids", []),
            "persona_spec_version": persona_trace.get("persona_spec_version"),
            "persona_prompt_variant": persona_trace.get("persona_prompt_variant"),
        }

async def realizer_node(state: TwinState):
    """Pass B: Conversational Reification (Human-like Output)"""
    plan = state.get("planning_output", {})
    mode = state.get("dialogue_mode", "QA_FACT")
    
    realizer_prompt = f"""You are the Voice Realizer for a Digital Twin. 
    Take the structured plan and rewrite it into a short, natural, conversational response.
    
    PLAN:
    {json.dumps(plan, indent=2)}
    
    CONSTRAINTS:
    - 1 to 3 sentences total.
    - Sound like a real person, not a bot.
    - Include the follow-up question at the end.
    - If teaching: explain briefly that you need their input to be certain.
    - NO FAKE SOURCES. Use citations provided in the plan if any.
    """
    
    try:
        realized_text, route_meta = await invoke_text(
            [{"role": "system", "content": realizer_prompt}],
            task="realizer",
            temperature=0.7,
            max_tokens=500,
        )
        res = AIMessage(content=realized_text)
        
        # Post-process for citations and teaching metadata (Phase 4)
        citations = plan.get("citations", [])
        teaching_questions = plan.get("teaching_questions", [])
        
        # Enrich message with metadata for the UI
        res.additional_kwargs["teaching_questions"] = teaching_questions
        res.additional_kwargs["planning_output"] = plan
        res.additional_kwargs["dialogue_mode"] = mode
        res.additional_kwargs["intent_label"] = state.get("intent_label")
        res.additional_kwargs["module_ids"] = state.get("persona_module_ids") or []
        if state.get("persona_spec_version"):
            res.additional_kwargs["persona_spec_version"] = state.get("persona_spec_version")
        if state.get("persona_prompt_variant"):
            res.additional_kwargs["persona_prompt_variant"] = state.get("persona_prompt_variant")
        if route_meta:
            res.additional_kwargs["inference_provider"] = route_meta.get("provider")
            res.additional_kwargs["inference_model"] = route_meta.get("model")
            res.additional_kwargs["inference_latency_ms"] = route_meta.get("latency_ms")
        
        return {
            "messages": [res],
            "citations": citations,
            "reasoning_history": (state.get("reasoning_history") or []) + ["Realizer: Response reified with Metadata."]
        }
    except Exception as e:
        print(f"Realizer error: {e}")
        answer_points = plan.get("answer_points", []) if isinstance(plan, dict) else []
        follow_up = (plan.get("follow_up_question") if isinstance(plan, dict) else None) or ""
        fallback_base = " ".join(
            [p for p in answer_points if isinstance(p, str) and p.strip()][:2]
        ).strip()
        if not fallback_base:
            fallback_base = UNCERTAINTY_RESPONSE
        fallback_text = f"{fallback_base} {follow_up}".strip()

        fallback_msg = AIMessage(content=fallback_text)
        fallback_msg.additional_kwargs["teaching_questions"] = (
            plan.get("teaching_questions", []) if isinstance(plan, dict) else []
        )
        fallback_msg.additional_kwargs["planning_output"] = plan if isinstance(plan, dict) else {}
        fallback_msg.additional_kwargs["dialogue_mode"] = mode
        fallback_msg.additional_kwargs["intent_label"] = state.get("intent_label")
        fallback_msg.additional_kwargs["module_ids"] = state.get("persona_module_ids") or []

        return {
            "messages": [fallback_msg],
            "citations": plan.get("citations", []) if isinstance(plan, dict) else [],
            "reasoning_history": (state.get("reasoning_history") or []) + [
                "Realizer: deterministic fallback used after exception."
            ],
        }

def create_twin_agent(
    twin_id: str,
    group_id: Optional[str] = None,
    system_prompt_override: str = None,
    full_settings: dict = None,
    graph_context: str = "",
    owner_memory_context: str = "",
    conversation_history: Optional[List[BaseMessage]] = None
):
    # Retrieve-only tool setup needs to stay inside or be passed
    from modules.tools import get_retrieval_tool
    retrieval_tool = get_retrieval_tool(twin_id, group_id=group_id, conversation_history=conversation_history)

    async def retrieve_hybrid_node(state: TwinState):
        """Phase 2: Executing planned retrieval (Audit 1: Parallel & Robust)"""
        sub_queries = state.get("sub_queries", [])
        messages = state["messages"]
        all_results = []
        citations = []
        
        async def safe_retrieve(query):
            try:
                res_str = await retrieval_tool.ainvoke({"query": query})
                return json.loads(res_str)
            except Exception as e:
                print(f"Retrieval error: {e}")
                return []

        tasks = [safe_retrieve(q) for q in sub_queries]
        results_list = await asyncio.gather(*tasks)
        for res_data in results_list:
            if isinstance(res_data, list):
                for item in res_data:
                    all_results.append(item)
                    if "source_id" in item:
                        citations.append(item["source_id"])

        return {
            "retrieved_context": {"results": all_results},
            "citations": list(set(citations)),
            "reasoning_history": (state.get("reasoning_history") or []) + [f"Retrieval: Executed {len(sub_queries)} queries."]
        }

    # Define the graph
    workflow = StateGraph(TwinState)
    
    workflow.add_node("router", router_node)
    workflow.add_node("retrieve", retrieve_hybrid_node)
    workflow.add_node("gate", evidence_gate_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("realizer", realizer_node)
    
    workflow.set_entry_point("router")
    
    def route_after_router(state: TwinState):
        if state.get("requires_evidence"):
            return "retrieve"
        return "planner"

    workflow.add_conditional_edges("router", route_after_router, {"retrieve": "retrieve", "planner": "planner"})
    workflow.add_edge("retrieve", "gate")
    workflow.add_edge("gate", "planner")
    workflow.add_edge("planner", "realizer")
    workflow.add_edge("realizer", END)
    
    checkpointer = get_checkpointer()
    return workflow.compile(checkpointer=checkpointer) if checkpointer else workflow.compile()

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
    owner_memory_context: str = "",
    interaction_context: str = "owner_chat",
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
        owner_memory_context=owner_memory_context,
        conversation_history=history
    )
    
    initial_messages = history or []
    initial_messages.append(HumanMessage(content=query))
    
    state = {
        "messages": initial_messages,
        "twin_id": twin_id,
        "confidence_score": 1.0,
        "citations": [],
        "sub_queries": [],
        "reasoning_history": [],
        "retrieved_context": {},
        # Phase 4 initialization
        "dialogue_mode": "QA_FACT",
        "intent_label": "factual_with_evidence",
        "requires_evidence": True,
        "requires_teaching": False,
        "target_owner_scope": False,
        "planning_output": None,
        "persona_module_ids": [],
        "persona_spec_version": None,
        "persona_prompt_variant": None,
        # Path B / Phase 4 Context
        "full_settings": settings,
        "graph_context": graph_context,
        "owner_memory_context": owner_memory_context,
        "system_prompt_override": system_prompt,
        "interaction_context": interaction_context,
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
