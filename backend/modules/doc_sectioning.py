"""
Generic section parsing utilities for document ingestion.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

_WHITESPACE_RE = re.compile(r"\s+")
_NUMBERED_HEADING_RE = re.compile(r"^\s*(\d{1,3})[\)\.]?\s+(.+?)\s*$")
_MARKDOWN_HEADING_RE = re.compile(r"^\s*#{1,6}\s+(.+?)\s*$")


def _normalize_text(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", (value or "").strip())


def _split_doc_lines(text: str) -> List[str]:
    raw = (text or "").replace("\r\n", "\n")
    raw = raw.replace(" | ", "\n").replace("|", "\n")
    rows: List[str] = []
    for line in raw.split("\n"):
        normalized = _normalize_text(line)
        if normalized:
            rows.append(normalized)
    return rows


def _looks_like_short_title(line: str) -> bool:
    words = line.split()
    if len(words) == 0 or len(words) > 12:
        return False
    if len(line) > 90:
        return False
    upper = sum(1 for ch in line if ch.isupper())
    alpha = sum(1 for ch in line if ch.isalpha())
    if alpha == 0:
        return False
    ratio = upper / float(alpha)
    return ratio > 0.65


def _detect_heading(line: str) -> Optional[Dict[str, Any]]:
    numbered = _NUMBERED_HEADING_RE.match(line)
    if numbered:
        return {"level": 1, "title": f"{numbered.group(1)}) {numbered.group(2).strip()}"}

    markdown = _MARKDOWN_HEADING_RE.match(line)
    if markdown:
        return {"level": 1, "title": markdown.group(1).strip()}

    if _looks_like_short_title(line):
        return {"level": 1, "title": line.strip()}

    if line.endswith(":") and len(line.split()) <= 10:
        return {"level": 2, "title": line.strip(": ").strip()}

    return None


def extract_section_blocks(
    text: str,
    *,
    source_id: Optional[str] = None,
    base_metadata: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Parse freeform text into coherent section blocks using generic heading detection.
    """
    lines = _split_doc_lines(text)
    if not lines:
        return []

    base = dict(base_metadata or {})
    blocks: List[Dict[str, Any]] = []
    root_title = "General"
    active_title = "General"
    active_path = "General"
    buffer: List[str] = []

    def flush() -> None:
        nonlocal buffer
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
        row["chunk_type"] = "section"
        blocks.append(row)
        buffer = []

    for line in lines:
        heading = _detect_heading(line)
        if heading:
            flush()
            if heading.get("level") == 1:
                root_title = str(heading["title"])
                active_title = root_title
                active_path = root_title
            else:
                active_title = str(heading["title"])
                active_path = f"{root_title} > {active_title}" if root_title else active_title
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
    allow_multi_section: bool = True
    disable_label_bonus: bool = True


def classify_query_intent_profile(_query: str) -> QueryIntentProfile:
    """
    Kept for backward compatibility. General mode only.
    """
    return QueryIntentProfile("general", tuple(), tuple())


def section_filter_contexts(
    _query: str,
    contexts: Sequence[Dict[str, Any]],
    *,
    max_items: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Generic context pass-through kept for compatibility.
    """
    if max_items is None:
        return [dict(c) for c in contexts if isinstance(c, dict)]
    return [dict(c) for c in contexts if isinstance(c, dict)][: max(0, max_items)]

