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
    "definition of",
    "referred to",
    "refers to",
    "clarification on what",
    "what are the three items",
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

_IDENTITY_METADATA_MARKERS = (
    "identity",
    "bio",
    "about",
    "profile",
    "credibility",
    "expertise",
    "background",
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
    "what do you see in",
    "look for in founders",
    "founder",
    "founders",
    "traits",
    "qualities",
    "act like",
    "digital twin",
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


def _chunk_meta_text(row: Dict[str, Any]) -> str:
    if not isinstance(row, dict):
        return ""
    parts = [
        str(row.get("section_title") or ""),
        str(row.get("section_path") or ""),
        str(row.get("doc_name") or ""),
        str(row.get("filename") or ""),
        str(row.get("source_name") or ""),
    ]
    merged = " ".join(part for part in parts if part)
    return re.sub(r"\s+", " ", merged.strip().lower())


def _is_answer_text_chunk(row: Dict[str, Any]) -> bool:
    if not isinstance(row, dict):
        return False
    raw = row.get("is_answer_text")
    if isinstance(raw, bool):
        return raw
    block_type = str(row.get("block_type") or row.get("chunk_type") or "").strip().lower()
    if not block_type:
        return True
    return block_type not in {"prompt_question", "heading"}


def _has_identity_evidence(chunks: Sequence[Dict[str, Any]]) -> bool:
    for row in chunks[:8]:
        text = _chunk_text(row)
        meta = _chunk_meta_text(row)
        if not _is_answer_text_chunk(row):
            continue
        text_match = bool(text) and any(marker in text for marker in _IDENTITY_EVIDENCE_MARKERS)
        meta_match = bool(meta) and any(marker in meta for marker in _IDENTITY_METADATA_MARKERS)
        if text_match or meta_match:
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
        meta = _chunk_meta_text(row)
        if not text:
            text = ""
        if any(marker in text for marker in _PROFILE_EVIDENCE_MARKERS) or any(
            marker in meta for marker in _PROFILE_EVIDENCE_MARKERS
        ):
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
    if re.search(r'from\s+"[^"]+"', lowered) and re.search(r'\bor\s+"[^"]+"', lowered):
        return True
    if lowered.startswith(("are you asking about ", "do you want this answered from ")):
        return True
    if re.search(r"\b(all three|all 3|both|either)\b", lowered):
        return True
    return False


def _clean_section_label(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "").strip())
    cleaned = re.sub(r"^[0-9]+\)\s*", "", cleaned)
    cleaned = cleaned.strip(" .:-")
    return cleaned


def _is_useful_section_candidate(value: str) -> bool:
    item = _clean_section_label(value)
    if not item:
        return False
    lowered = item.lower()
    if lowered in {"unknown", "none", "n/a"}:
        return False
    if len(item) < 6:
        return False
    if any(ch in item for ch in {">", "|", "="}):
        return False
    words = re.findall(r"[A-Za-z]{2,}", item)
    if len(words) < 2:
        return False
    alpha_chars = sum(1 for ch in item if ch.isalpha())
    ratio = alpha_chars / float(max(len(item), 1))
    if ratio < 0.55:
        return False
    return True


