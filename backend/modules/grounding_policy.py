from __future__ import annotations

import re
from typing import Any, Dict


_SMALLTALK_MARKERS = {
    "hi",
    "hello",
    "hey",
    "yo",
    "good morning",
    "good afternoon",
    "good evening",
    "thanks",
    "thank you",
    "ok",
    "okay",
    "cool",
    "sounds good",
    "got it",
    "understood",
    "how are you",
    "what's up",
    "whats up",
}

_IDENTITY_MARKERS = (
    "who are you",
    "what are you",
    "introduce yourself",
    "tell me about yourself",
    "what do you do",
    "what can you do",
)

_PROCEDURAL_MARKERS = (
    "how to",
    "how do",
    "how should",
    "how can",
    "workflow",
    "steps",
    "process",
    "use this twin",
    "use the twin",
)

_EVALUATIVE_MARKERS = (
    "should",
    "recommend",
    "tradeoff",
    "trade-off",
    "versus",
    " vs ",
    "would this twin",
    "would you invest",
    "would you like",
)

_QUOTE_PATTERNS = (
    r"\bquote\b",
    r"\bverbatim\b",
    r"\bexact (line|phrase|text|quote)\b",
    r"\bonly the exact\b",
    r"\bshow (me )?the exact\b",
)

_EXPLICIT_SOURCE_MARKERS = (
    "based on my sources",
    "from my sources",
    "from my documents",
    "from my knowledge",
    "cite",
    "citation",
    "according to my",
)

_OWNER_STRICT_PATTERNS = (
    r"\bwhat (do|did) i think\b",
    r"\bwhat('?s| is) my (stance|view|opinion|belief|thesis|principle)\b",
    r"\bmy (stance|view|opinion|belief|thesis|principle)\b",
    r"\bhow do i (approach|decide|evaluate)\b",
    r"\bwhat (is|was) my\b",
)


def _normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", str(query or "").strip().lower())


def _is_smalltalk(q: str) -> bool:
    if not q:
        return False
    q_plain = re.sub(r"[^a-z0-9\s']", "", q)
    if q in _SMALLTALK_MARKERS or q_plain in _SMALLTALK_MARKERS:
        return True
    return any(marker in q for marker in ("how's your day", "hows your day"))


def _query_class(q: str, is_smalltalk: bool) -> str:
    if is_smalltalk:
        return "smalltalk"
    if any(marker in q for marker in _IDENTITY_MARKERS):
        return "identity"
    if any(marker in q for marker in _PROCEDURAL_MARKERS):
        return "procedural"
    if any(marker in q for marker in _EVALUATIVE_MARKERS):
        return "evaluative"
    return "factual"


def _quote_intent(q: str) -> bool:
    if not q:
        return False
    return any(re.search(pattern, q) for pattern in _QUOTE_PATTERNS)


def _strict_grounding(q: str, query_class: str) -> bool:
    if not q or query_class == "smalltalk":
        return False
    if any(marker in q for marker in _EXPLICIT_SOURCE_MARKERS):
        return True
    if any(re.search(pattern, q) for pattern in _OWNER_STRICT_PATTERNS):
        return True
    return False


def get_grounding_policy(query: str, *, interaction_context: str | None = None) -> Dict[str, Any]:
    """
    Deterministic policy table used by chat/router/planner/online-eval.
    """
    q = _normalize_query(query)
    smalltalk = _is_smalltalk(q)
    query_class = _query_class(q, smalltalk)
    quote_intent = _quote_intent(q)
    requires_evidence = not smalltalk
    strict_grounding = _strict_grounding(q, query_class)
    allow_line_extractor = bool(quote_intent and requires_evidence)
    return {
        "query_class": query_class,
        "is_smalltalk": smalltalk,
        "quote_intent": quote_intent,
        "requires_evidence": requires_evidence,
        "strict_grounding": strict_grounding,
        "allow_line_extractor": allow_line_extractor,
        "interaction_context": (interaction_context or "").strip().lower() if interaction_context else None,
    }

