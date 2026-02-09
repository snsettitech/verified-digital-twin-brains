"""
Persona Compiler

Compiles a versioned persona spec into a typed PromptPlan with deterministic section order.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal
import json
import re

from pydantic import BaseModel, Field

from modules.persona_spec import PersonaSpec, ProceduralModule, PersonaExample


class PromptPlan(BaseModel):
    persona_spec_version: str
    constitution_text: str
    decision_policy_text: str
    style_rules_text: str
    intent_modules_text: str
    few_shots: List[Dict[str, Any]] = Field(default_factory=list)
    deterministic_rules: Dict[str, Any] = Field(default_factory=dict)
    selected_module_ids: List[str] = Field(default_factory=list)
    intent_label: Optional[str] = None


class PromptRenderOptions(BaseModel):
    variant_id: str = "baseline_v1"
    module_detail_level: Literal["expanded", "compact"] = "expanded"
    include_few_shots: bool = True
    include_anti_style_rules: bool = True
    max_few_shots: int = 4
    section_delimiter: str = "\n\n"


PROMPT_RENDER_VARIANTS: Dict[str, Dict[str, Any]] = {
    # Runtime-safe default.
    "baseline_v1": {
        "variant_id": "baseline_v1",
        "module_detail_level": "expanded",
        "include_few_shots": True,
        "include_anti_style_rules": True,
        "max_few_shots": 4,
        "section_delimiter": "\n\n",
    },
    # Lower token pressure, keeps anti-style safety constraints.
    "compact_v1": {
        "variant_id": "compact_v1",
        "module_detail_level": "compact",
        "include_few_shots": True,
        "include_anti_style_rules": True,
        "max_few_shots": 2,
        "section_delimiter": "\n\n",
    },
    # Fast/cheap mode for high-latency scenarios.
    "compact_no_examples_v1": {
        "variant_id": "compact_no_examples_v1",
        "module_detail_level": "compact",
        "include_few_shots": False,
        "include_anti_style_rules": True,
        "max_few_shots": 0,
        "section_delimiter": "\n\n",
    },
    # Style-heavy mode for voice alignment experiments.
    "voice_focus_v1": {
        "variant_id": "voice_focus_v1",
        "module_detail_level": "expanded",
        "include_few_shots": True,
        "include_anti_style_rules": True,
        "max_few_shots": 4,
        "section_delimiter": "\n\n",
    },
}


def get_prompt_render_options(
    variant_id: Optional[str] = None,
    overrides: Optional[Dict[str, Any]] = None,
) -> PromptRenderOptions:
    chosen = variant_id or "baseline_v1"
    payload = dict(PROMPT_RENDER_VARIANTS.get(chosen, PROMPT_RENDER_VARIANTS["baseline_v1"]))
    if overrides:
        payload.update(overrides)
    return PromptRenderOptions.model_validate(payload)


def _render_mapping(title: str, payload: Dict[str, Any]) -> str:
    if not payload:
        return ""
    lines = [f"{title}:"]
    for key in sorted(payload.keys()):
        value = payload[key]
        if isinstance(value, (dict, list)):
            value_str = json.dumps(value, ensure_ascii=True)
        else:
            value_str = str(value)
        lines.append(f"- {key}: {value_str}")
    return "\n".join(lines)


def _render_list(title: str, items: List[str]) -> str:
    if not items:
        return ""
    lines = [f"{title}:"]
    for item in items:
        lines.append(f"- {item}")
    return "\n".join(lines)


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9]+", (text or "").lower())


def _score_example(example: PersonaExample, intent_label: Optional[str], user_query: Optional[str]) -> float:
    score = 0.0
    if intent_label and example.intent_label == intent_label:
        score += 1.0
    if not user_query:
        return score
    q_tokens = set(_tokenize(user_query))
    if not q_tokens:
        return score
    ex_tokens = set(_tokenize(f"{example.prompt} {example.response} {' '.join(example.tags)}"))
    if not ex_tokens:
        return score
    overlap = len(q_tokens & ex_tokens) / float(len(q_tokens | ex_tokens))
    return score + overlap


def _select_modules(spec: PersonaSpec, intent_label: Optional[str]) -> List[ProceduralModule]:
    modules = [m for m in spec.procedural_modules if m.active]
    if intent_label:
        scoped = [m for m in modules if intent_label in m.intent_labels]
        if scoped:
            modules = scoped
    return sorted(modules, key=lambda m: (m.priority, m.id))


def _select_runtime_modules(
    runtime_modules: List[ProceduralModule],
    intent_label: Optional[str],
) -> List[ProceduralModule]:
    modules = [m for m in runtime_modules if m.active]
    if intent_label:
        modules = [m for m in modules if not m.intent_labels or intent_label in m.intent_labels]
    return sorted(modules, key=lambda m: (m.priority, m.id))


def _select_few_shots(
    spec: PersonaSpec,
    selected_modules: List[ProceduralModule],
    intent_label: Optional[str],
    user_query: Optional[str],
    max_examples: int = 4,
) -> List[Dict[str, Any]]:
    examples = list(spec.canonical_examples)
    if not examples or max_examples <= 0:
        return []

    selected_ids = []
    for module in selected_modules:
        selected_ids.extend(module.few_shot_ids)
    selected_ids = list(dict.fromkeys(selected_ids))

    by_id = {e.id: e for e in examples if e.id}
    selected_examples: List[PersonaExample] = []
    for ex_id in selected_ids:
        ex = by_id.get(ex_id)
        if ex:
            selected_examples.append(ex)
        if len(selected_examples) >= max_examples:
            break

    if len(selected_examples) < max_examples:
        remaining = [e for e in examples if e not in selected_examples]
        ranked = sorted(
            remaining,
            key=lambda e: _score_example(e, intent_label=intent_label, user_query=user_query),
            reverse=True,
        )
        for ex in ranked:
            selected_examples.append(ex)
            if len(selected_examples) >= max_examples:
                break

    output: List[Dict[str, Any]] = []
    for ex in selected_examples[:max_examples]:
        output.append(
            {
                "id": ex.id,
                "intent_label": ex.intent_label,
                "prompt": ex.prompt,
                "response": ex.response,
                "tags": ex.tags,
            }
        )
    return output


def compile_prompt_plan(
    spec: PersonaSpec,
    intent_label: Optional[str] = None,
    user_query: Optional[str] = None,
    max_few_shots: int = 4,
    runtime_modules: Optional[List[ProceduralModule]] = None,
    module_detail_level: str = "expanded",
) -> PromptPlan:
    selected_modules = _select_modules(spec, intent_label=intent_label)
    if runtime_modules:
        merged_by_id = {m.id: m for m in selected_modules}
        for module in _select_runtime_modules(runtime_modules, intent_label=intent_label):
            merged_by_id[module.id] = module
        selected_modules = sorted(merged_by_id.values(), key=lambda m: (m.priority, m.id))

    constitution_text = _render_list("CONSTITUTION", spec.constitution)
    decision_policy_sections = [
        _render_mapping("DECISION POLICY", spec.decision_policy),
        _render_mapping("STANCE VALUES", spec.stance_values),
    ]
    decision_policy_text = "\n\n".join([s for s in decision_policy_sections if s]).strip()

    style_sections = [
        _render_mapping("VOICE IDENTITY", spec.identity_voice),
        _render_mapping("INTERACTION STYLE", spec.interaction_style),
    ]
    style_rules_text = "\n\n".join([s for s in style_sections if s]).strip()

    detail_level = "compact" if str(module_detail_level).strip().lower() == "compact" else "expanded"
    module_lines = ["INTENT PROCEDURAL MODULES:"]
    if selected_modules:
        for module in selected_modules:
            module_lines.append(f"- id={module.id} priority={module.priority}")
            if detail_level == "compact":
                when_keys = sorted(list(module.when.keys())) if module.when else []
                do_count = len(module.do or [])
                ban_count = len(module.ban or [])
                module_lines.append(
                    f"  summary={{\"when_keys\": {json.dumps(when_keys, ensure_ascii=True)}, \"do_count\": {do_count}, \"ban_count\": {ban_count}}}"
                )
            else:
                if module.when:
                    module_lines.append(f"  when={json.dumps(module.when, ensure_ascii=True)}")
                if module.do:
                    module_lines.append(f"  do={json.dumps(module.do, ensure_ascii=True)}")
                if module.say_style:
                    module_lines.append(f"  say_style={json.dumps(module.say_style, ensure_ascii=True)}")
                if module.ban:
                    module_lines.append(f"  ban={json.dumps(module.ban, ensure_ascii=True)}")
    else:
        module_lines.append("- none")

    few_shots = _select_few_shots(
        spec=spec,
        selected_modules=selected_modules,
        intent_label=intent_label,
        user_query=user_query,
        max_examples=max_few_shots,
    )

    deterministic_rules = dict(spec.deterministic_rules or {})
    banned_phrases = deterministic_rules.get("banned_phrases", [])
    module_bans = []
    for module in selected_modules:
        module_bans.extend(module.ban)
    deterministic_rules["banned_phrases"] = list(dict.fromkeys([*banned_phrases, *module_bans]))

    return PromptPlan(
        persona_spec_version=spec.version,
        constitution_text=constitution_text,
        decision_policy_text=decision_policy_text,
        style_rules_text=style_rules_text,
        intent_modules_text="\n".join(module_lines),
        few_shots=few_shots,
        deterministic_rules=deterministic_rules,
        selected_module_ids=[m.id for m in selected_modules],
        intent_label=intent_label,
    )


def render_prompt_plan(plan: PromptPlan) -> str:
    """
    Render prompt plan into deterministic section order text payload.
    """
    options = get_prompt_render_options("baseline_v1")
    return render_prompt_plan_with_options(plan=plan, options=options)


def render_prompt_plan_with_options(
    *,
    plan: PromptPlan,
    options: PromptRenderOptions,
) -> str:
    """
    Render prompt plan using explicit typed render options.
    """
    blocks: List[str] = []
    if plan.constitution_text:
        blocks.append(plan.constitution_text)
    if plan.decision_policy_text:
        blocks.append(plan.decision_policy_text)
    if plan.style_rules_text:
        blocks.append(plan.style_rules_text)
    if plan.intent_modules_text:
        blocks.append(plan.intent_modules_text)

    if options.include_few_shots and plan.few_shots:
        shot_lines = ["CANONICAL FEW-SHOTS (INTENT-SCOPED):"]
        for item in plan.few_shots:
            shot_lines.append(
                f"- [{item.get('intent_label')}] user={item.get('prompt')} assistant={item.get('response')}"
            )
        blocks.append("\n".join(shot_lines))

    anti_rules = plan.deterministic_rules.get("anti_style_rules")
    if options.include_anti_style_rules and anti_rules:
        if isinstance(anti_rules, list):
            lines = ["ANTI-STYLE RULES:"] + [f"- {v}" for v in anti_rules]
            blocks.append("\n".join(lines))
        else:
            blocks.append(f"ANTI-STYLE RULES:\n- {anti_rules}")

    return options.section_delimiter.join([b for b in blocks if b]).strip()
