from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence, Set

from modules.inference_router import invoke_json

_AMBIGUITY_LEVELS = {"low", "medium", "high"}
_ANSWERABILITY_STATES = {"direct", "derivable", "insufficient"}
_ANSWERABILITY_RANK = {"insufficient": 0, "derivable": 1, "direct": 2}

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
    "with",
}

_GENERIC_CLARIFICATION_PATTERNS = (
    "what outcome do you want",
    "what would you like",
    "can you provide more context",
    "share more context",
    "tell me more",
)

_META_MISSING_PATTERNS = (
    "context for a conversation",
    "response to greeting",
    "response for greeting",
    "identity of you",
    "identity of yourself",
    "clarify the question",
    "tell me more",
    "more context",
    "what outcome do you want",
    "what would you like",
)

_IDENTITY_QUERY_PATTERNS = (
    "who are you",
    "tell me about yourself",
    "introduce yourself",
    "what do you do",
    "what are you",
    "your background",
)

_IDENTITY_EVIDENCE_MARKERS = (
    "i am ",
    "my name is",
    "i work on",
    "i focus on",
    "background",
    "experience",
    "expertise",
    "credibility",
    "bio",
)

_PROCEDURAL_QUERY_MARKERS = (
    "how to",
    "how do",
    "how should",
    "how can",
    "how does",
    "use this twin",
    "use the twin",
    "workflow",
    "process",
    "steps",
)

_PROCEDURAL_EVIDENCE_MARKERS = (
    "workflow",
    "process",
    "steps",
    "start",
    "onboarding",
    "configure",
    "setup",
    "review",
    "guide",
    "use",
)

_INFERENTIAL_QUERY_MARKERS = (
    "would this twin",
    "care about most",
    "like a",
    "summarize the twin",
    "summarise the twin",
    "optimize for",
    "optimise for",
    "red flags",
    "pass on",
    "how should i talk",
    "the way this twin would",
    "feedback the way",
    "communication style",
)

_PROFILE_EVIDENCE_MARKERS = (
    "decision rubric",
    "communication style",
    "style rules",
    "principles",
    "boundaries",
    "audience",
    "use cases",
    "prioritize",
    "values",
    "non-goals",
)

_SUMMARIZATION_QUERY_MARKERS = (
    "summarize",
    "summarise",
)

_RED_FLAGS_QUERY_MARKERS = (
    "red flag",
    "red flags",
)

_EVALUATIVE_FIT_QUERY_PATTERNS = (
    "would this twin like",
    "would you like",
    "would you invest",
    "would this twin invest",
)

_RUBRIC_THESIS_EVIDENCE_MARKERS = (
    "rubric",
    "thesis",
    "investment committee",
    "ic",
    "criteria",
    "decision",
    "invest",
    "red flag",
    "pass",
)


def _tokens(text: str) -> Set[str]:
    values = re.findall(r"[a-z0-9][a-z0-9._-]*", (text or "").lower())
    return {tok for tok in values if len(tok) > 1 and tok not in _STOPWORDS}


def _clamp_confidence(value: Any, default: float = 0.0) -> float:
    try:
        as_float = float(value)
    except Exception:
        return default
    return max(0.0, min(1.0, as_float))


