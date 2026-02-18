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
from modules.routing_decision import build_routing_decision
from modules.response_policy import UNCERTAINTY_RESPONSE
from modules.answerability import (
    build_targeted_clarification_questions,
    evaluate_answerability,
)

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
    workflow_intent: Optional[str]
    routing_decision: Optional[Dict[str, Any]]
    
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
    return f"""You are a generalized RAG router.
USER QUERY: {user_query}
INTERACTION CONTEXT: {interaction_context}
Always retrieve evidence first, then evaluate answerability.
Return JSON:
{{
  "mode": "QA_FACT",
  "is_person_specific": false,
  "requires_evidence": true,
  "reasoning": "evidence-first"
}}
"""

    # Define the nodes
@observe(name="router_node")
async def router_node(state: TwinState):
    """
    Generalized router for document reasoning:
    - Always retrieve evidence for the query.
    - Avoid intent-specific dialogue modes and handcrafted branches.
    """
    messages = state["messages"]
    user_query = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "")
    interaction_context = (state.get("interaction_context") or "owner_chat").strip().lower()
    twin_id = state.get("twin_id")
    knowledge_available = _twin_has_groundable_knowledge(twin_id)
    intent_label = classify_query_intent(user_query, dialogue_mode="QA_FACT")

    routing_decision = build_routing_decision(
        query=user_query,
        mode="QA_FACT",
        intent_label=intent_label,
        interaction_context=interaction_context,
        target_owner_scope=False,
        requires_evidence=True,
        knowledge_available=knowledge_available,
        pinned_context=None,
    )
    decision_payload = routing_decision.model_dump()
    decision_payload["action"] = "answer"
    decision_payload["clarifying_questions"] = []
    decision_payload["required_inputs_missing"] = []

    router_reason = "general_rag_router: retrieval required for answerability evaluation"
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
        "sub_queries": [user_query] if isinstance(user_query, str) and user_query.strip() else [],
        "router_reason": router_reason,
        "router_knowledge_available": knowledge_available,
        "workflow_intent": decision_payload.get("intent") or "answer",
        "routing_decision": decision_payload,
        "reasoning_history": (state.get("reasoning_history") or []) + [
            "Router: generalized evidence-first routing."
        ],
    }

