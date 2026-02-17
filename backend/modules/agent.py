import os
import asyncio
import json
import re
import time
from typing import Annotated, TypedDict, List, Dict, Any, Union, Optional, Tuple
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from modules.langfuse_sdk import langfuse_context, observe

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

_ROUTER_KNOWLEDGE_CACHE_TTL_SECONDS = float(
    os.getenv("ROUTER_KNOWLEDGE_CACHE_TTL_SECONDS", "30")
)
_ROUTER_FORCE_RETRIEVAL_WITH_KNOWLEDGE = (
    os.getenv("ROUTER_FORCE_RETRIEVAL_WITH_KNOWLEDGE", "true").lower() == "true"
)
_router_knowledge_cache: Dict[str, Dict[str, Any]] = {}

# Adaptive grounding policy for planner output rendering.
ADAPTIVE_GROUNDING_POLICY_ENABLED = (
    os.getenv("ADAPTIVE_GROUNDING_POLICY_ENABLED", "true").lower() == "true"
)
ADAPTIVE_GROUNDING_HIGH_SCORE = float(os.getenv("ADAPTIVE_GROUNDING_HIGH_SCORE", "0.82"))
ADAPTIVE_GROUNDING_HIGH_MARGIN = float(os.getenv("ADAPTIVE_GROUNDING_HIGH_MARGIN", "0.12"))
ADAPTIVE_GROUNDING_MID_SCORE = float(os.getenv("ADAPTIVE_GROUNDING_MID_SCORE", "0.65"))
ADAPTIVE_GROUNDING_MID_OVERLAP = float(os.getenv("ADAPTIVE_GROUNDING_MID_OVERLAP", "0.12"))

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
    router_reason: Optional[str]
    router_knowledge_available: Optional[bool]
    
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
- Owner-specific factual claims MUST be supported by retrieved context.
- If context is missing for owner-specific claims, say you don't know.
- For greetings/general coaching without owner-specific claims, stay conversational and helpful.
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


def _twin_has_groundable_knowledge(twin_id: Optional[str]) -> bool:
    """
    Lightweight runtime signal for router policy.
    True when the twin has any persisted source / verified QnA / graph node.
    """
    if not twin_id:
        return False

    now = time.time()
    cached = _router_knowledge_cache.get(twin_id)
    if cached and (now - float(cached.get("ts", 0))) <= _ROUTER_KNOWLEDGE_CACHE_TTL_SECONDS:
        return bool(cached.get("has_knowledge", False))

    has_knowledge = False
    try:
        # Prefer cheap existence checks (limit 1) to avoid heavy counts.
        src_res = (
            supabase.table("sources")
            .select("id")
            .eq("twin_id", twin_id)
            .in_("status", ["live", "processed"])
            .limit(1)
            .execute()
        )
        has_knowledge = bool(src_res.data)

        if not has_knowledge:
            qna_res = (
                supabase.table("verified_qna")
                .select("id")
                .eq("twin_id", twin_id)
                .eq("is_active", True)
                .limit(1)
                .execute()
            )
            has_knowledge = bool(qna_res.data)

        if not has_knowledge:
            nodes_res = supabase.rpc("get_nodes_system", {"t_id": twin_id, "limit_val": 1}).execute()
            has_knowledge = bool(nodes_res.data)
    except Exception as e:
        print(f"[Router] Knowledge availability check failed for twin {twin_id}: {e}")
        has_knowledge = False

    _router_knowledge_cache[twin_id] = {"ts": now, "has_knowledge": has_knowledge}
    return has_knowledge


def _is_identity_intro_query(query: str) -> bool:
    q = (query or "").strip().lower()
    if not q:
        return False
    markers = (
        "who are you",
        "what are you",
        "introduce yourself",
        "tell me about yourself",
        "what can you do",
    )
    return any(marker in q for marker in markers)


def _is_smalltalk_query(query: str) -> bool:
    q = (query or "").strip().lower()
    if not q:
        return False
    q_plain = re.sub(r"[^a-z0-9\s']", "", q)
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
        "who are you",
        "what are you",
        "introduce yourself",
        "tell me about yourself",
        "what can you do",
        "can you help me",
    }
    return (
        q in smalltalk_markers
        or q_plain in smalltalk_markers
        or any(marker in q for marker in {"how's your day", "hows your day"})
    )


def _is_owner_specific_query(query: str) -> bool:
    q = (query or "").strip().lower()
    if not q:
        return False
    markers = [
        r"\bwhere (did|do) i\b",
        r"\bwhen (did|do) i\b",
        r"\bwho am i\b",
        r"\bwhat (is|was) my (background|story|experience|history)\b",
        r"\bwhat (do|did) i think\b",
        r"\bwhat('?s| is) my (stance|view|opinion|belief|thesis|principle)\b",
        r"\bmy (stance|view|opinion|belief|thesis|principle)\b",
        r"\bhow do i (approach|decide|evaluate)\b",
        r"\bbased on my (sources|documents|knowledge)\b",
        r"\bfrom my (sources|documents|knowledge)\b",
    ]
    return any(re.search(pattern, q) for pattern in markers)


def _is_generic_business_coaching_query(query: str) -> bool:
    q = (query or "").strip().lower()
    if not q:
        return False
    coaching_markers = (
        "gtm",
        "go to market",
        "go-to-market",
        "icp",
        "positioning",
        "plg",
        "founder-led",
        "sales-led",
        "runway",
        "pricing",
        "startup",
        "founder",
        "traction",
        "funnel",
        "pipeline",
        "activation",
        "retention",
        "churn",
        "interview",
        "customer interview",
        "buyer",
        "objection",
        "pilot",
        "metrics",
        "kpi",
        "action items",
        "90-day",
        "90 day",
        "week 1",
        "week one",
        "month 1",
        "month one",
        "plan",
        "strategy",
        "cadence",
        "what should i do",
        "how should i",
        "help me",
    )
    return any(marker in q for marker in coaching_markers)


