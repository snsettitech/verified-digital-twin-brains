"""Retrieval tools used by the chat coordinator."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Iterable, List

from google.adk.tools import ToolContext

from adk_core.repositories.conversation_repository import ConversationRepository
from adk_core.repositories.persona_repository import PersonaRepository
from modules.clients import get_pinecone_index
from modules.pinecone_adapter import PineconeIndexAdapter

logger = logging.getLogger(__name__)

_persona_repository = PersonaRepository()
_conversation_repository = ConversationRepository()
_GENERIC_CONTEXT_TERMS = {
    "that",
    "this",
    "those",
    "these",
    "there",
    "thing",
    "stuff",
    "more",
    "about",
    "yourself",
    "your",
}
_STOPWORDS = {
    "about",
    "after",
    "also",
    "been",
    "being",
    "from",
    "have",
    "into",
    "like",
    "much",
    "more",
    "than",
    "that",
    "them",
    "then",
    "they",
    "this",
    "what",
    "when",
    "where",
    "which",
    "while",
    "with",
    "would",
    "your",
    "yourself",
}


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z'-]{2,}", str(text or "").lower())
        if token not in _STOPWORDS
    }


def _parse_json_state(raw: Any, default: Any) -> Any:
    if not raw:
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(str(raw))
    except Exception:
        return default


def _quote_score(query: str, quote: Dict[str, Any]) -> float:
    overlap = _tokens(query) & _tokens(quote.get("quote_text") or quote.get("quote") or "")
    return float(len(overlap))


def _merge_citations(*groups: List[str]) -> List[str]:
    merged: List[str] = []
    seen = set()
    for group in groups:
        for item in group:
            if item and item not in seen:
                seen.add(item)
                merged.append(item)
    return merged


def _load_persona_artifact(tool_context: ToolContext, twin_id: str) -> Dict[str, Any]:
    artifact = _parse_json_state(tool_context.state.get("persona_artifact_json"), {})
    if artifact:
        return artifact

    artifact_row = _persona_repository.get_active_artifact(
        twin_id=twin_id,
        tenant_id=tool_context.state.get("tenant_id"),
    )
    artifact = (artifact_row or {}).get("artifact_json") or {}
    if artifact:
        tool_context.state["persona_artifact_json"] = json.dumps(artifact)
    return artifact


def _field_snippets(value: Any, prefix: str) -> List[str]:
    snippets: List[str] = []
    if isinstance(value, dict):
        for key, inner in value.items():
            inner_prefix = f"{prefix}.{key}" if prefix else str(key)
            snippets.extend(_field_snippets(inner, inner_prefix))
    elif isinstance(value, list):
        scalar_items = [str(item).strip() for item in value if not isinstance(item, (dict, list)) and str(item).strip()]
        if scalar_items:
            snippets.append(f"{prefix}: {', '.join(scalar_items[:8])}")
        for idx, item in enumerate(value[:4]):
            if isinstance(item, (dict, list)):
                snippets.extend(_field_snippets(item, f"{prefix}[{idx}]"))
    else:
        text = str(value or "").strip()
        if text:
            snippets.append(f"{prefix}: {text}")
    return snippets


def _query_terms(query: str, history_rows: List[Dict[str, Any]]) -> set[str]:
    query_terms = _tokens(query)
    if len(query_terms) >= 2 and not (query_terms & _GENERIC_CONTEXT_TERMS):
        return query_terms

    history_terms: set[str] = set()
    for row in history_rows[-4:]:
        if str(row.get("role") or "") != "user":
            continue
        history_terms |= _tokens(str(row.get("content") or ""))
    return query_terms | history_terms


def _score_text(query_terms: set[str], query: str, text: str) -> float:
    text_terms = _tokens(text)
    overlap = query_terms & text_terms if query_terms else set()
    if overlap:
        return float(len(overlap)) + (len(overlap) / max(1, len(query_terms)))
    normalized_query = str(query or "").strip().lower()
    if normalized_query and normalized_query in str(text or "").lower():
        return 1.0
    return 0.0


def _ranked_persona_candidates(
    artifact: Dict[str, Any],
    *,
    query: str,
    query_terms: set[str],
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []

    for claim in artifact.get("claims") or []:
        text = str(claim.get("text") or "").strip()
        if not text:
            continue
        score = _score_text(query_terms, query, text) + float(claim.get("confidence") or 0.0)
        source_ids = [str(item) for item in (claim.get("source_ids") or []) if item]
        candidates.append(
            {
                "source_id": source_ids[0] if source_ids else "persona-artifact",
                "text": text,
                "score": score,
                "category": "persona_claim",
            }
        )

    for item in artifact.get("timeline") or []:
        date_or_range = str(item.get("date_or_range") or "").strip()
        event = str(item.get("event") or "").strip()
        if not event:
            continue
        text = f"{date_or_range}: {event}".strip(": ")
        score = _score_text(query_terms, query, text) + float(item.get("confidence") or 0.0)
        source_ids = [str(src) for src in (item.get("source_ids") or []) if src]
        candidates.append(
            {
                "source_id": source_ids[0] if source_ids else "persona-artifact",
                "text": text,
                "score": score,
                "category": "persona_timeline",
            }
        )

    for seed in artifact.get("retrieval_seeds") or []:
        text = str(seed or "").strip()
        if not text:
            continue
        candidates.append(
            {
                "source_id": "persona-artifact",
                "text": text,
                "score": _score_text(query_terms, query, text) + 0.2,
                "category": "persona_seed",
            }
        )

    profile_blocks: List[Dict[str, Any]] = []
    for field_name in (
        "identity_frame",
        "thinking_style",
        "public_profile",
        "persona_identity_pack",
        "provenance",
    ):
        for snippet in _field_snippets(artifact.get(field_name) or {}, field_name)[:10]:
            profile_blocks.append(
                {
                    "source_id": "persona-artifact",
                    "text": snippet,
                    "score": _score_text(query_terms, query, snippet),
                    "category": field_name,
                }
            )

    for field_name in ("values_and_decision_heuristics", "communication_rules"):
        for idx, item in enumerate(artifact.get(field_name) or [], start=1):
            text = str(item or "").strip()
            if not text:
                continue
            profile_blocks.append(
                {
                    "source_id": "persona-artifact",
                    "text": text,
                    "score": _score_text(query_terms, query, text) + 0.1,
                    "category": field_name,
                }
            )
            if idx >= 8:
                break

    candidates.extend(profile_blocks)
    ranked = sorted(candidates, key=lambda item: float(item.get("score") or 0.0), reverse=True)
    return ranked


def _fallback_persona_context(artifact: Dict[str, Any]) -> List[Dict[str, Any]]:
    fallback: List[Dict[str, Any]] = []
    subject_name = str(artifact.get("subject_name") or "").strip()
    if subject_name:
        fallback.append(
            {
                "source_id": "persona-artifact",
                "text": f"Subject: {subject_name}",
                "score": 0.1,
                "category": "persona_identity",
            }
        )

    for claim in artifact.get("claims") or []:
        text = str(claim.get("text") or "").strip()
        if not text:
            continue
        fallback.append(
            {
                "source_id": ((claim.get("source_ids") or ["persona-artifact"])[0]),
                "text": text,
                "score": float(claim.get("confidence") or 0.0),
                "category": "persona_claim",
            }
        )
        if len(fallback) >= 4:
            return fallback

    for field_name in ("public_profile", "identity_frame"):
        for snippet in _field_snippets(artifact.get(field_name) or {}, field_name)[:2]:
            fallback.append(
                {
                    "source_id": "persona-artifact",
                    "text": snippet,
                    "score": 0.05,
                    "category": field_name,
                }
            )
            if len(fallback) >= 4:
                return fallback
    return fallback


def _query_integrated_persona_namespace(query: str, twin_id: str) -> List[Dict[str, Any]]:
    try:
        adapter = PineconeIndexAdapter(get_pinecone_index())
    except Exception as exc:
        logger.info("Skipping ADK namespace retrieval for twin %s: %s", twin_id, exc)
        return []

    if adapter.mode != "integrated":
        return []

    try:
        response = adapter.query(
            vector=None,
            query_text=query,
            top_k=4,
            namespace=f"adk-persona-{twin_id}",
            include_metadata=True,
        )
    except Exception as exc:
        logger.warning("ADK namespace retrieval failed for twin %s: %s", twin_id, exc)
        return []

    normalized: List[Dict[str, Any]] = []
    for match in response.get("matches") or []:
        metadata = dict(match.get("metadata") or {})
        text = str(metadata.get("text") or "").strip()
        if not text:
            continue
        source_ids = [str(item) for item in (metadata.get("source_ids") or []) if item]
        source_id = str(metadata.get("source_id") or "").strip()
        normalized.append(
            {
                "source_id": source_id or (source_ids[0] if source_ids else "persona-artifact"),
                "text": text[:1000],
                "score": float(match.get("score") or 0.0),
                "category": str(metadata.get("doc_type") or "persona_namespace"),
            }
        )
    return normalized


def _dedupe_contexts(rows: Iterable[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    seen = set()
    for row in rows:
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        key = (text.lower(), str(row.get("category") or "").lower())
        if key in seen:
            continue
        seen.add(key)
        results.append(
            {
                "source_id": str(row.get("source_id") or "").strip(),
                "text": text[:1000],
                "score": row.get("score"),
                "category": row.get("category"),
            }
        )
        if len(results) >= limit:
            break
    return results


async def retrieve_fact_context(query: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Retrieve factual context from the canonical ADK persona artifact and optional ADK-owned namespace.
    """
    twin_id = str(tool_context.state.get("twin_id") or "").strip()
    if not twin_id:
        return {"status": "error", "error_message": "Missing twin_id in session state."}

    history_rows: List[Dict[str, Any]] = []
    conversation_id = tool_context.state.get("conversation_id")
    if conversation_id:
        history_rows = _conversation_repository.list_messages(conversation_id=conversation_id)[-8:]

    artifact = _load_persona_artifact(tool_context, twin_id)
    query_terms = _query_terms(query, history_rows)
    persona_contexts = _ranked_persona_candidates(artifact, query=query, query_terms=query_terms)
    namespace_contexts = _query_integrated_persona_namespace(query, twin_id)

    ranked_contexts = sorted(
        persona_contexts + namespace_contexts,
        key=lambda item: float(item.get("score") or 0.0),
        reverse=True,
    )
    all_contexts = _dedupe_contexts(ranked_contexts, limit=6)
    if not all_contexts:
        all_contexts = _dedupe_contexts(_fallback_persona_context(artifact), limit=4)

    all_citations = _merge_citations(
        [row["source_id"] for row in all_contexts if row.get("source_id")],
    )
    tool_context.state["fact_context_json"] = json.dumps(all_contexts)
    tool_context.state["fact_citations_json"] = json.dumps(all_citations)
    tool_context.state["active_citations_json"] = json.dumps(
        _merge_citations(
            json.loads(tool_context.state.get("quote_citations_json") or "[]"),
            all_citations,
        )
    )
    return {
        "status": "success",
        "result_count": len(all_contexts),
        "citations": all_citations,
    }


