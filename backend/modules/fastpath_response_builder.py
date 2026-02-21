"""
Persona fast-path response builder.

Builds concise, disclosure-safe identity responses from canonical profile data.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _default_disclosure(display_name: str) -> str:
    template = os.getenv(
        "PERSONA_DISCLOSURE_TEMPLATE",
        "I’m a digital AI representation of {display_name}, not the real person directly.",
    )
    name = display_name or "this person"
    return template.format(display_name=name)


def build_fastpath_response(
    *,
    intent: str,
    profile: Dict[str, Any],
    query: str = "",
) -> Dict[str, Any]:
    display_name = _safe_str(profile.get("display_name")) or "this twin"
    one_line_intro = _safe_str(profile.get("one_line_intro"))
    short_intro = _safe_str(profile.get("short_intro"))
    disclosure_line = _safe_str(profile.get("disclosure_line")) or _default_disclosure(display_name)
    handoff_line = _safe_str(profile.get("contact_handoff_line")) or (
        "For direct contact, please use the public channels listed in this profile."
    )
    preferred_channel = _safe_str(profile.get("preferred_contact_channel"))
    expertise = [str(x).strip() for x in _safe_list(profile.get("expertise_areas")) if str(x).strip()]
    restricted = [str(x).strip() for x in _safe_list(profile.get("restricted_topics")) if str(x).strip()]
    social_links = _safe_dict(profile.get("social_links"))

    text = ""
    if intent == "identity_intro":
        primary = one_line_intro or short_intro or f"I’m {display_name}."
        text = primary

    elif intent == "identity_about":
        primary = short_intro or one_line_intro or f"I’m {display_name}."
        text = primary

    elif intent == "authenticity_disclosure":
        intro = one_line_intro or short_intro or f"I’m {display_name}."
        text = f"{intro} {disclosure_line}"

    elif intent == "contact_handoff":
        channel_hint = ""
        if preferred_channel:
            channel_hint = f" Preferred channel: {preferred_channel}."
        link_hint = ""
        if social_links:
            ordered = []
            for key in ("website", "linkedin", "email", "youtube", "instagram"):
                if social_links.get(key):
                    ordered.append(f"{key}: {social_links[key]}")
            if ordered:
                link_hint = " " + " | ".join(ordered[:3])
        text = f"{handoff_line}{channel_hint}{link_hint} {disclosure_line}"

    elif intent == "scope_help":
        if expertise:
            text = f"I can help with {', '.join(expertise[:4])}."
        else:
            text = "I can help with topics grounded in this twin’s sources and profile."
        if restricted:
            text = f"{text} I avoid {', '.join(restricted[:3])}."

    else:
        text = one_line_intro or short_intro or f"I’m {display_name}."

    return {
        "intent": intent,
        "text": " ".join(text.split()).strip(),
        "disclosure_included": intent in {"authenticity_disclosure", "contact_handoff"},
        "profile_status": _safe_str(profile.get("profile_status")) or "draft",
    }
