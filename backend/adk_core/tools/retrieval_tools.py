"""Retrieval tools used by the chat coordinator."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from google.adk.tools import ToolContext

from adk_core.repositories.conversation_repository import ConversationRepository
from adk_core.repositories.persona_repository import PersonaRepository
from modules.retrieval import retrieve_context_with_intent

_persona_repository = PersonaRepository()
_conversation_repository = ConversationRepository()


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z'-]{2,}", str(text or "").lower())
    }


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


async def retrieve_fact_context(query: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Retrieve factual context from the legacy knowledge base plus persona seeds.
    """
    twin_id = str(tool_context.state.get("twin_id") or "").strip()
    if not twin_id:
        return {"status": "error", "error_message": "Missing twin_id in session state."}

    history_rows = []
    conversation_id = tool_context.state.get("conversation_id")
    if conversation_id:
        history_rows = _conversation_repository.list_messages(conversation_id=conversation_id)[-8:]
    history = [{"role": row["role"], "content": row["content"]} for row in history_rows]

    retrieval_result = await retrieve_context_with_intent(
        query=query,
        twin_id=twin_id,
        conversation_history=history,
        top_k=6,
    )
    contexts = retrieval_result.get("contexts") or []
    citations = []
    normalized_contexts: List[Dict[str, Any]] = []
    for row in contexts:
        source_id = str(row.get("source_id") or "").strip()
        if source_id:
            citations.append(source_id)
        normalized_contexts.append(
            {
                "source_id": source_id,
                "text": str(row.get("text") or row.get("content") or "")[:1000],
                "score": row.get("score"),
                "category": row.get("category") or row.get("block_type"),
            }
        )

    artifact_row = _persona_repository.get_active_artifact(twin_id=twin_id, tenant_id=tool_context.state.get("tenant_id"))
    artifact = (artifact_row or {}).get("artifact_json") or {}
    fallback_claims = []
    for claim in artifact.get("claims") or []:
        text = str(claim.get("text") or "").strip()
        if not text:
            continue
        if _tokens(query) & _tokens(text):
            fallback_claims.append(
                {
                    "source_id": (claim.get("source_ids") or ["persona-claim"])[0],
                    "text": text,
                    "score": claim.get("confidence"),
                    "category": "persona_claim",
                }
            )
        if len(fallback_claims) >= 4:
            break

    all_contexts = normalized_contexts + fallback_claims
    all_citations = _merge_citations(
        citations,
        [item["source_id"] for item in fallback_claims if item.get("source_id")],
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
    ranked = sorted(quotes, key=lambda item: (_quote_score(query, item), float(item.get("confidence") or 0.0)), reverse=True)
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