def _is_explicit_source_grounded_query(query: str) -> bool:
    q = (query or "").strip().lower()
    if not q:
        return False
    markers = (
        "based on my sources",
        "from my sources",
        "from my documents",
        "from my knowledge",
        "cite",
        "citation",
        "according to my",
    )
    return any(marker in q for marker in markers)


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


def _is_entity_probe_query(query: str) -> bool:
    q = (query or "").strip().lower()
    if not q:
        return False
    patterns = (
        r"^\s*do you know(?: about)?\s+.+",
        r"^\s*what is\s+.+",
        r"^\s*who is\s+.+",
        r"^\s*tell me about\s+.+",
        r"^\s*can you explain\s+.+",
    )
    return any(re.search(p, q) for p in patterns)


def _log_router_observation(
    *,
    mode: str,
    intent_label: str,
    requires_evidence: bool,
    target_owner_scope: bool,
    interaction_context: str,
    knowledge_available: bool,
    router_reason: Optional[str],
) -> None:
    """Best-effort router span metadata for Langfuse diagnostics."""
    try:
        langfuse_context.update_current_observation(
            metadata={
                "router_mode": mode,
                "router_intent_label": intent_label,
                "router_requires_evidence": bool(requires_evidence),
                "router_target_owner_scope": bool(target_owner_scope),
                "router_interaction_context": interaction_context,
                "router_knowledge_available": bool(knowledge_available),
                "router_reason": (router_reason or "")[:500],
            }
        )
    except Exception:
        pass


