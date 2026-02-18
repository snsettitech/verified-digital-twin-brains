"""
Routing Decision contract and helpers.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from modules.workflow_registry import (
    build_clarifying_questions,
    detect_required_inputs_missing,
    infer_workflow_intent,
    resolve_workflow_spec,
)


_ROUTER_CONFIDENCE_CLARIFY_THRESHOLD = float(
    os.getenv("ROUTER_CONFIDENCE_CLARIFY_THRESHOLD", "0.62")
)


class RoutingDecision(BaseModel):
    intent: str
    confidence: float = Field(ge=0.0, le=1.0)
    required_inputs_missing: List[str] = Field(default_factory=list)
    chosen_workflow: str
    output_schema: str
    action: str = Field(default="answer")
    clarifying_questions: List[str] = Field(default_factory=list)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _estimate_confidence(
    *,
    mode: str,
    query: str,
    knowledge_available: bool,
    requires_evidence: bool,
    required_inputs_missing: List[str],
    target_owner_scope: bool,
) -> float:
    score = 0.70
    q = (query or "").strip().lower()
    mode_upper = (mode or "").strip().upper()

    if mode_upper == "SMALLTALK":
        score += 0.20
    if not q:
        score -= 0.20
    if len(q.split()) <= 3:
        score -= 0.10
    if requires_evidence and knowledge_available:
        score += 0.08
    if requires_evidence and not knowledge_available:
        score -= 0.14
    if target_owner_scope and not knowledge_available:
        score -= 0.08
    if required_inputs_missing:
        score -= min(0.24, 0.08 * len(required_inputs_missing))

    return _clamp(round(score, 4), 0.0, 1.0)


def build_routing_decision(
    *,
    query: str,
    mode: str,
    intent_label: str,
    interaction_context: str,
    target_owner_scope: bool,
    requires_evidence: bool,
    knowledge_available: bool,
    pinned_context: Optional[Dict[str, Any]] = None,
) -> RoutingDecision:
    """
    Build a stable routing decision object for downstream workflow execution.
    """
    workflow_intent = infer_workflow_intent(query)
    if workflow_intent == "answer":
        # Preserve behavioral compatibility for existing intent taxonomy.
        if intent_label == "summarize_or_transform":
            workflow_intent = "summarize"
        elif intent_label == "advice_or_stance":
            workflow_intent = "plan"
        elif intent_label == "disagreement_or_conflict":
            workflow_intent = "critique"
        elif intent_label == "ambiguity_or_clarify":
            workflow_intent = "diagnose"
        elif intent_label == "action_or_tool_execution":
            workflow_intent = "write"

    workflow = resolve_workflow_spec(workflow_intent)
    missing = detect_required_inputs_missing(
        workflow=workflow,
        query=query,
        pinned_context=pinned_context,
    )
    confidence = _estimate_confidence(
        mode=mode,
        query=query,
        knowledge_available=knowledge_available,
        requires_evidence=requires_evidence,
        required_inputs_missing=missing,
        target_owner_scope=target_owner_scope,
    )

    action = "answer"
    clarifying_questions: List[str] = []

    if target_owner_scope and requires_evidence and not knowledge_available:
        action = "escalate"
        clarifying_questions = [
            "I do not have enough approved source context for this owner-specific request. Can you provide a source or owner-confirmed answer?"
        ]
    elif confidence < _ROUTER_CONFIDENCE_CLARIFY_THRESHOLD or bool(missing):
        action = "clarify"
        clarifying_questions = build_clarifying_questions(workflow, missing)
        if not clarifying_questions:
            clarifying_questions = [
                "Could you share a bit more context so I can answer precisely?",
            ]

    if (
        action == "answer"
        and interaction_context in {"public_share", "public_widget"}
        and requires_evidence
        and not knowledge_available
    ):
        action = "clarify"
        clarifying_questions = [
            "I need more context to answer this accurately. What details should I use?",
        ]

    return RoutingDecision(
        intent=workflow_intent,
        confidence=confidence,
        required_inputs_missing=missing[:3],
        chosen_workflow=workflow.name,
        output_schema=workflow.output_schema,
        action=action,
        clarifying_questions=clarifying_questions[:3],
    )

