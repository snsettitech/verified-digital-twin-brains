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
        return {"matched": False, "intent": None, "confidence": 0.0}

    intent_patterns = [
        ("identity_intro", (r"\bwho are you\b", r"\bintroduce yourself\b"), 0.96),
        ("identity_about", (r"\btell me about yourself\b", r"\babout you\b"), 0.94),
        (
            "authenticity_disclosure",
            (
                r"\bare you really\b",
                r"\bare you the real\b",
                r"\bare you actually\b",
            ),
            0.95,
        ),
        (
            "contact_handoff",
            (
                r"\bcan i talk to\b",
                r"\bhow can i contact\b",
                r"\bhow do i reach\b",
                r"\bdirectly\b",
            ),
            0.92,
        ),
        (
            "scope_help",
            (
                r"\bwhat can you help with\b",
                r"\bwhat can you do\b",
                r"\bhow can you help\b",
            ),
            0.93,
        ),
    ]

    for intent, patterns, confidence in intent_patterns:
        if any(re.search(pattern, q) for pattern in patterns):
            return {"matched": True, "intent": intent, "confidence": confidence}

    return {"matched": False, "intent": None, "confidence": 0.0}


def is_identity_fastpath_intent(intent: Optional[str]) -> bool:
    return intent in {
        "identity_intro",
        "identity_about",
        "authenticity_disclosure",
        "contact_handoff",
        "scope_help",
    }