def _build_router_prompt(user_query: str, interaction_context: str) -> str:
    return f"""You are a Strategic Dialogue Router for a Digital Twin.
Classify the user's intent to determine retrieval and evidence requirements.

USER QUERY: {user_query}
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

    # Define the nodes
@observe(name="router_node")
async def router_node(state: TwinState):
    """Phase 4 Orchestrator: Intent Classification & Routing"""
    messages = state["messages"]
    last_human_msg = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "")
    interaction_context = (state.get("interaction_context") or "owner_chat").strip().lower()
    twin_id = state.get("twin_id")
    knowledge_available = _twin_has_groundable_knowledge(twin_id)

    # Deterministic fast-path keeps obvious greetings and owner-specific prompts stable.
    if _is_smalltalk_query(last_human_msg):
        # Identity prompts should be grounded in owned knowledge when available.
        if knowledge_available and _is_identity_intro_query(last_human_msg):
            router_reason = "identity prompt rerouted to QA_FACT with evidence because knowledge is available"
            intent_label = classify_query_intent(last_human_msg, dialogue_mode="QA_FACT")
            _log_router_observation(
                mode="QA_FACT",
                intent_label=intent_label,
                requires_evidence=True,
                target_owner_scope=False,
                interaction_context=interaction_context,
                knowledge_available=knowledge_available,
                router_reason=router_reason,
            )
            return {
                "dialogue_mode": "QA_FACT",
                "intent_label": intent_label,
                "target_owner_scope": False,
                "requires_evidence": True,
                "sub_queries": [last_human_msg],
                "router_reason": router_reason,
                "router_knowledge_available": knowledge_available,
                "reasoning_history": (state.get("reasoning_history") or []) + [
                    "Router: identity prompt rerouted to retrieval-backed QA (knowledge available)"
                ],
            }
        router_reason = "deterministic SMALLTALK fast-path"
        intent_label = classify_query_intent(last_human_msg, dialogue_mode="SMALLTALK")
        _log_router_observation(
            mode="SMALLTALK",
            intent_label=intent_label,
            requires_evidence=False,
            target_owner_scope=False,
            interaction_context=interaction_context,
            knowledge_available=knowledge_available,
            router_reason=router_reason,
        )
        return {
            "dialogue_mode": "SMALLTALK",
            "intent_label": intent_label,
            "target_owner_scope": False,
            "requires_evidence": False,
            "sub_queries": [],
            "router_reason": router_reason,
            "router_knowledge_available": knowledge_available,
            "reasoning_history": (state.get("reasoning_history") or []) + [
                "Router: deterministic SMALLTALK fast-path"
            ],
        }

    owner_specific_heuristic = _is_owner_specific_query(last_human_msg)
    explicit_teaching = _is_explicit_teaching_query(last_human_msg)
    generic_coaching_heuristic = _is_generic_business_coaching_query(last_human_msg)
    explicit_source_grounded = _is_explicit_source_grounded_query(last_human_msg)
    
    # Try Langfuse-managed prompt, but hard-fallback to strict inline prompt when
    # the fetched prompt is too generic (e.g., default one-liner).
    router_prompt = ""
    try:
        from modules.langfuse_prompt_manager import compile_prompt
        candidate = compile_prompt(
            "router",
            variables={
                "user_query": last_human_msg,
                "interaction_context": interaction_context,
            }
        )
        lowered = (candidate or "").lower()
        if all(marker in lowered for marker in ["output format", "\"mode\"", "\"requires_evidence\""]):
            router_prompt = candidate
    except Exception:
        router_prompt = ""

    if not router_prompt:
        router_prompt = _build_router_prompt(last_human_msg, interaction_context)
    
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

        # Generic coaching should not be forced into owner-specific/teaching lanes
        # unless user explicitly asks about the owner's personal stance or sources.
        if generic_coaching_heuristic and not owner_specific_heuristic and not explicit_teaching:
            if mode in {"STANCE_GLOBAL", "TEACHING"}:
                mode = "QA_FACT"
            is_specific = False
            req_evidence = False

        # Entity probe queries ("do you know X", "what is X") should use retrieval.
        if _is_entity_probe_query(last_human_msg):
            if mode == "SMALLTALK":
                mode = "QA_FACT"
            req_evidence = True

        # Owner conversational mode default:
        # unless user explicitly asks for owner/source-grounded evidence, keep
        # generic prompts fluent and avoid noisy retrieval misses.
        if (
            interaction_context in {"owner_chat", "owner_training"}
            and not is_specific
            and not explicit_source_grounded
            and not explicit_teaching
        ):
            if mode in {"STANCE_GLOBAL", "TEACHING"}:
                mode = "QA_FACT"
            is_specific = False
            req_evidence = False

        # Public-facing conversations should not drift into owner-training lanes
        # unless the user explicitly asks for owner-specific/source-grounded behavior.
        if (
            interaction_context in {"public_share", "public_widget"}
            and not owner_specific_heuristic
            and not explicit_source_grounded
            and not explicit_teaching
        ):
            if mode in {"STANCE_GLOBAL", "TEACHING"}:
                mode = "QA_FACT"
            is_specific = False

        if mode == "TEACHING" and interaction_context != "owner_training" and not explicit_teaching:
            mode = "QA_FACT"

        # Person-specific queries MUST have evidence verification.
        if is_specific:
            req_evidence = True

        # Knowledge-aware policy:
        # When the twin has ingested knowledge, force retrieval for non-smalltalk
        # modes to keep responses source-grounded by default.
        knowledge_forced_retrieval = False
        if (
            _ROUTER_FORCE_RETRIEVAL_WITH_KNOWLEDGE
            and knowledge_available
            and mode != "SMALLTALK"
        ):
            req_evidence = True
            knowledge_forced_retrieval = True
            
        # Sub-query generation for retrieval. Entity probes benefit from a
        # normalized factual variant ("what is X") in addition to raw phrasing.
        sub_queries = [last_human_msg] if mode != "SMALLTALK" else []
        if mode != "SMALLTALK" and _is_entity_probe_query(last_human_msg):
            lowered = (last_human_msg or "").strip().lower()
            m = re.search(
                r"^\s*(?:do you know(?: about)?|what is|who is|tell me about|can you explain)\s+(.+?)\s*\??$",
                lowered,
            )
            if m:
                entity = m.group(1).strip()
                if entity:
                    normalized = f"what is {entity}"
                    if normalized not in sub_queries:
                        sub_queries.insert(0, normalized)
        
        router_reason = (
            f"mode={mode}; intent={intent_label}; specific={is_specific}; "
            f"requires_evidence={req_evidence}; context={interaction_context}; "
            f"knowledge_available={knowledge_available}; "
            f"knowledge_forced_retrieval={knowledge_forced_retrieval}; "
            f"explicit_source_grounded={explicit_source_grounded}; explicit_teaching={explicit_teaching}"
        )
        _log_router_observation(
            mode=mode,
            intent_label=intent_label,
            requires_evidence=req_evidence,
            target_owner_scope=is_specific,
            interaction_context=interaction_context,
            knowledge_available=knowledge_available,
            router_reason=router_reason,
        )
        return {
            "dialogue_mode": mode,
            "intent_label": intent_label,
            "target_owner_scope": is_specific,
            "requires_evidence": req_evidence,
            "sub_queries": sub_queries,
            "router_reason": router_reason,
            "router_knowledge_available": knowledge_available,
            "reasoning_history": (state.get("reasoning_history") or [])
            + [f"Router: Mode={mode}, Intent={intent_label}, Specific={is_specific}"]
        }
    except Exception as e:
        print(f"Router error: {e}")
        # Tag error in Langfuse
        try:
            langfuse_context.update_current_observation(
                level="ERROR",
                status_message=f"Router failed: {str(e)[:255]}",
                metadata={
                    "error": True,
                    "error_type": type(e).__name__,
                    "error_node": "router_node",
                    "query": last_human_msg[:200] if last_human_msg else None,
                }
            )
        except Exception:
            pass
        if _is_smalltalk_query(last_human_msg):
            fallback_intent = classify_query_intent(last_human_msg, dialogue_mode="SMALLTALK")
            fallback_reason = "router exception fallback to SMALLTALK"
            _log_router_observation(
                mode="SMALLTALK",
                intent_label=fallback_intent,
                requires_evidence=False,
                target_owner_scope=False,
                interaction_context=interaction_context,
                knowledge_available=knowledge_available,
                router_reason=fallback_reason,
            )
            return {
                "dialogue_mode": "SMALLTALK",
                "intent_label": fallback_intent,
                "target_owner_scope": False,
                "requires_evidence": False,
                "sub_queries": [],
                "router_reason": fallback_reason,
                "router_knowledge_available": knowledge_available,
            }
        fallback_intent = classify_query_intent(last_human_msg, dialogue_mode="QA_FACT")
        fallback_reason = "router exception fallback to QA_FACT with evidence"
        _log_router_observation(
            mode="QA_FACT",
            intent_label=fallback_intent,
            requires_evidence=True,
            target_owner_scope=False,
            interaction_context=interaction_context,
            knowledge_available=knowledge_available,
            router_reason=fallback_reason,
        )
        return {
            "dialogue_mode": "QA_FACT",
            "intent_label": fallback_intent,
            "target_owner_scope": False,
            "requires_evidence": True,
            "sub_queries": [last_human_msg],
            "router_reason": fallback_reason,
            "router_knowledge_available": knowledge_available,
        }

@observe(name="evidence_gate_node")
async def evidence_gate_node(state: TwinState):
    """Phase 4: Evidence Gate (Hard Constraint with LLM Verifier)"""
    mode = state.get("dialogue_mode")
    is_specific = state.get("target_owner_scope", False)
    context = state.get("retrieved_context", {}).get("results", [])
    last_human_msg = next((m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), "")
    requires_evidence = state.get("requires_evidence", True)
    interaction_context = (state.get("interaction_context") or "owner_chat").strip().lower()
    explicit_teaching = _is_explicit_teaching_query(last_human_msg)
    inferred_owner_specific = (
        bool(is_specific)
        or _is_owner_specific_query(last_human_msg)
        or _is_explicit_source_grounded_query(last_human_msg)
    )
    
    # Hard Gate Logic
    requires_teaching = False
    reason = "Sufficient evidence found."
    clear_context_for_uncertainty = False

    if mode == "SMALLTALK":
        return {
            "dialogue_mode": mode,
            "requires_teaching": False,
            "reasoning_history": (state.get("reasoning_history") or []) + ["Gate: SKIP (smalltalk)"]
        }

    if requires_evidence and not context:
        if inferred_owner_specific:
            requires_teaching = True
            if interaction_context == "owner_training" and (mode == "TEACHING" or explicit_teaching):
                reason = "No evidence retrieved for owner-specific query in training mode."
            else:
                reason = "No evidence retrieved for owner-specific query."
        elif interaction_context == "owner_training" and (mode == "TEACHING" or explicit_teaching):
            requires_teaching = True
            reason = "Training context without evidence; collecting owner guidance."
        else:
            # Keep generic/public conversations fluent even when retrieval is empty.
            requires_teaching = False
            reason = "No retrieval evidence for generic query; proceeding with general response."
    
    if (not requires_teaching) and inferred_owner_specific:
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
                    if interaction_context == "owner_training" and (mode == "TEACHING" or explicit_teaching):
                        requires_teaching = True
                        reason = f"Verifier (training): {v_res.get('reason')}"
                    else:
                        requires_teaching = False
                        clear_context_for_uncertainty = True
                        reason = f"Verifier failed: {v_res.get('reason')}"
            except Exception as e:
                print(f"Verifier error: {e}")
                # Tag error in Langfuse
                try:
                    langfuse_context.update_current_observation(
                        level="WARNING",
                        status_message=f"Verifier failed: {str(e)[:255]}",
                        metadata={
                            "error": True,
                            "error_type": type(e).__name__,
                            "error_node": "evidence_gate_verifier",
                        }
                    )
                except Exception:
                    pass
                # Fallback to simple context check
                if len(context) < 1:
                    if interaction_context == "owner_training" and (mode == "TEACHING" or explicit_teaching):
                        requires_teaching = True
                        reason = "Fallback: Insufficient context length in training mode."
                    else:
                        requires_teaching = False
                        clear_context_for_uncertainty = True
                        reason = "Fallback: Insufficient context length."

    if requires_teaching:
        new_mode = "TEACHING"
    elif mode == "TEACHING":
        # TEACHING should not leak into normal chat turns without explicit trigger.
        new_mode = "QA_FACT"
    else:
        new_mode = mode
    
    result = {
        "dialogue_mode": new_mode,
        "requires_teaching": requires_teaching,
        "reasoning_history": (state.get("reasoning_history") or []) + [f"Gate: {'FAIL -> TEACHING' if requires_teaching else 'PASS'}. {reason}"]
    }
    if clear_context_for_uncertainty:
        result["retrieved_context"] = {"results": []}
    return result


_PLANNER_QUERY_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "we",
    "what",
    "with",
    "you",
    "your",
}


def _planner_query_tokens(query: str) -> List[str]:
    tokens = re.findall(r"[a-z0-9][a-z0-9._-]*", (query or "").lower())
    return [tok for tok in tokens if len(tok) > 2 and tok not in _PLANNER_QUERY_STOPWORDS]


def _planner_text_tokens(text: str) -> set:
    tokens = re.findall(r"[a-z0-9][a-z0-9._-]*", (text or "").lower())
    return {tok for tok in tokens if len(tok) > 2 and tok not in _PLANNER_QUERY_STOPWORDS}


def _planner_overlap_ratio(query_tokens: List[str], text: str) -> float:
    if not query_tokens:
        return 0.0
    qset = set(query_tokens)
    tset = _planner_text_tokens(text)
    if not tset:
        return 0.0
    return len(qset.intersection(tset)) / float(len(qset))


def _collect_source_faithful_points(
    context_data: List[Dict[str, Any]],
    query_tokens: List[str],
) -> Tuple[List[str], List[str], float]:
    def _normalize_extract(raw: str) -> str:
        return re.sub(r"\s+", " ", (raw or "").strip().lstrip("-*").strip())

    scored_sentences: Dict[str, Dict[str, float]] = {}
    citation_ids: List[str] = []
    order_idx = 0

    for ctx in context_data[:5]:
        source_id = ctx.get("source_id")
        if isinstance(source_id, str) and source_id and source_id not in citation_ids:
            citation_ids.append(source_id)

        text = (ctx.get("text") or "").strip()
        if not text:
            continue

        vector_score = float(ctx.get("vector_score", ctx.get("score", 0.0)) or 0.0)
        for raw in re.split(r"(?<=[.!?])\s+|\n+", text):
            sentence = _normalize_extract(raw)
            if not sentence or len(sentence) < 18:
                continue

            lowered = sentence.lower()
            overlap = sum(1 for tok in query_tokens if tok in lowered)
            label_bonus = 2 if lowered.startswith(("recommendation:", "assumptions:", "why:")) else 0
            score = float(overlap * 2 + label_bonus) + min(vector_score, 1.0)

            existing = scored_sentences.get(sentence)
            if existing is None or score > float(existing.get("score", 0.0)):
                scored_sentences[sentence] = {"score": score, "order": float(order_idx)}
            order_idx += 1

    ranked = sorted(
        scored_sentences.items(),
        key=lambda item: (-float(item[1].get("score", 0.0)), float(item[1].get("order", 0.0))),
    )
    answer_points = [sentence for sentence, _meta in ranked[:3]]

    if not answer_points:
        fallback_lines: List[str] = []
        for ctx in context_data[:3]:
            for raw_line in (ctx.get("text") or "").splitlines():
                line = _normalize_extract(raw_line)
                if line and line not in fallback_lines:
                    fallback_lines.append(line)
                if len(fallback_lines) >= 3:
                    break
            if len(fallback_lines) >= 3:
                break
        answer_points = fallback_lines[:3]

    max_score = max((float(meta.get("score", 0.0)) for _s, meta in ranked[:3]), default=0.0)
    return answer_points, citation_ids[:3], max_score


def _classify_grounding_policy(
    context_data: List[Dict[str, Any]],
    user_query: str,
) -> Dict[str, Any]:
    if not ADAPTIVE_GROUNDING_POLICY_ENABLED or not context_data:
        return {"level": "disabled", "top_score": 0.0, "margin": 0.0, "best_overlap": 0.0}

    scores = sorted(
        [float(ctx.get("score", ctx.get("vector_score", 0.0)) or 0.0) for ctx in context_data],
        reverse=True,
    )
    top_score = scores[0] if scores else 0.0
    second_score = scores[1] if len(scores) > 1 else 0.0
    margin = max(0.0, top_score - second_score)

    query_tokens = _planner_query_tokens(user_query)
    overlap_values = [
        _planner_overlap_ratio(query_tokens, str(ctx.get("text", "")))
        for ctx in context_data[:5]
    ]
    best_overlap = max(overlap_values, default=0.0)

    if top_score >= ADAPTIVE_GROUNDING_HIGH_SCORE and margin >= ADAPTIVE_GROUNDING_HIGH_MARGIN:
        level = "high"
    elif top_score >= ADAPTIVE_GROUNDING_MID_SCORE and best_overlap >= ADAPTIVE_GROUNDING_MID_OVERLAP:
        level = "mid"
    else:
        level = "low"

    return {
        "level": level,
        "top_score": top_score,
        "margin": margin,
        "best_overlap": best_overlap,
    }

@observe(name="planner_node")
async def planner_node(state: TwinState):
    """Pass A: Strategic Planning & Logic (Structured JSON)"""
    mode = state.get("dialogue_mode", "QA_FACT")
    context_data = state.get("retrieved_context", {}).get("results", [])
    user_query = next((m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), "")
    target_owner_scope = bool(state.get("target_owner_scope", False))
    
    # Use the dynamic system prompt (Phase 4)
    system_msg, persona_trace = build_system_prompt_with_trace(state)
    
    # Prepare context
    context_str = ""
    for i, res in enumerate(context_data):
        text = res.get("text", "")
        date_info = res.get("metadata", {}).get("effective_from", "Unknown Date")
        source = res.get("source_id", "Unknown")
        context_str += f"[{i}] (Date: {date_info} | ID: {source}): {text}\n"

    if mode == "SMALLTALK":
        q_lower = (user_query or "").strip().lower()
        settings = state.get("full_settings") if isinstance(state.get("full_settings"), dict) else {}
        public_intro = ((settings or {}).get("public_intro") or "").strip() if isinstance(settings, dict) else ""
        identity_markers = (
            "who are you",
            "what are you",
            "introduce yourself",
            "tell me about yourself",
            "what can you do",
        )

        if any(marker in q_lower for marker in identity_markers):
            if public_intro:
                answer = public_intro
            else:
                answer = "I am your AI digital twin. I can help with coaching and answers grounded in your knowledge."
            follow_up = "What would you like to talk about?"
        else:
            answer = "Hi there! How can I assist you today?"
            follow_up = "What would you like to discuss?"

        return {
            "planning_output": {
                "answer_points": [answer],
                "citations": [],
                "follow_up_question": follow_up,
                "confidence": 0.8,
                "teaching_questions": [],
                "reasoning_trace": "Deterministic smalltalk plan.",
            },
            "intent_label": persona_trace.get("intent_label"),
            "persona_module_ids": persona_trace.get("module_ids", []),
            "persona_spec_version": persona_trace.get("persona_spec_version"),
            "persona_prompt_variant": persona_trace.get("persona_prompt_variant"),
            "reasoning_history": (state.get("reasoning_history") or []) + [
                "Planner: deterministic smalltalk plan."
            ],
        }

    # Deterministic direct-answer path for "do you know X" when evidence exists.
    # This avoids drifting into persona intros for factual probe queries.
    if context_data and re.search(r"^\s*do you know(?: about)?\s+.+", (user_query or "").strip().lower()):
        evidence_lines = []
        for idx, res in enumerate(context_data[:3]):
            text = (res.get("text") or "").strip()
            source_id = res.get("source_id", "unknown")
            if text:
                evidence_lines.append(f"[{idx}] source={source_id}: {text[:500]}")
        evidence_blob = "\n".join(evidence_lines)

        direct_prompt = f"""You are answering a factual probe.