def retrieve_quote_context(query: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Retrieve top persona quotes using lightweight lexical matching.
    """
    twin_id = str(tool_context.state.get("twin_id") or "").strip()
    if not twin_id:
        return {"status": "error", "error_message": "Missing twin_id in session state."}

    quotes = _persona_repository.list_quotes(
        twin_id=twin_id,
        tenant_id=tool_context.state.get("tenant_id"),
    )
    if not quotes:
        artifact = _load_persona_artifact(tool_context, twin_id)
        quotes = [
            {
                "quote_text": item.get("quote"),
                "source_id": item.get("source_id"),
                "context": item.get("context") or "",
                "confidence": item.get("confidence"),
            }
            for item in artifact.get("quote_pack") or []
            if item.get("quote")
        ]

    ranked = sorted(
        quotes,
        key=lambda item: (_quote_score(query, item), float(item.get("confidence") or 0.0)),
        reverse=True,
    )
    top_quotes = [
        {
            "quote": row.get("quote_text"),
            "source_id": row.get("source_id"),
            "context": row.get("context") or "",
            "confidence": row.get("confidence"),
        }
        for row in ranked[:4]
        if row.get("quote_text")
    ]
    citations = [row["source_id"] for row in top_quotes if row.get("source_id")]
    tool_context.state["quote_context_json"] = json.dumps(top_quotes)
    tool_context.state["quote_citations_json"] = json.dumps(citations)
    tool_context.state["active_citations_json"] = json.dumps(
        _merge_citations(
            json.loads(tool_context.state.get("fact_citations_json") or "[]"),
            citations,
        )
    )
    return {
        "status": "success",
        "result_count": len(top_quotes),
        "citations": citations,
    }


def retrieve_recent_conversation(max_messages: int, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Load recent conversation turns for follow-up coherence.
    """
    conversation_id = str(tool_context.state.get("conversation_id") or "").strip()
    if not conversation_id:
        tool_context.state["recent_conversation_json"] = "[]"
        return {"status": "success", "result_count": 0}

    rows = _conversation_repository.list_messages(conversation_id=conversation_id)
    simplified = [
        {"role": row.get("role"), "content": row.get("content")}
        for row in rows[-max(1, min(max_messages, 12)) :]
    ]
    tool_context.state["recent_conversation_json"] = json.dumps(simplified)
    return {"status": "success", "result_count": len(simplified)}
