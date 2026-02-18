from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence, Set

from modules.inference_router import invoke_json

_AMBIGUITY_LEVELS = {"low", "medium", "high"}

_STOPWORDS: Set[str] = {
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

_GENERIC_CLARIFICATION_PATTERNS = (
    "what outcome do you want",
    "what would you like",
    "can you provide more context",
    "share more context",
    "tell me more",
)


def _tokens(text: str) -> Set[str]:
    values = re.findall(r"[a-z0-9][a-z0-9._-]*", (text or "").lower())
    return {tok for tok in values if len(tok) > 2 and tok not in _STOPWORDS}


def _clamp_confidence(value: Any, default: float = 0.0) -> float:
    try:
        as_float = float(value)
    except Exception:
        return default
    return max(0.0, min(1.0, as_float))


def _normalize_missing_information(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    out: List[str] = []
    seen: Set[str] = set()
    for raw in values:
        item = re.sub(r"\s+", " ", str(raw or "").strip()).strip(" .")
        if len(item) < 6:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= 5:
            break
    return out


def _default_missing_information(query: str, evidence_chunks: Sequence[Dict[str, Any]]) -> List[str]:
    q = re.sub(r"\s+", " ", (query or "").strip())
    q_tokens = sorted(_tokens(q))
    if not evidence_chunks:
        if q_tokens:
            return [f"document evidence about: {', '.join(q_tokens[:5])}"]
        return ["document evidence that directly answers the question"]
    if q:
        return [f"the missing factual detail needed to answer: \"{q[:120]}\""]
    return ["the missing factual detail required for a complete answer"]


def _heuristic_answerability(query: str, evidence_chunks: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    chunks = [row for row in evidence_chunks if isinstance(row, dict)]
    if not chunks:
        return {
            "answerable": False,
            "confidence": 0.0,
            "reasoning": "No evidence chunks were retrieved.",
            "missing_information": _default_missing_information(query, chunks),
            "ambiguity_level": "high",
        }

    query_tokens = _tokens(query)
    if not query_tokens:
        return {
            "answerable": False,
            "confidence": 0.2,
            "reasoning": "The question is too vague to evaluate against evidence.",
            "missing_information": _default_missing_information(query, chunks),
            "ambiguity_level": "high",
        }

    best_overlap = 0.0
    for row in chunks[:5]:
        text_tokens = _tokens(str(row.get("text") or ""))
        if not text_tokens:
            continue
        overlap = len(query_tokens.intersection(text_tokens)) / float(len(query_tokens))
        best_overlap = max(best_overlap, overlap)

    if best_overlap >= 0.55:
        return {
            "answerable": True,
            "confidence": min(0.85, 0.45 + best_overlap),
            "reasoning": "Evidence has strong lexical overlap with the question.",
            "missing_information": [],
            "ambiguity_level": "low",
        }

    return {
        "answerable": False,
        "confidence": max(0.15, best_overlap),
        "reasoning": "Evidence does not contain enough direct support for a complete answer.",
        "missing_information": _default_missing_information(query, chunks),
        "ambiguity_level": "medium" if best_overlap >= 0.3 else "high",
    }


def _render_evidence_for_prompt(evidence_chunks: Sequence[Dict[str, Any]], *, max_chunks: int = 6) -> str:
    lines: List[str] = []
    for idx, row in enumerate(evidence_chunks[: max(1, max_chunks)], 1):
        if not isinstance(row, dict):
            continue
        source_id = str(row.get("source_id") or f"chunk-{idx}")
        section = str(row.get("section_path") or row.get("section_title") or "unknown")
        text = re.sub(r"\s+", " ", str(row.get("text") or "").strip())[:1200]
        if not text:
            continue
        lines.append(f"[{idx}] source_id={source_id}; section={section}; text={text}")
    return "\n".join(lines)


async def evaluate_answerability(query: str, evidence_chunks: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Evaluate if a query can be fully answered from retrieved evidence.
    """
    chunks = [row for row in evidence_chunks if isinstance(row, dict)]
    if not chunks:
        return _heuristic_answerability(query, chunks)

    prompt = f"""You are an evidence sufficiency evaluator for RAG.
Determine whether the USER QUESTION can be answered fully and accurately using only the EVIDENCE CHUNKS.

USER QUESTION:
{query}

EVIDENCE CHUNKS:
{_render_evidence_for_prompt(chunks)}

Return STRICT JSON:
{{
  "answerable": boolean,
  "confidence": number,
  "reasoning": string,
  "missing_information": ["concrete missing item"],
  "ambiguity_level": "low|medium|high"
}}

Rules:
- Use only evidence from the chunks.
- If answerable is true, missing_information must be [].
- If answerable is false, missing_information must list concrete missing facts/constraints (no generic requests).
- Keep missing_information <= 5 items.
"""

    try:
        raw, _meta = await invoke_json(
            [{"role": "system", "content": prompt}],
            task="verifier",
            temperature=0,
            max_tokens=450,
        )
    except Exception:
        return _heuristic_answerability(query, chunks)

    answerable = bool(raw.get("answerable"))
    confidence = _clamp_confidence(raw.get("confidence"), default=0.0)
    reasoning = re.sub(r"\s+", " ", str(raw.get("reasoning") or "").strip())
    if not reasoning:
        reasoning = "Evaluator returned no reasoning."
    ambiguity_level = str(raw.get("ambiguity_level") or "medium").strip().lower()
    if ambiguity_level not in _AMBIGUITY_LEVELS:
        ambiguity_level = "medium"

    missing_information = _normalize_missing_information(raw.get("missing_information"))
    if answerable:
        missing_information = []
        confidence = max(confidence, 0.5)
    else:
        if not missing_information:
            missing_information = _default_missing_information(query, chunks)

    return {
        "answerable": answerable,
        "confidence": confidence,
        "reasoning": reasoning,
        "missing_information": missing_information,
        "ambiguity_level": ambiguity_level,
    }


def build_targeted_clarification_questions(
    query: str,
    missing_information: Sequence[str],
    *,
    limit: int = 3,
) -> List[str]:
    questions: List[str] = []
    for raw in missing_information:
        item = re.sub(r"\s+", " ", str(raw or "").strip()).strip(" .")
        if len(item) < 5:
            continue
        lowered = item.lower()
        if any(pattern in lowered for pattern in _GENERIC_CLARIFICATION_PATTERNS):
            continue
        if item.endswith("?"):
            question = item
        elif lowered.startswith(("the ", "a ", "an ")):
            question = f"Can you share {item}?"
        else:
            question = f"Can you clarify {item}?"
        if question not in questions:
            questions.append(question)
        if len(questions) >= max(1, limit):
            break

    if not questions:
        fallback_query = re.sub(r"\s+", " ", (query or "").strip())[:120]
        if fallback_query:
            questions.append(
                f'Can you share the specific document detail that answers: "{fallback_query}"?'
            )
    return questions[: max(1, limit)]