User asked: "{user_query}"

Use only this evidence:
{evidence_blob}

Rules:
- Answer directly in 1-2 sentences.
- Start with "Yes," only if evidence supports it.
- Do not introduce yourself.
- Do not add coaching boilerplate.
- If evidence is weak, say that clearly.
"""
        try:
            direct_answer, _meta = await invoke_text(
                [{"role": "system", "content": direct_prompt}],
                task="realizer",
                temperature=0.2,
                max_tokens=220,
            )
            answer = (direct_answer or "").strip()
        except Exception:
            answer = ""

        if not answer:
            answer = "I have partial context, but I need a bit more detail to answer that precisely."

        citation_ids: List[str] = []
        for ctx in context_data:
            source_id = ctx.get("source_id")
            if isinstance(source_id, str) and source_id and source_id not in citation_ids:
                citation_ids.append(source_id)
        citation_ids = citation_ids[:3]

        return {
            "planning_output": {
                "answer_points": [answer],
                "citations": citation_ids,
                "follow_up_question": "",
                "confidence": 0.55,
                "teaching_questions": [],
                "render_strategy": "source_faithful",
                "reasoning_trace": "Deterministic direct-answer plan for do-you-know probe.",
            },
            "intent_label": persona_trace.get("intent_label"),
            "persona_module_ids": persona_trace.get("module_ids", []),
            "persona_spec_version": persona_trace.get("persona_spec_version"),
            "persona_prompt_variant": persona_trace.get("persona_prompt_variant"),
            "reasoning_history": (state.get("reasoning_history") or []) + [
                "Planner: deterministic direct-answer path for do-you-know query."
            ],
        }

    # Deterministic direct-answer path for comparative "should we use X or Y"
    # questions when recommendation-style evidence is present.
    q_lower = (user_query or "").strip().lower()
    if (
        context_data
        and " or " in q_lower
        and re.search(r"\bshould\s+(?:i|we)\s+use\b", q_lower)
    ):
        answer_points: List[str] = []
        citation_ids: List[str] = []
        sentence_candidates: List[str] = []

        query_text = (user_query or "").strip()
        option_a = ""
        option_b = ""
        option_match = re.search(
            r"\bshould\s+(?:i|we)\s+use\s+(.+?)\s+or\s+(.+)",
            query_text,
            flags=re.IGNORECASE,
        )
        if option_match:
            option_a = re.sub(r"\bfor\b.*$", "", option_match.group(1), flags=re.IGNORECASE).strip(" ,.?")
            option_b = re.sub(r"\bfor\b.*$", "", option_match.group(2), flags=re.IGNORECASE).strip(" ,.?")

        def _normalize_sentence(raw: str) -> str:
            return re.sub(r"\s+", " ", raw.strip().lstrip("-*").strip())

        def _collect_sentence(raw: str) -> None:
            sentence = _normalize_sentence(raw)
            if sentence and sentence not in sentence_candidates:
                sentence_candidates.append(sentence)

        def _keywords(text: str) -> List[str]:
            stopwords = {"and", "the", "for", "our", "your", "with", "from", "into", "that", "this", "use"}
            tokens = re.findall(r"[a-z0-9][a-z0-9._-]*", text.lower())
            return [tok for tok in tokens if len(tok) > 2 and tok not in stopwords]

        option_keywords = _keywords(option_a) + _keywords(option_b)
        if not option_keywords:
            option_keywords = _keywords(query_text)

        def _pick_sentence(cues: List[str], *, require_option: bool = False, used: Optional[set] = None) -> str:
            used_set = used or set()
            for sentence in sentence_candidates:
                if sentence in used_set:
                    continue
                lowered = sentence.lower()
                if require_option and option_keywords and not any(tok in lowered for tok in option_keywords):
                    continue
                if any(cue in lowered for cue in cues):
                    return sentence
            return ""

        for ctx in context_data:
            source_id = ctx.get("source_id")
            if isinstance(source_id, str) and source_id and source_id not in citation_ids:
                citation_ids.append(source_id)

            text = (ctx.get("text") or "")
            for raw_sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
                _collect_sentence(raw_sentence)
            for raw_line in text.splitlines():
                line = _normalize_sentence(raw_line)
                if not line:
                    continue
                lowered = line.lower()
                if (
                    lowered.startswith("recommendation:")
                    or lowered.startswith("assumptions:")
                    or lowered.startswith("why:")
                ):
                    if line not in answer_points:
                        answer_points.append(line)
                if len(answer_points) >= 3:
                    break
            if len(answer_points) >= 3:
                break

        if not answer_points and sentence_candidates:
            recommendation_cues = [
                "recommend",
                "start with",
                "prefer",
                "choose",
                "best",
                "better",
                "managed platform",
                "containers",
                "serverless",
            ]
            assumption_primary_cues = [
                "early-stage",
                "early stage",
                "small team",
                "startup",
                "founding team",
                "for an",
                "for a",
            ]
            assumption_secondary_cues = [
                "mvp",
                "if ",
                "when ",
                "assum",
            ]
            why_primary_cues = [
                "cold start",
                "timeout",
                "constraint",
                "risk",
                "tradeoff",
                "latency",
                "slow",
                "cost",
                "overhead",
            ]
            why_secondary_cues = [
                "because",
                "due",
                "can",
                "could",
                "might",
                "debug",
            ]

            recommendation_sentence = _pick_sentence(
                recommendation_cues,
                require_option=True,
                used=set(),
            )
            if not recommendation_sentence:
                recommendation_sentence = sentence_candidates[0]

            why_sentence = _pick_sentence(
                why_primary_cues,
                used={recommendation_sentence},
            )
            if not why_sentence:
                why_sentence = _pick_sentence(
                    why_secondary_cues,
                    used={recommendation_sentence},
                )
            if not why_sentence:
                why_sentence = next(
                    (
                        sentence
                        for sentence in sentence_candidates
                        if sentence != recommendation_sentence
                    ),
                    recommendation_sentence,
                )

            assumptions_sentence = _pick_sentence(
                assumption_primary_cues,
                used={why_sentence},
            )
            if not assumptions_sentence:
                assumptions_sentence = _pick_sentence(
                    assumption_secondary_cues,
                    used={why_sentence},
                )
            if not assumptions_sentence:
                assumptions_sentence = recommendation_sentence

            if why_sentence == recommendation_sentence:
                why_sentence = next(
                    (
                        sentence
                        for sentence in sentence_candidates
                        if sentence != recommendation_sentence
                    ),
                    recommendation_sentence,
                )
            if assumptions_sentence == why_sentence and assumptions_sentence != recommendation_sentence:
                assumptions_sentence = recommendation_sentence

            synthesized_points = [
                f"Recommendation: {recommendation_sentence}".strip(),
                f"Assumptions: {assumptions_sentence}".strip(),
                f"Why: {why_sentence}".strip(),
            ]
            answer_points = [point for point in synthesized_points if point.split(":", 1)[1].strip()]

        if answer_points:
            return {
                "planning_output": {
                    "answer_points": answer_points[:3],
                    "citations": citation_ids[:3],
                    "follow_up_question": "",
                    "confidence": 0.9,
                    "teaching_questions": [],
                    "render_strategy": "source_faithful",
                    "reasoning_trace": "Deterministic comparison recommendation extracted from evidence.",
                },
                "intent_label": persona_trace.get("intent_label"),
                "persona_module_ids": persona_trace.get("module_ids", []),
                "persona_spec_version": persona_trace.get("persona_spec_version"),
                "persona_prompt_variant": persona_trace.get("persona_prompt_variant"),
                "reasoning_history": (state.get("reasoning_history") or []) + [
                    "Planner: deterministic comparison plan from recommendation evidence."
                ],
            }

    # Adaptive grounding policy:
    # - high confidence retrieval: allow conversational synthesis (default planner path)
    # - mid confidence retrieval: keep source-faithful extractive rendering
    # - low confidence retrieval: owner-specific questions should abstain
    if context_data and mode in {"QA_FACT", "QA_RELATIONSHIP", "STANCE_GLOBAL"}:
        profile = _classify_grounding_policy(context_data, user_query)
        profile_level = profile.get("level", "disabled")

        if profile_level == "mid":
            query_tokens = _planner_query_tokens(user_query)
            answer_points, citation_ids, max_score = _collect_source_faithful_points(context_data, query_tokens)
            if answer_points:
                confidence = 0.78 if max_score >= 1.0 else 0.70
                return {
                    "planning_output": {
                        "answer_points": answer_points,
                        "citations": citation_ids,
                        "follow_up_question": "",
                        "confidence": confidence,
                        "teaching_questions": [],
                        "render_strategy": "source_faithful",
                        "reasoning_trace": (
                            "Adaptive grounding policy selected extractive rendering "
                            f"(level=mid, top_score={profile.get('top_score', 0.0):.3f}, "
                            f"margin={profile.get('margin', 0.0):.3f}, "
                            f"best_overlap={profile.get('best_overlap', 0.0):.3f})."
                        ),
                    },
                    "intent_label": persona_trace.get("intent_label"),
                    "persona_module_ids": persona_trace.get("module_ids", []),
                    "persona_spec_version": persona_trace.get("persona_spec_version"),
                    "persona_prompt_variant": persona_trace.get("persona_prompt_variant"),
                    "reasoning_history": (state.get("reasoning_history") or []) + [
                        "Planner: adaptive grounding policy chose source-faithful mode (mid confidence)."
                    ],
                }

        if profile_level == "low" and target_owner_scope:
            return {
                "planning_output": {
                    "answer_points": [UNCERTAINTY_RESPONSE],
                    "citations": [],
                    "follow_up_question": "",
                    "confidence": 0.2,
                    "teaching_questions": [],
                    "reasoning_trace": (
                        "Adaptive grounding policy blocked owner-specific synthesis "
                        f"(level=low, top_score={profile.get('top_score', 0.0):.3f}, "
                        f"margin={profile.get('margin', 0.0):.3f}, "
                        f"best_overlap={profile.get('best_overlap', 0.0):.3f})."
                    ),
                },
                "intent_label": persona_trace.get("intent_label"),
                "persona_module_ids": persona_trace.get("module_ids", []),
                "persona_spec_version": persona_trace.get("persona_spec_version"),
                "persona_prompt_variant": persona_trace.get("persona_prompt_variant"),
                "reasoning_history": (state.get("reasoning_history") or []) + [
                    "Planner: adaptive grounding policy forced uncertainty for low-confidence owner query."
                ],
            }

    # Owner-specific requests without sufficient evidence should be explicit
    # about uncertainty; only owner_training mode should prompt for teaching.
    if not context_data and target_owner_scope and mode in {"QA_FACT", "QA_RELATIONSHIP", "STANCE_GLOBAL", "TEACHING"}:
        interaction_context = (state.get("interaction_context") or "owner_chat").strip().lower()
        is_training_context = interaction_context == "owner_training"
        return {
            "planning_output": {
                "answer_points": [UNCERTAINTY_RESPONSE],
                "citations": [],
                "follow_up_question": (
                    "Can you share the source or clarify what I should say for this?"
                    if is_training_context
                    else ""
                ),
                "confidence": 0.2,
                "teaching_questions": (
                    [
                        f"What should I answer when asked: \"{user_query}\"?",
                        "Do you have a source, quote, or document I should use for this topic?",
                    ]
                    if is_training_context
                    else []
                ),
                "reasoning_trace": "Owner-specific query without sufficient evidence.",
            },
            "intent_label": persona_trace.get("intent_label"),
            "persona_module_ids": persona_trace.get("module_ids", []),
            "persona_spec_version": persona_trace.get("persona_spec_version"),
            "persona_prompt_variant": persona_trace.get("persona_prompt_variant"),
            "reasoning_history": (state.get("reasoning_history") or []) + [
                "Planner: deterministic owner uncertainty plan (insufficient evidence)."
            ],
        }

    # Deterministic generic fallback: if no owner evidence is available for a
    # non-owner-specific query, keep the conversation useful with general help.
    if not context_data and not target_owner_scope and mode in {"QA_FACT", "QA_RELATIONSHIP", "STANCE_GLOBAL"}:
        generic_prompt = f"""You are Shambhavi, a pragmatic VC partner running founder office hours.
