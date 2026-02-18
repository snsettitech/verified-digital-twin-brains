"""
Persona Intent Taxonomy

Stable intent labels and lightweight classification helpers used by runtime
persona module selection.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple


INTENT_LABELS: Tuple[str, ...] = (
    "factual_with_evidence",
    "advice_or_stance",
    "action_or_tool_execution",
    "ambiguity_or_clarify",
    "disagreement_or_conflict",
    "summarize_or_transform",
    "meta_or_system",
    "sensitive_boundary_or_refusal",
)

DEFAULT_INTENT_LABEL = "factual_with_evidence"

_INTENT_SET = set(INTENT_LABELS)


DIALOGUE_MODE_TO_INTENT: Dict[str, str] = {
    "QA_FACT": "factual_with_evidence",
    "IDENTITY_FACT": "meta_or_system",
    "QA_RELATIONSHIP": "factual_with_evidence",
    "STANCE_GLOBAL": "advice_or_stance",
    "SMALLTALK": "meta_or_system",
    "REPAIR": "disagreement_or_conflict",
    "TEACHING": "ambiguity_or_clarify",
}


def normalize_intent_label(value: Optional[str]) -> str:
    raw = (value or "").strip().lower().replace(" ", "_")
    if raw in _INTENT_SET:
        return raw
    return DEFAULT_INTENT_LABEL


def intent_from_dialogue_mode(dialogue_mode: Optional[str]) -> Optional[str]:
    if not dialogue_mode:
        return None
    return DIALOGUE_MODE_TO_INTENT.get(dialogue_mode.strip().upper())


def classify_query_intent(query: str, dialogue_mode: Optional[str] = None) -> str:
    """
    Lightweight deterministic classifier used as Phase 3 runtime fallback.
    """
    mode_intent = intent_from_dialogue_mode(dialogue_mode)
    if mode_intent:
        return mode_intent

    q = (query or "").lower()
    if not q:
        return DEFAULT_INTENT_LABEL

    if any(k in q for k in ("summarize", "rewrite", "rephrase", "translate", "transform")):
        return "summarize_or_transform"
    if any(k in q for k in ("book", "schedule", "send", "email", "create", "draft", "set up")):
        return "action_or_tool_execution"
    if any(k in q for k in ("disagree", "wrong", "not true", "you are off", "push back")):
        return "disagreement_or_conflict"
    if any(k in q for k in ("illegal", "bypass", "exploit", "hack", "weapon", "self-harm")):
        return "sensitive_boundary_or_refusal"
    if any(k in q for k in ("what should", "recommend", "advice", "would you", "stance", "opinion")):
        return "advice_or_stance"
    if any(k in q for k in ("who are you", "how do you work", "your rules", "system prompt")):
        return "meta_or_system"
    if any(k in q for k in ("not sure", "unclear", "ambiguous", "which one", "clarify")):
        return "ambiguity_or_clarify"

    return DEFAULT_INTENT_LABEL
