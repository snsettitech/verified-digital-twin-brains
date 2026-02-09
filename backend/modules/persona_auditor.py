"""
Persona Auditor

Phase 4 runtime enforcement:
- deterministic fingerprint gate
- structure/policy judge
- voice fidelity judge
- clause-targeted rewrite
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from eval.judges import (
    judge_persona_structure_policy,
    judge_persona_voice_fidelity,
    rewrite_with_clause_directives,
)
from modules.observability import supabase
from modules.persona_compiler import compile_prompt_plan
from modules.persona_fingerprint_gate import run_persona_fingerprint_gate
from modules.persona_intents import classify_query_intent, normalize_intent_label
from modules.persona_module_store import list_runtime_modules_for_intent
from modules.persona_spec import PersonaSpec
from modules.persona_spec_store import get_active_persona_spec


HIGH_RISK_INTENTS = {
    "factual_with_evidence",
    "advice_or_stance",
    "disagreement_or_conflict",
    "sensitive_boundary_or_refusal",
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if (
        hasattr(value, "item")
        and callable(getattr(value, "item", None))
        and type(value).__module__.startswith("numpy")
    ):
        try:
            return _json_safe(value.item())
        except Exception:
            return str(value)
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    return str(value)


class PersonaAuditResult(BaseModel):
    final_response: str
    draft_response: str
    intent_label: str
    module_ids: List[str] = Field(default_factory=list)
    persona_spec_version: Optional[str] = None
    deterministic_gate_passed: bool = True
    structure_policy_score: float = 1.0
    voice_score: float = 1.0
    draft_persona_score: float = 1.0
    final_persona_score: float = 1.0
    rewrite_applied: bool = False
    structure_policy_passed: bool = True
    voice_passed: bool = True
    rewrite_reason_categories: List[str] = Field(default_factory=list)
    violated_clause_ids: List[str] = Field(default_factory=list)
    rewrite_directives: List[str] = Field(default_factory=list)
    deterministic_checks: Dict[str, Any] = Field(default_factory=dict)


def _score_blend(deterministic: float, structure: float, voice: float) -> float:
    # Weighted toward policy/structure correctness.
    return round((deterministic * 0.30) + (structure * 0.45) + (voice * 0.25), 4)


def _to_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except Exception:
        return default


def _citations_required(intent_label: str, spec: PersonaSpec) -> bool:
    if intent_label == "factual_with_evidence":
        return True
    flag = spec.decision_policy.get("cite_when_factual")
    return bool(flag and intent_label == "factual_with_evidence")


def _fallback_response(intent_label: str) -> str:
    if intent_label in {"factual_with_evidence", "sensitive_boundary_or_refusal"}:
        return "I want to be accurate and safe. I do not have enough verified evidence to answer confidently."
    if intent_label == "ambiguity_or_clarify":
        return "I want to answer precisely. Can you clarify the key detail that matters most here?"
    return "I want to give you a precise answer. I need one clarification before I continue."


def _extract_length_limit(deterministic_band: Dict[str, Any]) -> Optional[int]:
    value = deterministic_band.get("max_words")
    if isinstance(value, int) and value > 0:
        return value
    return None


async def _persist_judge_result(
    *,
    twin_id: str,
    tenant_id: Optional[str],
    conversation_id: Optional[str],
    interaction_context: Optional[str],
    result: PersonaAuditResult,
) -> None:
    payload = _json_safe(
        {
        "twin_id": twin_id,
        "tenant_id": tenant_id,
        "conversation_id": conversation_id,
        "interaction_context": interaction_context,
        "intent_label": result.intent_label,
        "module_ids": result.module_ids,
        "persona_spec_version": result.persona_spec_version,
        "deterministic_gate_passed": result.deterministic_gate_passed,
        "structure_policy_score": result.structure_policy_score,
        "voice_score": result.voice_score,
        "draft_persona_score": result.draft_persona_score,
        "final_persona_score": result.final_persona_score,
        "rewrite_applied": result.rewrite_applied,
        "structure_policy_passed": result.structure_policy_passed,
        "voice_passed": result.voice_passed,
        "violated_clause_ids": result.violated_clause_ids,
        "rewrite_reason_categories": result.rewrite_reason_categories,
        "rewrite_directives": result.rewrite_directives,
        }
    )
    try:
        supabase.table("persona_judge_results").insert(payload).execute()
    except Exception as e:
        # Non-blocking for chat path.
        print(f"[PersonaAuditor] persona_judge_results insert failed: {e}")


async def audit_persona_response(
    *,
    twin_id: str,
    user_query: str,
    draft_response: str,
    intent_label: Optional[str],
    module_ids: Optional[List[str]],
    citations: Optional[List[str]],
    tenant_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    interaction_context: Optional[str] = None,
) -> PersonaAuditResult:
    """
    Main Phase 4 audit entrypoint.
    """
    normalized_intent = normalize_intent_label(intent_label) if intent_label else classify_query_intent(user_query)
    module_ids = module_ids or []
    answer = (draft_response or "").strip()
    if not answer:
        result = PersonaAuditResult(
            final_response=draft_response or "",
            draft_response=draft_response or "",
            intent_label=normalized_intent,
            module_ids=module_ids,
        )
        await _persist_judge_result(
            twin_id=twin_id,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            interaction_context=interaction_context,
            result=result,
        )
        return result

    active = get_active_persona_spec(twin_id=twin_id)
    if not active or not active.get("spec"):
        # No active spec: pass-through while still providing trace fields.
        result = PersonaAuditResult(
            final_response=answer,
            draft_response=answer,
            intent_label=normalized_intent,
            module_ids=module_ids,
            persona_spec_version=None,
        )
        await _persist_judge_result(
            twin_id=twin_id,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            interaction_context=interaction_context,
            result=result,
        )
        return result

    try:
        spec = PersonaSpec.model_validate(active["spec"])
    except Exception as e:
        print(f"[PersonaAuditor] invalid active persona spec: {e}")
        result = PersonaAuditResult(
            final_response=answer,
            draft_response=answer,
            intent_label=normalized_intent,
            module_ids=module_ids,
            persona_spec_version=active.get("version"),
        )
        await _persist_judge_result(
            twin_id=twin_id,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            interaction_context=interaction_context,
            result=result,
        )
        return result

    runtime_modules = list_runtime_modules_for_intent(
        twin_id=twin_id,
        intent_label=normalized_intent,
        limit=8,
        include_draft=True,
    )
    prompt_plan = compile_prompt_plan(
        spec=spec,
        intent_label=normalized_intent,
        user_query=user_query,
        runtime_modules=runtime_modules,
    )
    selected_module_ids = prompt_plan.selected_module_ids or module_ids
    citations_required = _citations_required(normalized_intent, spec)
    citations_present = bool(citations)

    det = run_persona_fingerprint_gate(
        answer=answer,
        intent_label=normalized_intent,
        deterministic_rules=prompt_plan.deterministic_rules,
        interaction_style=spec.interaction_style,
    )
    required_structure = det.get("required_structure")

    structure = await judge_persona_structure_policy(
        user_query=user_query,
        answer=answer,
        intent_label=normalized_intent,
        required_structure=required_structure,
        citations_required=citations_required,
        citations_present=citations_present,
        banned_phrases=prompt_plan.deterministic_rules.get("banned_phrases", []),
    )

    voice_required = (normalized_intent in HIGH_RISK_INTENTS) or (not det.get("passed", True))
    if structure.get("verdict") != "pass":
        voice_required = False

    if voice_required:
        voice = await judge_persona_voice_fidelity(
            user_query=user_query,
            answer=answer,
            intent_label=normalized_intent,
            voice_identity=spec.identity_voice,
            interaction_style=spec.interaction_style,
        )
    else:
        voice = {
            "score": 1.0,
            "verdict": "pass",
            "violated_clauses": [],
            "rewrite_directives": [],
            "reasoning": "Voice judge skipped by policy.",
        }

    draft_score = _score_blend(
        det.get("score", 1.0),
        float(structure.get("score", 1.0)),
        float(voice.get("score", 1.0)),
    )
    threshold = _to_float_env("PERSONA_COMPLIANCE_THRESHOLD", 0.88)

    violated = list(
        dict.fromkeys(
            [
                *(det.get("violated_clauses") or []),
                *(structure.get("violated_clauses") or []),
                *(voice.get("violated_clauses") or []),
            ]
        )
    )
    rewrite_directives = list(
        dict.fromkeys(
            [
                *(structure.get("rewrite_directives") or []),
                *(voice.get("rewrite_directives") or []),
            ]
        )
    )
    rewrite_categories = list(
        dict.fromkeys(
            [
                *(det.get("reason_categories") or []),
                "structure_policy" if structure.get("verdict") != "pass" else "",
                "voice" if voice.get("verdict") != "pass" else "",
            ]
        )
    )
    rewrite_categories = [c for c in rewrite_categories if c]

    rewrite_needed = (
        draft_score < threshold
        or not det.get("passed", True)
        or structure.get("verdict") != "pass"
        or (voice_required and voice.get("verdict") != "pass")
    )

    final_answer = answer
    final_det = det
    final_structure = structure
    final_voice = voice
    rewrite_applied = False

    if rewrite_needed:
        rewrite_result = await rewrite_with_clause_directives(
            user_query=user_query,
            draft_answer=answer,
            intent_label=normalized_intent,
            violated_clauses=violated,
            rewrite_directives=rewrite_directives,
            max_words=_extract_length_limit(det.get("length_band") or {}),
            required_structure=required_structure,
        )
        rewritten = (rewrite_result.get("rewritten_answer") or "").strip()
        if rewritten and rewritten != answer:
            rewrite_applied = bool(rewrite_result.get("applied", True))
            final_answer = rewritten
            final_det = run_persona_fingerprint_gate(
                answer=final_answer,
                intent_label=normalized_intent,
                deterministic_rules=prompt_plan.deterministic_rules,
                interaction_style=spec.interaction_style,
            )
            final_structure = await judge_persona_structure_policy(
                user_query=user_query,
                answer=final_answer,
                intent_label=normalized_intent,
                required_structure=required_structure,
                citations_required=citations_required,
                citations_present=citations_present,
                banned_phrases=prompt_plan.deterministic_rules.get("banned_phrases", []),
            )
            if voice_required and final_structure.get("verdict") == "pass":
                final_voice = await judge_persona_voice_fidelity(
                    user_query=user_query,
                    answer=final_answer,
                    intent_label=normalized_intent,
                    voice_identity=spec.identity_voice,
                    interaction_style=spec.interaction_style,
                )
            else:
                final_voice = {
                    "score": 1.0,
                    "verdict": "pass",
                    "violated_clauses": [],
                    "rewrite_directives": [],
                    "reasoning": "Voice judge skipped post-rewrite.",
                }

    final_score = _score_blend(
        final_det.get("score", 1.0),
        float(final_structure.get("score", 1.0)),
        float(final_voice.get("score", 1.0)),
    )

    # Fail-safe fallback if still below threshold.
    if final_score < threshold:
        final_answer = _fallback_response(normalized_intent)
        final_det = run_persona_fingerprint_gate(
            answer=final_answer,
            intent_label=normalized_intent,
            deterministic_rules=prompt_plan.deterministic_rules,
            interaction_style=spec.interaction_style,
        )
        final_structure = {
            "score": 0.9,
            "verdict": "pass",
            "violated_clauses": [],
            "rewrite_directives": [],
            "reasoning": "Fail-safe fallback response applied.",
        }
        final_voice = {
            "score": 0.9,
            "verdict": "pass",
            "violated_clauses": [],
            "rewrite_directives": [],
            "reasoning": "Fallback voice pass.",
        }
        final_score = _score_blend(final_det.get("score", 1.0), 0.9, 0.9)
        rewrite_applied = True
        rewrite_categories = list(dict.fromkeys([*rewrite_categories, "fallback"]))

    result = PersonaAuditResult(
        final_response=final_answer,
        draft_response=answer,
        intent_label=normalized_intent,
        module_ids=selected_module_ids,
        persona_spec_version=prompt_plan.persona_spec_version or active.get("version"),
        deterministic_gate_passed=bool(final_det.get("passed", True)),
        structure_policy_score=float(final_structure.get("score", 1.0)),
        voice_score=float(final_voice.get("score", 1.0)),
        draft_persona_score=draft_score,
        final_persona_score=final_score,
        rewrite_applied=rewrite_applied,
        structure_policy_passed=final_structure.get("verdict") == "pass",
        voice_passed=final_voice.get("verdict") == "pass",
        rewrite_reason_categories=rewrite_categories,
        violated_clause_ids=violated,
        rewrite_directives=rewrite_directives,
        deterministic_checks=final_det.get("checks", {}),
    )
    await _persist_judge_result(
        twin_id=twin_id,
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        interaction_context=interaction_context,
        result=result,
    )
    return result
