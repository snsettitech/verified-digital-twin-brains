"""
Twin Spec contract and transformation helpers.

Twin Spec is a runtime artifact composed from owner training and persona specs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from modules.workflow_registry import WORKFLOW_REGISTRY


class ToneSliders(BaseModel):
    directness: float = Field(default=0.65, ge=0.0, le=1.0)
    warmth: float = Field(default=0.55, ge=0.0, le=1.0)
    skepticism: float = Field(default=0.55, ge=0.0, le=1.0)


class PersonaArtifact(BaseModel):
    tone_sliders: ToneSliders = Field(default_factory=ToneSliders)
    voice_rules: List[str] = Field(default_factory=list)
    preferred_phrases: List[str] = Field(default_factory=list)
    avoid_phrases: List[str] = Field(default_factory=list)
    pushback_style: Optional[str] = None
    summary_style: Optional[str] = None


class DecisionSystemArtifact(BaseModel):
    rubric_dimensions: List[Dict[str, Any]] = Field(default_factory=list)
    green_flags: List[str] = Field(default_factory=list)
    red_flags: List[str] = Field(default_factory=list)
    default_assumptions: List[str] = Field(default_factory=list)
    missing_info_behavior: str = "ask_clarifying_questions"


class WorkflowArtifact(BaseModel):
    workflow: str
    output_schema: str
    required_inputs: List[str] = Field(default_factory=list)
    steps: List[str] = Field(default_factory=list)
    template: Optional[str] = None


class GuardrailsArtifact(BaseModel):
    forbidden_topics: List[str] = Field(default_factory=list)
    refusal_templates: List[str] = Field(default_factory=list)
    confidentiality_rules: List[str] = Field(default_factory=list)
    conflict_rules: List[str] = Field(default_factory=list)
    uncertainty_rule: str = "If uncertain, say you do not know and ask to clarify."
    escalation_rule: str = "Escalate to owner when confidence is low."


class FAQArtifact(BaseModel):
    question: str
    answer: str
    template: Optional[str] = None


class TwinSpec(BaseModel):
    version: str = "1.0.0"
    persona: PersonaArtifact = Field(default_factory=PersonaArtifact)
    decision_system: DecisionSystemArtifact = Field(default_factory=DecisionSystemArtifact)
    workflows: List[WorkflowArtifact] = Field(default_factory=list)
    guardrails: GuardrailsArtifact = Field(default_factory=GuardrailsArtifact)
    faq: List[FAQArtifact] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


def _default_workflows() -> List[WorkflowArtifact]:
    rows: List[WorkflowArtifact] = []
    for key, spec in WORKFLOW_REGISTRY.items():
        rows.append(
            WorkflowArtifact(
                workflow=key,
                output_schema=spec.output_schema,
                required_inputs=list(spec.required_inputs),
                steps=[],
                template=None,
            )
        )
    return rows


def build_twin_spec_from_persona_spec_row(row: Optional[Dict[str, Any]]) -> TwinSpec:
    """
    Build a Twin Spec view from existing persona_specs storage.
    """
    payload = (row or {}).get("spec") if isinstance((row or {}).get("spec"), dict) else {}
    version = str((row or {}).get("version") or payload.get("version") or "1.0.0")

    identity_voice = payload.get("identity_voice") if isinstance(payload.get("identity_voice"), dict) else {}
    interaction_style = payload.get("interaction_style") if isinstance(payload.get("interaction_style"), dict) else {}
    decision_policy = payload.get("decision_policy") if isinstance(payload.get("decision_policy"), dict) else {}
    deterministic_rules = payload.get("deterministic_rules") if isinstance(payload.get("deterministic_rules"), dict) else {}
    stance_values = payload.get("stance_values") if isinstance(payload.get("stance_values"), dict) else {}
    raw_guardrails = payload.get("guardrails") if isinstance(payload.get("guardrails"), dict) else {}

    tone_sliders = interaction_style.get("tone_sliders") if isinstance(interaction_style.get("tone_sliders"), dict) else {}
    persona = PersonaArtifact(
        tone_sliders=ToneSliders(
            directness=float(tone_sliders.get("directness", 0.65)),
            warmth=float(tone_sliders.get("warmth", 0.55)),
            skepticism=float(tone_sliders.get("skepticism", 0.55)),
        ),
        voice_rules=[
            str(v).strip()
            for v in (identity_voice.get("voice_rules") or [])
            if str(v).strip()
        ],
        preferred_phrases=[
            str(v).strip()
            for v in (identity_voice.get("signature_phrases") or [])
            if str(v).strip()
        ],
        avoid_phrases=[
            str(v).strip()
            for v in (deterministic_rules.get("banned_phrases") or [])
            if str(v).strip()
        ],
        pushback_style=str(interaction_style.get("disagreement_style") or "").strip() or None,
        summary_style=str(interaction_style.get("structure_default") or "").strip() or None,
    )

    rubric = decision_policy.get("rubric_dimensions") if isinstance(decision_policy.get("rubric_dimensions"), list) else []
    if not rubric and isinstance(decision_policy.get("rubric_rules"), list):
        rubric = decision_policy.get("rubric_rules")

    decision_system = DecisionSystemArtifact(
        rubric_dimensions=[r for r in rubric if isinstance(r, dict)],
        green_flags=[
            str(v).strip()
            for v in (decision_policy.get("green_flags") or [])
            if str(v).strip()
        ],
        red_flags=[
            str(v).strip()
            for v in (decision_policy.get("red_flags") or [])
            if str(v).strip()
        ],
        default_assumptions=[
            str(v).strip()
            for v in (decision_policy.get("default_assumptions") or [])
            if str(v).strip()
        ],
        missing_info_behavior=str(decision_policy.get("missing_info_behavior") or "ask_clarifying_questions"),
    )

    workflow_rows: List[WorkflowArtifact] = []
    raw_workflow_library = payload.get("workflow_library")
    if isinstance(raw_workflow_library, dict):
        for wf_name, wf_value in raw_workflow_library.items():
            if not isinstance(wf_value, dict):
                continue
            workflow_rows.append(
                WorkflowArtifact(
                    workflow=str(wf_name),
                    output_schema=str(wf_value.get("output_schema") or f"workflow.{wf_name}.v1"),
                    required_inputs=[
                        str(v).strip() for v in (wf_value.get("required_inputs") or []) if str(v).strip()
                    ],
                    steps=[str(v).strip() for v in (wf_value.get("steps") or []) if str(v).strip()],
                    template=str(wf_value.get("template") or "").strip() or None,
                )
            )
    if not workflow_rows:
        workflow_rows = _default_workflows()

    guardrails = GuardrailsArtifact(
        forbidden_topics=[
            str(v).strip()
            for v in (raw_guardrails.get("forbidden_topics") or [])
            if str(v).strip()
        ],
        refusal_templates=[
            str(v).strip()
            for v in (raw_guardrails.get("refusal_templates") or [])
            if str(v).strip()
        ],
        confidentiality_rules=[
            str(v).strip()
            for v in (raw_guardrails.get("confidentiality_rules") or [])
            if str(v).strip()
        ],
        conflict_rules=[
            str(v).strip()
            for v in (raw_guardrails.get("conflict_rules") or [])
            if str(v).strip()
        ],
        uncertainty_rule=str(raw_guardrails.get("uncertainty_rule") or "If uncertain, say you do not know and ask to clarify."),
        escalation_rule=str(raw_guardrails.get("escalation_rule") or "Escalate to owner when confidence is low."),
    )

    faq_rows: List[FAQArtifact] = []
    raw_faq = payload.get("faq_library")
    if isinstance(raw_faq, list):
        for item in raw_faq:
            if not isinstance(item, dict):
                continue
            question = str(item.get("question") or "").strip()
            answer = str(item.get("answer") or "").strip()
            if not question or not answer:
                continue
            faq_rows.append(
                FAQArtifact(
                    question=question,
                    answer=answer,
                    template=str(item.get("template") or "").strip() or None,
                )
            )

    twin_spec = TwinSpec(
        version=version,
        persona=persona,
        decision_system=decision_system,
        workflows=workflow_rows,
        guardrails=guardrails,
        faq=faq_rows,
        metadata={
            "source": "persona_specs",
            "persona_spec_version": version,
            "has_stance_values": bool(stance_values),
        },
    )
    return twin_spec

