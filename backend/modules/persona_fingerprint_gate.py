"""
Persona Fingerprint Gate

Deterministic low-latency checks to catch obvious style/policy drift before
model-based judges run.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import re


DEFAULT_HEDGES = {
    "maybe",
    "might",
    "probably",
    "possibly",
    "i think",
    "i guess",
    "perhaps",
}


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def _get_length_band(
    *,
    deterministic_rules: Dict[str, Any],
    interaction_style: Dict[str, Any],
    intent_label: str,
) -> Dict[str, Optional[int]]:
    bands = deterministic_rules.get("length_bands")
    if isinstance(bands, dict):
        raw = bands.get(intent_label) or bands.get("default") or {}
        if isinstance(raw, dict):
            min_words = raw.get("min_words")
            max_words = raw.get("max_words")
            return {
                "min_words": int(min_words) if isinstance(min_words, (int, float)) else None,
                "max_words": int(max_words) if isinstance(max_words, (int, float)) else None,
            }

    brevity = (interaction_style.get("brevity_default") or "").strip().lower()
    if brevity == "concise":
        return {"min_words": 8, "max_words": 120}
    if brevity in {"detailed", "thorough"}:
        return {"min_words": 60, "max_words": 260}
    return {"min_words": 8, "max_words": 180}


def _required_structure(
    *,
    deterministic_rules: Dict[str, Any],
    interaction_style: Dict[str, Any],
    intent_label: str,
) -> Optional[str]:
    format_by_intent = deterministic_rules.get("format_by_intent")
    if isinstance(format_by_intent, dict):
        val = format_by_intent.get(intent_label) or format_by_intent.get("default")
        if isinstance(val, str) and val.strip():
            return val.strip().lower()

    signature = deterministic_rules.get("format_signature")
    if isinstance(signature, str) and signature.strip():
        return signature.strip().lower()
    if isinstance(signature, dict):
        val = signature.get(intent_label) or signature.get("default")
        if isinstance(val, str) and val.strip():
            return val.strip().lower()

    structure_default = (interaction_style.get("structure_default") or "").strip().lower()
    if "bullet" in structure_default:
        return "bullets"
    if "question" in structure_default and "first" in structure_default:
        return "question_first"
    return None


def run_persona_fingerprint_gate(
    *,
    answer: str,
    intent_label: str,
    deterministic_rules: Optional[Dict[str, Any]] = None,
    interaction_style: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    deterministic_rules = deterministic_rules or {}
    interaction_style = interaction_style or {}
    text = answer or ""
    text_lower = text.lower()

    checks: Dict[str, Dict[str, Any]] = {}
    violated: List[str] = []
    categories: List[str] = []

    # Length band check
    band = _get_length_band(
        deterministic_rules=deterministic_rules,
        interaction_style=interaction_style,
        intent_label=intent_label,
    )
    wc = _word_count(text)
    min_words = band.get("min_words")
    max_words = band.get("max_words")
    length_ok = True
    if min_words is not None and wc < min_words:
        length_ok = False
    if max_words is not None and wc > max_words:
        length_ok = False
    checks["length_band"] = {
        "passed": length_ok,
        "word_count": wc,
        "min_words": min_words,
        "max_words": max_words,
    }
    if not length_ok:
        violated.append("POL_DET_LENGTH_BAND")
        categories.append("length")

    # Banned phrase check
    banned_phrases = [
        str(v).strip()
        for v in (deterministic_rules.get("banned_phrases") or [])
        if str(v).strip()
    ]
    banned_hits = [p for p in banned_phrases if p.lower() in text_lower]
    checks["banned_phrases"] = {"passed": len(banned_hits) == 0, "hits": banned_hits}
    if banned_hits:
        violated.append("POL_DET_BANNED_PHRASE")
        categories.append("banned_phrase")

    # Formatting signature check
    required_structure = _required_structure(
        deterministic_rules=deterministic_rules,
        interaction_style=interaction_style,
        intent_label=intent_label,
    )
    structure_ok = True
    if required_structure == "bullets":
        structure_ok = bool(re.search(r"(?m)^\s*([-*]|\d+\.)\s+", text))
    elif required_structure == "question_first":
        first_line = (text.strip().splitlines() or [""])[0].strip()
        structure_ok = first_line.endswith("?")
    checks["format_signature"] = {"passed": structure_ok, "required": required_structure}
    if required_structure and not structure_ok:
        violated.append("POL_DET_FORMAT_SIGNATURE")
        categories.append("format")

    # Hedge policy check
    allowed_hedges = {
        str(v).strip().lower()
        for v in (deterministic_rules.get("allowed_hedges") or [])
        if str(v).strip()
    }
    disallow_extra_hedges = bool(deterministic_rules.get("strict_hedges"))
    detected_hedges = sorted([h for h in DEFAULT_HEDGES if h in text_lower])
    hedge_ok = True
    if disallow_extra_hedges and allowed_hedges:
        disallowed = [h for h in detected_hedges if h not in allowed_hedges]
        hedge_ok = len(disallowed) == 0
    else:
        disallowed = []
    checks["hedges"] = {"passed": hedge_ok, "detected": detected_hedges, "disallowed": disallowed}
    if not hedge_ok:
        violated.append("POL_DET_HEDGE_POLICY")
        categories.append("hedges")

    # Speed vs depth preference check
    speed_pref = (deterministic_rules.get("speed_depth_preference") or "").strip().lower()
    speed_ok = True
    if speed_pref == "speed" and wc > 140:
        speed_ok = False
    if speed_pref == "depth" and wc < 40:
        speed_ok = False
    checks["speed_depth"] = {"passed": speed_ok, "preference": speed_pref or None}
    if speed_pref and not speed_ok:
        violated.append("POL_DET_SPEED_DEPTH")
        categories.append("speed_depth")

    total_checks = len(checks)
    failed_checks = sum(1 for c in checks.values() if not c.get("passed"))
    score = 1.0 if total_checks == 0 else max(0.0, 1.0 - (failed_checks / total_checks))

    return {
        "passed": failed_checks == 0,
        "score": round(score, 4),
        "violated_clauses": violated,
        "reason_categories": list(dict.fromkeys(categories)),
        "checks": checks,
        "required_structure": required_structure,
        "length_band": band,
    }

