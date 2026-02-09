"""
Phase 5 Persona Prompt Optimizer

Track A (no fine-tuning):
- mutate typed prompt render variants
- evaluate on regression dataset
- rank by objective score
- optionally persist and activate best variant
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, Field

# Add backend directory to path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from modules.persona_compiler import (  # noqa: E402
    PROMPT_RENDER_VARIANTS,
    PromptRenderOptions,
    compile_prompt_plan,
    get_prompt_render_options,
    render_prompt_plan_with_options,
)
from modules.persona_fingerprint_gate import run_persona_fingerprint_gate  # noqa: E402
from modules.persona_intents import normalize_intent_label  # noqa: E402
from modules.persona_prompt_variant_store import (  # noqa: E402
    activate_persona_prompt_variant,
    activate_persona_prompt_variant_record,
    create_persona_prompt_variant,
    create_prompt_optimization_run,
    finalize_prompt_optimization_run,
)
from modules.persona_spec import PersonaSpec  # noqa: E402
from modules.persona_spec_store import get_active_persona_spec  # noqa: E402


DEFAULT_DATASET_PATH = Path(BACKEND_DIR) / "eval" / "persona_prompt_optimization_dataset.json"


class ExpectedProperties(BaseModel):
    max_words: Optional[int] = None
    required_structure: Optional[str] = None
    forbidden_phrases: List[str] = Field(default_factory=list)
    should_ask_clarifying: Optional[bool] = None
    must_include_any: List[str] = Field(default_factory=list)
    must_avoid_any: List[str] = Field(default_factory=list)
    pass_threshold: float = 0.82


class OptimizationCase(BaseModel):
    id: str
    intent_label: str
    user_query: str
    expected: ExpectedProperties


class OptimizationDataset(BaseModel):
    version: str = "v1"
    cases: List[OptimizationCase] = Field(default_factory=list)


class CandidateConfig(BaseModel):
    variant_id: str
    render_overrides: Dict[str, Any] = Field(default_factory=dict)


class CaseEvaluation(BaseModel):
    case_id: str
    intent_label: str
    score: float
    passed: bool
    response: str
    violations: List[str] = Field(default_factory=list)
    gate_score: float = 0.0
    include_score: float = 0.0
    avoid_score: float = 0.0
    clarify_score: float = 0.0
    response_words: int = 0
    prompt_tokens_est: int = 0


class CandidateResult(BaseModel):
    candidate: CandidateConfig
    objective_score: float
    avg_case_score: float
    pass_rate: float
    avg_response_words: float
    avg_prompt_tokens_est: float
    cases: List[CaseEvaluation] = Field(default_factory=list)


def _word_count(text: str) -> int:
    return len((text or "").split())


def _estimate_tokens(text: str) -> int:
    # Lightweight approximation for optimization objective.
    return max(1, int(len(text or "") / 4))


class ResponseGenerator:
    async def generate(self, *, system_prompt: str, user_query: str, intent_label: str) -> str:
        raise NotImplementedError


class HeuristicResponseGenerator(ResponseGenerator):
    """
    Deterministic fallback for CI/local runs when API keys are absent.
    """

    async def generate(self, *, system_prompt: str, user_query: str, intent_label: str) -> str:
        prompt_lower = (system_prompt or "").lower()
        query = (user_query or "").strip()
        wants_bullets = "bullets" in prompt_lower
        asks_clarify = ("ask_one_clarifying_question" in prompt_lower) or ("clarify" in prompt_lower)
        concise_bias = "brevity_default" in prompt_lower or "concise" in prompt_lower

        if intent_label == "ambiguity_or_clarify" or asks_clarify:
            return "What is the single most important constraint I should optimize for here?"

        if intent_label == "action_or_tool_execution":
            if wants_bullets:
                return "- Confirm target and permissions.\n- Execute the requested action.\n- Report completion and next step."
            return "I can do this. Confirm the target and permissions, then I will execute and report completion."

        if intent_label == "factual_with_evidence":
            if wants_bullets:
                return "- Key fact: based on available evidence.\n- Confidence: medium.\n- Next: provide a source link for verification."
            if concise_bias:
                return "Based on available evidence, this is the best-supported answer. I can provide source-backed detail if needed."
            return "Based on available evidence, this is the likely answer. I can break down sources and assumptions if you want depth."

        if intent_label == "advice_or_stance":
            if asks_clarify and "not shared" in query.lower():
                return "- Clarifying question: what budget and timeline constraints apply?\n- Assumption: medium risk tolerance if constraints stay unknown.\n- Recommendation: prioritize one measurable objective first."
            if wants_bullets:
                return "- Recommendation: choose one measurable objective.\n- Assumption: current resources remain stable.\n- Next step: review impact in one week."
            return "Recommendation: pick one measurable objective first. Assumption: resources stay stable for one sprint."

        if intent_label == "disagreement_or_conflict":
            return "I disagree on one key point. Here is the direct correction, plus the tradeoff behind it."

        if intent_label == "summarize_or_transform":
            return "Summary: direct answer first. Keep only the critical point, one assumption, and one next step."

        if intent_label == "meta_or_system":
            if "hidden prompt" in query.lower():
                return "I cannot disclose hidden system instructions. I can explain my clarification policy and safety boundaries."
            return "I ask clarifying questions when key constraints are missing and the outcome would materially change."

        if intent_label == "sensitive_boundary_or_refusal":
            return "I cannot help with harmful or unauthorized actions. A safe alternative is to use approved security testing workflows."

        if wants_bullets:
            return f"- Direct answer: {query[:80]}\n- Assumption: one key missing detail.\n- Next step: confirm and proceed."
        return f"Direct answer: {query[:120]}. One assumption is required; confirm that and I will refine."


class OpenAIResponseGenerator(ResponseGenerator):
    def __init__(self, *, model: str = "gpt-4o-mini"):
        from modules.clients import get_async_openai_client

        self._client = get_async_openai_client()
        self._model = model

    async def generate(self, *, system_prompt: str, user_query: str, intent_label: str) -> str:
        prompt = (
            f"{system_prompt}\n\n"
            f"Current intent label: {intent_label}\n"
            f"Respond to the user query while following the persona and policy instructions above."
        )
        resp = await self._client.chat.completions.create(
            model=self._model,
            temperature=0.3,
            max_tokens=280,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_query},
            ],
        )
        return (resp.choices[0].message.content or "").strip()


def _default_candidates() -> List[CandidateConfig]:
    candidates = [CandidateConfig(variant_id=variant_id, render_overrides={}) for variant_id in PROMPT_RENDER_VARIANTS]
    # Add lightweight mutations for search around baseline.
    candidates.extend(
        [
            CandidateConfig(variant_id="baseline_v1", render_overrides={"max_few_shots": 2}),
            CandidateConfig(variant_id="compact_v1", render_overrides={"max_few_shots": 1}),
            CandidateConfig(variant_id="voice_focus_v1", render_overrides={"max_few_shots": 3}),
        ]
    )
    # Dedupe while preserving order.
    seen = set()
    unique: List[CandidateConfig] = []
    for candidate in candidates:
        key = (candidate.variant_id, json.dumps(candidate.render_overrides, sort_keys=True))
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _candidate_key(candidate: CandidateConfig) -> str:
    return f"{candidate.variant_id}|{json.dumps(candidate.render_overrides, sort_keys=True)}"


def _fallback_spec() -> PersonaSpec:
    return PersonaSpec(
        version="1.0.0",
        identity_voice={
            "tone": "direct",
            "cadence": "short paragraphs",
            "vocabulary": "plain, executive",
        },
        decision_policy={
            "clarify_when_ambiguous": True,
            "cite_when_factual": True,
            "assumption_policy": "state assumptions briefly",
        },
        stance_values={
            "priorities": ["accuracy", "clarity", "speed"],
            "risk_tolerance": "medium",
        },
        interaction_style={
            "brevity_default": "concise",
            "structure_default": "bullets for action/advice",
            "disagreement_style": "direct_respectful",
        },
        constitution=[
            "Do not fabricate sources or certainty.",
            "Disclose uncertainty clearly.",
            "Ask one clarifying question when ambiguity is material.",
        ],
        procedural_modules=[
            {
                "id": "procedural.decision.clarify_before_advice",
                "intent_labels": ["advice_or_stance", "ambiguity_or_clarify"],
                "when": {"missing_material_parameters": True},
                "do": ["ask_one_clarifying_question", "state_assumptions_if_answering"],
                "say_style": {"tone": "direct", "max_questions": 1},
                "ban": ["As an AI language model"],
                "priority": 40,
                "active": True,
            },
            {
                "id": "procedural.factual.cite_or_disclose_uncertainty",
                "intent_labels": ["factual_with_evidence"],
                "when": {"requires_evidence": True},
                "do": ["retrieve_evidence_first", "cite_sources", "disclose_uncertainty_if_low_confidence"],
                "say_style": {"format": "concise_bullets"},
                "ban": ["without evidence"],
                "priority": 35,
                "active": True,
            },
        ],
        deterministic_rules={
            "banned_phrases": ["As an AI language model", "I might be wrong but"],
            "length_bands": {
                "default": {"min_words": 8, "max_words": 120},
                "factual_with_evidence": {"min_words": 12, "max_words": 100},
                "action_or_tool_execution": {"min_words": 10, "max_words": 80},
            },
            "format_by_intent": {
                "advice_or_stance": "bullets",
                "action_or_tool_execution": "bullets",
            },
            "anti_style_rules": [
                "No motivational fluff.",
                "Do not over-explain obvious points.",
            ],
        },
    )


def _load_spec(*, twin_id: Optional[str], spec_path: Optional[str]) -> tuple[PersonaSpec, Optional[str]]:
    if spec_path:
        raw = json.loads(Path(spec_path).read_text(encoding="utf-8"))
        spec = PersonaSpec.model_validate(raw)
        return spec, spec.version

    if twin_id:
        active = get_active_persona_spec(twin_id=twin_id)
        if active and active.get("spec"):
            try:
                return PersonaSpec.model_validate(active["spec"]), str(active.get("version") or "")
            except Exception as e:
                print(f"[Phase5] active spec invalid for twin {twin_id}: {e}")

    spec = _fallback_spec()
    return spec, spec.version


def _load_dataset(path: Optional[str]) -> OptimizationDataset:
    dataset_path = Path(path) if path else DEFAULT_DATASET_PATH
    if not dataset_path.exists():
        raise FileNotFoundError(f"dataset not found: {dataset_path}")
    raw = json.loads(dataset_path.read_text(encoding="utf-8"))
    return OptimizationDataset.model_validate(raw)


def _merge_case_rules(plan_rules: Dict[str, Any], case: OptimizationCase) -> Dict[str, Any]:
    merged = dict(plan_rules or {})
    expected = case.expected

    banned = list(merged.get("banned_phrases") or [])
    banned.extend(expected.forbidden_phrases or [])
    merged["banned_phrases"] = list(dict.fromkeys([str(v).strip() for v in banned if str(v).strip()]))

    if expected.max_words is not None:
        bands = dict(merged.get("length_bands") or {})
        intent_band = dict(bands.get(case.intent_label) or {})
        intent_band["max_words"] = int(expected.max_words)
        if "min_words" not in intent_band:
            intent_band["min_words"] = 8
        bands[case.intent_label] = intent_band
        merged["length_bands"] = bands

    if expected.required_structure:
        fmt = dict(merged.get("format_by_intent") or {})
        fmt[case.intent_label] = str(expected.required_structure).strip().lower()
        merged["format_by_intent"] = fmt

    return merged


def _clarify_check(answer: str) -> bool:
    text = (answer or "").strip().lower()
    if not text:
        return False
    return ("?" in text) and any(
        token in text for token in ("clarify", "which", "what", "constraint", "confirm")
    )


def _contains_any(answer: str, phrases: Sequence[str]) -> bool:
    if not phrases:
        return True
    text = (answer or "").lower()
    return any(str(p).strip().lower() in text for p in phrases if str(p).strip())


def _contains_none(answer: str, phrases: Sequence[str]) -> bool:
    if not phrases:
        return True
    text = (answer or "").lower()
    return all(str(p).strip().lower() not in text for p in phrases if str(p).strip())


@dataclass
class EvaluationContext:
    spec: PersonaSpec
    dataset: OptimizationDataset
    generator: ResponseGenerator


async def _evaluate_case(
    *,
    ctx: EvaluationContext,
    candidate: CandidateConfig,
    case: OptimizationCase,
) -> CaseEvaluation:
    intent = normalize_intent_label(case.intent_label)
    render_options = get_prompt_render_options(candidate.variant_id, overrides=candidate.render_overrides)
    plan = compile_prompt_plan(
        spec=ctx.spec,
        intent_label=intent,
        user_query=case.user_query,
        max_few_shots=max(0, int(render_options.max_few_shots)),
        module_detail_level=render_options.module_detail_level,
    )
    system_prompt = render_prompt_plan_with_options(plan=plan, options=render_options)
    response = await ctx.generator.generate(
        system_prompt=system_prompt,
        user_query=case.user_query,
        intent_label=intent,
    )

    gate_rules = _merge_case_rules(plan.deterministic_rules, case)
    gate = run_persona_fingerprint_gate(
        answer=response,
        intent_label=intent,
        deterministic_rules=gate_rules,
        interaction_style=ctx.spec.interaction_style,
    )

    include_ok = _contains_any(response, case.expected.must_include_any)
    avoid_ok = _contains_none(response, case.expected.must_avoid_any)
    clarify_expected = case.expected.should_ask_clarifying
    clarify_ok = True
    if clarify_expected is not None:
        clarify_ok = _clarify_check(response) if clarify_expected else not _clarify_check(response)

    include_score = 1.0 if include_ok else 0.0
    avoid_score = 1.0 if avoid_ok else 0.0
    clarify_score = 1.0 if clarify_ok else 0.0
    gate_score = float(gate.get("score", 0.0))

    score = round(
        (gate_score * 0.70) + (include_score * 0.10) + (avoid_score * 0.10) + (clarify_score * 0.10),
        4,
    )
    passed = score >= float(case.expected.pass_threshold)

    violations = list(gate.get("violated_clauses") or [])
    if not include_ok and case.expected.must_include_any:
        violations.append("POL_EXPECT_MUST_INCLUDE")
    if not avoid_ok and case.expected.must_avoid_any:
        violations.append("POL_EXPECT_MUST_AVOID")
    if not clarify_ok and clarify_expected is not None:
        violations.append("POL_EXPECT_CLARIFY_BEHAVIOR")

    return CaseEvaluation(
        case_id=case.id,
        intent_label=intent,
        score=score,
        passed=passed,
        response=response,
        violations=list(dict.fromkeys(violations)),
        gate_score=gate_score,
        include_score=include_score,
        avoid_score=avoid_score,
        clarify_score=clarify_score,
        response_words=_word_count(response),
        prompt_tokens_est=_estimate_tokens(system_prompt),
    )


async def evaluate_candidate(
    *,
    ctx: EvaluationContext,
    candidate: CandidateConfig,
) -> CandidateResult:
    cases: List[CaseEvaluation] = []
    for case in ctx.dataset.cases:
        cases.append(await _evaluate_case(ctx=ctx, candidate=candidate, case=case))

    if not cases:
        return CandidateResult(
            candidate=candidate,
            objective_score=0.0,
            avg_case_score=0.0,
            pass_rate=0.0,
            avg_response_words=0.0,
            avg_prompt_tokens_est=0.0,
            cases=[],
        )

    avg_case_score = sum(c.score for c in cases) / len(cases)
    pass_rate = sum(1 for c in cases if c.passed) / len(cases)
    avg_response_words = sum(c.response_words for c in cases) / len(cases)
    avg_prompt_tokens_est = sum(c.prompt_tokens_est for c in cases) / len(cases)

    # Token pressure penalty: keep prompts lean for two-pass runtime budgets.
    token_penalty = min(1.0, avg_prompt_tokens_est / 1800.0)
    objective = round((pass_rate * 0.55) + (avg_case_score * 0.40) - (token_penalty * 0.05), 6)

    return CandidateResult(
        candidate=candidate,
        objective_score=objective,
        avg_case_score=round(avg_case_score, 6),
        pass_rate=round(pass_rate, 6),
        avg_response_words=round(avg_response_words, 2),
        avg_prompt_tokens_est=round(avg_prompt_tokens_est, 2),
        cases=cases,
    )


def _choose_generator(mode: str, model: str) -> tuple[ResponseGenerator, str]:
    mode_norm = (mode or "auto").strip().lower()
    if mode_norm == "heuristic":
        return HeuristicResponseGenerator(), "heuristic"
    if mode_norm == "openai":
        return OpenAIResponseGenerator(model=model), "openai"
    if os.getenv("OPENAI_API_KEY"):
        try:
            return OpenAIResponseGenerator(model=model), "openai"
        except Exception:
            return HeuristicResponseGenerator(), "heuristic"
    return HeuristicResponseGenerator(), "heuristic"


async def optimize_persona_prompts(
    *,
    twin_id: Optional[str],
    tenant_id: Optional[str],
    created_by: Optional[str],
    dataset_path: Optional[str],
    spec_path: Optional[str],
    candidates: Optional[List[CandidateConfig]],
    generator_mode: str = "auto",
    model: str = "gpt-4o-mini",
    apply_best: bool = False,
    persist: bool = False,
) -> Dict[str, Any]:
    spec, spec_version = _load_spec(twin_id=twin_id, spec_path=spec_path)
    dataset = _load_dataset(dataset_path)
    candidate_list = candidates or _default_candidates()

    generator, run_mode = _choose_generator(generator_mode, model)
    ctx = EvaluationContext(spec=spec, dataset=dataset, generator=generator)

    run_row = None
    if persist and twin_id:
        run_row = create_prompt_optimization_run(
            twin_id=twin_id,
            tenant_id=tenant_id,
            created_by=created_by,
            base_persona_spec_version=spec_version,
            dataset_version=dataset.version,
            run_mode=run_mode,
            candidate_count=len(candidate_list),
        )

    results: List[CandidateResult] = []
    errors: List[str] = []
    persisted_variants: Dict[str, Dict[str, Any]] = {}
    for candidate in candidate_list:
        try:
            result = await evaluate_candidate(ctx=ctx, candidate=candidate)
            results.append(result)
            if persist and twin_id:
                stored = create_persona_prompt_variant(
                    twin_id=twin_id,
                    tenant_id=tenant_id,
                    created_by=created_by,
                    variant_id=result.candidate.variant_id,
                    render_options=result.candidate.render_overrides,
                    status="draft",
                    source="phase5_optimizer",
                    objective_score=result.objective_score,
                    metrics={
                        "avg_case_score": result.avg_case_score,
                        "pass_rate": result.pass_rate,
                        "avg_response_words": result.avg_response_words,
                        "avg_prompt_tokens_est": result.avg_prompt_tokens_est,
                        "dataset_version": dataset.version,
                        "run_mode": run_mode,
                    },
                    optimization_run_id=run_row["id"] if run_row else None,
                )
                if stored:
                    persisted_variants[_candidate_key(result.candidate)] = stored
        except Exception as e:
            errors.append(f"{candidate.variant_id}: {e}")

    if not results:
        summary = {
            "status": "failed",
            "error": "no candidate results",
            "errors": errors,
        }
        if run_row:
            finalize_prompt_optimization_run(
                run_id=run_row["id"],
                status="failed",
                summary=summary,
                best_variant_id=None,
                best_objective_score=None,
            )
        return summary

    ranked = sorted(
        results,
        key=lambda r: (r.objective_score, r.pass_rate, r.avg_case_score),
        reverse=True,
    )
    best = ranked[0]

    activated_variant = None
    if apply_best and twin_id and persist:
        selected_row = persisted_variants.get(_candidate_key(best.candidate))
        if selected_row and selected_row.get("id"):
            activated_variant = activate_persona_prompt_variant_record(
                twin_id=twin_id,
                record_id=selected_row["id"],
            )
        else:
            activated_variant = activate_persona_prompt_variant(
                twin_id=twin_id,
                variant_id=best.candidate.variant_id,
            )

    summary = {
        "status": "completed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_mode": run_mode,
        "dataset_version": dataset.version,
        "persona_spec_version": spec_version,
        "candidate_count": len(results),
        "best_variant": best.candidate.model_dump(),
        "best_objective_score": best.objective_score,
        "best_metrics": {
            "avg_case_score": best.avg_case_score,
            "pass_rate": best.pass_rate,
            "avg_response_words": best.avg_response_words,
            "avg_prompt_tokens_est": best.avg_prompt_tokens_est,
        },
        "ranking": [
            {
                "rank": idx + 1,
                "variant": item.candidate.model_dump(),
                "objective_score": item.objective_score,
                "pass_rate": item.pass_rate,
                "avg_case_score": item.avg_case_score,
                "avg_prompt_tokens_est": item.avg_prompt_tokens_est,
            }
            for idx, item in enumerate(ranked)
        ],
        "activated_variant": activated_variant,
        "errors": errors,
    }

    if run_row:
        finalize_prompt_optimization_run(
            run_id=run_row["id"],
            status="completed",
            summary=summary,
            best_variant_id=best.candidate.variant_id,
            best_objective_score=best.objective_score,
        )
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 5 persona prompt optimizer")
    parser.add_argument("--twin-id", type=str, default=None, help="Twin ID for active spec loading/persistence")
    parser.add_argument("--tenant-id", type=str, default=None, help="Tenant ID for persistence")
    parser.add_argument("--created-by", type=str, default=None, help="Owner user ID for persistence")
    parser.add_argument("--dataset", type=str, default=None, help="Dataset path")
    parser.add_argument("--spec-path", type=str, default=None, help="Persona spec JSON path")
    parser.add_argument(
        "--mode",
        type=str,
        default="auto",
        choices=["auto", "heuristic", "openai"],
        help="Response generation mode",
    )
    parser.add_argument("--model", type=str, default="gpt-4o-mini", help="Model for openai mode")
    parser.add_argument("--apply-best", action="store_true", help="Activate best variant after optimization")
    parser.add_argument("--persist", action="store_true", help="Persist run + variants in database")
    parser.add_argument("--output", type=str, default=None, help="Optional JSON output path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    return parser.parse_args()


async def _main_async() -> int:
    args = _parse_args()
    random.seed(args.seed)

    summary = await optimize_persona_prompts(
        twin_id=args.twin_id,
        tenant_id=args.tenant_id,
        created_by=args.created_by,
        dataset_path=args.dataset,
        spec_path=args.spec_path,
        candidates=None,
        generator_mode=args.mode,
        model=args.model,
        apply_best=args.apply_best,
        persist=args.persist,
    )

    output = json.dumps(summary, indent=2)
    print(output)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    return 0 if summary.get("status") == "completed" else 1


def main() -> int:
    return asyncio.run(_main_async())


if __name__ == "__main__":
    raise SystemExit(main())