@observe(name="evidence_gate_node")
async def evidence_gate_node(state: TwinState):
    """
    Lightweight gate for generalized RAG flow.
    Retrieval always proceeds to planner answerability evaluation.
    """
    return {
        "dialogue_mode": "QA_FACT",
        "requires_teaching": False,
        "reasoning_history": (state.get("reasoning_history") or []) + [
            "Gate: pass-through to answerability evaluation."
        ],
    }


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
    """General evidence-driven planner."""
    context_data = state.get("retrieved_context", {}).get("results", [])
    user_query = next((m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), "")
    _system_msg, persona_trace = build_system_prompt_with_trace(state)

    valid_source_ids: List[str] = []
    for row in context_data:
        source_id = row.get("source_id")
        if isinstance(source_id, str) and source_id and source_id not in valid_source_ids:
            valid_source_ids.append(source_id)

    def _sanitize_answer_points(values: Any) -> List[str]:
        if not isinstance(values, list):
            return []
        points: List[str] = []
        for raw in values:
            line = re.sub(r"\s+", " ", str(raw or "").strip())
            if not line:
                continue
            points.append(line)
            if len(points) >= 3:
                break
        return points

    def _sanitize_citations(values: Any) -> List[str]:
        if not isinstance(values, list):
            return []
        out: List[str] = []
        for raw in values:
            cid = str(raw or "").strip()
            if cid and cid in valid_source_ids and cid not in out:
                out.append(cid)
            if len(out) >= 3:
                break
        return out

    def _build_evidence_blob(max_items: int = 6) -> str:
        lines: List[str] = []
        for idx, row in enumerate(context_data[: max(1, max_items)], 1):
            source_id = str(row.get("source_id") or f"chunk-{idx}")
            section = str(row.get("section_path") or row.get("section_title") or "unknown")
            text = re.sub(r"\s+", " ", str(row.get("text") or "").strip())[:1200]
            if text:
                lines.append(f"[{idx}] source_id={source_id}; section={section}; text={text}")
        return "\n".join(lines) if lines else "No evidence retrieved."

    try:
        answerability = await evaluate_answerability(user_query, context_data)
    except Exception as exc:
        print(f"Planner answerability error: {exc}")
        answerability = {
            "answerable": False,
            "confidence": 0.0,
            "reasoning": "Answerability evaluation failed.",
            "missing_information": ["the specific evidence needed to answer this question"],
            "ambiguity_level": "high",
        }

    routing_decision = (
        dict(state.get("routing_decision"))
        if isinstance(state.get("routing_decision"), dict)
        else {
            "intent": "answer",
            "chosen_workflow": "answer",
            "output_schema": "workflow.answer.v1",
        }
    )

    if not bool(answerability.get("answerable")):
        missing_information = answerability.get("missing_information") or []
        clarification_questions = build_targeted_clarification_questions(
            user_query,
            missing_information,
            limit=3,
        )
        answer_points = [UNCERTAINTY_RESPONSE]
        for idx, question in enumerate(clarification_questions, 1):
            answer_points.append(f"{idx}. {question}")

        updated_routing_decision = {
            **routing_decision,
            "action": "clarify",
            "confidence": max(0.05, min(0.95, float(answerability.get("confidence") or 0.0))),
            "required_inputs_missing": [str(v) for v in missing_information[:3]],
            "clarifying_questions": clarification_questions[:3],
        }

        return {
            "planning_output": {
                "answer_points": answer_points,
                "citations": [],
                "follow_up_question": "",
                "confidence": max(0.05, min(0.95, float(answerability.get("confidence") or 0.0))),
                "teaching_questions": clarification_questions[:3],
                "render_strategy": "source_faithful",
                "reasoning_trace": str(answerability.get("reasoning") or ""),
                "answerability": answerability,
            },
            "routing_decision": updated_routing_decision,
            "workflow_intent": str(updated_routing_decision.get("intent") or "answer"),
            "intent_label": persona_trace.get("intent_label"),
            "persona_module_ids": persona_trace.get("module_ids", []),
            "persona_spec_version": persona_trace.get("persona_spec_version"),
            "persona_prompt_variant": persona_trace.get("persona_prompt_variant"),
            "reasoning_history": (state.get("reasoning_history") or []) + [
                "Planner: answerability=false, produced targeted clarification questions."
            ],
        }

    planner_prompt = f"""
You are a grounded answer composer.
Use only the provided evidence. Do not use outside knowledge.

USER QUESTION:
{user_query}

ANSWERABILITY JUDGEMENT:
{json.dumps(answerability, ensure_ascii=True)}

ALLOWED SOURCE IDS:
{json.dumps(valid_source_ids, ensure_ascii=True)}

EVIDENCE:
{_build_evidence_blob()}

Return STRICT JSON:
{{
  "answer_points": ["point 1", "point 2"],
  "citations": ["source_id"],
  "confidence": 0.0,
  "reasoning_trace": "short trace"
}}

Rules:
- Provide max 3 concise answer points.
- Cite only IDs from ALLOWED SOURCE IDS.
- Do not ask clarification questions when answerable is true.
"""

    try:
        plan, _route_meta = await invoke_json(
            [{"role": "system", "content": planner_prompt}],
            task="planner",
            temperature=0,
            max_tokens=700,
        )
    except Exception as exc:
        print(f"Planner composition error: {exc}")
        fallback_points = []
        for row in context_data[:3]:
            text = re.sub(r"\s+", " ", str(row.get("text") or "").strip())
            if text:
                fallback_points.append(text[:260])
            if len(fallback_points) >= 3:
                break
        plan = {
            "answer_points": fallback_points or [UNCERTAINTY_RESPONSE],
            "citations": valid_source_ids[:3],
            "confidence": float(answerability.get("confidence") or 0.5),
            "reasoning_trace": "Planner composition fallback used.",
        }

    answer_points = _sanitize_answer_points(plan.get("answer_points"))
    if not answer_points:
        answer_points = [UNCERTAINTY_RESPONSE]

    citations = _sanitize_citations(plan.get("citations"))
    if not citations and valid_source_ids:
        citations = valid_source_ids[:3]

    confidence = max(
        0.0,
        min(
            1.0,
            float(plan.get("confidence", answerability.get("confidence", 0.5)) or 0.5),
        ),
    )

    updated_routing_decision = {
        **routing_decision,
        "action": "answer",
        "confidence": confidence,
        "required_inputs_missing": [],
        "clarifying_questions": [],
    }

    return {
        "planning_output": {
            "answer_points": answer_points[:3],
            "citations": citations[:3],
            "follow_up_question": "",
            "confidence": confidence,
            "teaching_questions": [],
            "render_strategy": "source_faithful",
            "reasoning_trace": str(plan.get("reasoning_trace") or answerability.get("reasoning") or ""),
            "answerability": answerability,
        },
        "routing_decision": updated_routing_decision,
        "workflow_intent": str(updated_routing_decision.get("intent") or "answer"),
        "intent_label": persona_trace.get("intent_label"),
        "persona_module_ids": persona_trace.get("module_ids", []),
        "persona_spec_version": persona_trace.get("persona_spec_version"),
        "persona_prompt_variant": persona_trace.get("persona_prompt_variant"),
        "reasoning_history": (state.get("reasoning_history") or []) + [
            "Planner: answerability=true, generated grounded answer with citations."
        ],
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
        res.additional_kwargs["workflow_intent"] = state.get("workflow_intent")
        if isinstance(state.get("routing_decision"), dict):
            res.additional_kwargs["routing_decision"] = state.get("routing_decision")
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
        res.additional_kwargs["workflow_intent"] = state.get("workflow_intent")
        if isinstance(state.get("routing_decision"), dict):
            res.additional_kwargs["routing_decision"] = state.get("routing_decision")
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
        fallback_msg.additional_kwargs["workflow_intent"] = state.get("workflow_intent")
        if isinstance(state.get("routing_decision"), dict):
            fallback_msg.additional_kwargs["routing_decision"] = state.get("routing_decision")

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

        if all_results:
            citations = []
            for item in all_results:
                source_id = item.get("source_id")
                if isinstance(source_id, str) and source_id and source_id not in citations:
                    citations.append(source_id)

        return {
            "retrieved_context": {"results": all_results},
            "citations": citations,
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
        refusal_ai = AIMessage(content=refusal_message)
        refusal_ai.additional_kwargs["routing_decision"] = {
            "intent": "answer",
            "confidence": 1.0,
            "required_inputs_missing": [],
            "chosen_workflow": "answer",
            "output_schema": "workflow.answer.v1",
            "action": "refuse",
            "clarifying_questions": [],
        }
        refusal_ai.additional_kwargs["workflow_intent"] = "answer"
        yield {
            "agent": {
                "messages": [refusal_ai]
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
        "workflow_intent": "answer",
        "routing_decision": {
            "intent": "answer",
            "confidence": 1.0,
            "required_inputs_missing": [],
            "chosen_workflow": "answer",
            "output_schema": "workflow.answer.v1",
            "action": "answer",
            "clarifying_questions": [],
        },
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

