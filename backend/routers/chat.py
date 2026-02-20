from fastapi import APIRouter, Depends, HTTPException, Header, Request
from fastapi.responses import StreamingResponse
from typing import List, Optional, Dict, Any, Set, Tuple
from modules.schemas import (
    ChatRequest, ChatMetadata, ChatWidgetRequest, PublicChatRequest, 
    MessageSchema, ConversationSchema
)
from modules.auth_guard import get_current_user, verify_twin_ownership, verify_conversation_ownership, ensure_twin_active
from modules.access_groups import get_user_group, get_default_group
from modules.observability import (
    supabase, get_conversations, get_messages, 
    log_interaction, create_conversation
)
from modules.agent import run_agent_stream
from modules.identity_gate import run_identity_gate
from modules.interaction_context import (
    InteractionContext,
    ResolvedInteractionContext,
    resolve_owner_chat_context,
    resolve_widget_context,
    resolve_public_share_context,
    identity_gate_mode_for_context,
    trace_fields,
)
from modules.persona_auditor import audit_persona_response
from modules.persona_spec_store import get_active_persona_spec
from modules.owner_memory_store import format_owner_memory_context
from modules.response_policy import UNCERTAINTY_RESPONSE, owner_guidance_suffix
from modules.grounding_policy import get_grounding_policy
from modules.deepagents_policy import classify_deepagents_intent
from modules.runtime_audit_store import (
    enqueue_owner_review_item,
    persist_response_audit,
    persist_routing_decision,
)
from langchain_core.messages import HumanMessage, AIMessage
from datetime import datetime
import re
import json
import asyncio
import uuid
import os
from modules.langfuse_sdk import (
    flush_client,
    get_client as get_langfuse_client,
    is_enabled as is_langfuse_enabled,
    langfuse_context,
    log_score,
    observe,
    propagate_attributes,
)

_langfuse_available = is_langfuse_enabled()
_langfuse_client = get_langfuse_client()


import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

GROUNDING_VERIFIER_ENABLED = os.getenv("GROUNDING_VERIFIER_ENABLED", "true").lower() == "true"
GROUNDING_MIN_SUPPORT_RATIO = float(os.getenv("GROUNDING_MIN_SUPPORT_RATIO", "0.78"))
GROUNDING_MIN_CLAIM_OVERLAP = float(os.getenv("GROUNDING_MIN_CLAIM_OVERLAP", "0.28"))
GROUNDING_MAX_CONTEXT_SNIPPETS = max(3, int(os.getenv("GROUNDING_MAX_CONTEXT_SNIPPETS", "8")))
ONLINE_EVAL_POLICY_ENABLED = os.getenv("ONLINE_EVAL_POLICY_ENABLED", "true").lower() == "true"
ONLINE_EVAL_POLICY_MIN_OVERALL_SCORE = float(os.getenv("ONLINE_EVAL_POLICY_MIN_OVERALL_SCORE", "0.72"))
ONLINE_EVAL_POLICY_TIMEOUT_SECONDS = float(os.getenv("ONLINE_EVAL_POLICY_TIMEOUT_SECONDS", "8.0"))
ONLINE_EVAL_POLICY_MIN_CONTEXT_CHARS = max(0, int(os.getenv("ONLINE_EVAL_POLICY_MIN_CONTEXT_CHARS", "80")))
ONLINE_EVAL_POLICY_STRICT_ONLY = os.getenv("ONLINE_EVAL_POLICY_STRICT_ONLY", "false").lower() == "true"
ONLINE_EVAL_POLICY_FALLBACK_POINTS = max(1, int(os.getenv("ONLINE_EVAL_POLICY_FALLBACK_POINTS", "3")))
ONLINE_EVAL_LINE_EXTRACTOR_MIN_SCORE = float(os.getenv("ONLINE_EVAL_LINE_EXTRACTOR_MIN_SCORE", "0.2"))

_GROUNDING_STOPWORDS = {
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
    "have",
    "i",
    "in",
    "is",
    "it",
    "my",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "we",
    "what",
    "with",
    "you",
    "your",
}


def _uncertainty_message(interaction_context: Optional[str]) -> str:
    return f"{UNCERTAINTY_RESPONSE}{owner_guidance_suffix(interaction_context)}"


def _grounding_tokens(text: str) -> Set[str]:
    tokens = re.findall(r"[a-z0-9][a-z0-9._-]*", (text or "").lower())
    return {tok for tok in tokens if len(tok) > 2 and tok not in _GROUNDING_STOPWORDS}


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None


