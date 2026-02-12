"""
Identity Confidence Gate

Deterministic gate to decide whether to answer or ask a clarification
based on Owner Memory availability and conflicts.
"""

from typing import Dict, Any, List, Optional
import re

from modules.owner_memory_store import (
    extract_topic_from_query,
    find_owner_memory_candidates,
    detect_conflicts,
    format_owner_memory_context
)
from modules.clarification_manager import build_clarification
from modules.observability import supabase


STANCE_PATTERNS = [
    r"\bwhat do you think\b",
    r"\bhow do you feel\b",
    r"\bwhat is your stance\b",
    r"\bwould you\b",
    r"\bshould i\b",
    r"\bshould we\b",
    r"\bshould you\b",
    r"\brecommend\b",
    r"\bopinion\b",
    r"\bview\b",
    r"\bbelieve\b",
    r"\bdo you support\b",
    r"\bis it a good idea\b",
    r"\bdo you agree\b",
]

PREFERENCE_KEYWORDS = {"prefer", "preference", "like", "dislike", "favorite", "favourite", "avoid"}
TONE_KEYWORDS = {"tone", "voice", "style", "sound", "wording", "phrasing"}
LENS_KEYWORDS = {"lens", "framework", "principle", "values", "philosophy"}
BELIEF_KEYWORDS = {"belief", "conviction"}
GOAL_KEYWORDS = {"goal", "goals", "objective", "objectives", "aim", "aims", "target"}
INTENT_KEYWORDS = {"intent", "intention", "trying to", "want to", "plan to", "planning to"}
CONSTRAINT_KEYWORDS = {"constraint", "constraints", "limitation", "limitations", "restricted", "must", "can't", "cannot"}
BOUNDARY_KEYWORDS = {"boundary", "boundaries", "won't", "will not", "never"}


def _contains_any(text: str, keywords: set) -> bool:
    return any(k in text for k in keywords)


def _load_intent_profile(twin_id: str) -> Dict[str, str]:
    try:
        twin_res = supabase.rpc("get_twin_system", {"t_id": twin_id}).single().execute()
        settings = twin_res.data.get("settings", {}) if twin_res.data else {}
        profile = settings.get("intent_profile") or {}
        if not isinstance(profile, dict):
            return {}
        return {
            "use_case": (profile.get("use_case") or "").strip(),
            "audience": (profile.get("audience") or "").strip(),
            "boundaries": (profile.get("boundaries") or "").strip()
        }
    except Exception as e:
        print(f"[IdentityGate] Failed to load intent profile: {e}")
        return {}


def _intent_profile_to_memories(
    profile: Dict[str, str],
    include_use_case: bool,
    include_audience: bool,
    include_boundaries: bool,
    boundary_memory_type: str
) -> List[Dict[str, Any]]:
    memories: List[Dict[str, Any]] = []
    use_case = (profile.get("use_case") or "").strip()
    audience = (profile.get("audience") or "").strip()
    boundaries = (profile.get("boundaries") or "").strip()

    if include_use_case and use_case:
        memories.append({
            "memory_type": "belief",
            "topic_normalized": "intent",
            "value": use_case,
            "confidence": 0.9
        })
    if include_audience and audience:
        memories.append({
            "memory_type": "belief",
            "topic_normalized": "audience",
            "value": audience,
            "confidence": 0.9
        })
    if include_boundaries and boundaries:
        memories.append({
            "memory_type": boundary_memory_type or "tone_rule",
            "topic_normalized": "boundaries",
            "value": boundaries,
            "confidence": 0.9
        })
    return memories


def classify_query(query: str) -> Dict[str, Any]:
    q = (query or "").lower()

    if _contains_any(q, TONE_KEYWORDS):
        return {"requires_owner": True, "memory_type": "tone_rule"}
    if _contains_any(q, LENS_KEYWORDS):
        return {"requires_owner": True, "memory_type": "lens"}
    if _contains_any(q, PREFERENCE_KEYWORDS):
        return {"requires_owner": True, "memory_type": "preference"}
    if _contains_any(q, BELIEF_KEYWORDS):
        return {"requires_owner": True, "memory_type": "belief"}
    if _contains_any(q, GOAL_KEYWORDS) or _contains_any(q, INTENT_KEYWORDS):
        return {"requires_owner": True, "memory_type": "belief"}
    if _contains_any(q, CONSTRAINT_KEYWORDS):
        return {"requires_owner": True, "memory_type": "lens"}
    if _contains_any(q, BOUNDARY_KEYWORDS):
        return {"requires_owner": True, "memory_type": "tone_rule"}

    for pattern in STANCE_PATTERNS:
        if re.search(pattern, q):
            return {"requires_owner": True, "memory_type": "stance"}

    # Decision verbs imply stance even if not in patterns
    if "should" in q or "recommend" in q or "ought" in q:
        return {"requires_owner": True, "memory_type": "stance"}

    return {"requires_owner": False, "memory_type": None}


