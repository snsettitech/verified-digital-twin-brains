from modules.persona_compiler import (
    compile_prompt_plan,
    get_prompt_render_options,
    render_prompt_plan,
    render_prompt_plan_with_options,
)
from modules.persona_spec import PersonaSpec, ProceduralModule


def test_compile_prompt_plan_deterministic_order_and_module_selection():
    spec = PersonaSpec(
        version="1.2.3",
        constitution=["Never fabricate sources."],
        decision_policy={"clarify_when_ambiguous": True},
        stance_values={"risk_tolerance": "medium"},
        identity_voice={"tone": "direct"},
        interaction_style={"brevity_default": "concise"},
        canonical_examples=[
            {
                "id": "ex_fact",
                "intent_label": "factual_with_evidence",
                "prompt": "What happened?",
                "response": "Here is what happened with citations.",
            },
            {
                "id": "ex_advice",
                "intent_label": "advice_or_stance",
                "prompt": "What should I do?",
                "response": "I would clarify constraints first.",
            },
        ],
        procedural_modules=[
            {
                "id": "procedural.b",
                "intent_labels": ["factual_with_evidence"],
                "do": ["retrieve_evidence_first"],
                "few_shot_ids": ["ex_fact"],
                "priority": 20,
                "active": True,
            },
            {
                "id": "procedural.a",
                "intent_labels": ["factual_with_evidence"],
                "do": ["cite_sources"],
                "priority": 10,
                "active": True,
            },
        ],
        deterministic_rules={"banned_phrases": ["As an AI language model"]},
    )

    plan = compile_prompt_plan(spec, intent_label="factual_with_evidence", user_query="facts with evidence")
    assert plan.persona_spec_version == "1.2.3"
    assert plan.selected_module_ids == ["procedural.a", "procedural.b"]
    assert len(plan.few_shots) <= 4
    assert any(item.get("id") == "ex_fact" for item in plan.few_shots)
    assert "As an AI language model" in plan.deterministic_rules.get("banned_phrases", [])

    rendered = render_prompt_plan(plan)
    constitution_idx = rendered.find("CONSTITUTION")
    decision_idx = rendered.find("DECISION POLICY")
    style_idx = rendered.find("VOICE IDENTITY")
    module_idx = rendered.find("INTENT PROCEDURAL MODULES")
    assert -1 not in [constitution_idx, decision_idx, style_idx, module_idx]
    assert constitution_idx < decision_idx < style_idx < module_idx


def test_compile_prompt_plan_merges_runtime_modules():
    spec = PersonaSpec(
        version="1.0.0",
        constitution=["Never fabricate."],
        identity_voice={"tone": "direct"},
        decision_policy={"clarify_when_ambiguous": True},
        stance_values={},
        interaction_style={"brevity_default": "concise"},
        procedural_modules=[
            {
                "id": "procedural.spec.default",
                "intent_labels": ["factual_with_evidence"],
                "do": ["cite_sources"],
                "priority": 40,
                "active": True,
            }
        ],
    )

    runtime = ProceduralModule(
        id="procedural.runtime.recent",
        intent_labels=["factual_with_evidence"],
        do=["disclose_uncertainty_if_low_confidence"],
        priority=20,
        active=True,
    )

    plan = compile_prompt_plan(
        spec=spec,
        intent_label="factual_with_evidence",
        runtime_modules=[runtime],
    )

    assert plan.selected_module_ids == ["procedural.runtime.recent", "procedural.spec.default"]
    assert "procedural.runtime.recent" in render_prompt_plan(plan)


def test_render_prompt_plan_with_compact_variant_can_hide_few_shots():
    spec = PersonaSpec(
        version="1.0.0",
        constitution=["Never fabricate."],
        identity_voice={"tone": "direct"},
        decision_policy={"clarify_when_ambiguous": True},
        stance_values={},
        interaction_style={"brevity_default": "concise"},
        canonical_examples=[
            {
                "id": "ex_1",
                "intent_label": "factual_with_evidence",
                "prompt": "What happened?",
                "response": "Here is the factual answer.",
            }
        ],
        procedural_modules=[
            {
                "id": "procedural.spec.default",
                "intent_labels": ["factual_with_evidence"],
                "do": ["cite_sources"],
                "priority": 40,
                "active": True,
            }
        ],
    )
    options = get_prompt_render_options("compact_no_examples_v1")
    plan = compile_prompt_plan(
        spec=spec,
        intent_label="factual_with_evidence",
        user_query="What happened?",
        max_few_shots=options.max_few_shots,
        module_detail_level=options.module_detail_level,
    )
    rendered = render_prompt_plan_with_options(plan=plan, options=options)
    assert "INTENT PROCEDURAL MODULES" in rendered
    assert "CANONICAL FEW-SHOTS" not in rendered
