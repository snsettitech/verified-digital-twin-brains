"""
Section-aware parsing and intent helpers for document-grounded answering.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple


_WHITESPACE_RE = re.compile(r"\s+")
_NUMBERED_HEADING_RE = re.compile(r"^\s*(\d+)\)\s+(.+?)\s*$")


def _normalize_text(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", (value or "").strip())


def _normalize_key(value: str) -> str:
    lowered = _normalize_text(value).lower()
    lowered = re.sub(r"[\"'`“”’()\-_/,:;.!?]", " ", lowered)
    lowered = _WHITESPACE_RE.sub(" ", lowered).strip()
    return lowered


_MAIN_SECTION_KEYWORDS: Tuple[Tuple[Tuple[str, ...], str], ...] = (
    (("owner identity and credibility",), "identity"),
    (("audience and use cases",), "audience"),
    (("non goals and boundaries", "non-goals and boundaries"), "boundaries"),
    (("decision rubric", "how your twin should think"), "decision_rubric"),
    (("communication style rules",), "style_rules"),
    (("what the twin should ask users", "opening questions"), "opening_questions"),
    (("knowledge base doc content guidelines",), "content_guidelines"),
    (("example answers", "what your twin should sound like"), "examples"),
)

_SUBSECTION_KEYWORDS: Tuple[Tuple[Tuple[str, ...], str], ...] = (
    (("who are you short bio used in the twin", "who are you"), "identity"),
    (("core expertise areas",), "expertise"),
    (("primary audience",), "audience"),
    (("top 5 office hours use cases", "office hours use cases"), "audience"),
    (("non goals", "what your twin should not do", "boundaries"), "boundaries"),
    (("default response template",), "style_template"),
    (("tone", "format", "answering behavior"), "style_rules"),
    (("decision framework", "decision rubric"), "decision_rubric"),
    (("example 1", "example 2", "example 3"), "examples"),
)


def _chunk_type_from_heading(heading: str, default: str = "general") -> str:
    key = _normalize_key(heading)
    if not key:
        return default

    for markers, chunk_type in _SUBSECTION_KEYWORDS:
        if any(marker in key for marker in markers):
            return chunk_type
    for markers, chunk_type in _MAIN_SECTION_KEYWORDS:
        if any(marker in key for marker in markers):
            return chunk_type
    return default


def _chunk_type_from_text(text: str, default: str = "general") -> str:
    key = _normalize_key(text)
    if not key:
        return default
    return _chunk_type_from_heading(key, default=default)


def _split_doc_lines(text: str) -> List[str]:
    raw = (text or "").replace("\r\n", "\n")
    # Word-table exports in this project often flatten cells with pipes.
    raw = raw.replace(" | ", "\n").replace("|", "\n")
    lines = []
    for line in raw.split("\n"):
        normalized = _normalize_text(line)
        if normalized:
            lines.append(normalized)
    return lines


def _detect_heading(line: str) -> Optional[Dict[str, Any]]:
    numbered = _NUMBERED_HEADING_RE.match(line or "")
    if numbered:
        title = f"{numbered.group(1)}) {numbered.group(2).strip()}"
        return {
            "level": 1,
            "title": title,
            "chunk_type": _chunk_type_from_heading(title, default="general"),
        }

    chunk_type = _chunk_type_from_heading(line, default="")
    if chunk_type:
        return {
            "level": 2,
            "title": _normalize_text(line),
            "chunk_type": chunk_type,
        }
    return None


def extract_section_blocks(
    text: str,
    *,
    source_id: Optional[str] = None,
    base_metadata: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Parse freeform document text into coherent heading-scoped blocks.
    """
    lines = _split_doc_lines(text)
    if not lines:
        return []

    base = dict(base_metadata or {})
    blocks: List[Dict[str, Any]] = []

    root_title = "General"
    active_title = "General"
    active_path = "General"
    active_chunk_type = _chunk_type_from_text(text, default="general")
    buffer: List[str] = []

    def flush() -> None:
        nonlocal buffer, active_title, active_path, active_chunk_type
        joined = "\n".join(buffer).strip()
        if not joined:
            buffer = []
            return
        row = dict(base)
        row["text"] = joined
        if source_id:
            row["source_id"] = source_id
        row["section_title"] = active_title
        row["section_path"] = active_path
        row["chunk_type"] = active_chunk_type or "general"
        blocks.append(row)
        buffer = []

    for line in lines:
        heading = _detect_heading(line)
        if heading:
            flush()
            if heading["level"] == 1:
                root_title = heading["title"]
                active_title = heading["title"]
                active_path = heading["title"]
                active_chunk_type = heading["chunk_type"] or "general"
            else:
                active_title = heading["title"]
                active_path = f"{root_title} > {active_title}" if root_title else active_title
                active_chunk_type = heading["chunk_type"] or active_chunk_type or "general"
            buffer.append(line)
            continue
        buffer.append(line)

    flush()
    return blocks


@dataclass(frozen=True)
class QueryIntentProfile:
    intent: str
    allowed_chunk_types: Tuple[str, ...]
    preferred_chunk_types: Tuple[str, ...]
    allow_multi_section: bool = False
    disable_label_bonus: bool = False