def _avg(values: List[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / float(len(values)))


def _is_quote_intent(query: str) -> bool:
    return bool(get_grounding_policy(query).get("quote_intent"))


def _classify_query_class(query: str) -> str:
    return str(get_grounding_policy(query).get("query_class") or "factual")


def _summarize_retrieval_stats(contexts: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows = [row for row in (contexts or []) if isinstance(row, dict)]
    retrieval_stats_payload: Dict[str, Any] = {}
    for row in rows:
        raw_stats = row.get("retrieval_stats")
        if isinstance(raw_stats, dict):
            retrieval_stats_payload = dict(raw_stats)
            break

    def _extract_scores(keys: Tuple[str, ...]) -> List[float]:
        values: List[float] = []
        for row in rows:
            score = None
            for key in keys:
                candidate = _safe_float(row.get(key))
                if candidate is not None:
                    score = candidate
                    break
            if score is not None:
                values.append(score)
        values.sort(reverse=True)
        return values

    dense_scores = _extract_scores(("vector_score",))
    sparse_scores = _extract_scores(("sparse_score", "lexical_score"))
    rerank_scores = _extract_scores(("score",))

    dense_top1 = dense_scores[0] if dense_scores else 0.0
    sparse_top1 = sparse_scores[0] if sparse_scores else 0.0
    rerank_top1 = rerank_scores[0] if rerank_scores else 0.0

    block_counts: Dict[str, int] = {}
    for row in rows:
        block_type = str(row.get("block_type") or row.get("chunk_type") or "unknown").strip().lower() or "unknown"
        block_counts[block_type] = block_counts.get(block_type, 0) + 1

    fallback_stats = {
        "chunk_count": len(rows),
        "dense_top1": dense_top1,
        "dense_top5_avg": _avg(dense_scores[:5]),
        "sparse_top1": sparse_top1,
        "sparse_top5_avg": _avg(sparse_scores[:5]),
        "rerank_top1": rerank_top1,
        "rerank_top5_avg": _avg(rerank_scores[:5]),
        "evidence_block_counts": block_counts,
    }
    if retrieval_stats_payload:
        merged = dict(fallback_stats)
        merged.update(retrieval_stats_payload)
        merged["chunk_count"] = len(rows)
        if "evidence_block_counts" not in merged or not isinstance(merged.get("evidence_block_counts"), dict):
            merged["evidence_block_counts"] = block_counts
        return merged
    return fallback_stats


def _extract_answerability_state(planning_output: Optional[Dict[str, Any]]) -> str:
    if not isinstance(planning_output, dict):
        return "unknown"
    raw = planning_output.get("answerability")
    if isinstance(raw, dict):
        normalized = str(raw.get("answerability") or "").strip().lower()
        if normalized:
            return normalized
    return "unknown"


def _extract_deepagents_metadata(planning_output: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(planning_output, dict):
        return {}

    lane = planning_output.get("execution_lane")
    if not isinstance(lane, dict):
        return {}

    status = str(lane.get("status") or "").strip().lower()
    if not status:
        return {}

    return {
        "status": status,
        "needs_approval": bool(lane.get("needs_approval", False)),
        "action_type": str(lane.get("action_type") or "").strip() or None,
        "action_id": str(lane.get("action_id") or "").strip() or None,
        "execution_id": str(lane.get("execution_id") or "").strip() or None,
        "error_code": str(lane.get("error_code") or "").strip() or None,
    }


def _selected_evidence_block_types(contexts: List[Dict[str, Any]]) -> List[str]:
    values: List[str] = []
    for row in contexts:
        if not isinstance(row, dict):
            continue
        block_type = str(row.get("block_type") or row.get("chunk_type") or "").strip().lower()
        if block_type and block_type not in values:
            values.append(block_type)
    return values


def _build_debug_snapshot(
    *,
    query: str,
    requires_evidence: Optional[bool],
    planning_output: Optional[Dict[str, Any]],
    routing_decision: Optional[Dict[str, Any]],
    contexts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    policy = get_grounding_policy(query)
    query_class = str(policy.get("query_class") or "factual")
    quote_intent = bool(policy.get("quote_intent"))
    answerability_state = _extract_answerability_state(planning_output)
    planner_telemetry = _extract_planner_telemetry(planning_output)
    planner_action = "unknown"
    if isinstance(routing_decision, dict):
        planner_action = str(routing_decision.get("action") or planner_action)
    retrieval_stats = _summarize_retrieval_stats(contexts)
    selected_block_types = _selected_evidence_block_types(contexts)
    return {
        "query_class": query_class,
        "requires_evidence": bool(requires_evidence) if requires_evidence is not None else None,
        "quote_intent": quote_intent,
        "answerability_state": answerability_state,
        "planner_action": planner_action,
        "retrieval_stats": retrieval_stats,
        "selected_evidence_block_types": selected_block_types,
        "retrieval.retry_reason": planner_telemetry["retrieval.retry_reason"],
        "retrieval.prompt_question_dominance": planner_telemetry["retrieval.prompt_question_dominance"],
        "retrieval.answer_text_ratio": planner_telemetry["retrieval.answer_text_ratio"],
        "planner.intent_recovered": planner_telemetry["planner.intent_recovered"],
        "clarify.noisy_section_filtered_count": planner_telemetry["clarify.noisy_section_filtered_count"],
        "clarify.option_count": planner_telemetry["clarify.option_count"],
        "deepagents_route_rate": planner_telemetry["deepagents_route_rate"],
        "deepagents_forbidden_context_rate": planner_telemetry["deepagents_forbidden_context_rate"],
        "deepagents_missing_params_rate": planner_telemetry["deepagents_missing_params_rate"],
        "deepagents_needs_approval_rate": planner_telemetry["deepagents_needs_approval_rate"],
        "deepagents_executed_rate": planner_telemetry["deepagents_executed_rate"],
        "public_action_query_guarded_rate": planner_telemetry["public_action_query_guarded_rate"],
        "selection_recovery_failure_rate": planner_telemetry["selection_recovery_failure_rate"],
    }


def _extract_planner_telemetry(planning_output: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    defaults = {
        "retrieval.retry_reason": "none",
        "retrieval.prompt_question_dominance": False,
        "retrieval.answer_text_ratio": 0.0,
        "planner.intent_recovered": False,
        "clarify.noisy_section_filtered_count": 0,
        "clarify.option_count": 0,
        "deepagents_route_rate": 0,
        "deepagents_forbidden_context_rate": 0,
        "deepagents_missing_params_rate": 0,
        "deepagents_needs_approval_rate": 0,
        "deepagents_executed_rate": 0,
        "public_action_query_guarded_rate": 0,
        "selection_recovery_failure_rate": 0,
    }
    if not isinstance(planning_output, dict):
        return defaults
    raw = planning_output.get("telemetry")
    if not isinstance(raw, dict):
        return defaults

    out = dict(defaults)
    for key in out.keys():
        if key in raw:
            out[key] = raw.get(key)

    try:
        out["retrieval.answer_text_ratio"] = float(out.get("retrieval.answer_text_ratio") or 0.0)
    except Exception:
        out["retrieval.answer_text_ratio"] = 0.0
    out["retrieval.prompt_question_dominance"] = bool(
        out.get("retrieval.prompt_question_dominance")
    )
    out["planner.intent_recovered"] = bool(out.get("planner.intent_recovered"))
    out["clarify.noisy_section_filtered_count"] = int(
        out.get("clarify.noisy_section_filtered_count") or 0
    )
    out["clarify.option_count"] = int(out.get("clarify.option_count") or 0)
    out["deepagents_route_rate"] = int(out.get("deepagents_route_rate") or 0)
    out["deepagents_forbidden_context_rate"] = int(
        out.get("deepagents_forbidden_context_rate") or 0
    )
    out["deepagents_missing_params_rate"] = int(out.get("deepagents_missing_params_rate") or 0)
    out["deepagents_needs_approval_rate"] = int(out.get("deepagents_needs_approval_rate") or 0)
    out["deepagents_executed_rate"] = int(out.get("deepagents_executed_rate") or 0)
    out["public_action_query_guarded_rate"] = int(
        out.get("public_action_query_guarded_rate") or 0
    )
    out["selection_recovery_failure_rate"] = int(
        out.get("selection_recovery_failure_rate") or 0
    )
    out["retrieval.retry_reason"] = str(out.get("retrieval.retry_reason") or "none")
    return out


def _emit_langfuse_turn_telemetry(debug_snapshot: Dict[str, Any]) -> None:
    if not isinstance(debug_snapshot, dict):
        return
    counter_payload = {
        "deepagents_route_rate": int(debug_snapshot.get("deepagents_route_rate", 0) or 0),
        "deepagents_forbidden_context_rate": int(
            debug_snapshot.get("deepagents_forbidden_context_rate", 0) or 0
        ),
        "deepagents_missing_params_rate": int(
            debug_snapshot.get("deepagents_missing_params_rate", 0) or 0
        ),
        "deepagents_needs_approval_rate": int(
            debug_snapshot.get("deepagents_needs_approval_rate", 0) or 0
        ),
        "deepagents_executed_rate": int(debug_snapshot.get("deepagents_executed_rate", 0) or 0),
        "public_action_query_guarded_rate": int(
            debug_snapshot.get("public_action_query_guarded_rate", 0) or 0
        ),
        "selection_recovery_failure_rate": int(
            debug_snapshot.get("selection_recovery_failure_rate", 0) or 0
        ),
    }
    payload = {
        "retrieval.retry_reason": debug_snapshot.get("retrieval.retry_reason", "none"),
        "retrieval.prompt_question_dominance": bool(
            debug_snapshot.get("retrieval.prompt_question_dominance", False)
        ),
        "retrieval.answer_text_ratio": float(
            debug_snapshot.get("retrieval.answer_text_ratio", 0.0) or 0.0
        ),
        "planner.intent_recovered": bool(debug_snapshot.get("planner.intent_recovered", False)),
        "clarify.noisy_section_filtered_count": int(
            debug_snapshot.get("clarify.noisy_section_filtered_count", 0) or 0
        ),
        "clarify.option_count": int(debug_snapshot.get("clarify.option_count", 0) or 0),
        **counter_payload,
    }
    try:
        logger.info(json.dumps({"component": "chat_telemetry", "event": "turn_counters", **counter_payload}))
    except Exception:
        pass
    try:
        langfuse_context.update_current_observation(metadata=payload)
        langfuse_context.update_current_trace(metadata=payload)
    except Exception:
        pass


def _extract_turn_counter_payload(debug_snapshot: Dict[str, Any]) -> Dict[str, int]:
    if not isinstance(debug_snapshot, dict):
        return {
            "deepagents_route_rate": 0,
            "deepagents_forbidden_context_rate": 0,
            "deepagents_missing_params_rate": 0,
            "deepagents_needs_approval_rate": 0,
            "deepagents_executed_rate": 0,
            "public_action_query_guarded_rate": 0,
            "selection_recovery_failure_rate": 0,
        }
    return {
        "deepagents_route_rate": int(debug_snapshot.get("deepagents_route_rate", 0) or 0),
        "deepagents_forbidden_context_rate": int(
            debug_snapshot.get("deepagents_forbidden_context_rate", 0) or 0
        ),
        "deepagents_missing_params_rate": int(
            debug_snapshot.get("deepagents_missing_params_rate", 0) or 0
        ),
        "deepagents_needs_approval_rate": int(
            debug_snapshot.get("deepagents_needs_approval_rate", 0) or 0
        ),
        "deepagents_executed_rate": int(debug_snapshot.get("deepagents_executed_rate", 0) or 0),
        "public_action_query_guarded_rate": int(
            debug_snapshot.get("public_action_query_guarded_rate", 0) or 0
        ),
        "selection_recovery_failure_rate": int(
            debug_snapshot.get("selection_recovery_failure_rate", 0) or 0
        ),
    }


async def _run_identity_gate_passthrough(
    *,
    query: str,
    history: List[Dict[str, Any]],
    twin_id: str,
    tenant_id: Optional[str],
    group_id: Optional[str],
    mode: str,
    allow_clarify: bool = False,
) -> Dict[str, Any]:
    """
    Identity gate is restricted to context/safety interpretation.
    Clarification decisions are planner-only.
    """
    policy = get_grounding_policy(query)
    if bool(policy.get("is_smalltalk")):
        return {
            "decision": "ANSWER",
            "requires_owner": False,
            "reason": "smalltalk_bypass_pre_identity_gate",
            "gate_mode": mode,
            "owner_memory": [],
            "owner_memory_refs": [],
            "owner_memory_context": "",
        }

    gate = await run_identity_gate(
        query=query,
        history=history,
        twin_id=twin_id,
        tenant_id=tenant_id,
        group_id=group_id,
        mode=mode,
        allow_clarify=allow_clarify,
    )
    if str(gate.get("decision") or "").upper() == "CLARIFY":
        return {
            **gate,
            "decision": "ANSWER",
            "reason": f"clarify_suppressed:{gate.get('reason') or 'identity_gate'}",
            "question": "",
            "options": [],
            "memory_write_proposal": {},
            "owner_memory": gate.get("owner_memory") or [],
            "owner_memory_refs": gate.get("owner_memory_refs") or [],
            "owner_memory_context": gate.get("owner_memory_context") or "",
        }
    return gate


def _merge_context_snippets(existing: List[Dict[str, Any]], incoming: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    if not isinstance(incoming, list):
        return existing

    seen = {
        f"{(row.get('source_id') or '').strip()}::{(row.get('text') or '').strip()[:180]}"
        for row in existing
        if isinstance(row, dict)
    }
    merged = list(existing)

    for row in incoming:
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        source_id = str(row.get("source_id") or "").strip()
        sig = f"{source_id}::{text[:180]}"
        if sig in seen:
            continue
        normalized_row: Dict[str, Any] = {"source_id": source_id, "text": text}
        for key in ("section_title", "section_path", "chunk_type", "block_type"):
            value = row.get(key)
            if isinstance(value, str) and value.strip():
                normalized_row[key] = value.strip()
        raw_stats = row.get("retrieval_stats")
        if isinstance(raw_stats, dict):
            normalized_row["retrieval_stats"] = dict(raw_stats)
        for key in ("score", "vector_score"):
            value = row.get(key)
            if isinstance(value, (int, float)):
                normalized_row[key] = float(value)
        merged.append(normalized_row)
        seen.add(sig)
        if len(merged) >= GROUNDING_MAX_CONTEXT_SNIPPETS:
            break

    return merged


def _load_public_publish_controls(twin_id: str) -> Dict[str, Set[str]]:
    controls = {
        "published_identity_topics": set(),
        "published_policy_topics": set(),
        "published_source_ids": set(),
    }
    try:
        twin_res = supabase.table("twins").select("settings").eq("id", twin_id).single().execute()
        settings = twin_res.data.get("settings") if twin_res.data else {}
        publish_controls = settings.get("publish_controls") if isinstance(settings, dict) else {}
        if not isinstance(publish_controls, dict):
            return controls
        for key in ("published_identity_topics", "published_policy_topics", "published_source_ids"):
            raw = publish_controls.get(key)
            if isinstance(raw, list):
                controls[key] = {
                    str(value).strip()
                    for value in raw
                    if isinstance(value, (str, int, float)) and str(value).strip()
                }
    except Exception:
        return controls
    return controls


def _filter_public_owner_memory_candidates(
    owner_memory_candidates: List[Dict[str, Any]],
    *,
    published_identity_topics: Set[str],
    published_policy_topics: Set[str],
) -> List[Dict[str, Any]]:
    if not owner_memory_candidates:
        return []
    out: List[Dict[str, Any]] = []
    policy_types = {"stance", "lens", "tone_rule"}
    for row in owner_memory_candidates:
        if not isinstance(row, dict):
            continue
        topic = str(row.get("topic_normalized") or row.get("topic") or "").strip()
        if not topic:
            continue
        memory_type = str(row.get("memory_type") or "").strip().lower()
        if memory_type in policy_types:
            if topic in published_policy_topics:
                out.append(row)
        else:
            if topic in published_identity_topics:
                out.append(row)
    return out


def _filter_contexts_to_allowed_sources(
    contexts: List[Dict[str, Any]],
    allowed_source_ids: Set[str],
) -> Tuple[List[Dict[str, Any]], int]:
    if not isinstance(contexts, list):
        return [], 0
    if not allowed_source_ids:
        return [], len([row for row in contexts if isinstance(row, dict)])

    filtered: List[Dict[str, Any]] = []
    removed = 0
    for row in contexts:
        if not isinstance(row, dict):
            continue
        source_id = str(row.get("source_id") or "").strip()
        if source_id and source_id in allowed_source_ids:
            filtered.append(row)
        else:
            removed += 1
    return filtered, removed


def _filter_citations_to_allowed_sources(citations: List[str], allowed_source_ids: Set[str]) -> List[str]:
    if not isinstance(citations, list):
        return []
    if not allowed_source_ids:
        return []
    return [c for c in citations if isinstance(c, str) and c.strip() in allowed_source_ids]


def _extract_answer_claims(answer: str) -> List[str]:
    raw = re.split(r"(?<=[.!?])\s+|\n+", (answer or "").strip())
    claims = []
    for item in raw:
        line = item.strip().lstrip("-*").strip()
        if len(line) < 18:
            continue
        claims.append(line)
    return claims[:6]


def _evaluate_grounding_support(answer: str, contexts: List[Dict[str, Any]]) -> Dict[str, Any]:
    claims = _extract_answer_claims(answer)
    if not claims:
        return {
            "supported": True,
            "support_ratio": 1.0,
            "total_claims": 0,
            "supported_claims": 0,
            "unsupported_claims": [],
        }

    context_token_sets = [_grounding_tokens(str(c.get("text") or "")) for c in contexts if isinstance(c, dict)]
    if not context_token_sets:
        return {
            "supported": False,
            "support_ratio": 0.0,
            "total_claims": len(claims),
            "supported_claims": 0,
            "unsupported_claims": claims[:3],
        }

    supported_claims = 0
    unsupported_claims: List[str] = []

    for claim in claims:
        claim_tokens = _grounding_tokens(claim)
        if not claim_tokens:
            supported_claims += 1
            continue

        max_overlap = 0.0
        for token_set in context_token_sets:
            if not token_set:
                continue
            overlap = len(claim_tokens.intersection(token_set)) / float(len(claim_tokens))
            if overlap > max_overlap:
                max_overlap = overlap

        if max_overlap >= GROUNDING_MIN_CLAIM_OVERLAP:
            supported_claims += 1
        else:
            unsupported_claims.append(claim)

    support_ratio = supported_claims / float(len(claims))
    return {
        "supported": support_ratio >= GROUNDING_MIN_SUPPORT_RATIO,
        "support_ratio": support_ratio,
        "total_claims": len(claims),
        "supported_claims": supported_claims,
        "unsupported_claims": unsupported_claims[:3],
    }


def _resolve_trace_id(fallback: Optional[str] = None) -> str:
    trace_id = None
    try:
        if hasattr(langfuse_context, "get_current_trace_id"):
            trace_id = langfuse_context.get_current_trace_id()
        if not trace_id:
            trace_id = getattr(langfuse_context, "current_trace_id", None)
    except Exception:
        trace_id = None
    return str(trace_id or fallback or "unknown")


def _online_eval_capable() -> bool:
    if not ONLINE_EVAL_POLICY_ENABLED:
        return False
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return False
    if api_key.lower().startswith("mock"):
        return False
    return True


def _build_eval_context_text(contexts: List[Dict[str, Any]], max_snippets: int = 5, max_chars: int = 4000) -> str:
    if not contexts or max_chars <= 0:
        return ""

    lines: List[str] = []
    remaining = max_chars
    for idx, row in enumerate(contexts[: max(1, max_snippets)], 1):
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        source_id = str(row.get("source_id") or "unknown").strip() or "unknown"
        clipped = text[:remaining]
        lines.append(f"[{idx}] source={source_id}: {clipped}")
        remaining -= len(clipped)
        if remaining <= 0:
            break

    return "\n".join(lines)


def _build_eval_citation_payload(citations: List[str], contexts: List[Dict[str, Any]], max_items: int = 5) -> List[Dict[str, str]]:
    source_text: Dict[str, str] = {}
    for row in contexts[: max(1, max_items * 2)]:
        if not isinstance(row, dict):
            continue
        source_id = str(row.get("source_id") or "").strip()
        text = str(row.get("text") or "").strip()
        if source_id and text and source_id not in source_text:
            source_text[source_id] = text[:600]

    payload: List[Dict[str, str]] = []
    seen: Set[str] = set()
    for raw in citations or []:
        source_id = str(raw or "").strip()
        if not source_id or source_id in seen:
            continue
        payload.append(
            {
                "id": source_id,
                "title": source_id,
                "content": source_text.get(source_id, ""),
            }
        )
        seen.add(source_id)
        if len(payload) >= max_items:
            return payload

    for source_id, text in source_text.items():
        if source_id in seen:
            continue
        payload.append({"id": source_id, "title": source_id, "content": text})
        if len(payload) >= max_items:
            break

    return payload


def _is_answer_text_block(row: Dict[str, Any]) -> bool:
    if not isinstance(row, dict):
        return False
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


def _has_strong_quote_evidence(contexts: List[Dict[str, Any]]) -> bool:
    rows = [row for row in contexts if isinstance(row, dict)]
    if not rows:
        return False

    for row in rows:
        stats = row.get("retrieval_stats")
        if isinstance(stats, dict):
            floor_value = _safe_float(stats.get("confidence_floor_value"))
            threshold = _safe_float(stats.get("confidence_floor_threshold"))
            if floor_value is not None:
                required = threshold if threshold is not None else ONLINE_EVAL_LINE_EXTRACTOR_MIN_SCORE
                return float(floor_value) >= float(required)

    max_score = 0.0
    for row in rows:
        score = _safe_float(row.get("score"))
        vector_score = _safe_float(row.get("vector_score"))
        max_score = max(max_score, float(score or vector_score or 0.0))
    return max_score >= ONLINE_EVAL_LINE_EXTRACTOR_MIN_SCORE


def _build_source_faithful_fallback_answer(
    query: str,
    contexts: List[Dict[str, Any]],
    *,
    quote_intent: bool,
) -> str:
    if not quote_intent:
        return ""
    if not contexts or not _has_strong_quote_evidence(contexts):
        return ""

    query_tokens = _grounding_tokens(query)
    candidate_contexts = [
        row
        for row in contexts[: max(GROUNDING_MAX_CONTEXT_SNIPPETS, ONLINE_EVAL_POLICY_FALLBACK_POINTS * 3)]
        if isinstance(row, dict) and _is_answer_text_block(row)
    ]
    if not candidate_contexts:
        return ""

    def _candidate_lines(text: str, *, min_len: int = 18) -> List[str]:
        rows: List[str] = []
        for raw in re.split(r"(?<=[.!?])\s+|\n+", text):
            line = re.sub(r"\s+", " ", raw.strip().lstrip("-*").strip())
            if len(line) >= min_len:
                rows.append(line)
        return rows

    def _line_score(line: str, base_score: float = 0.0) -> float:
        line_tokens = _grounding_tokens(line)
        overlap = (
            len(query_tokens.intersection(line_tokens)) / float(len(query_tokens))
            if query_tokens
            else 0.0
        )
        return overlap + (0.20 * base_score)

    scored_blocks: List[Tuple[float, Dict[str, Any]]] = []
    for row in candidate_contexts:
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        block_tokens = _grounding_tokens(text)
        overlap = (
            len(query_tokens.intersection(block_tokens)) / float(len(query_tokens))
            if query_tokens
            else 0.0
        )
        base_score = float(row.get("score", row.get("vector_score", 0.0)) or 0.0)
        scored_blocks.append((overlap + (0.25 * base_score), {**row}))

    if not scored_blocks:
        return ""

    scored_blocks.sort(key=lambda item: item[0], reverse=True)
    selected_blocks = [row for _score, row in scored_blocks[:2]]

    scored_lines: List[Tuple[float, str]] = []
    seen_lines: Set[str] = set()
    for row in selected_blocks:
        text = str(row.get("text") or "")
        base_score = float(row.get("score", row.get("vector_score", 0.0)) or 0.0)
        for line in _candidate_lines(text):
            sig = line.lower()[:220]
            if sig in seen_lines:
                continue
            seen_lines.add(sig)
            scored_lines.append((_line_score(line, base_score=base_score), line))

    if not scored_lines:
        return ""

    scored_lines.sort(key=lambda item: item[0], reverse=True)
    points = [line for _score, line in scored_lines[:ONLINE_EVAL_POLICY_FALLBACK_POINTS]]
    if not points:
        return ""
    return "\n".join(points)


async def _apply_online_eval_policy(
    *,
    query: str,
    response: str,
    fallback_message: str,
    contexts: List[Dict[str, Any]],
    citations: List[str],
    trace_id: Optional[str],
    strict_grounding: bool,
    source_faithful: bool,
    planner_answerability: str,
    quote_intent: bool,
) -> Tuple[str, Dict[str, Any]]:
    policy_result: Dict[str, Any] = {
        "enabled": ONLINE_EVAL_POLICY_ENABLED,
        "ran": False,
        "skipped_reason": None,
        "context_chars": 0,
        "overall_score": None,
        "needs_review": None,
        "flags": [],
        "action": "none",
    }

    normalized_answerability = str(planner_answerability or "").strip().lower()
    if normalized_answerability in {"direct", "derivable"} and not quote_intent:
        policy_result["skipped_reason"] = "no_override_planner_answerable_non_quote"
        policy_result["action"] = "annotate_only"
        return response, policy_result

    if not ONLINE_EVAL_POLICY_ENABLED:
        policy_result["skipped_reason"] = "disabled"
        return response, policy_result
    if not isinstance(response, str) or not response.strip() or response.strip() == fallback_message:
        policy_result["skipped_reason"] = "empty_or_fallback_response"
        return response, policy_result
    if not contexts:
        policy_result["skipped_reason"] = "no_context_snippets"
        return response, policy_result
    if ONLINE_EVAL_POLICY_STRICT_ONLY and not strict_grounding:
        policy_result["skipped_reason"] = "strict_only_query_not_strict"
        return response, policy_result
    if not _online_eval_capable():
        policy_result["skipped_reason"] = "llm_judge_unavailable"
        return response, policy_result

    context_text = _build_eval_context_text(contexts, max_snippets=GROUNDING_MAX_CONTEXT_SNIPPETS)
    policy_result["context_chars"] = len(context_text)
    if len(context_text) < ONLINE_EVAL_POLICY_MIN_CONTEXT_CHARS:
        policy_result["skipped_reason"] = "insufficient_context_text"
        return response, policy_result

    eval_citations = _build_eval_citation_payload(citations, contexts)
    try:
        from modules.evaluation_pipeline import get_evaluation_pipeline

        pipeline = get_evaluation_pipeline(threshold=ONLINE_EVAL_POLICY_MIN_OVERALL_SCORE)
        eval_result = await asyncio.wait_for(
            pipeline.evaluate_response(
                trace_id=_resolve_trace_id(trace_id),
                query=query,
                response=response,
                context=context_text,
                citations=eval_citations,
                metadata={"online_eval_policy": True},
            ),
            timeout=ONLINE_EVAL_POLICY_TIMEOUT_SECONDS,
        )
        policy_result["ran"] = True
        policy_result["overall_score"] = float(eval_result.overall_score)
        policy_result["needs_review"] = bool(eval_result.needs_review)
        policy_result["flags"] = list(eval_result.flags or [])

        below_threshold = (
            eval_result.overall_score is not None
            and float(eval_result.overall_score) < ONLINE_EVAL_POLICY_MIN_OVERALL_SCORE
        )
        low_quality = bool(eval_result.needs_review or below_threshold)
        if low_quality and not source_faithful:
            fallback_answer = _build_source_faithful_fallback_answer(
                query,
                contexts,
                quote_intent=quote_intent,
            )
            if fallback_answer:
                policy_result["action"] = "fallback_source_faithful"
                return fallback_answer, policy_result
            if strict_grounding:
                policy_result["action"] = "fallback_uncertainty"
                return fallback_message, policy_result

        return response, policy_result
    except asyncio.TimeoutError:
        policy_result["skipped_reason"] = "timeout"
        return response, policy_result
    except Exception as e:
        policy_result["skipped_reason"] = f"error:{type(e).__name__}"
        return response, policy_result


def _query_requires_strict_grounding(query: str) -> bool:
    return bool(get_grounding_policy(query).get("strict_grounding"))


def _should_hard_enforce_grounding(
    *,
    query: str,
    strict_grounding: bool,
    target_owner_scope: Optional[bool],
    dialogue_mode: Optional[str],
) -> bool:
    """
    Hard grounding should be reserved for high-risk turns:
    - Explicit source-grounded / owner-specific requests
    - Queries that clearly ask for personal stance/identity details

    For general retrieval-enabled QA, we prefer soft controls (eval + fallback to
    source-faithful) over immediate uncertainty downgrades.
    """
    if strict_grounding:
        return True
    if bool(target_owner_scope):
        return True

    mode = str(dialogue_mode or "").strip().upper()
    if mode in {"SMALLTALK", "REPAIR"}:
        return False

    q = (query or "").strip().lower()
    if not q:
        return False

    owner_high_risk_patterns = (
        r"\bwhat (do|did) i think\b",
        r"\bwhat('?s| is) my (stance|view|opinion|belief|thesis|principle)\b",
        r"\bmy (stance|view|opinion|belief|thesis|principle)\b",
        r"\bhow do i (approach|decide|evaluate)\b",
        r"\bwhat (is|was) my\b",
    )
    if any(re.search(pattern, q) for pattern in owner_high_risk_patterns):
        return True

    return False


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except Exception:
        return False


def _resolve_citation_details(citations: List[str], twin_id: str) -> List[dict]:
    """
    Resolve source UUID citations into UI-friendly details.
    Leaves non-UUID citations as bare ids.
    """
    citation_details: List[dict] = []
    try:
        source_ids = [c for c in (citations or []) if isinstance(c, str) and _is_uuid(c)]
        by_id = {}
        if source_ids:
            src_res = (
                supabase.table("sources")
                .select("id, filename, citation_url")
                .in_("id", source_ids)
                .eq("twin_id", twin_id)
                .execute()
            )
            for row in (src_res.data or []):
                by_id[str(row.get("id"))] = row

        for citation in (citations or []):
            row = by_id.get(str(citation))
            if row:
                citation_details.append(
                    {
                        "id": row.get("id"),
                        "filename": row.get("filename"),
                        "citation_url": row.get("citation_url"),
                    }
                )
            else:
                citation_details.append({"id": citation})
    except Exception as e:
        logger.warning(f"Citation resolution failed (non-blocking): {e}")
    return citation_details


def _merge_citations(existing: List[str], incoming: Optional[List[str]]) -> List[str]:
    """
    Keep non-empty citation evidence stable across streamed tool events.
    Later empty arrays should not erase previously discovered citations.
    """
    if not isinstance(incoming, list):
        return existing
    normalized = [str(c).strip() for c in incoming if isinstance(c, str) and str(c).strip()]
    if normalized:
        return normalized
    return existing

@router.get("/share/resolve/{handle}")
async def resolve_share_handle(handle: str):
    """
    Resolve a twin handle to its twin_id and share_token.
    This is used to support /share/handle style URLs.
    """
    try:
        # Search twins by handle in settings
        # In a high-traffic system, we'd use a indexed column or specific lookup
        res = supabase.table("twins").select("id, settings").execute()
        
        target_twin = None
        for twin in res.data:
            settings = twin.get("settings", {})
            if settings.get("handle") == handle:
                target_twin = twin
                break
        
        if not target_twin:
            raise HTTPException(status_code=404, detail="Twin not found with this handle")
        
        settings = target_twin.get("settings", {})
        widget_settings = settings.get("widget_settings", {})
        share_token = widget_settings.get("share_token")
        
        if not widget_settings.get("public_share_enabled") or not share_token:
             raise HTTPException(status_code=403, detail="Sharing is disabled for this twin")

        return {
            "twin_id": target_twin["id"],
            "share_token": share_token
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving share handle: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def _normalize_json(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    # Only coerce numpy-like scalar wrappers; mocks may expose `.item()`
    # and return non-serializable objects.
    if (
        hasattr(value, "item")
        and callable(getattr(value, "item", None))
        and type(value).__module__.startswith("numpy")
    ):
        try:
            return _normalize_json(value.item())
        except Exception:
            pass
    if isinstance(value, list):
        return [_normalize_json(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalize_json(v) for k, v in value.items()}
    return str(value)


def _extract_stream_payload(event: dict) -> tuple[Optional[dict], Optional[dict]]:
    """
    Extract tool/agent payloads from either legacy stream shape:
      {"tools": {...}} / {"agent": {...}}
    or LangGraph node-update shape:
      {"retrieve": {...}} / {"realizer": {...}}.
    """
    if not isinstance(event, dict):
        return None, None

    tools_payload = event.get("tools") if isinstance(event.get("tools"), dict) else None
    agent_payload = event.get("agent") if isinstance(event.get("agent"), dict) else None

    if tools_payload is None:
        for node_payload in event.values():
            if not isinstance(node_payload, dict):
                continue
            if (
                "citations" in node_payload
                or "confidence_score" in node_payload
                or "retrieved_context" in node_payload
            ):
                tools_payload = {}
                if "citations" in node_payload:
                    citations = _normalize_json(node_payload.get("citations"))
                    if isinstance(citations, list):
                        tools_payload["citations"] = citations
                confidence = node_payload.get("confidence_score")
                if confidence is not None:
                    try:
                        tools_payload["confidence_score"] = float(confidence)
                    except Exception:
                        pass
                retrieved_context = node_payload.get("retrieved_context")
                if isinstance(retrieved_context, dict):
                    raw_results = retrieved_context.get("results")
                    if isinstance(raw_results, list):
                        contexts = []
                        for row in raw_results:
                            if not isinstance(row, dict):
                                continue
                            text = str(row.get("text") or "").strip()
                            if not text:
                                continue
                            normalized_row: Dict[str, Any] = {
                                "source_id": str(row.get("source_id") or "").strip(),
                                "text": text,
                            }
                            for key in ("section_title", "section_path", "chunk_type", "block_type"):
                                value = row.get(key)
                                if isinstance(value, str) and value.strip():
                                    normalized_row[key] = value.strip()
                            raw_stats = row.get("retrieval_stats")
                            if isinstance(raw_stats, dict):
                                normalized_row["retrieval_stats"] = dict(raw_stats)
                            for key in ("score", "vector_score"):
                                value = row.get(key)
                                if isinstance(value, (int, float)):
                                    normalized_row[key] = float(value)
                            contexts.append(normalized_row)
                        if contexts:
                            tools_payload["contexts"] = contexts[:GROUNDING_MAX_CONTEXT_SNIPPETS]
                if not tools_payload:
                    tools_payload = None
                else:
                    break

    if agent_payload is None:
        for node_payload in event.values():
            if not isinstance(node_payload, dict):
                continue
            messages = node_payload.get("messages")
            if isinstance(messages, list):
                agent_payload = {"messages": messages}
                break

    return tools_payload, agent_payload


def _fetch_conversation_record(conversation_id: str):
    try:
        res = (
            supabase.table("conversations")
            .select("id,twin_id,group_id,interaction_context,training_session_id")
            .eq("id", conversation_id)
            .single()
            .execute()
        )
        return res.data if res.data else None
    except Exception:
        return None


def _context_reset_reason_for_conversation(
    conversation_row: dict | None,
    twin_id: str,
    resolved_context: ResolvedInteractionContext,
):
    if not conversation_row:
        return "conversation_not_found"

    if conversation_row.get("twin_id") != twin_id:
        return "conversation_twin_mismatch"

    existing_context = conversation_row.get("interaction_context")
    expected_context = resolved_context.context.value
    if existing_context != expected_context:
        return f"context_mismatch:{existing_context or 'none'}->{expected_context}"

    if expected_context == "owner_training":
        existing_session_id = conversation_row.get("training_session_id")
        if existing_session_id and existing_session_id != resolved_context.training_session_id:
            return "training_session_mismatch"

    return None


def _init_persona_audit_trace(context_trace: dict) -> None:
    context_trace.update(
        {
            "deterministic_gate_passed": None,
            "structure_policy_score": None,
            "voice_score": None,
            "draft_persona_score": None,
            "final_persona_score": None,
            "rewrite_applied": False,
            "rewrite_reason_categories": [],
            "violated_clause_ids": [],
        }
    )


async def _apply_persona_audit(
    *,
    twin_id: str,
    user_query: str,
    draft_response: str,
    intent_label: Optional[str],
    module_ids: List[str],
    citations: List[str],
    context_trace: dict,
    tenant_id: Optional[str],
    conversation_id: Optional[str],
    interaction_context: str,
) -> tuple[str, Optional[str], List[str]]:
    try:
        audit = await audit_persona_response(
            twin_id=twin_id,
            user_query=user_query,
            draft_response=draft_response,
            intent_label=intent_label,
            module_ids=module_ids,
            citations=citations,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            interaction_context=interaction_context,
        )
        context_trace.update(
            {
                "persona_spec_version": audit.persona_spec_version or context_trace.get("persona_spec_version"),
                "deterministic_gate_passed": audit.deterministic_gate_passed,
                "structure_policy_score": audit.structure_policy_score,
                "voice_score": audit.voice_score,
                "draft_persona_score": audit.draft_persona_score,
                "final_persona_score": audit.final_persona_score,
                "rewrite_applied": audit.rewrite_applied,
                "rewrite_reason_categories": audit.rewrite_reason_categories,
                "violated_clause_ids": audit.violated_clause_ids,
            }
        )
        
        # Log persona audit scores to Langfuse
        try:
            if _langfuse_available and _langfuse_client:
                # Get the current trace ID
                trace_id = None
                try:
                    if hasattr(langfuse_context, "get_current_trace_id"):
                        trace_id = langfuse_context.get_current_trace_id()
                    if not trace_id:
                        trace_id = getattr(langfuse_context, "current_trace_id", None)
                except Exception:
                    pass
                
                if trace_id:
                    # Log individual scores
                    if audit.structure_policy_score is not None:
                        log_score(
                            _langfuse_client,
                            trace_id=trace_id,
                            name="persona_structure_policy",
                            value=audit.structure_policy_score,
                            data_type="NUMERIC",
                        )
                    if audit.voice_score is not None:
                        log_score(
                            _langfuse_client,
                            trace_id=trace_id,
                            name="persona_voice_fidelity",
                            value=audit.voice_score,
                            data_type="NUMERIC",
                        )
                    if audit.final_persona_score is not None:
                        log_score(
                            _langfuse_client,
                            trace_id=trace_id,
                            name="persona_overall",
                            value=audit.final_persona_score,
                            data_type="NUMERIC",
                        )
                    
                    # Log rewrite flag
                    if audit.rewrite_applied:
                        log_score(
                            _langfuse_client,
                            trace_id=trace_id,
                            name="persona_rewrite_applied",
                            value=1,
                            comment=f"Reasons: {', '.join(audit.rewrite_reason_categories)}",
                            data_type="BOOLEAN",
                        )
                    
                    flush_client(_langfuse_client)
        except Exception as e:
            logger.debug(f"Failed to log persona scores to Langfuse: {e}")
        
        return audit.final_response, audit.intent_label, audit.module_ids
    except Exception as e:
        logger.warning(f"Persona audit failed, using draft response: {e}")
        # Tag error in Langfuse for visibility
        try:
            langfuse_context.update_current_observation(
                level="WARNING",
                metadata={
                    "persona_audit_error": True,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                }
            )
        except Exception:
            pass
        return draft_response, intent_label, module_ids


def _derive_review_reason(
    *,
    action: str,
    confidence_score: float,
    online_eval_result: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    if action in {"clarify", "escalate", "refuse"}:
        return action
    if confidence_score < 0.45:
        return "low_confidence"
    if isinstance(online_eval_result, dict) and online_eval_result.get("needs_review"):
        return "needs_review"
    return None


def _persist_runtime_audit(
    *,
    twin_id: str,
    tenant_id: Optional[str],
    conversation_id: Optional[str],
    user_message_id: Optional[str],
    assistant_message_id: Optional[str],
    interaction_context: Optional[str],
    dialogue_mode: Optional[str],
    intent_label: Optional[str],
    workflow_intent: Optional[str],
    routing_decision: Optional[Dict[str, Any]],
    persona_spec_version: Optional[str],
    persona_prompt_variant: Optional[str],
    confidence_score: float,
    citations: List[str],
    retrieved_context_snippets: List[Dict[str, Any]],
    final_response: str,
    fallback_message: str,
    online_eval_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    decision = routing_decision if isinstance(routing_decision, dict) else {}
    action = str(decision.get("action") or "answer")

    routing_row = persist_routing_decision(
        twin_id=twin_id,
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        message_id=user_message_id,
        interaction_context=interaction_context,
        router_mode=dialogue_mode,
        decision=decision or {
            "intent": workflow_intent or "answer",
            "confidence": confidence_score,
            "required_inputs_missing": [],
            "chosen_workflow": workflow_intent or "answer",
            "output_schema": f"workflow.{workflow_intent or 'answer'}.v1",
            "action": action,
            "clarifying_questions": [],
        },
        metadata={
            "intent_label": intent_label,
            "persona_spec_version": persona_spec_version,
            "persona_prompt_variant": persona_prompt_variant,
        },
    )

    refusal_reason = None
    if action == "refuse":
        refusal_reason = "guardrail_refusal"
    escalation_reason = None
    if action == "escalate":
        escalation_reason = "router_escalation"
    elif final_response.strip() == fallback_message.strip() and confidence_score < 0.35:
        escalation_reason = "uncertainty_fallback"
        if action == "answer":
            action = "escalate"

    audit_row = persist_response_audit(
        twin_id=twin_id,
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        assistant_message_id=assistant_message_id,
        routing_decision_id=(routing_row or {}).get("id"),
        spec_version=persona_spec_version,
        prompt_variant=persona_prompt_variant,
        intent_label=intent_label,
        workflow_intent=workflow_intent or str(decision.get("intent") or "answer"),
        response_action=action,
        confidence_score=confidence_score,
        citations=citations,
        sources_used=retrieved_context_snippets,
        refusal_reason=refusal_reason,
        escalation_reason=escalation_reason,
        retrieval_summary={
            "citation_count": len(citations or []),
            "context_count": len(retrieved_context_snippets or []),
            "online_eval_action": (online_eval_result or {}).get("action") if isinstance(online_eval_result, dict) else None,
            "online_eval_score": (online_eval_result or {}).get("overall_score") if isinstance(online_eval_result, dict) else None,
        },
        artifacts_used={
            "persona_spec_version": persona_spec_version,
            "persona_prompt_variant": persona_prompt_variant,
            "intent_label": intent_label,
            "workflow_intent": workflow_intent or str(decision.get("intent") or "answer"),
            "routing_decision": decision,
        },
    )

    review_reason = _derive_review_reason(
        action=action,
        confidence_score=confidence_score,
        online_eval_result=online_eval_result,
    )
    if review_reason:
        enqueue_owner_review_item(
            twin_id=twin_id,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            message_id=assistant_message_id,
            routing_decision_id=(routing_row or {}).get("id"),
            reason=review_reason,
            priority="high" if review_reason in {"escalate", "refuse"} else "medium",
            payload={
                "query_action": action,
                "intent_label": intent_label,
                "workflow_intent": workflow_intent,
                "confidence_score": confidence_score,
                "citations": citations,
            },
        )

    return {
        "routing_decision_id": (routing_row or {}).get("id"),
        "response_audit_id": (audit_row or {}).get("id"),
        "response_action": action,
    }

@router.post("/chat/{twin_id}")
@observe(name="chat_request")
async def chat(
    twin_id: str, 
    request: ChatRequest, 
    user=Depends(get_current_user),
    x_langfuse_trace_id: Optional[str] = Header(None, alias="X-Langfuse-Trace-Id")
):
    # P0: Verify user has access to this twin
    verify_twin_ownership(twin_id, user)
    ensure_twin_active(twin_id)
    
    # Compatibility: accept legacy {message} payloads
    query = request.query or request.message or ""
    if not query:
        raise HTTPException(status_code=422, detail="query is required")
    
    # Use trace_id from header or body (header takes precedence for frontend linking)
    trace_id = x_langfuse_trace_id or request.trace_id
    if trace_id:
        try:
            langfuse_context.update_current_trace(id=trace_id)
        except Exception:
            pass  # Trace ID setting is best-effort
    
    conversation_id = request.conversation_id
    group_id = request.group_id
    requested_group_id = request.group_id
    resolved_context = resolve_owner_chat_context(request, user or {}, twin_id)
    mode = identity_gate_mode_for_context(resolved_context.context)
    context_trace = trace_fields(resolved_context)
    context_trace.update(
        {
            "forced_new_conversation": False,
            "context_reset_reason": None,
            "previous_conversation_id": None,
            "persona_spec_version": None,
            "persona_prompt_variant": None,
        }
    )
    _init_persona_audit_trace(context_trace)
    active_spec = get_active_persona_spec(twin_id=twin_id)
    if active_spec:
        context_trace["persona_spec_version"] = active_spec.get("version")

    conversation_row = None
    if conversation_id:
        conversation_row = _fetch_conversation_record(conversation_id)
        reset_reason = _context_reset_reason_for_conversation(
            conversation_row=conversation_row,
            twin_id=twin_id,
            resolved_context=resolved_context,
        )
        if reset_reason:
            context_trace["forced_new_conversation"] = True
            context_trace["context_reset_reason"] = reset_reason
            context_trace["previous_conversation_id"] = conversation_id
            conversation_id = None
            conversation_row = None
        elif not group_id and conversation_row.get("group_id"):
            group_id = conversation_row["group_id"]

    # Update Langfuse trace with session and user info (v3 pattern)
    import os
    release = os.getenv("LANGFUSE_RELEASE", "dev")
    langfuse_prop = propagate_attributes(
        user_id=twin_id,
        session_id=conversation_id,
        metadata={
            "group_id": str(group_id) if group_id else None,
            "query_length": str(len(query)) if query else "0",
            "release": release,
        }
    )

    # Determine user's group
    try:
        if not group_id:
            # If still no group_id, get user's default group
            if not group_id:
                user_id = user.get("user_id") if user else None
                if user_id:
                    user_group = await get_user_group(user_id, twin_id)
                    if user_group:
                        group_id = user_group["id"]
            
            # If still no group_id (anonymous or no group assigned), try public default
            if not group_id:
                default_group = await get_default_group(twin_id)
                if default_group:
                    group_id = default_group["id"]
    except Exception as e:
        logger.error(f"Chat Setup Error: {e}", exc_info=True)
        # Don't raise, let stream generator handle it or default to None
        logger.error(f"Chat Setup Failed: {e}")

    async def stream_generator():
        nonlocal conversation_id
        try:
            if not conversation_id:
                user_id = user.get("user_id") if user else None
                conv = create_conversation(
                    twin_id,
                    user_id,
                    group_id=group_id,
                    interaction_context=resolved_context.context.value,
                    origin_endpoint=resolved_context.origin_endpoint,
                    share_link_id=resolved_context.share_link_id,
                    training_session_id=resolved_context.training_session_id,
                )
                if conv and conv.get("id"):
                    conversation_id = conv["id"]
                else:
                    raise RuntimeError("Failed to initialize conversation")

            # 1. Prepare History
            raw_history = []
            langchain_history = []
            if conversation_id:
                raw_history = get_messages(conversation_id)
                for msg in raw_history:
                    if msg.get("role") == "user":
                        langchain_history.append(HumanMessage(content=msg.get("content", "")))
                    elif msg.get("role") == "assistant":
                        langchain_history.append(AIMessage(content=msg.get("content", "")))

            # 2. Run Agent Stream - collect final response
            full_response = ""
            citations = []
            confidence_score = 0.0
            decision_trace = None
            teaching_questions = []
            planning_output = {}
            dialogue_mode = "ANSWER"
            intent_label = None
            workflow_intent = None
            module_ids = []
            render_strategy = None
            retrieved_context_snippets: List[Dict[str, Any]] = []
            requires_evidence = None
            target_owner_scope = None
            router_reason = None
            router_knowledge_available = None
            routing_decision: Optional[Dict[str, Any]] = None
            
            # Fetch graph stats for this twin
            from modules.graph_context import get_graph_stats
            graph_stats = get_graph_stats(twin_id)
            
            # Identity Confidence Gate (deterministic)
            history_for_gate = []
            if raw_history:
                for msg in raw_history[-6:]:
                    history_for_gate.append({
                        "role": msg.get("role"),
                        "content": msg.get("content", "")
                    })

            gate = await _run_identity_gate_passthrough(
                query=query,
                history=history_for_gate,
                twin_id=twin_id,
                tenant_id=user.get("tenant_id") if user else None,
                group_id=group_id,
                mode=mode,
                allow_clarify=False,
            )

            owner_memory_context = gate.get("owner_memory_context", "")
            owner_memory_refs = gate.get("owner_memory_refs", [])
            owner_memory_candidates = gate.get("owner_memory") or []
            owner_memory_summaries = []
            for mem in owner_memory_candidates:
                topic = mem.get("topic_normalized") or mem.get("topic")
                if mem.get("id") or topic:
                    owner_memory_summaries.append({
                        "id": mem.get("id"),
                        "topic": topic
                    })
            owner_memory_topics = [s.get("topic") for s in owner_memory_summaries if s.get("topic")]

            # DETECT REASONING INTENT (Simple Heuristic for now)
            # In production, use a classifier model
            is_reasoning_query = any(phrase in query.lower() for phrase in [
                "would i ", "do i think", "what is my stance", "how do i feel"
            ])
            # If owner memory is available, skip reasoning engine for stance queries
            if owner_memory_refs:
                is_reasoning_query = False
            
            if is_reasoning_query:
                try:
                    from modules.reasoning_engine import ReasoningEngine
                    engine = ReasoningEngine(twin_id)
                    trace = await engine.predict_stance(query, context_context=owner_memory_context)
                    
                    full_response = trace.to_readable_trace()
                    confidence_score = trace.confidence_score
                    decision_trace = trace.model_dump()
                    
                    # Log as assistant message
                    langchain_history.append(AIMessage(content=full_response))
                    
                except Exception as e:
                    print(f"Reasoning Engine Failed: {e}")
                    # Fallback to standard agent
                    is_reasoning_query = False
            
            print(f"[Chat] Stream started for twin_id={twin_id}, query='{query}'")
            # Log full query for debugging
            print(f"[Chat DEBUG] Full Query: {query}")
            
            if not is_reasoning_query:
                agent_iter = run_agent_stream(
                    twin_id=twin_id,
                    query=query,
                    history=langchain_history,
                    group_id=group_id,
                    conversation_id=conversation_id,
                    owner_memory_context=owner_memory_context,
                    interaction_context=resolved_context.context.value,
                    enforce_group_filtering=(resolved_context.is_public or bool(requested_group_id)),
                    actor_user_id=user.get("user_id") if user else None,
                    tenant_id=user.get("tenant_id") if user else None,
                ).__aiter__()

                pending_task = None
                while True:
                    if pending_task is None:
                        pending_task = asyncio.create_task(agent_iter.__anext__())

                    done, _ = await asyncio.wait({pending_task}, timeout=10)
                    if not done:
                        # Keep the SSE stream alive while the agent is still thinking.
                        # Keep SSE stream alive using canonical event type
                        yield json.dumps({"type": "metadata", "ping": True}) + "\n"
                        continue

                    try:
                        chunk = pending_task.result()
                    except StopAsyncIteration:
                        break
                    finally:
                        pending_task = None

                    tools_payload, agent_payload = _extract_stream_payload(chunk)

                    # Capture metadata from tools
                    if tools_payload:
                        next_citations = tools_payload.get("citations")
                        citations = _merge_citations(citations, next_citations)
                        next_confidence = tools_payload.get("confidence_score")
                        if isinstance(next_confidence, (int, float)):
                            confidence_score = float(next_confidence)
                        next_contexts = tools_payload.get("contexts")
                        if isinstance(next_contexts, list):
                            retrieved_context_snippets = _merge_context_snippets(
                                retrieved_context_snippets,
                                next_contexts,
                            )
                        print(f"[Chat] Tools event: confidence={confidence_score}, citations={len(citations)}")
    
                    # Capture final response and metadata from agent
                    if agent_payload:
                        msgs = agent_payload.get("messages", [])
                        if msgs and isinstance(msgs[-1], AIMessage):
                            msg = msgs[-1]
                            
                            # Capture metadata for the stream (Phase 4)
                            if hasattr(msg, "additional_kwargs"):
                                if "teaching_questions" in msg.additional_kwargs:
                                    teaching_questions = msg.additional_kwargs["teaching_questions"]
                                if "planning_output" in msg.additional_kwargs:
                                    planning_output = msg.additional_kwargs["planning_output"]
                                    if isinstance(planning_output, dict):
                                        plan_render = planning_output.get("render_strategy")
                                        if isinstance(plan_render, str) and plan_render.strip():
                                            render_strategy = plan_render
                                if "dialogue_mode" in msg.additional_kwargs:
                                    dialogue_mode = msg.additional_kwargs["dialogue_mode"]
                                if "intent_label" in msg.additional_kwargs:
                                    intent_label = msg.additional_kwargs["intent_label"]
                                if "workflow_intent" in msg.additional_kwargs:
                                    raw_workflow_intent = msg.additional_kwargs["workflow_intent"]
                                    if isinstance(raw_workflow_intent, str):
                                        workflow_intent = raw_workflow_intent
                                if "module_ids" in msg.additional_kwargs:
                                    module_ids = msg.additional_kwargs["module_ids"] or []
                                if "render_strategy" in msg.additional_kwargs:
                                    raw_render = msg.additional_kwargs["render_strategy"]
                                    if isinstance(raw_render, str) and raw_render.strip():
                                        render_strategy = raw_render
                                if "requires_evidence" in msg.additional_kwargs:
                                    raw_requires = msg.additional_kwargs["requires_evidence"]
                                    if isinstance(raw_requires, bool):
                                        requires_evidence = raw_requires
                                if "target_owner_scope" in msg.additional_kwargs:
                                    raw_scope = msg.additional_kwargs["target_owner_scope"]
                                    if isinstance(raw_scope, bool):
                                        target_owner_scope = raw_scope
                                if "router_reason" in msg.additional_kwargs:
                                    raw_router_reason = msg.additional_kwargs["router_reason"]
                                    if isinstance(raw_router_reason, str):
                                        router_reason = raw_router_reason
                                if "router_knowledge_available" in msg.additional_kwargs:
                                    raw_knowledge = msg.additional_kwargs["router_knowledge_available"]
                                    if isinstance(raw_knowledge, bool):
                                        router_knowledge_available = raw_knowledge
                                if "routing_decision" in msg.additional_kwargs:
                                    raw_decision = msg.additional_kwargs["routing_decision"]
                                    if isinstance(raw_decision, dict):
                                        routing_decision = _normalize_json(raw_decision)
                                if "persona_spec_version" in msg.additional_kwargs:
                                    context_trace["persona_spec_version"] = msg.additional_kwargs["persona_spec_version"]
                                if "persona_prompt_variant" in msg.additional_kwargs:
                                    context_trace["persona_prompt_variant"] = msg.additional_kwargs["persona_prompt_variant"]

                            # Only update if there's actual content (not just tool calls)
                            if msg.content and not getattr(msg, 'tool_calls', None):
                                full_response = msg.content

            # If model fell back despite having citations, try a deterministic extract
            if not workflow_intent and isinstance(routing_decision, dict):
                raw_intent = routing_decision.get("intent")
                if isinstance(raw_intent, str):
                    workflow_intent = raw_intent
            fallback_message = _uncertainty_message(resolved_context.context.value)
            if full_response.strip() == fallback_message and citations:
                needs_exact = re.search(r"(exact|verbatim|only the exact).*(phrase|quote|line)", query.lower())
                if needs_exact:
                    try:
                        from modules.retrieval import retrieve_context
                        contexts = await retrieve_context(query, twin_id, group_id=group_id, top_k=1)
                        if contexts:
                            context_text = contexts[0].get("text", "")
                            first_line = next((line.strip() for line in context_text.splitlines() if line.strip()), "")
                            if first_line:
                                full_response = first_line
                                print("[Chat] Fallback override: extracted exact line from context")
                    except Exception as e:
                        print(f"[Chat] Fallback override failed: {e}")

            # Safety override: if we ended with no evidence and no owner-memory refs,
            # force uncertainty response instead of a generic/hallucinated answer.
            strict_grounding = _query_requires_strict_grounding(query)
            if strict_grounding:
                print(
                    f"[Chat] Strict grounding ON context={resolved_context.context.value} "
                    f"mode={dialogue_mode} query='{query[:120]}'"
                )
            if (
                full_response
                and full_response.strip()
                and full_response.strip() != fallback_message
                and not citations
                and not owner_memory_refs
                and strict_grounding
                and str(dialogue_mode).upper() != "SMALLTALK"
            ):
                print("[Chat] Safety override: no evidence available; forcing uncertainty response")
                full_response = fallback_message
                confidence_score = 0.0
            
            # Determine if graph was likely used (no external citations and has graph)
            graph_used = any(str(c).startswith("graph-") for c in (citations or []))
            
            citation_details = _resolve_citation_details(citations, twin_id)

            draft_for_audit = full_response if full_response else fallback_message
            source_faithful = isinstance(render_strategy, str) and render_strategy.strip().lower() == "source_faithful"
            if source_faithful:
                audited_response, audited_intent_label, audited_module_ids = (
                    draft_for_audit,
                    intent_label,
                    module_ids,
                )
                context_trace["rewrite_applied"] = False
            else:
                audited_response, audited_intent_label, audited_module_ids = await _apply_persona_audit(
                    twin_id=twin_id,
                    user_query=query,
                    draft_response=draft_for_audit,
                    intent_label=intent_label,
                    module_ids=module_ids,
                    citations=citations,
                    context_trace=context_trace,
                    tenant_id=user.get("tenant_id") if user else None,
                    conversation_id=conversation_id,
                    interaction_context=resolved_context.context.value,
                )
            full_response = audited_response
            intent_label = audited_intent_label or intent_label
            module_ids = audited_module_ids or module_ids

            grounding_result = {
                "supported": None,
                "support_ratio": None,
                "total_claims": 0,
                "supported_claims": 0,
                "unsupported_claims": [],
            }
            online_eval_result: Dict[str, Any] = {
                "enabled": ONLINE_EVAL_POLICY_ENABLED,
                "ran": False,
                "skipped_reason": "not_run",
                "context_chars": 0,
                "overall_score": None,
                "needs_review": None,
                "flags": [],
                "action": "none",
            }
            grounding_enforced = _should_hard_enforce_grounding(
                query=query,
                strict_grounding=bool(strict_grounding),
                target_owner_scope=target_owner_scope if isinstance(target_owner_scope, bool) else None,
                dialogue_mode=dialogue_mode if isinstance(dialogue_mode, str) else None,
            )
            if (
                GROUNDING_VERIFIER_ENABLED
                and isinstance(full_response, str)
                and full_response.strip()
                and full_response.strip() != fallback_message
                and retrieved_context_snippets
            ):
                grounding_result = _evaluate_grounding_support(full_response, retrieved_context_snippets)
                context_trace["grounding_support_ratio"] = grounding_result.get("support_ratio")
                context_trace["grounding_total_claims"] = grounding_result.get("total_claims")
                context_trace["grounding_supported_claims"] = grounding_result.get("supported_claims")
                context_trace["grounding_unsupported_claims"] = grounding_result.get("unsupported_claims")
                context_trace["grounding_verifier_supported"] = grounding_result.get("supported")
                context_trace["grounding_verifier_enforced"] = grounding_enforced

                if grounding_enforced and not grounding_result.get("supported"):
                    print(
                        "[Chat] Grounding verifier failed under strict policy; "
                        f"support_ratio={grounding_result.get('support_ratio')}"
                    )
                    full_response = fallback_message
                    confidence_score = min(confidence_score, 0.2)
                    context_trace["grounding_downgraded"] = True

            full_response, online_eval_result = await _apply_online_eval_policy(
                query=query,
                response=full_response,
                fallback_message=fallback_message,
                contexts=retrieved_context_snippets,
                citations=citations,
                trace_id=trace_id or conversation_id,
                strict_grounding=grounding_enforced,
                source_faithful=source_faithful,
                planner_answerability=_extract_answerability_state(
                    planning_output if isinstance(planning_output, dict) else {}
                ),
                quote_intent=_is_quote_intent(query),
            )
            if online_eval_result.get("action") == "fallback_uncertainty":
                confidence_score = min(confidence_score, 0.2)
            elif online_eval_result.get("action") == "fallback_source_faithful":
                confidence_score = min(confidence_score, 0.6)
            context_trace["online_eval_ran"] = bool(online_eval_result.get("ran"))
            context_trace["online_eval_action"] = online_eval_result.get("action")
            context_trace["online_eval_score"] = online_eval_result.get("overall_score")
            context_trace["online_eval_flags"] = online_eval_result.get("flags")
            
            debug_snapshot = _build_debug_snapshot(
                query=query,
                requires_evidence=requires_evidence,
                planning_output=planning_output if isinstance(planning_output, dict) else {},
                routing_decision=routing_decision if isinstance(routing_decision, dict) else {},
                contexts=retrieved_context_snippets,
            )
            _emit_langfuse_turn_telemetry(debug_snapshot)
            deepagents_meta = _extract_deepagents_metadata(
                planning_output if isinstance(planning_output, dict) else {}
            )

            # 3. Send metadata first
            metadata = _normalize_json({
                "type": "metadata",
                "citations": citations,
                "citation_details": citation_details,
                "confidence_score": confidence_score,
                "conversation_id": conversation_id,
                "owner_memory_refs": owner_memory_refs,
                "owner_memory_topics": owner_memory_topics,
                "owner_memory_summaries": owner_memory_summaries,
                "teaching_questions": teaching_questions,
                "planning_output": planning_output,
                "dialogue_mode": dialogue_mode,
                "intent_label": intent_label,
                "workflow_intent": workflow_intent,
                "requires_evidence": requires_evidence,
                "target_owner_scope": target_owner_scope,
                "router_reason": router_reason,
                "router_knowledge_available": router_knowledge_available,
                "routing_decision": routing_decision,
                "render_strategy": render_strategy,
                "query_class": debug_snapshot.get("query_class"),
                "quote_intent": debug_snapshot.get("quote_intent"),
                "answerability_state": debug_snapshot.get("answerability_state"),
                "planner_action": debug_snapshot.get("planner_action"),
                "retrieval_stats": debug_snapshot.get("retrieval_stats"),
                "selected_evidence_block_types": debug_snapshot.get("selected_evidence_block_types"),
                "debug_snapshot": debug_snapshot,
                "grounding_verifier": grounding_result,
                "online_eval": online_eval_result,
                "deepagents": deepagents_meta,
                "turn_counters": _extract_turn_counter_payload(debug_snapshot),
                "router_policy": {
                    "requires_evidence": requires_evidence,
                    "target_owner_scope": target_owner_scope,
                    "knowledge_available": router_knowledge_available,
                    "reason": router_reason,
                },
                "module_ids": module_ids,
                "graph_context": {
                    "has_graph": graph_stats["has_graph"],
                    "node_count": graph_stats["node_count"],
                    "graph_used": graph_used
                },
                "decision_trace": decision_trace,
                "identity_gate_mode": gate.get("gate_mode"),
                "effective_conversation_id": conversation_id,
                **context_trace,
            })
            yield json.dumps(metadata) + "\n"
            
            # 4. Send final content
            if full_response:
                print(f"[Chat] Yielding content: {len(full_response)} chars")
                yield json.dumps({"type": "content", "token": full_response, "content": full_response}) + "\n"
            else:
                fallback = _uncertainty_message(resolved_context.context.value)
                print(f"[Chat] Fallback emitted: {fallback}")
                yield json.dumps({"type": "content", "token": fallback, "content": fallback}) + "\n"

            # 5. Done event
            yield json.dumps({"type": "done"}) + "\n"
            
            print(f"[Chat] Stream ended for twin_id={twin_id}")
            
            # 6. Run evaluation (fire-and-forget, non-blocking)
            try:
                from modules.evaluation_pipeline import evaluate_response_async
                # Build context text from retrieved chunk snippets (not citation IDs).
                context_text = _build_eval_context_text(
                    retrieved_context_snippets,
                    max_snippets=GROUNDING_MAX_CONTEXT_SNIPPETS,
                )
                if not context_text and citations:
                    context_text = "\n".join([str(c) for c in citations[:5]])
                eval_citations = _build_eval_citation_payload(citations, retrieved_context_snippets)
                
                # Get trace_id from current context if available
                current_trace_id = trace_id  # Use the one from request
                
                evaluate_response_async(
                    trace_id=current_trace_id or conversation_id or "unknown",
                    query=query,
                    response=full_response or fallback,
                    context=context_text,
                    citations=eval_citations
                )
                print(f"[Chat] Evaluation triggered for conversation {conversation_id}")
            except Exception as eval_err:
                print(f"[Chat] Evaluation trigger failed (non-blocking): {eval_err}")

            # 7. Log conversation
            if full_response or True: # Always log if we reached here
                # Create conversation if needed
                if not conversation_id:
                    user_id = user.get("user_id") if user else None
                    conv = create_conversation(
                        twin_id,
                        user_id,
                        group_id=group_id,
                        interaction_context=resolved_context.context.value,
                        origin_endpoint=resolved_context.origin_endpoint,
                        share_link_id=resolved_context.share_link_id,
                        training_session_id=resolved_context.training_session_id,
                    )
                    conversation_id = conv["id"]
                
                user_msg_row = log_interaction(
                    conversation_id,
                    "user",
                    query,
                    interaction_context=resolved_context.context.value,
                )
                assistant_msg_row = log_interaction(
                    conversation_id,
                    "assistant",
                    full_response or fallback,
                    citations,
                    confidence_score,
                    interaction_context=resolved_context.context.value,
                )
                try:
                    _persist_runtime_audit(
                        twin_id=twin_id,
                        tenant_id=user.get("tenant_id") if user else None,
                        conversation_id=conversation_id,
                        user_message_id=(user_msg_row or {}).get("id"),
                        assistant_message_id=(assistant_msg_row or {}).get("id"),
                        interaction_context=resolved_context.context.value,
                        dialogue_mode=dialogue_mode,
                        intent_label=intent_label,
                        workflow_intent=workflow_intent,
                        routing_decision=routing_decision,
                        persona_spec_version=context_trace.get("persona_spec_version"),
                        persona_prompt_variant=context_trace.get("persona_prompt_variant"),
                        confidence_score=float(confidence_score or 0.0),
                        citations=citations,
                        retrieved_context_snippets=retrieved_context_snippets,
                        final_response=full_response or fallback,
                        fallback_message=fallback_message,
                        online_eval_result=online_eval_result,
                    )
                except Exception as audit_err:
                    logger.debug(f"Runtime audit persistence failed (non-blocking): {audit_err}")
            
            # 8. Trigger Scribe (Job Queue for reliability)
            try:
                from modules._core.scribe_engine import enqueue_graph_extraction_job
                job_id = None
                if full_response:
                    # Get tenant_id from user for MemoryEvent audit trail
                    tenant_id = user.get("tenant_id") if user else None
                    # Enqueue graph extraction job (replaces fire-and-forget)
                    job_id = enqueue_graph_extraction_job(
                        twin_id=twin_id,
                        user_message=query,
                        assistant_message=full_response,
                        history=raw_history,
                        tenant_id=tenant_id,
                        conversation_id=conversation_id
                    )
                    if job_id:
                        print(f"[Chat] Enqueued graph extraction job {job_id} for conversation {conversation_id}")
            except Exception as se:
                print(f"[Chat] Scribe enqueue failed (non-blocking): {se}")

        except Exception as e:
            import traceback
            traceback.print_exc()
            error_msg = f"Error: {str(e)}"
            print(f"[Chat] ERROR yielded in stream: {error_msg}")
            # Tag trace as error in Langfuse for visibility
            try:
                langfuse_context.update_current_observation(
                    level="ERROR",
                    status_message=str(e)[:255],
                    metadata={
                        "error": True,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "traceback": traceback.format_exc()[:1000],
                    }
                )
                langfuse_context.update_current_trace(
                    metadata={
                        "error": True,
                        "error_phase": "stream_generator",
                        "error_type": type(e).__name__,
                    }
                )
            except Exception as lf_err:
                print(f"[Chat] Failed to tag Langfuse error: {lf_err}")
            yield json.dumps({"type": "error", "error": error_msg}) + "\n"
        
        finally:
            # =================================================================
            # CRITICAL FIX H4: Proper cleanup on stream end or disconnect
            # =================================================================
            try:
                # Flush Langfuse traces if client is available.
                if _langfuse_client:
                    try:
                        flush_client(_langfuse_client)
                        print(f"[Chat] Langfuse traces flushed for conversation {conversation_id}")
                    except Exception as flush_err:
                        print(f"[Chat] Langfuse flush error (non-critical): {flush_err}")
                
                # Clean up large objects to free memory
                if 'raw_history' in locals():
                    raw_history.clear()
                if 'langchain_history' in locals():
                    langchain_history.clear()
                
                # Force garbage collection for large responses
                import gc
                gc.collect()
                
                print(f"[Chat] Stream cleanup completed for conversation {conversation_id}")
                
            except Exception as cleanup_err:
                print(f"[Chat] Cleanup error (non-critical): {cleanup_err}")

    with langfuse_prop:
        return StreamingResponse(stream_generator(), media_type="text/event-stream")

@router.get("/conversations/{twin_id}")
async def list_conversations_endpoint(twin_id: str, user=Depends(get_current_user)):
    verify_twin_ownership(twin_id, user)
    ensure_twin_active(twin_id)
    return get_conversations(twin_id)

@router.get("/conversations/{conversation_id}/messages")
async def list_messages_endpoint(conversation_id: str, user=Depends(get_current_user)):
    verify_conversation_ownership(conversation_id, user)
    return get_messages(conversation_id)

# Chat Widget Interface
@router.post("/chat-widget/{twin_id}")
@observe(name="chat_widget_request")
async def chat_widget(twin_id: str, request: ChatWidgetRequest, req_raw: Request = None):
    """
    Public chat interface for widgets.
    Uses API keys and sessions instead of user auth.
    """
    from modules.api_keys import validate_api_key, validate_domain
    from modules.sessions import create_session, get_session, update_session_activity
    from modules.rate_limiting import check_rate_limit, record_request
    
    # 1. Validate API Key
    key_info = validate_api_key(request.api_key)
    if not key_info or key_info["twin_id"] != twin_id:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # 2. Validate Domain (CORS/Origin check)
    origin = ""
    if req_raw:
        origin = req_raw.headers.get("origin", "")
    
    if key_info["allowed_domains"] and not validate_domain(origin, key_info["allowed_domains"]):
        raise HTTPException(status_code=403, detail="Domain not allowed")
    
    # 3. Handle Session
    ensure_twin_active(twin_id)
    session_id = request.session_id
    if session_id:
        session = get_session(session_id)
        if not session or session["twin_id"] != twin_id:
            session_id = None # Force new session if invalid
        else:
            update_session_activity(session_id)
    
    if not session_id:
        session_id = create_session(
            twin_id=twin_id,
            group_id=key_info.get("group_id"),
            session_type="anonymous",
            ip_address=req_raw.client.host if req_raw else None,
            user_agent=req_raw.headers.get("user-agent") if req_raw else None
        )
    
    # 4. Rate Limiting Check
    # Check sessions per hour
    allowed, status = check_rate_limit(session_id, "session", "requests_per_hour", 30)
    if not allowed:
        raise HTTPException(status_code=429, detail="Session rate limit exceeded")
    
    # 5. Process Chat
    # Compatibility: accept legacy {message} payloads
    query = request.query or request.message or ""
    if not query:
        raise HTTPException(status_code=422, detail="query is required")
    group_id = key_info.get("group_id")
    
    # Load publish controls for widget safety parity with public-share (PR6-A)
    publish_controls = _load_public_publish_controls(twin_id)
    published_identity_topics = publish_controls.get("published_identity_topics", set())
    published_policy_topics = publish_controls.get("published_policy_topics", set())
    published_source_ids = publish_controls.get("published_source_ids", set())
    context_trace["published_identity_topics_count"] = len(published_identity_topics)
    context_trace["published_policy_topics_count"] = len(published_policy_topics)
    context_trace["published_source_ids_count"] = len(published_source_ids)
    
    resolved_context = resolve_widget_context()
    context_trace = trace_fields(resolved_context)
    context_trace.update(
        {
            "forced_new_conversation": False,
            "context_reset_reason": None,
            "previous_conversation_id": None,
            "persona_spec_version": None,
            "persona_prompt_variant": None,
        }
    )
    _init_persona_audit_trace(context_trace)
    active_spec = get_active_persona_spec(twin_id=twin_id)
    if active_spec:
        context_trace["persona_spec_version"] = active_spec.get("version")
    
    # Langfuse trace propagation for widget endpoint
    import os
    release = os.getenv("LANGFUSE_RELEASE", "dev")
    langfuse_prop_widget = propagate_attributes(
        user_id=twin_id,
        session_id=session_id,
        metadata={
            "endpoint": "chat-widget",
            "group_id": str(group_id) if group_id else None,
            "query_length": str(len(query)) if query else "0",
            "api_key_id": key_info.get("id"),
            "origin": origin,
            "release": release,
        }
    )
    
    # Get conversation for session
    # (Simplified for now: 1 conversation per session)
    conv_response = (
        supabase.table("conversations")
        .select("id")
        .eq("session_id", session_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if conv_response.data and len(conv_response.data) > 0:
        conversation_id = conv_response.data[0]["id"]
        conversation_row = _fetch_conversation_record(conversation_id)
        reset_reason = _context_reset_reason_for_conversation(
            conversation_row=conversation_row,
            twin_id=twin_id,
            resolved_context=resolved_context,
        )
        if reset_reason:
            context_trace["forced_new_conversation"] = True
            context_trace["context_reset_reason"] = reset_reason
            context_trace["previous_conversation_id"] = conversation_id
            conversation_id = None
    else:
        conversation_id = None

    if not conversation_id:
        conv_obj = create_conversation(
            twin_id,
            None,
            group_id=group_id,
            interaction_context=resolved_context.context.value,
            origin_endpoint=resolved_context.origin_endpoint,
        )
        conversation_id = conv_obj["id"]
        # Link conversation to session
        supabase.table("conversations").update({"session_id": session_id}).eq("id", conversation_id).execute()
    
    # Get system prompt and history
    twin_res = supabase.table("twins").select("settings").eq("id", twin_id).single().execute()
    system_prompt = ""
    if twin_res.data:
        system_prompt = twin_res.data.get("settings", {}).get("system_prompt", "")
    
    # Inject Style Guidelines
    from modules.graph_context import get_style_guidelines
    style_guide = get_style_guidelines(twin_id)
    if style_guide:
        system_prompt += f"\n\n{style_guide}"
    
    history = get_messages(conversation_id)

    # Identity gate for public/widget (context only; no pre-agent clarification)
    gate = await _run_identity_gate_passthrough(
        query=query,
        history=[{"role": m.get("role"), "content": m.get("content", "")} for m in (history or [])[-6:]],
        twin_id=twin_id,
        tenant_id=None,
        group_id=group_id,
        mode=identity_gate_mode_for_context(resolved_context.context),
        allow_clarify=False,
    )

    # Filter owner memories by publish controls (parity with public-share) (PR6-A)
    owner_memory_candidates = _filter_public_owner_memory_candidates(
        gate.get("owner_memory") or [],
        published_identity_topics=published_identity_topics,
        published_policy_topics=published_policy_topics,
    )
    owner_memory_refs = [m.get("id") for m in owner_memory_candidates if isinstance(m, dict) and m.get("id")]
    owner_memory_topics = [
        (m.get("topic_normalized") or m.get("topic"))
        for m in owner_memory_candidates
        if (m.get("topic_normalized") or m.get("topic"))
    ]
    owner_memory_context = format_owner_memory_context(owner_memory_candidates) if owner_memory_candidates else ""
    
    async def widget_stream_generator():
        final_content = ""
        citations = []
        confidence_score = 0.0
        dialogue_mode = None
        intent_label = None
        workflow_intent = None
        module_ids = []
        render_strategy = None
        planning_output = {}
        routing_decision: Optional[Dict[str, Any]] = None
        retrieved_context_snippets: List[Dict[str, Any]] = []

        async for event in run_agent_stream(
            twin_id,
            query,
            history,
            system_prompt,
            group_id=group_id,
            conversation_id=conversation_id,
            owner_memory_context=owner_memory_context,
            interaction_context=resolved_context.context.value,
            actor_user_id=None,
            tenant_id=None,
        ):
            tools_payload, agent_payload = _extract_stream_payload(event)

            if tools_payload:
                next_citations = tools_payload.get("citations")
                citations = _merge_citations(citations, next_citations)
                next_confidence = tools_payload.get("confidence_score")
                if isinstance(next_confidence, (int, float)):
                    confidence_score = float(next_confidence)
                next_contexts = tools_payload.get("contexts")
                if isinstance(next_contexts, list):
                    retrieved_context_snippets = _merge_context_snippets(
                        retrieved_context_snippets,
                        next_contexts,
                    )

            if agent_payload:
                messages = agent_payload.get("messages", [])
                if not messages:
                    continue
                msg = messages[-1]
                if isinstance(msg, AIMessage):
                    if hasattr(msg, "additional_kwargs") and isinstance(msg.additional_kwargs, dict):
                        dialogue_mode = msg.additional_kwargs.get("dialogue_mode", dialogue_mode)
                        intent_label = msg.additional_kwargs.get("intent_label", intent_label)
                        workflow_intent = msg.additional_kwargs.get("workflow_intent", workflow_intent)
                        module_ids = msg.additional_kwargs.get("module_ids", module_ids) or []
                        raw_routing_decision = msg.additional_kwargs.get("routing_decision")
                        if isinstance(raw_routing_decision, dict):
                            routing_decision = _normalize_json(raw_routing_decision)
                        raw_render = msg.additional_kwargs.get("render_strategy")
                        if isinstance(raw_render, str) and raw_render.strip():
                            render_strategy = raw_render
                        planning_output = msg.additional_kwargs.get("planning_output")
                        if not render_strategy and isinstance(planning_output, dict):
                            plan_render = planning_output.get("render_strategy")
                            if isinstance(plan_render, str) and plan_render.strip():
                                render_strategy = plan_render
                        if msg.additional_kwargs.get("persona_spec_version"):
                            context_trace["persona_spec_version"] = msg.additional_kwargs["persona_spec_version"]
                        if msg.additional_kwargs.get("persona_prompt_variant"):
                            context_trace["persona_prompt_variant"] = msg.additional_kwargs["persona_prompt_variant"]
                    if msg.content:
                        final_content += msg.content

        # Filter contexts and citations by published sources (parity with public-share) (PR6-A)
        retrieved_context_snippets, removed_context_count = _filter_contexts_to_allowed_sources(
            retrieved_context_snippets,
            published_source_ids,
        )
        citations = _filter_citations_to_allowed_sources(citations, published_source_ids)
        if removed_context_count > 0:
            context_trace["public_scope_removed_context_count"] = removed_context_count
            context_trace["public_scope_violation"] = True

        if not workflow_intent and isinstance(routing_decision, dict):
            raw_intent = routing_decision.get("intent")
            if isinstance(raw_intent, str):
                workflow_intent = raw_intent
        fallback_message = _uncertainty_message(resolved_context.context.value)
        draft_for_audit = final_content if final_content else fallback_message
        source_faithful = isinstance(render_strategy, str) and render_strategy.strip().lower() == "source_faithful"
        if source_faithful:
            final_content = draft_for_audit
            context_trace["rewrite_applied"] = False
        else:
            final_content, intent_label, module_ids = await _apply_persona_audit(
                twin_id=twin_id,
                user_query=query,
                draft_response=draft_for_audit,
                intent_label=intent_label,
                module_ids=module_ids,
                citations=citations,
                context_trace=context_trace,
                tenant_id=None,
                conversation_id=conversation_id,
                interaction_context=resolved_context.context.value,
            )
        grounding_result = {
            "supported": None,
            "support_ratio": None,
            "total_claims": 0,
            "supported_claims": 0,
            "unsupported_claims": [],
        }
        online_eval_result: Dict[str, Any] = {
            "enabled": ONLINE_EVAL_POLICY_ENABLED,
            "ran": False,
            "skipped_reason": "not_run",
            "context_chars": 0,
            "overall_score": None,
            "needs_review": None,
            "flags": [],
            "action": "none",
        }
        strict_grounding = _query_requires_strict_grounding(query)
        if (
            GROUNDING_VERIFIER_ENABLED
            and isinstance(final_content, str)
            and final_content.strip()
            and final_content.strip() != fallback_message
            and strict_grounding
            and retrieved_context_snippets
        ):
            grounding_result = _evaluate_grounding_support(final_content, retrieved_context_snippets)
            if not grounding_result.get("supported"):
                final_content = fallback_message
                confidence_score = min(confidence_score, 0.2)
                context_trace["grounding_downgraded"] = True
            context_trace["grounding_support_ratio"] = grounding_result.get("support_ratio")
            context_trace["grounding_total_claims"] = grounding_result.get("total_claims")
            context_trace["grounding_supported_claims"] = grounding_result.get("supported_claims")
            context_trace["grounding_unsupported_claims"] = grounding_result.get("unsupported_claims")
            context_trace["grounding_verifier_supported"] = grounding_result.get("supported")

        final_content, online_eval_result = await _apply_online_eval_policy(
            query=query,
            response=final_content,
            fallback_message=fallback_message,
            contexts=retrieved_context_snippets,
            citations=citations,
            trace_id=_resolve_trace_id(conversation_id or session_id),
            strict_grounding=strict_grounding,
            source_faithful=source_faithful,
            planner_answerability=_extract_answerability_state(
                planning_output if isinstance(planning_output, dict) else {}
            ),
            quote_intent=_is_quote_intent(query),
        )
        if online_eval_result.get("action") == "fallback_uncertainty":
            confidence_score = min(confidence_score, 0.2)
        elif online_eval_result.get("action") == "fallback_source_faithful":
            confidence_score = min(confidence_score, 0.6)
        context_trace["online_eval_ran"] = bool(online_eval_result.get("ran"))
        context_trace["online_eval_action"] = online_eval_result.get("action")
        context_trace["online_eval_score"] = online_eval_result.get("overall_score")
        context_trace["online_eval_flags"] = online_eval_result.get("flags")
        citation_details = _resolve_citation_details(citations, twin_id)
        debug_snapshot = _build_debug_snapshot(
            query=query,
            requires_evidence=True,
            planning_output=planning_output if isinstance(planning_output, dict) else {},
            routing_decision=routing_decision if isinstance(routing_decision, dict) else {},
            contexts=retrieved_context_snippets,
        )
        _emit_langfuse_turn_telemetry(debug_snapshot)

        deepagents_meta = _extract_deepagents_metadata(
            planning_output if isinstance(planning_output, dict) else {}
        )
        output = {
            "type": "metadata",
            "confidence_score": confidence_score,
            "citations": citations,
            "citation_details": citation_details,
            "conversation_id": conversation_id,
            "owner_memory_refs": owner_memory_refs,
            "owner_memory_topics": owner_memory_topics,
            "dialogue_mode": dialogue_mode,
            "intent_label": intent_label,
            "workflow_intent": workflow_intent,
            "module_ids": module_ids,
            "routing_decision": routing_decision,
            "render_strategy": render_strategy,
            "query_class": debug_snapshot.get("query_class"),
            "quote_intent": debug_snapshot.get("quote_intent"),
            "answerability_state": debug_snapshot.get("answerability_state"),
            "planner_action": debug_snapshot.get("planner_action"),
            "retrieval_stats": debug_snapshot.get("retrieval_stats"),
            "selected_evidence_block_types": debug_snapshot.get("selected_evidence_block_types"),
            "debug_snapshot": debug_snapshot,
            "grounding_verifier": grounding_result,
            "online_eval": online_eval_result,
            "deepagents": deepagents_meta,
            "turn_counters": _extract_turn_counter_payload(debug_snapshot),
            "session_id": session_id,
            "identity_gate_mode": gate.get("gate_mode"),
            **context_trace,
        }
        yield json.dumps(output) + "\n"
        yield json.dumps({"type": "content", "token": final_content, "content": final_content}) + "\n"

        try:
            from modules.evaluation_pipeline import evaluate_response_async
            eval_context_text = _build_eval_context_text(
                retrieved_context_snippets,
                max_snippets=GROUNDING_MAX_CONTEXT_SNIPPETS,
            )
            if not eval_context_text and citations:
                eval_context_text = "\n".join([str(c) for c in citations[:5]])
            eval_citations = _build_eval_citation_payload(citations, retrieved_context_snippets)
            evaluate_response_async(
                trace_id=_resolve_trace_id(conversation_id or session_id),
                query=query,
                response=final_content,
                context=eval_context_text,
                citations=eval_citations,
            )
        except Exception as eval_err:
            logger.debug(f"Widget evaluation trigger failed (non-blocking): {eval_err}")

        # Record usage
        record_request(session_id, "session", "requests_per_hour")
        
        # Log interaction
        user_msg_row = log_interaction(
            conversation_id,
            "user",
            query,
            interaction_context=resolved_context.context.value,
        )
        assistant_msg_row = log_interaction(
            conversation_id,
            "assistant",
            final_content,
            citations,
            confidence_score,
            interaction_context=resolved_context.context.value,
        )
        try:
            _persist_runtime_audit(
                twin_id=twin_id,
                tenant_id=None,
                conversation_id=conversation_id,
                user_message_id=(user_msg_row or {}).get("id"),
                assistant_message_id=(assistant_msg_row or {}).get("id"),
                interaction_context=resolved_context.context.value,
                dialogue_mode=dialogue_mode,
                intent_label=intent_label,
                workflow_intent=workflow_intent,
                routing_decision=routing_decision,
                persona_spec_version=context_trace.get("persona_spec_version"),
                persona_prompt_variant=context_trace.get("persona_prompt_variant"),
                confidence_score=float(confidence_score or 0.0),
                citations=citations,
                retrieved_context_snippets=retrieved_context_snippets,
                final_response=final_content,
                fallback_message=fallback_message,
                online_eval_result=online_eval_result,
            )
        except Exception as audit_err:
            logger.debug(f"Widget runtime audit persistence failed (non-blocking): {audit_err}")

        yield json.dumps({"type": "done", "escalated": confidence_score < 0.7}) + "\n"

    with langfuse_prop_widget:
        return StreamingResponse(widget_stream_generator(), media_type="text/event-stream")

@router.post("/public/chat/{twin_id}/{token}")
@observe(name="public_chat_request")
async def public_chat_endpoint(
    twin_id: str, 
    token: str, 
    request: PublicChatRequest, 
    req_raw: Request = None,
    x_langfuse_trace_id: Optional[str] = Header(None, alias="X-Langfuse-Trace-Id")
):
    """Handle public chat via share link"""
    from modules.share_links import validate_share_token, get_public_group_for_twin
    from modules.actions_engine import EventEmitter, TriggerMatcher, ActionDraftManager
    from modules.rate_limiting import check_rate_limit
    
    # Use trace_id from header or body (header takes precedence for frontend linking)
    trace_id = x_langfuse_trace_id or request.trace_id
    if trace_id:
        try:
            langfuse_context.update_current_trace(id=trace_id)
        except Exception:
            pass  # Trace ID setting is best-effort
    
    # Validate share token
    if not validate_share_token(token, twin_id):
        raise HTTPException(status_code=403, detail="Invalid or expired share link")
    resolved_context = resolve_public_share_context(token)
    context_trace = trace_fields(resolved_context)
    context_trace.update(
        {
            "forced_new_conversation": False,
            "context_reset_reason": None,
            "previous_conversation_id": None,
            "persona_spec_version": None,
            "persona_prompt_variant": None,
        }
    )
    _init_persona_audit_trace(context_trace)
    active_spec = get_active_persona_spec(twin_id=twin_id)
    if active_spec:
        context_trace["persona_spec_version"] = active_spec.get("version")
    
    ensure_twin_active(twin_id)

    publish_controls = _load_public_publish_controls(twin_id)
    published_identity_topics = publish_controls.get("published_identity_topics", set())
    published_policy_topics = publish_controls.get("published_policy_topics", set())
    published_source_ids = publish_controls.get("published_source_ids", set())
    context_trace["published_identity_topics_count"] = len(published_identity_topics)
    context_trace["published_policy_topics_count"] = len(published_policy_topics)
    context_trace["published_source_ids_count"] = len(published_source_ids)
    
    # Rate limit by IP address for public endpoints
    client_ip = req_raw.client.host if req_raw and req_raw.client else "unknown"
    group_id = None
    
    # Langfuse trace propagation for public chat endpoint
    release = os.getenv("LANGFUSE_RELEASE", "dev")
    langfuse_prop_public = propagate_attributes(
        user_id=twin_id,
        session_id=None,  # Public chat doesn't have persistent sessions
        metadata={
            "endpoint": "public-chat",
            "group_id": None,
            "query_length": str(len(request.message)) if request.message else "0",
            "share_token": token,
            "client_ip": client_ip,
            "release": release,
        }
    )
    
    rate_key = f"public_chat:{twin_id}:{client_ip}"
    allowed, status = check_rate_limit(rate_key, "ip", "requests_per_minute", 10)
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again later.")
    
    # Get public group for context (with fallback to default group)
    public_group = get_public_group_for_twin(twin_id)
    if public_group:
        group_id = public_group["id"]
    else:
        # Fallback to default group for access permissions
        from modules.access_groups import get_default_group
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're already in an async context
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    default_group = pool.submit(asyncio.run, get_default_group(twin_id)).result()
            else:
                default_group = loop.run_until_complete(get_default_group(twin_id))
            group_id = default_group["id"]
            print(f"[PublicChat] Using default group {group_id} as fallback for twin {twin_id}")
        except Exception as e:
            print(f"[PublicChat] Warning: Could not get default group: {e}")
            group_id = None

    public_action_like_query = bool(
        classify_deepagents_intent(request.message).get("is_action_or_control")
    )
    if public_action_like_query:
        context_trace["public_action_query_guarded"] = True
    
    # Emit message_received event for trigger matching
    triggered_actions = []
    if not public_action_like_query:
        try:
            event_id = EventEmitter.emit(
                twin_id=twin_id,
                event_type='message_received',
                payload={
                    'user_message': request.message,
                    'user_id': 'anonymous'
                },
                source_context={
                    'group_id': group_id,
                    'channel': 'public_share'
                }
            )
            if event_id:
                pending_drafts = ActionDraftManager.get_pending_drafts(twin_id)
                for draft in pending_drafts:
                    if draft.get('event_id') == event_id:
                        triggered_actions.append(draft.get('proposed_action', {}).get('action_type'))
        except Exception as e:
            print(f"Warning: Could not emit event or check triggers: {e}")
    
    conversation_id = None
    # Build conversation history (tolerate extra fields)
    history = []
    if request.conversation_history:
        for msg in request.conversation_history:
            role = msg.get("role") if isinstance(msg, dict) else None
            content = msg.get("content") if isinstance(msg, dict) else None
            if not isinstance(content, str):
                continue
            if role == "user":
                history.append(HumanMessage(content=content))
            elif role == "assistant":
                history.append(AIMessage(content=content))

    # Identity gate for public chat (context only; no pre-agent clarification)
    gate = await _run_identity_gate_passthrough(
        query=request.message,
        history=[{"role": "user", "content": m.content} for m in history[-6:]] if history else [],
        twin_id=twin_id,
        tenant_id=None,
        group_id=group_id,
        mode=identity_gate_mode_for_context(resolved_context.context),
        allow_clarify=False,
    )

    owner_memory_candidates = _filter_public_owner_memory_candidates(
        gate.get("owner_memory") or [],
        published_identity_topics=published_identity_topics,
        published_policy_topics=published_policy_topics,
    )
    owner_memory_refs = [m.get("id") for m in owner_memory_candidates if isinstance(m, dict) and m.get("id")]
    owner_memory_topics = [
        (m.get("topic_normalized") or m.get("topic"))
        for m in owner_memory_candidates
        if (m.get("topic_normalized") or m.get("topic"))
    ]
    owner_memory_context = format_owner_memory_context(owner_memory_candidates) if owner_memory_candidates else ""

    with langfuse_prop_public:
        try:
            final_response = ""
            citations = []
            confidence_score = 0.0
            dialogue_mode = None
            intent_label = None
            workflow_intent = None
            module_ids = []
            render_strategy = None
            planning_output = {}
            routing_decision: Optional[Dict[str, Any]] = None
            retrieved_context_snippets: List[Dict[str, Any]] = []
            async for event in run_agent_stream(
                twin_id,
                request.message,
                history,
                group_id=group_id,
                conversation_id=conversation_id,
                owner_memory_context=owner_memory_context,
                interaction_context=resolved_context.context.value,
                actor_user_id=None,
                tenant_id=None,
            ):
                tools_payload, agent_payload = _extract_stream_payload(event)
                if tools_payload:
                    next_citations = tools_payload.get("citations")
                    citations = _merge_citations(citations, next_citations)
                    next_confidence = tools_payload.get("confidence_score")
                    if isinstance(next_confidence, (int, float)):
                        confidence_score = float(next_confidence)
                    next_contexts = tools_payload.get("contexts")
                    if isinstance(next_contexts, list):
                        retrieved_context_snippets = _merge_context_snippets(
                            retrieved_context_snippets,
                            next_contexts,
                        )
                if agent_payload:
                    messages = agent_payload.get("messages", [])
                    if not messages:
                        continue
                    msg = messages[-1]
                    if isinstance(msg, AIMessage) and msg.content:
                        if hasattr(msg, "additional_kwargs") and isinstance(msg.additional_kwargs, dict):
                            dialogue_mode = msg.additional_kwargs.get("dialogue_mode", dialogue_mode)
                            intent_label = msg.additional_kwargs.get("intent_label", intent_label)
                            workflow_intent = msg.additional_kwargs.get("workflow_intent", workflow_intent)
                            module_ids = msg.additional_kwargs.get("module_ids", module_ids) or []
                            raw_routing_decision = msg.additional_kwargs.get("routing_decision")
                            if isinstance(raw_routing_decision, dict):
                                routing_decision = _normalize_json(raw_routing_decision)
                            raw_render = msg.additional_kwargs.get("render_strategy")
                            if isinstance(raw_render, str) and raw_render.strip():
                                render_strategy = raw_render
                            planning_output = msg.additional_kwargs.get("planning_output")
                            if not render_strategy and isinstance(planning_output, dict):
                                plan_render = planning_output.get("render_strategy")
                                if isinstance(plan_render, str) and plan_render.strip():
                                    render_strategy = plan_render
                            if msg.additional_kwargs.get("persona_spec_version"):
                                context_trace["persona_spec_version"] = msg.additional_kwargs["persona_spec_version"]
                            if msg.additional_kwargs.get("persona_prompt_variant"):
                                context_trace["persona_prompt_variant"] = msg.additional_kwargs["persona_prompt_variant"]
                        final_response = msg.content

            retrieved_context_snippets, removed_context_count = _filter_contexts_to_allowed_sources(
                retrieved_context_snippets,
                published_source_ids,
            )
            citations = _filter_citations_to_allowed_sources(citations, published_source_ids)
            if removed_context_count > 0:
                context_trace["public_scope_removed_context_count"] = removed_context_count
                context_trace["public_scope_violation"] = True

            # If actions were triggered, append acknowledgment
            if triggered_actions:
                acknowledgments = []
                for action in triggered_actions:
                    if action == 'escalate' or action == 'notify_owner':
                        acknowledgments.append("I've notified the owner about your request.")
                    elif action == 'draft_email':
                        acknowledgments.append("I'm drafting an email for the owner to review.")
                    elif action == 'draft_calendar_event':
                        acknowledgments.append("I'm preparing a calendar event for the owner to review.")
                
                if acknowledgments:
                    final_response += "\n\n" + " ".join(acknowledgments)

            if not workflow_intent and isinstance(routing_decision, dict):
                raw_intent = routing_decision.get("intent")
                if isinstance(raw_intent, str):
                    workflow_intent = raw_intent
            fallback_message = _uncertainty_message(resolved_context.context.value)
            draft_for_audit = final_response if final_response else fallback_message

            if context_trace.get("public_scope_violation"):
                draft_for_audit = fallback_message
                final_response = fallback_message
                confidence_score = min(confidence_score, 0.2)
                citations = []
                retrieved_context_snippets = []
                owner_memory_refs = []
                owner_memory_topics = []
                owner_memory_candidates = []
                owner_memory_context = ""

            if public_action_like_query:
                routing_decision = {}
                module_ids = []
                workflow_intent = None
                render_strategy = "source_faithful"
                debug_snapshot = {}
                online_eval_result = {
                    "enabled": False,
                    "ran": False,
                    "skipped_reason": "public_action_query_guarded",
                    "overall_score": None,
                    "flags": [],
                    "action": "none",
                }

            source_faithful = isinstance(render_strategy, str) and render_strategy.strip().lower() == "source_faithful"
            if source_faithful:
                final_response = draft_for_audit
                context_trace["rewrite_applied"] = False
            else:
                final_response, intent_label, module_ids = await _apply_persona_audit(
                    twin_id=twin_id,
                    user_query=request.message,
                    draft_response=draft_for_audit,
                    intent_label=intent_label,
                    module_ids=module_ids,
                    citations=citations,
                    context_trace=context_trace,
                    tenant_id=None,
                    conversation_id=conversation_id,
                    interaction_context=resolved_context.context.value,
                )

            grounding_result = {
                "supported": None,
                "support_ratio": None,
                "total_claims": 0,
                "supported_claims": 0,
                "unsupported_claims": [],
            }
            online_eval_result: Dict[str, Any] = {
                "enabled": ONLINE_EVAL_POLICY_ENABLED,
                "ran": False,
                "skipped_reason": "not_run",
                "context_chars": 0,
                "overall_score": None,
                "needs_review": None,
                "flags": [],
                "action": "none",
            }
            strict_grounding = _query_requires_strict_grounding(request.message)
            if strict_grounding and not retrieved_context_snippets and not owner_memory_candidates:
                final_response = fallback_message
                confidence_score = min(confidence_score, 0.2)
                citations = []
            if (
                GROUNDING_VERIFIER_ENABLED
                and isinstance(final_response, str)
                and final_response.strip()
                and final_response.strip() != fallback_message
                and strict_grounding
                and retrieved_context_snippets
            ):
                grounding_result = _evaluate_grounding_support(final_response, retrieved_context_snippets)
                if not grounding_result.get("supported"):
                    final_response = fallback_message
                    confidence_score = min(confidence_score, 0.2)
                    context_trace["grounding_downgraded"] = True
                context_trace["grounding_support_ratio"] = grounding_result.get("support_ratio")
                context_trace["grounding_total_claims"] = grounding_result.get("total_claims")
                context_trace["grounding_supported_claims"] = grounding_result.get("supported_claims")
                context_trace["grounding_unsupported_claims"] = grounding_result.get("unsupported_claims")
                context_trace["grounding_verifier_supported"] = grounding_result.get("supported")

            final_response, online_eval_result = await _apply_online_eval_policy(
                query=request.message,
                response=final_response,
                fallback_message=fallback_message,
                contexts=retrieved_context_snippets,
                citations=citations,
                trace_id=trace_id,
                strict_grounding=strict_grounding,
                source_faithful=source_faithful,
                planner_answerability=_extract_answerability_state(
                    planning_output if isinstance(planning_output, dict) else {}
                ),
                quote_intent=_is_quote_intent(request.message),
            )
            if online_eval_result.get("action") == "fallback_uncertainty":
                confidence_score = min(confidence_score, 0.2)
            elif online_eval_result.get("action") == "fallback_source_faithful":
                confidence_score = min(confidence_score, 0.6)
            context_trace["online_eval_ran"] = bool(online_eval_result.get("ran"))
            context_trace["online_eval_action"] = online_eval_result.get("action")
            context_trace["online_eval_score"] = online_eval_result.get("overall_score")
            context_trace["online_eval_flags"] = online_eval_result.get("flags")

            try:
                from modules.evaluation_pipeline import evaluate_response_async

                eval_context_text = _build_eval_context_text(
                    retrieved_context_snippets,
                    max_snippets=GROUNDING_MAX_CONTEXT_SNIPPETS,
                )
                if not eval_context_text and citations:
                    eval_context_text = "\n".join([str(c) for c in citations[:5]])
                eval_citations = _build_eval_citation_payload(citations, retrieved_context_snippets)
                evaluate_response_async(
                    trace_id=_resolve_trace_id(trace_id),
                    query=request.message,
                    response=final_response,
                    context=eval_context_text,
                    citations=eval_citations,
                )
            except Exception as eval_err:
                logger.debug(f"Public evaluation trigger failed (non-blocking): {eval_err}")
            
            citations = _normalize_json(citations)
            citation_details = _normalize_json(_resolve_citation_details(citations, twin_id))
            owner_memory_refs = _normalize_json([])
            owner_memory_topics = _normalize_json([])
            routing_decision = _normalize_json(routing_decision)
            debug_snapshot = _build_debug_snapshot(
                query=request.message,
                requires_evidence=True,
                planning_output=planning_output if isinstance(planning_output, dict) else {},
                routing_decision=routing_decision if isinstance(routing_decision, dict) else {},
                contexts=retrieved_context_snippets,
            )
            debug_snapshot["public_action_query_guarded_rate"] = 1 if public_action_like_query else 0
            _emit_langfuse_turn_telemetry(debug_snapshot)

            if public_action_like_query:
                routing_decision = {}
                debug_snapshot = {}
                online_eval_result = {
                    "enabled": False,
                    "ran": False,
                    "skipped_reason": "public_action_query_guarded",
                    "context_chars": 0,
                    "overall_score": None,
                    "needs_review": None,
                    "flags": [],
                    "action": "none",
                }

            try:
                _persist_runtime_audit(
                    twin_id=twin_id,
                    tenant_id=None,
                    conversation_id=conversation_id,
                    user_message_id=None,
                    assistant_message_id=None,
                    interaction_context=resolved_context.context.value,
                    dialogue_mode=dialogue_mode,
                    intent_label=intent_label,
                    workflow_intent=workflow_intent,
                    routing_decision=routing_decision if isinstance(routing_decision, dict) else None,
                    persona_spec_version=context_trace.get("persona_spec_version"),
                    persona_prompt_variant=context_trace.get("persona_prompt_variant"),
                    confidence_score=float(confidence_score or 0.0),
                    citations=citations if isinstance(citations, list) else [],
                    retrieved_context_snippets=retrieved_context_snippets,
                    final_response=final_response,
                    fallback_message=fallback_message,
                    online_eval_result=online_eval_result,
                )
            except Exception as audit_err:
                logger.debug(f"Public runtime audit persistence failed (non-blocking): {audit_err}")

            return {
                "status": "answer",
                "response": final_response,
                "citations": citations,
                "citation_details": citation_details,
                "confidence_score": confidence_score,
                "owner_memory_refs": owner_memory_refs,
                "owner_memory_topics": owner_memory_topics,
                "dialogue_mode": dialogue_mode,
                "intent_label": intent_label,
                "workflow_intent": workflow_intent,
                "module_ids": module_ids,
                "routing_decision": routing_decision,
                "render_strategy": render_strategy,
                "query_class": debug_snapshot.get("query_class"),
                "quote_intent": debug_snapshot.get("quote_intent"),
                "answerability_state": debug_snapshot.get("answerability_state"),
                "planner_action": debug_snapshot.get("planner_action"),
                "retrieval_stats": debug_snapshot.get("retrieval_stats"),
                "selected_evidence_block_types": debug_snapshot.get("selected_evidence_block_types"),
                "debug_snapshot": debug_snapshot,
                "grounding_verifier": grounding_result,
                "online_eval": online_eval_result,
                "used_owner_memory": False,
                "identity_gate_mode": gate.get("gate_mode"),
                **context_trace,
            }
        except Exception as e:
            print(f"Error in public chat: {e}")
            import traceback
            traceback.print_exc()
            # Tag trace as error in Langfuse for visibility
            try:
                langfuse_context.update_current_observation(
                    level="ERROR",
                    status_message=str(e)[:255],
                    metadata={
                        "error": True,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "traceback": traceback.format_exc()[:1000],
                    }
                )
                langfuse_context.update_current_trace(
                    metadata={
                        "error": True,
                        "error_phase": "public_chat",
                        "error_type": type(e).__name__,
                    }
                )
            except Exception as lf_err:
                print(f"[PublicChat] Failed to tag Langfuse error: {lf_err}")
            raise HTTPException(status_code=500, detail="Failed to process message")
