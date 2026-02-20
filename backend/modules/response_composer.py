from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence, Tuple


_STOPWORDS = {
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
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "what",
    "who",
    "with",
    "you",
    "your",
}

_PROMPT_RE = re.compile(r"^\s*\d{1,3}[\)\.]?\s+")
_LEADING_Q_RE = re.compile(
    r"^\s*(?:who|what|when|where|why|how|can|do|does|did|should|would|is|are)\b",
    re.IGNORECASE,
)

_QUERY_CLASS_LABELS: Dict[str, Tuple[str, ...]] = {
    "identity": ("Who I am", "Core expertise", "How I help"),
    "procedural": ("How to use this twin", "Recommended flow", "Expected outcome"),
    "factual": ("Answer", "Evidence", "Notes"),
    "evaluative": ("Recommendation", "Why", "Risks + mitigations"),
}


def _tokens(text: str) -> List[str]:
    values = re.findall(r"[a-z0-9][a-z0-9._-]*", (text or "").lower())
    return [tok for tok in values if len(tok) > 2 and tok not in _STOPWORDS]


def _normalize_line(raw: str) -> str:
    return re.sub(r"\s+", " ", str(raw or "").strip())


def _is_prompt_like_line(line: str) -> bool:
    normalized = _normalize_line(line)
    if not normalized:
        return False
    if normalized.endswith("?"):
        return True
    if _PROMPT_RE.match(normalized):
        return True
    if _LEADING_Q_RE.match(normalized):
        return True
    return False


def _is_answer_text_row(row: Dict[str, Any]) -> bool:
    raw = row.get("is_answer_text")
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        lowered = raw.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
    block_type = str(row.get("block_type") or row.get("chunk_type") or "").strip().lower()
    if not block_type:
        return True
    return block_type not in {"prompt_question", "heading"}


def _candidate_sentences(
    query: str,
    context_data: Sequence[Dict[str, Any]],
    *,
    quote_intent: bool,
    max_items: int = 24,
) -> List[Tuple[str, str]]:
    query_tokens = set(_tokens(query))
    scored: List[Tuple[float, str, str]] = []
    seen: set[str] = set()

    for row in context_data[: max(1, max_items)]:
        if not isinstance(row, dict):
            continue
        if not quote_intent and not _is_answer_text_row(row):
            continue
        source_id = str(row.get("source_id") or "").strip()
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        base_score = float(row.get("score", row.get("vector_score", 0.0)) or 0.0)
        for raw in re.split(r"(?<=[.!?])\s+|\n+", text):
            line = _normalize_line(raw)
            if len(line) < 18:
                continue
            if not quote_intent and _is_prompt_like_line(line):
                continue
            sig = line.lower()[:240]
            if sig in seen:
                continue
            seen.add(sig)
            line_tokens = set(_tokens(line))
            overlap = (
                len(query_tokens.intersection(line_tokens)) / float(len(query_tokens))
                if query_tokens
                else 0.0
            )
            score = overlap + (0.20 * base_score)
            scored.append((score, line, source_id))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [(line, source_id) for _score, line, source_id in scored]


def _with_template_labels(query_class: str, points: List[str], *, quote_intent: bool) -> List[str]:
    if quote_intent:
        return points
    labels = _QUERY_CLASS_LABELS.get(str(query_class or "").strip().lower(), _QUERY_CLASS_LABELS["factual"])
    out: List[str] = []
    for idx, point in enumerate(points):
        if idx >= len(labels):
            out.append(point)
            continue
        line = _normalize_line(point)
        if ":" in line and len(line.split(":")[0]) <= 28:
            out.append(line)
            continue
        out.append(f"{labels[idx]}: {line}")
    return out


def compose_answer_points(
    *,
    query: str,
    query_class: str,
    quote_intent: bool,
    planner_points: Sequence[str] | None,
    context_data: Sequence[Dict[str, Any]] | None,
    max_points: int = 3,
) -> Dict[str, Any]:
    points: List[str] = []
    used_source_ids: List[str] = []

    for raw in planner_points or []:
        line = _normalize_line(raw)
        if not line:
            continue
        if not quote_intent and _is_prompt_like_line(line):
            continue
        if line not in points:
            points.append(line)
        if len(points) >= max(1, max_points):
            break

    if not points:
        for line, source_id in _candidate_sentences(
            query,
            context_data or [],
            quote_intent=quote_intent,
            max_items=max(8, max_points * 6),
        ):
            if line not in points:
                points.append(line)
            if source_id and source_id not in used_source_ids:
                used_source_ids.append(source_id)
            if len(points) >= max(1, max_points):
                break

    points = _with_template_labels(query_class, points[: max(1, max_points)], quote_intent=quote_intent)
    return {"points": points[: max(1, max_points)], "source_ids": used_source_ids[: max(1, max_points)]}