async def run_identity_gate(
    query: str,
    history: Optional[List[Dict[str, Any]]],
    twin_id: str,
    tenant_id: Optional[str],
    group_id: Optional[str],
    mode: str = "owner"
) -> Dict[str, Any]:
    """
    Returns a decision dict:
    - decision: "ANSWER" | "CLARIFY"
    - memory_type, topic, owner_memory, owner_memory_refs
    - question, options, memory_write_proposal (if CLARIFY)
    """
    classification = classify_query(query)
    requires_owner = classification["requires_owner"]
    memory_type = classification["memory_type"]

    if not requires_owner:
        return {
            "decision": "ANSWER",
            "requires_owner": False,
            "reason": "not_stance_query",
            "owner_memory": [],
            "owner_memory_refs": [],
            "owner_memory_context": ""
        }

    q_lower = (query or "").lower()
    wants_intent = _contains_any(q_lower, GOAL_KEYWORDS) or _contains_any(q_lower, INTENT_KEYWORDS)
    wants_constraints = _contains_any(q_lower, CONSTRAINT_KEYWORDS)
    wants_boundaries = _contains_any(q_lower, BOUNDARY_KEYWORDS)

    topic = extract_topic_from_query(query, history)
    candidates = find_owner_memory_candidates(
        query=query,
        twin_id=twin_id,
        topic_normalized=topic,
        memory_type=memory_type
    )

    # Thresholds
    best_score = candidates[0].get("_score", 0.0) if candidates else 0.0
    has_conflict = detect_conflicts(candidates[:3]) if candidates else False

    if not candidates or best_score < 0.70 or has_conflict:
        # Phase 4/5 integration: preference queries are safe to defer to the main agent
        # (which already enforces evidence for person-specific queries) rather than forcing
        # a clarification loop here. This improves UX for realtime-ingested persona facts.
        if memory_type == "preference":
            return {
                "decision": "ANSWER",
                "requires_owner": True,
                "memory_type": memory_type,
                "topic": topic,
                "reason": "missing_owner_memory_preference_defer_to_agent",
                "owner_memory": [],
                "owner_memory_refs": [],
                "owner_memory_context": ""
            }
        if not candidates or best_score < 0.70:
            if wants_intent or wants_constraints or wants_boundaries:
                profile = _load_intent_profile(twin_id)
                if profile:
                    intent_memories = _intent_profile_to_memories(
                        profile=profile,
                        include_use_case=wants_intent,
                        include_audience=wants_intent,
                        include_boundaries=(wants_boundaries or wants_constraints),
                        boundary_memory_type=memory_type if memory_type in {"lens", "tone_rule"} else "tone_rule"
                    )
                    if intent_memories:
                        return {
                            "decision": "ANSWER",
                            "requires_owner": True,
                            "memory_type": memory_type,
                            "topic": topic,
                            "reason": "intent_profile_fallback",
                            "owner_memory": intent_memories,
                            "owner_memory_refs": [],
                            "owner_memory_context": format_owner_memory_context(intent_memories)
                        }
        clarification = build_clarification(query, topic, memory_type or "stance")
        return {
            "decision": "CLARIFY",
            "requires_owner": True,
            "memory_type": memory_type or "stance",
            "topic": topic,
            "reason": "missing_or_conflicting",
            "question": clarification["question"],
            "options": clarification["options"],
            "memory_write_proposal": clarification["memory_write_proposal"],
            "owner_memory": [],
            "owner_memory_refs": []
        }

    # Use best memory for answer
    owner_memory_refs = [m.get("id") for m in candidates[:3] if m.get("id")]
    owner_memory_context = format_owner_memory_context(candidates[:3])

    return {
        "decision": "ANSWER",
        "requires_owner": True,
        "memory_type": memory_type,
        "topic": topic,
        "reason": "memory_found",
        "owner_memory": candidates[:3],
        "owner_memory_refs": owner_memory_refs,
        "owner_memory_context": owner_memory_context
    }