Answer the user's message using general startup/VC knowledge.

Rules:
- Do NOT claim this came from owner's private sources or documents.
- Be useful first: give concrete guidance, not generic filler.
- If the user asks for tactical help (GTM, pricing, pilots, interviews, metrics), provide a compact action plan.
- Prefer 3-5 bullets for action plans, each with one specific action and one measurable check.
- If context is missing, ask one clarifying question after giving a reasonable default.
- Keep tone direct, calm, and coach-like.

User message: {user_query}
"""
        try:
            generic_answer, _meta = await invoke_text(
                [{"role": "system", "content": generic_prompt}],
                task="realizer",
                temperature=0.3,
                max_tokens=320,
            )
            answer = (generic_answer or "").strip()
        except Exception:
            answer = ""

        if not answer:
            answer = "Happy to help. Share a bit more context and I can give you a concrete recommendation."

        return {
            "planning_output": {
                "answer_points": [answer],
                "citations": [],
                "follow_up_question": "",
                "confidence": 0.45,
                "teaching_questions": [],
                "reasoning_trace": "No owner evidence for non-owner-specific query; general fallback answer.",
            },
            "intent_label": persona_trace.get("intent_label"),
            "persona_module_ids": persona_trace.get("module_ids", []),
            "persona_spec_version": persona_trace.get("persona_spec_version"),
            "persona_prompt_variant": persona_trace.get("persona_prompt_variant"),
            "reasoning_history": (state.get("reasoning_history") or []) + [
                "Planner: deterministic general fallback plan (no evidence, non-owner-specific)."
            ],
        }

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
1. Identify the core points for the user's answer (max 3) and answer directly.
2. If in TEACHING mode, generate 2-3 specific questions for the owner.
3. Add a follow-up question ONLY when genuinely needed to unblock the user.
4. If evidence is present, map points to citations.
5. If query pattern is "do you know X" or "what is X", answer with specific facts about X first.

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

        # Prevent fabricated citation IDs from planner output.
        valid_source_ids = {
            str(res.get("source_id"))
            for res in context_data
            if isinstance(res.get("source_id"), str) and res.get("source_id")
        }
        raw_citations = plan.get("citations", []) if isinstance(plan, dict) else []
        sanitized_citations: List[str] = []
        if isinstance(raw_citations, list):
            for c in raw_citations:
                c_str = str(c)
                if c_str in valid_source_ids and c_str not in sanitized_citations:
                    sanitized_citations.append(c_str)
        if not sanitized_citations and valid_source_ids:
            sanitized_citations = list(valid_source_ids)[:3]
        plan["citations"] = sanitized_citations

        if mode != "TEACHING":
            plan["teaching_questions"] = []
        
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
        # Tag error in Langfuse
        try:
            langfuse_context.update_current_observation(
                level="ERROR",
                status_message=f"Planner failed: {str(e)[:255]}",
                metadata={
                    "error": True,
                    "error_type": type(e).__name__,
                    "error_node": "planner_node",
                }
            )
        except Exception:
            pass
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

@observe(name="realizer_node")
async def realizer_node(state: TwinState):
    """Pass B: Conversational Reification (Human-like Output)"""
    plan = state.get("planning_output", {})
    mode = state.get("dialogue_mode", "QA_FACT")
    render_strategy = str(plan.get("render_strategy", "")).strip().lower() if isinstance(plan, dict) else ""

    if render_strategy == "source_faithful":
        points = []
        for p in (plan.get("answer_points", []) if isinstance(plan, dict) else []):
            if isinstance(p, str) and p.strip():
                points.append(p.strip())

        follow_up = (plan.get("follow_up_question") if isinstance(plan, dict) else None) or ""
        response_lines: List[str] = []
        response_lines.extend(points[:3])
        if isinstance(follow_up, str) and follow_up.strip():
            response_lines.append(follow_up.strip())

        # Source-faithful mode intentionally avoids LLM rewrite/paraphrase.
        realized_text = "\n".join(response_lines).strip()
        if not realized_text:
            realized_text = UNCERTAINTY_RESPONSE

        res = AIMessage(content=realized_text)
        citations = plan.get("citations", []) if isinstance(plan, dict) else []
        teaching_questions = plan.get("teaching_questions", []) if isinstance(plan, dict) else []

        res.additional_kwargs["teaching_questions"] = teaching_questions
        res.additional_kwargs["planning_output"] = plan
        res.additional_kwargs["dialogue_mode"] = mode
        res.additional_kwargs["intent_label"] = state.get("intent_label")
        res.additional_kwargs["module_ids"] = state.get("persona_module_ids") or []
        res.additional_kwargs["requires_evidence"] = bool(state.get("requires_evidence", False))
        res.additional_kwargs["target_owner_scope"] = bool(state.get("target_owner_scope", False))
        res.additional_kwargs["router_reason"] = state.get("router_reason")
        res.additional_kwargs["router_knowledge_available"] = state.get("router_knowledge_available")
        res.additional_kwargs["render_strategy"] = "source_faithful"
        if state.get("persona_spec_version"):
            res.additional_kwargs["persona_spec_version"] = state.get("persona_spec_version")
        if state.get("persona_prompt_variant"):
            res.additional_kwargs["persona_prompt_variant"] = state.get("persona_prompt_variant")

        return {
            "messages": [res],
            "citations": citations,
            "reasoning_history": (state.get("reasoning_history") or []) + [
                "Realizer: source-faithful deterministic rendering (no paraphrase)."
            ],
        }
    
    realizer_prompt = f"""You are the Voice Realizer for a Digital Twin. 
    Take the structured plan and rewrite it into a short, natural, conversational response.
    
    PLAN:
    {json.dumps(plan, indent=2)}
    
    CONSTRAINTS:
    - 1 to 3 sentences total.
    - Sound like a real person, not a bot.
    - Include follow-up question ONLY if `follow_up_question` is non-empty and needed.
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
        res.additional_kwargs["requires_evidence"] = bool(state.get("requires_evidence", False))
        res.additional_kwargs["target_owner_scope"] = bool(state.get("target_owner_scope", False))
        res.additional_kwargs["router_reason"] = state.get("router_reason")
        res.additional_kwargs["router_knowledge_available"] = state.get("router_knowledge_available")
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
        # Tag error in Langfuse
        try:
            langfuse_context.update_current_observation(
                level="ERROR",
                status_message=f"Realizer failed: {str(e)[:255]}",
                metadata={
                    "error": True,
                    "error_type": type(e).__name__,
                    "error_node": "realizer_node",
                }
            )
        except Exception:
            pass
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
        fallback_msg.additional_kwargs["requires_evidence"] = bool(state.get("requires_evidence", False))
        fallback_msg.additional_kwargs["target_owner_scope"] = bool(state.get("target_owner_scope", False))
        fallback_msg.additional_kwargs["router_reason"] = state.get("router_reason")
        fallback_msg.additional_kwargs["router_knowledge_available"] = state.get("router_knowledge_available")

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
    resolve_default_group: bool = True,
    system_prompt_override: str = None,
    full_settings: dict = None,
    graph_context: str = "",
    owner_memory_context: str = "",
    conversation_history: Optional[List[BaseMessage]] = None
):
    # Retrieve-only tool setup needs to stay inside or be passed
    from modules.tools import get_retrieval_tool
    retrieval_tool = get_retrieval_tool(
        twin_id,
        group_id=group_id,
        conversation_history=conversation_history,
        resolve_default_group=resolve_default_group,
    )

    @observe(name="retrieve_hybrid_node")
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
                # Tag error in Langfuse
                try:
                    langfuse_context.update_current_observation(
                        level="WARNING",
                        metadata={
                            "retrieval_error": True,
                            "error_type": type(e).__name__,
                            "query": query[:200] if query else None,
                        }
                    )
                except Exception:
                    pass
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
    enforce_group_filtering: bool = True,
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

    effective_group_id = group_id if enforce_group_filtering else None

    agent = create_twin_agent(
        twin_id,
        group_id=effective_group_id,
        resolve_default_group=enforce_group_filtering,
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
        "router_reason": None,
        "router_knowledge_available": None,
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

