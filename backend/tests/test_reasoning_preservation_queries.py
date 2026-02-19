from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import HumanMessage

from modules.agent import planner_node


def _trace():
    return (
        "system",
        {
            "intent_label": "factual_with_evidence",
            "module_ids": [],
            "persona_spec_version": "1.0.0",
            "persona_prompt_variant": "baseline_v1",
        },
    )


def _base_state(query: str, evidence_rows):
    return {
        "messages": [HumanMessage(content=query)],
        "dialogue_mode": "QA_FACT",
        "retrieved_context": {"results": evidence_rows},
        "routing_decision": {"intent": "answer", "chosen_workflow": "answer", "output_schema": "workflow.answer.v1"},
        "reasoning_history": [],
    }


@pytest.mark.asyncio
async def test_conceptual_reasoning_derivable_without_clarification(monkeypatch):
    monkeypatch.setattr("modules.agent.build_system_prompt_with_trace", lambda _state: _trace())
    monkeypatch.setattr("modules.answerability.invoke_json", AsyncMock(side_effect=RuntimeError("offline")))
    monkeypatch.setattr("modules.agent.invoke_json", AsyncMock(side_effect=RuntimeError("planner unavailable")))

    state = _base_state(
        "What would this twin care about most in a startup?",
        [
            {"source_id": "s1", "text": "Decision rubric: prioritize validated learning, execution speed, and clear tradeoffs."},
            {"source_id": "s2", "text": "Communication style rules: direct, calm, pragmatic, and outcome-first."},
            {"source_id": "s3", "text": "Audience and use cases: founders building B2B products."},
        ],
    )

    out = await planner_node(state)
    plan = out["planning_output"]
    assert out["routing_decision"]["action"] == "answer"
    assert plan["answerability"]["answerability"] == "derivable"
    assert plan["teaching_questions"] == []
    assert "don't know" not in " ".join(plan["answer_points"]).lower()


@pytest.mark.asyncio
async def test_persona_evaluation_derivable_without_clarification(monkeypatch):
    monkeypatch.setattr("modules.agent.build_system_prompt_with_trace", lambda _state: _trace())
    monkeypatch.setattr("modules.answerability.invoke_json", AsyncMock(side_effect=RuntimeError("offline")))
    monkeypatch.setattr("modules.agent.invoke_json", AsyncMock(side_effect=RuntimeError("planner unavailable")))

    state = _base_state(
        "Would this twin like a B2B payroll SaaS?",
        [
            {"source_id": "s1", "text": "Decision rubric: prioritize pragmatic execution and measurable customer value."},
            {"source_id": "s2", "text": "Audience and use cases: operators and founders running B2B teams."},
            {"source_id": "s3", "text": "Communication style rules: direct recommendations with tradeoffs."},
        ],
    )

    out = await planner_node(state)
    plan = out["planning_output"]
    assert out["routing_decision"]["action"] == "answer"
    assert plan["answerability"]["answerability"] == "derivable"
    assert plan["teaching_questions"] == []
    assert "don't know" not in " ".join(plan["answer_points"]).lower()


@pytest.mark.asyncio
async def test_communication_style_inference_derivable_without_clarification(monkeypatch):
    monkeypatch.setattr("modules.agent.build_system_prompt_with_trace", lambda _state: _trace())
    monkeypatch.setattr("modules.answerability.invoke_json", AsyncMock(side_effect=RuntimeError("offline")))
    monkeypatch.setattr("modules.agent.invoke_json", AsyncMock(side_effect=RuntimeError("planner unavailable")))

    state = _base_state(
        "How should I talk to this twin?",
        [
            {"source_id": "s1", "text": "Communication style rules: concise bullets, direct wording, and explicit next steps."},
            {"source_id": "s2", "text": "Non-goals and boundaries: avoid vague theory without operational implications."},
            {"source_id": "s3", "text": "Decision rubric: prioritize practical outcomes over abstract framing."},
        ],
    )

    out = await planner_node(state)
    plan = out["planning_output"]
    assert out["routing_decision"]["action"] == "answer"
    assert plan["answerability"]["answerability"] == "derivable"
    assert plan["teaching_questions"] == []
    assert "don't know" not in " ".join(plan["answer_points"]).lower()


@pytest.mark.asyncio
async def test_adversarial_wording_preserves_persona_answer_mode(monkeypatch):
    monkeypatch.setattr("modules.agent.build_system_prompt_with_trace", lambda _state: _trace())
    monkeypatch.setattr("modules.answerability.invoke_json", AsyncMock(side_effect=RuntimeError("offline")))
    monkeypatch.setattr("modules.agent.invoke_json", AsyncMock(side_effect=RuntimeError("planner unavailable")))

    state = _base_state(
        "Give feedback the way this twin would",
        [
            {"source_id": "s1", "text": "Communication style rules: give direct, calm, pragmatic feedback."},
            {"source_id": "s2", "text": "Decision rubric: include recommendation, assumptions, risks, and next steps."},
            {"source_id": "s3", "text": "Example answers: concise bullets with clear actions."},
        ],
    )

    out = await planner_node(state)
    plan = out["planning_output"]
    assert out["routing_decision"]["action"] == "answer"
    assert plan["answerability"]["answerability"] == "derivable"
    assert plan["teaching_questions"] == []
    assert "don't know" not in " ".join(plan["answer_points"]).lower()