def _normalize_answerability(value: Any, legacy_answerable: Any = None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in _ANSWERABILITY_STATES:
        return normalized

    if isinstance(value, bool):
        return "direct" if value else "insufficient"

    if isinstance(legacy_answerable, bool):
        return "direct" if legacy_answerable else "insufficient"

    legacy_str = str(legacy_answerable or "").strip().lower()
    if legacy_str in {"true", "1", "yes"}:
        return "direct"
    if legacy_str in {"false", "0", "no"}:
        return "insufficient"

    return "insufficient"


def _max_reasoning_state(original_state: str, proposed_state: str, *, has_evidence: bool) -> str:
    original = _normalize_answerability(original_state)
    proposed = _normalize_answerability(proposed_state)
    if not has_evidence:
        return proposed
    return proposed if _ANSWERABILITY_RANK[proposed] >= _ANSWERABILITY_RANK[original] else original


def _is_identity_intro_query(query: str) -> bool:
    q = re.sub(r"\s+", " ", str(query or "").strip().lower())
    if not q:
        return False
    return any(marker in q for marker in _IDENTITY_QUERY_PATTERNS)


def _chunk_text(row: Dict[str, Any]) -> str:
    return re.sub(r"\s+", " ", str((row or {}).get("text") or "").strip().lower())


def _has_identity_evidence(chunks: Sequence[Dict[str, Any]]) -> bool:
    for row in chunks[:8]:
        text = _chunk_text(row)
        if not text:
            continue
        if any(marker in text for marker in _IDENTITY_EVIDENCE_MARKERS):
            return True
    return False


def _is_procedural_query(query: str) -> bool:
    q = re.sub(r"\s+", " ", str(query or "").strip().lower())
    if not q:
        return False
    return any(marker in q for marker in _PROCEDURAL_QUERY_MARKERS)


def _procedural_chunk_count(chunks: Sequence[Dict[str, Any]]) -> int:
    count = 0
    for row in chunks[:8]:
        text = _chunk_text(row)
        if not text:
            continue
        if any(marker in text for marker in _PROCEDURAL_EVIDENCE_MARKERS):
            count += 1
    return count


def _is_inferential_persona_query(query: str) -> bool:
    q = re.sub(r"\s+", " ", str(query or "").strip().lower())
    if not q:
        return False
    return any(marker in q for marker in _INFERENTIAL_QUERY_MARKERS)


def _is_summarization_query(query: str) -> bool:
    q = re.sub(r"\s+", " ", str(query or "").strip().lower())
    if not q:
        return False
    return any(marker in q for marker in _SUMMARIZATION_QUERY_MARKERS)


def _is_red_flags_query(query: str) -> bool:
    q = re.sub(r"\s+", " ", str(query or "").strip().lower())
    if not q:
        return False
    return any(marker in q for marker in _RED_FLAGS_QUERY_MARKERS)


def _is_evaluative_fit_query(query: str) -> bool:
    q = re.sub(r"\s+", " ", str(query or "").strip().lower())
    if not q:
        return False
    return any(pattern in q for pattern in _EVALUATIVE_FIT_QUERY_PATTERNS)


def _has_rubric_thesis_evidence(chunks: Sequence[Dict[str, Any]]) -> bool:
    for row in chunks[:10]:
        text = _chunk_text(row)
        if not text:
            continue
        if any(marker in text for marker in _RUBRIC_THESIS_EVIDENCE_MARKERS):
            return True
    return False


def _profile_evidence_count(chunks: Sequence[Dict[str, Any]]) -> int:
    count = 0
    for row in chunks[:8]:
        text = _chunk_text(row)
        if not text:
            continue
        if any(marker in text for marker in _PROFILE_EVIDENCE_MARKERS):
            count += 1
    return count


def _contains_meta_missing_item(item: str) -> bool:
    lowered = re.sub(r"\s+", " ", str(item or "").strip().lower())
    if not lowered:
        return True
    if any(pattern in lowered for pattern in _GENERIC_CLARIFICATION_PATTERNS):
        return True
    if any(pattern in lowered for pattern in _META_MISSING_PATTERNS):
        return True
    return False


def _clean_section_label(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "").strip())
    cleaned = re.sub(r"^[0-9]+\)\s*", "", cleaned)
    cleaned = cleaned.strip(" .:-")
    return cleaned


def _derive_section_candidates(
    evidence_chunks: Sequence[Dict[str, Any]],
    *,
    limit: int = 4,
) -> List[str]:
    candidates: List[str] = []

    def _add(value: str) -> None:
        item = _clean_section_label(value)
        if not item:
            return
        low = item.lower()
        if low in {"unknown", "none", "n/a"}:
            return
        if any(existing.lower() == low for existing in candidates):
            return
        candidates.append(item)

    for row in evidence_chunks[:8]:
        if not isinstance(row, dict):
            continue
        _add(str(row.get("section_title") or ""))
        _add(str(row.get("section_path") or ""))

        text = str(row.get("text") or "")
        if not text:
            continue
        for raw_line in text.splitlines():
            line = _clean_section_label(raw_line)
            if not line:
                continue
            if re.match(r"^[A-Za-z][A-Za-z0-9 '&/()-]{2,70}$", line):
                if (
                    "example" in line.lower()
                    or "rules" in line.lower()
                    or "rubric" in line.lower()
                    or "purpose" in line.lower()
                    or "non-goals" in line.lower()
                    or "boundaries" in line.lower()
                    or "communication" in line.lower()
                    or "audience" in line.lower()
                    or "opening questions" in line.lower()
                    or "core expertise" in line.lower()
                ):
                    _add(line)
            if len(candidates) >= max(1, limit):
                return candidates[: max(1, limit)]

    return candidates[: max(1, limit)]


