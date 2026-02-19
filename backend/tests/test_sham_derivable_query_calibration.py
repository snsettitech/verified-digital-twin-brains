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
        "routing_decision": {
            "intent": "answer",
            "chosen_workflow": "answer",
            "output_schema": "workflow.answer.v1",
        },
        "reasoning_history": [],
    }


def _assert_answer_not_clarify(out):
    plan = out["planning_output"]
    assert out["routing_decision"]["action"] == "answer"
    assert plan["answerability"]["answerability"] == "derivable"
    assert plan["teaching_questions"] == []
    assert "don't know" not in " ".join(plan["answer_points"]).lower()


@pytest.mark.asyncio
async def test_sham_summary_query_is_derivable_and_not_clarified(monkeypatch):
    monkeypatch.setattr("modules.agent.build_system_prompt_with_trace", lambda _state: _trace())
    monkeypatch.setattr("modules.answerability.invoke_json", AsyncMock(side_effect=RuntimeError("offline")))
    monkeypatch.setattr("modules.agent.invoke_json", AsyncMock(side_effect=RuntimeError("planner unavailable")))

    sham_rows = [
        {
            "source_id": "sham-1",
            "section_path": "Sham's Knowledge Base.pdf/VC Thesis",
            "text": "Sham's twin helps evaluate founders using investment thesis and execution clarity.",
        },
        {
            "source_id": "sham-2",
            "section_path": "Sham's Knowledge Base.pdf/IC Process",
            "text": "IC reviews focus on evidence, founder velocity, and practical risk handling.",
        },
        {
            "source_id": "sham-3",
            "section_path": "Sham's Knowledge Base.pdf/Communication",
            "text": "Communication style is direct, calm, and recommendation-first.",
        },
        {
            "source_id": "sham-4",
            "section_path": "Sham's Knowledge Base.pdf/Boundaries",
            "text": "Non-goals include generic theory without decision implications.",
        },
    ]
    out = await planner_node(_base_state("Summarize the twin in 3 bullets", sham_rows))
    _assert_answer_not_clarify(out)


@pytest.mark.asyncio
async def test_sham_red_flags_query_is_derivable_and_not_clarified(monkeypatch):
    monkeypatch.setattr("modules.agent.build_system_prompt_with_trace", lambda _state: _trace())
    monkeypatch.setattr("modules.answerability.invoke_json", AsyncMock(side_effect=RuntimeError("offline")))
    monkeypatch.setattr("modules.agent.invoke_json", AsyncMock(side_effect=RuntimeError("planner unavailable")))

    sham_rows = [
        {
            "source_id": "sham-1",
            "section_path": "Sham's Knowledge Base.pdf/VC Thesis",
            "text": "Thesis emphasizes founder-market fit and repeatable execution signals.",
        },
        {
            "source_id": "sham-2",
            "section_path": "Sham's Knowledge Base.pdf/Decision Rubric",
            "text": "Decision rubric weighs evidence quality, speed of learning, and downside control.",
        },
        {
            "source_id": "sham-3",
            "section_path": "Sham's Knowledge Base.pdf/Risk Signals",
            "text": "Risk patterns include weak evidence loops and unclear ownership of outcomes.",
        },
        {
            "source_id": "sham-4",
            "section_path": "Sham's Knowledge Base.pdf/IC Notes",
            "text": "IC notes capture pass criteria when founder conviction lacks proof.",
        },
    ]
    out = await planner_node(_base_state("Give me the top 3 red flags this twin would pass on", sham_rows))
    _assert_answer_not_clarify(out)


@pytest.mark.asyncio
async def test_sham_evaluative_fit_query_is_derivable_with_rubric_evidence(monkeypatch):
    monkeypatch.setattr("modules.agent.build_system_prompt_with_trace", lambda _state: _trace())
    monkeypatch.setattr("modules.answerability.invoke_json", AsyncMock(side_effect=RuntimeError("offline")))
    monkeypatch.setattr("modules.agent.invoke_json", AsyncMock(side_effect=RuntimeError("planner unavailable")))

    sham_rows = [
        {
            "source_id": "sham-1",
            "section_path": "Sham's Knowledge Base.pdf/Investment Thesis",
            "text": "Investment thesis prioritizes B2B products with clear economic buyers.",
        },
        {
            "source_id": "sham-2",
            "section_path": "Sham's Knowledge Base.pdf/IC Rubric",
            "text": "IC rubric asks whether the team can execute and prove demand quickly.",
        },
        {
            "source_id": "sham-3",
            "section_path": "Sham's Knowledge Base.pdf/Decision Criteria",
            "text": "Decision criteria include defensibility, sales motion clarity, and measured traction.",
        },
        {
            "source_id": "sham-4",
            "section_path": "Sham's Knowledge Base.pdf/Risk Review",
            "text": "Risk review checks if operational complexity can be handled by the founding team.",
        },
    ]
    out = await planner_node(_base_state("Would this twin like a B2B payroll SaaS?", sham_rows))
    _assert_answer_not_clarify(out)