def classify_query_intent_profile(query: str) -> QueryIntentProfile:
    q = _normalize_key(query)
    if not q:
        return QueryIntentProfile("general", tuple(), tuple())

    identity_patterns = (
        r"\bwho are you\b",
        r"\bwhat are you\b",
        r"\bintroduce yourself\b",
        r"\btell me about yourself\b",
        r"\btell me about you\b",
        r"\byour background\b",
        r"\byour expertise\b",
    )
    if any(re.search(pattern, q) for pattern in identity_patterns):
        return QueryIntentProfile(
            intent="identity",
            allowed_chunk_types=("identity", "expertise"),
            preferred_chunk_types=("identity", "expertise"),
            allow_multi_section=True,
            disable_label_bonus=True,
        )

    boundaries_patterns = (
        "non goals",
        "non-goals",
        "boundaries",
        "what should you not do",
        "what shouldnt you do",
        "what should you avoid",
    )
    if any(p in q for p in boundaries_patterns):
        return QueryIntentProfile(
            intent="boundaries",
            allowed_chunk_types=("boundaries",),
            preferred_chunk_types=("boundaries",),
            disable_label_bonus=True,
        )

    style_template_patterns = (
        "how should you respond by default",
        "default response template",
        "response template",
        "communication style rules",
        "how should you respond",
    )
    if any(p in q for p in style_template_patterns):
        return QueryIntentProfile(
            intent="style_template",
            allowed_chunk_types=("style_template", "style_rules"),
            preferred_chunk_types=("style_template", "style_rules"),
            allow_multi_section=True,
            disable_label_bonus=True,
        )

    decision_patterns = (
        "should i",
        "should we",
        "recommend",
        "architecture",
        "pricing",
        "tradeoff",
        "trade off",
        "serverless",
        "containers",
        "rag",
        "fine tune",
        "fine-tune",
        "ai choice",
    )
    if any(p in q for p in decision_patterns):
        return QueryIntentProfile(
            intent="decision",
            allowed_chunk_types=("decision_rubric", "examples", "style_rules", "style_template"),
            preferred_chunk_types=("decision_rubric", "examples", "style_template"),
            allow_multi_section=True,
        )

    return QueryIntentProfile("general", tuple(), tuple())


def _tokenize_query(text: str) -> Set[str]:
    stop = {
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
        "how",
        "i",
        "in",
        "is",
        "it",
        "me",
        "my",
        "of",
        "on",
        "or",
        "the",
        "to",
        "what",
        "who",
        "with",
        "you",
        "your",
    }
    tokens = re.findall(r"[a-z0-9][a-z0-9._-]*", (text or "").lower())
    return {tok for tok in tokens if len(tok) > 2 and tok not in stop}


def _context_chunk_type(context: Dict[str, Any]) -> str:
    for key in ("chunk_type",):
        raw = context.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip().lower()
    return _chunk_type_from_text(str(context.get("section_title") or context.get("text") or ""), default="general")


def section_filter_contexts(
    query: str,
    contexts: Sequence[Dict[str, Any]],
    *,
    max_items: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Intent-aware context filtering that prefers heading-coherent blocks.
    """
    profile = classify_query_intent_profile(query)
    if profile.intent == "general" or not contexts:
        return list(contexts[: max_items or len(contexts)])

    expanded: List[Dict[str, Any]] = []
    for ctx in contexts:
        if not isinstance(ctx, dict):
            continue
        source_id = str(ctx.get("source_id") or "").strip() or None
        blocks = extract_section_blocks(
            str(ctx.get("text") or ""),
            source_id=source_id,
            base_metadata={
                "score": ctx.get("score"),
                "vector_score": ctx.get("vector_score"),
                "rrf_score": ctx.get("rrf_score"),
                "chunk_id": ctx.get("chunk_id"),
                "category": ctx.get("category"),
                "tone": ctx.get("tone"),
                "is_verified": bool(ctx.get("is_verified", False)),
            },
        )
        if blocks:
            expanded.extend(blocks)
        else:
            cloned = dict(ctx)
            cloned["chunk_type"] = _context_chunk_type(cloned)
            cloned["section_title"] = cloned.get("section_title") or "General"
            cloned["section_path"] = cloned.get("section_path") or cloned["section_title"]
            expanded.append(cloned)

    allowed = set(profile.allowed_chunk_types)
    filtered = [ctx for ctx in expanded if _context_chunk_type(ctx) in allowed]
    if not filtered:
        # If metadata/tagging is missing, keep the original to avoid empty retrieval.
        return list(contexts[: max_items or len(contexts)])

    query_tokens = _tokenize_query(query)
    preferred = set(profile.preferred_chunk_types)

    def score_ctx(row: Dict[str, Any]) -> float:
        text = str(row.get("text") or "").lower()
        overlap = 0.0
        if query_tokens:
            overlap = len([tok for tok in query_tokens if tok in text]) / float(len(query_tokens))
        type_boost = 0.18 if _context_chunk_type(row) in preferred else 0.0
        base_score = float(row.get("score", row.get("vector_score", 0.0)) or 0.0)
        return overlap + type_boost + (0.25 * base_score)

    ranked = sorted(filtered, key=score_ctx, reverse=True)
    deduped: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for row in ranked:
        text_sig = _normalize_key(str(row.get("text") or ""))[:240]
        if not text_sig or text_sig in seen:
            continue
        deduped.append(row)
        seen.add(text_sig)
        if max_items and len(deduped) >= max_items:
            break
    return deduped