def _normalize_missing_information(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    out: List[str] = []
    seen: Set[str] = set()
    for raw in values:
        item = re.sub(r"\s+", " ", str(raw or "").strip()).strip(" .")
        if len(item) < 6:
            continue
        if _contains_meta_missing_item(item):
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
    if _is_identity_intro_query(q):
        return ["the twin's identity bio and core expertise"]
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
        answerability = "insufficient"
        return {
            "answerability": answerability,
            "answerable": False,
            "confidence": 0.0,
            "reasoning": "No evidence chunks were retrieved.",
            "missing_information": _default_missing_information(query, chunks),
            "ambiguity_level": "high",
        }

    if _is_identity_intro_query(query) and _has_identity_evidence(chunks):
        return {
            "answerability": "direct",
            "answerable": True,
            "confidence": 0.78,
            "reasoning": "Identity query matched identity evidence in retrieved chunks.",
            "missing_information": [],
            "ambiguity_level": "low",
        }

    query_tokens = _tokens(query)

    # If we have retrieved chunks, bias toward answering — the retrieval pipeline
    # already filtered for relevance.  Very short / vague queries should still
    # attempt an answer when evidence was found.
    if not query_tokens:
        answerability = "insufficient"
        return {
            "answerability": "derivable",
            "answerable": True,
            "confidence": 0.45,
            "reasoning": "Evidence chunks retrieved; attempting answer despite vague query.",
            "missing_information": [],
            "ambiguity_level": "medium",
        }

    best_overlap = 0.0
    all_tokens: Set[str] = set()
    supporting_chunks = 0
    for row in chunks[:5]:
        text_tokens = _tokens(str(row.get("text") or ""))
        if not text_tokens:
            continue
        all_tokens.update(text_tokens)
        overlap = len(query_tokens.intersection(text_tokens)) / float(len(query_tokens))
        best_overlap = max(best_overlap, overlap)
        if overlap >= 0.22:
            supporting_chunks += 1

    if best_overlap >= 0.35:
        answerability = "direct"
        return {
            "answerability": answerability,
            "answerable": True,
            "confidence": min(0.85, 0.40 + best_overlap),
            "reasoning": "Evidence has sufficient overlap with the question.",
            "missing_information": [],
            "ambiguity_level": "low" if best_overlap >= 0.55 else "medium",
        }

    # Even with low lexical overlap, if chunks were retrieved the vector search
    # already established semantic relevance.  Give the planner a chance.
    return {
        "answerability": "derivable",
        "answerable": True,
        "confidence": max(0.35, 0.25 + best_overlap),
        "reasoning": "Evidence retrieved via semantic search; attempting answer.",
        "missing_information": [],
        "ambiguity_level": "medium",
    }


def _apply_contract_overrides(
    query: str,
    chunks: Sequence[Dict[str, Any]],
    result: Dict[str, Any],
) -> Dict[str, Any]:
    has_evidence = bool(chunks)
    chunk_count = len(chunks)
    original_answerability = _normalize_answerability(result.get("answerability"), result.get("answerable"))
    proposed_answerability = original_answerability
    confidence = _clamp_confidence(result.get("confidence"), default=0.0)
    reasoning = re.sub(r"\s+", " ", str(result.get("reasoning") or "").strip()) or "No reasoning provided."
    missing_information = _normalize_missing_information(result.get("missing_information"))
    ambiguity_level = str(result.get("ambiguity_level") or "medium").strip().lower()
    if ambiguity_level not in _AMBIGUITY_LEVELS:
        ambiguity_level = "medium"

    # Overrides are interpretation helpers only. They may unblock reasoning, not downgrade it.
    if _is_identity_intro_query(query) and _has_identity_evidence(chunks):
        proposed_answerability = "direct"
        confidence = max(confidence, 0.65)
        missing_information = []
        ambiguity_level = "low"
        reasoning = f"{reasoning} Identity evidence found in retrieved chunks."

    if _is_summarization_query(query) and chunk_count >= 3:
        if original_answerability == "insufficient":
            proposed_answerability = "derivable"
            confidence = max(confidence, 0.6)
            missing_information = []
            ambiguity_level = "medium"
            reasoning = (
                f"{reasoning} Summarization query is derivable from multiple retrieved chunks."
            )

    if _is_red_flags_query(query) and chunk_count >= 4:
        if original_answerability == "insufficient":
            proposed_answerability = "derivable"
            confidence = max(confidence, 0.6)
            missing_information = []
            ambiguity_level = "medium"
            reasoning = (
                f"{reasoning} Red-flags query is derivable from evidence synthesis across chunks."
            )

    if (
        _is_evaluative_fit_query(query)
        and chunk_count >= 4
        and _has_rubric_thesis_evidence(chunks)
    ):
        if original_answerability == "insufficient":
            proposed_answerability = "derivable"
            confidence = max(confidence, 0.62)
            missing_information = []
            ambiguity_level = "medium"
            reasoning = (
                f"{reasoning} Evaluative fit query is derivable using rubric/thesis evidence."
            )

    if _is_procedural_query(query) and _procedural_chunk_count(chunks) >= 2:
        if original_answerability == "insufficient":
            proposed_answerability = "derivable"
            confidence = max(confidence, 0.65)
            missing_information = []
            ambiguity_level = "medium"
            reasoning = f"{reasoning} Procedural answer is derivable by combining sections."

    if _is_inferential_persona_query(query) and _profile_evidence_count(chunks) >= 1:
        if original_answerability == "insufficient":
            proposed_answerability = "derivable"
            confidence = max(confidence, 0.55)
            missing_information = []
            ambiguity_level = "medium"
            reasoning = f"{reasoning} Persona inference is derivable by combining profile sections."

    answerability = _max_reasoning_state(
        original_answerability,
        proposed_answerability,
        has_evidence=has_evidence,
    )
    if answerability in {"direct", "derivable"}:
        missing_information = []
    elif not missing_information:
        missing_information = _default_missing_information(query, chunks)

    return {
        "answerability": answerability,
        "answerable": answerability in {"direct", "derivable"},
        "confidence": confidence,
        "reasoning": reasoning,
        "missing_information": missing_information,
        "ambiguity_level": ambiguity_level,
    }


def _render_evidence_for_prompt(evidence_chunks: Sequence[Dict[str, Any]], *, max_chunks: int = 6) -> str:
    lines: List[str] = []
    for idx, row in enumerate(evidence_chunks[: max(1, max_chunks)], 1):
        if not isinstance(row, dict):
            continue
        source_id = str(row.get("source_id") or f"chunk-{idx}")
        section = str(row.get("section_path") or row.get("section_title") or "").strip()
        page_number = row.get("page_number")
        if not section and page_number is not None:
            section = f"page_{page_number}"
        if not section:
            section = "unknown"
        text = re.sub(r"\s+", " ", str(row.get("text") or "").strip())[:1200]
        if not text:
            continue
        lines.append(f"[{idx}] source_id={source_id}; section={section}; text={text}")
    return "\n".join(lines)


async def evaluate_answerability(query: str, evidence_chunks: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Evaluate if a query is direct, derivable, or insufficient from retrieved evidence.
    """
    chunks = [row for row in evidence_chunks if isinstance(row, dict)]
    if not chunks:
        return _heuristic_answerability(query, chunks)

    prompt = f"""You are an evidence sufficiency evaluator for RAG.
Determine whether the USER QUESTION can be at least partially answered using the EVIDENCE CHUNKS.

USER QUESTION:
{query}

EVIDENCE CHUNKS:
{_render_evidence_for_prompt(chunks)}

Return STRICT JSON:
{{
  "answerability": "direct|derivable|insufficient",
  "confidence": number,
  "reasoning": string,
  "missing_information": ["concrete missing item"],
  "ambiguity_level": "low|medium|high"
}}

Rules:
- Set answerable=true if ANY of the evidence chunks contain information relevant to the question, even partially.
- A partial answer is better than no answer. Only set answerable=false if the evidence is completely unrelated.
- For vague or follow-up questions (e.g. "for this module", "how many"), set answerable=true if evidence provides context.
- If answerable is true, missing_information must be [].
- If answerable is false, missing_information must list concrete missing facts (no generic requests).
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

    answerability = _normalize_answerability(raw.get("answerability"), raw.get("answerable"))
    confidence = _clamp_confidence(raw.get("confidence"), default=0.0)
    reasoning = re.sub(r"\s+", " ", str(raw.get("reasoning") or "").strip())
    if not reasoning:
        reasoning = "Evaluator returned no reasoning."
    ambiguity_level = str(raw.get("ambiguity_level") or "medium").strip().lower()
    if ambiguity_level not in _AMBIGUITY_LEVELS:
        ambiguity_level = "medium"

    missing_information = _normalize_missing_information(raw.get("missing_information"))
    if answerability in {"direct", "derivable"}:
        missing_information = []
        if answerability == "direct":
            confidence = max(confidence, 0.5)
        else:
            confidence = max(confidence, 0.45)
    else:
        if not missing_information:
            missing_information = _default_missing_information(query, chunks)

    return _apply_contract_overrides(
        query,
        chunks,
        {
            "answerability": answerability,
            "answerable": answerability in {"direct", "derivable"},
            "confidence": confidence,
            "reasoning": reasoning,
            "missing_information": missing_information,
            "ambiguity_level": ambiguity_level,
        },
    )


def build_targeted_clarification_questions(
    query: str,
    missing_information: Sequence[str],
    *,
    evidence_chunks: Sequence[Dict[str, Any]] | None = None,
    limit: int = 3,
) -> List[str]:
    evidence_rows = [row for row in (evidence_chunks or []) if isinstance(row, dict)]
    section_candidates = _derive_section_candidates(evidence_rows, limit=4) if evidence_rows else []
    has_evidence = bool(evidence_rows)

    questions: List[str] = []
    for raw in missing_information:
        item = re.sub(r"\s+", " ", str(raw or "").strip()).strip(" .")
        if len(item) < 5:
            continue
        lowered = item.lower()
        if _contains_meta_missing_item(lowered):
            continue
        if section_candidates:
            if len(section_candidates) >= 2:
                question = (
                    f'Are you asking about {item} from "{section_candidates[0]}" '
                    f'or "{section_candidates[1]}"?'
                )
            else:
                question = (
                    f'Do you want this answered from "{section_candidates[0]}" '
                    f'focused on {item}?'
                )
        elif has_evidence:
            focus = item if len(item) <= 84 else f"{item[:81]}..."
            question = f"Within the retrieved document sections, should I focus on {focus}?"
        elif item.endswith("?"):
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
        if section_candidates:
            if len(section_candidates) >= 2:
                default_targets = [
                    f'Should I answer from "{section_candidates[0]}" or "{section_candidates[1]}"?',
                    f'Are you asking for guidance from "{section_candidates[0]}" or decisions from "{section_candidates[1]}"?',
                    "Should I keep this grounded strictly to the retrieved sections above?",
                ]
            else:
                default_targets = [
                    f'Should I answer strictly from "{section_candidates[0]}"?',
                    f'Do you want a summary or recommendation based on "{section_candidates[0]}"?',
                    "Should I keep this grounded strictly to the retrieved section above?",
                ]
        elif has_evidence:
            default_targets = [
                "Should I keep the answer strictly within the retrieved document sections?",
                "Do you want a summary, recommendation, or evaluation from the retrieved evidence?",
                "Should I focus on one specific section of the retrieved document?",
            ]
        else:
            default_targets = [
                "What timeframe should I optimize for?",
                "What budget or resource constraints should I assume?",
                "Who is the primary user or audience for this answer?",
            ]
        for q in default_targets:
            if q not in questions:
                questions.append(q)
            if len(questions) >= max(1, limit):
                break
    return questions[: max(1, limit)]
