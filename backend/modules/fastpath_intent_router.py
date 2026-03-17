"""
Lightweight deterministic intent router for identity/persona fast-path.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional


def is_persona_fastpath_enabled() -> bool:
    return os.getenv("PERSONA_FASTPATH_ENABLED", "false").strip().lower() == "true"


def is_persona_draft_profile_allowed() -> bool:
    return os.getenv("PERSONA_DRAFT_PROFILE_ALLOWED", "false").strip().lower() == "true"


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def classify_fastpath_intent(query: str) -> Dict[str, Any]:
    q = _normalize(query)
    if not q:
        return {"matched": False, "intent": None}

    intent_patterns = [
        ("identity_intro", (r"\bwho are you\b", r"\bintroduce yourself\b")),
        ("identity_about", (r"\btell me about yourself\b", r"\babout you\b")),
        (
            "identity_role",
            (
                r"\bwhat public role\b",
                r"\bwhat role\b",
                r"\bwhat position\b",
                r"\bwhat office\b",
                r"\bwhat title\b",
                r"\bwhat are you associated with\b",
                r"\bwhat role are you associated with\b",
            ),
        ),
        (
            "identity_background",
            (
                r"\bwhat(?:'s| is)? your background\b",
                r"\bhow did you get into\b",
                r"\bhow you got into\b",
                r"\bhow did you become\b",
                r"\bhow did you start\b",
                r"\bwhat experience led\b",
                r"\bcareer path\b",
                r"\bget into politics\b",
                r"\bpublic life\b",
            ),
        ),
        (
            "authenticity_disclosure",
            (
                r"\bare you really\b",
                r"\bare you the real\b",
                r"\bare you actually\b",
            ),
        ),
        (
            "contact_handoff",
            (
                r"\bcan i talk to\b",
                r"\bhow can i contact\b",
                r"\bhow do i reach\b",
                r"\bdirectly\b",
            ),
        ),
        (
            "scope_help",
            (
                r"\bwhat can you help\b",   # catches "help with" and "help me with"
                r"\bwhat can you do\b",
                r"\bhow can you help\b",
                r"\bwhat topics\b",
                r"\bwhat subjects\b",
                r"\bwhat are your areas\b",
            ),
        ),
    ]

    for intent, patterns in intent_patterns:
        if any(re.search(pattern, q) for pattern in patterns):
            return {"matched": True, "intent": intent}

    return {"matched": False, "intent": None}


def is_identity_fastpath_intent(intent: Optional[str]) -> bool:
    return intent in {
        "identity_intro",
        "identity_about",
        "identity_role",
        "identity_background",
        "authenticity_disclosure",
        "contact_handoff",
        "scope_help",
    }