def _derive_section_candidates(
    evidence_chunks: Sequence[Dict[str, Any]],
    *,
    limit: int = 4,
) -> List[str]:
    candidates: List[str] = []

    def _add(value: str) -> None:
        item = _clean_section_label(value)
        if not _is_useful_section_candidate(item):
            return
        low = item.lower()
        if any(existing.lower() == low for existing in candidates):
            return
        candidates.append(item)

    answer_rows = [row for row in evidence_chunks[:10] if isinstance(row, dict) and _is_answer_text_chunk(row)]
    rows_for_sections = answer_rows if answer_rows else [row for row in evidence_chunks[:10] if isinstance(row, dict)]

    for row in rows_for_sections:
        if not isinstance(row, dict):
            continue
        _add(str(row.get("section_title") or ""))
        section_path = str(row.get("section_path") or "")
        if section_path:
            _add(section_path.split("/")[-1])
        doc_name = str(row.get("doc_name") or "")
        if _is_answer_text_chunk(row):
            _add(doc_name)

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
    if not query_tokens:
        answerability = "insufficient"
        return {
            "answerability": answerability,
            "answerable": False,
            "confidence": 0.2,
            "reasoning": "The question is too vague to evaluate against evidence.",
            "missing_information": _default_missing_information(query, chunks),
            "ambiguity_level": "high",
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

    collective_overlap = len(query_tokens.intersection(all_tokens)) / float(len(query_tokens))
    procedural_chunks = _procedural_chunk_count(chunks)
    procedural_query = _is_procedural_query(query)
    inferential_query = _is_inferential_persona_query(query)
    profile_chunks = _profile_evidence_count(chunks)

    if best_overlap >= 0.55 or (len(query_tokens) <= 2 and best_overlap >= 0.45):
        answerability = "direct"
        return {
            "answerability": answerability,
            "answerable": True,
            "confidence": min(0.85, 0.45 + best_overlap),
            "reasoning": "A single evidence chunk directly supports the answer.",
            "missing_information": [],
            "ambiguity_level": "low",
        }

    if (
        (collective_overlap >= 0.62 and supporting_chunks >= 2 and best_overlap >= 0.2)
        or (procedural_query and procedural_chunks >= 2)
        or (inferential_query and profile_chunks >= 1)
    ):
        answerability = "derivable"
        return {
            "answerability": answerability,
            "answerable": True,
            "confidence": min(0.82, max(0.5, 0.35 + (collective_overlap * 0.5))),
            "reasoning": "The answer is derivable by combining evidence across multiple chunks.",
            "missing_information": [],
            "ambiguity_level": "medium",
        }

    answerability = "insufficient"
    return {
        "answerability": answerability,
        "answerable": False,
        "confidence": max(0.15, best_overlap),
        "reasoning": "Evidence does not contain enough direct support for a complete answer.",
        "missing_information": _default_missing_information(query, chunks),
        "ambiguity_level": "medium" if best_overlap >= 0.3 else "high",
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
Determine whether the USER QUESTION can be answered fully and accurately using only the EVIDENCE CHUNKS.

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
- Use only evidence from the chunks.
- direct: one chunk explicitly answers the question.
- derivable: multiple chunks must be combined to answer.
- insufficient: evidence truly lacks required information.
- If answerability is direct or derivable, missing_information must be [].
- If answerability is insufficient, missing_information must list concrete missing facts/constraints (no generic requests).
- Never output meta missing items such as "context for a conversation" or "identity of you".
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
    has_answer_evidence = any(_is_answer_text_chunk(row) for row in evidence_rows)
    section_candidates = (
        _derive_section_candidates(evidence_rows, limit=4)
        if (evidence_rows and has_answer_evidence)
        else []
    )
    has_evidence = bool(evidence_rows)

    if _is_identity_intro_query(query):
        identity_defaults = [
            "Do you want a short bio, core expertise, or both?",
            "Should I focus on background, current focus areas, or communication style?",
            "Should I keep this strictly grounded to the twin identity/profile sections?",
        ]
        return identity_defaults[: max(1, limit)]

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
        elif has_evidence and has_answer_evidence:
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
        elif has_evidence and has_answer_evidence:
            default_targets = [
                "Should I keep the answer strictly within the retrieved document sections?",
                "Do you want a summary, recommendation, or evaluation from the retrieved evidence?",
                "Should I focus on one specific section of the retrieved document?",
            ]
        elif has_evidence:
            default_targets = [
                "Should I retry and focus on non-questionnaire guidance sections in your documents?",
                "Do you want an evidence-based summary from profile/rubric sections if available?",
                "Should I answer only from blocks that contain direct guidance rather than interview prompts?",
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
