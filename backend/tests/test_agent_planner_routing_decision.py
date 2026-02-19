import pytest
from langchain_core.messages import HumanMessage
from unittest.mock import AsyncMock

from modules.agent import planner_node


@pytest.mark.asyncio
async def test_planner_non_answerable_emits_targeted_clarifications(monkeypatch):
    monkeypatch.setattr(
        "modules.agent.build_system_prompt_with_trace",
        lambda _state: (
            "system",
            {
                "intent_label": "factual_with_evidence",
                "module_ids": [],
                "persona_spec_version": "1.0.0",
                "persona_prompt_variant": "baseline_v1",
            },
        ),
    )
    monkeypatch.setattr(
        "modules.agent.evaluate_answerability",
        AsyncMock(
            return_value={
                "answerability": "insufficient",
                "confidence": 0.22,
                "reasoning": "Evidence does not include budget limits or success criteria.",
                "missing_information": ["the budget ceiling for this plan", "the success metric to optimize for"],
                "ambiguity_level": "high",
            }
        ),
    )

    state = {
        "messages": [HumanMessage(content="Create a rollout plan")],
        "dialogue_mode": "QA_FACT",
        "retrieved_context": {"results": [{"text": "Use phased rollout.", "source_id": "src-1"}]},
        "routing_decision": {"intent": "plan", "chosen_workflow": "plan", "output_schema": "workflow.plan.v1"},
        "reasoning_history": [],
    }

    out = await planner_node(state)
    planning = out["planning_output"]

    assert planning["render_strategy"] == "source_faithful"
    assert planning["answer_points"][0].startswith("I don't know based on available sources")
    assert len(planning["teaching_questions"]) <= 3
    assert any("budget" in q.lower() for q in planning["teaching_questions"])
    assert "what outcome do you want from this conversation" not in " ".join(planning["teaching_questions"]).lower()
    assert out["routing_decision"]["action"] == "clarify"


@pytest.mark.asyncio
async def test_planner_derivable_answers_without_i_dont_know(monkeypatch):
    monkeypatch.setattr(
        "modules.agent.build_system_prompt_with_trace",
        lambda _state: (
            "system",
            {
                "intent_label": "factual_with_evidence",
                "module_ids": [],
                "persona_spec_version": "1.0.0",
                "persona_prompt_variant": "baseline_v1",
            },
        ),
    )
    monkeypatch.setattr(
        "modules.agent.evaluate_answerability",
        AsyncMock(
            return_value={
                "answerability": "derivable",
                "confidence": 0.67,
                "reasoning": "Answer is derivable by combining setup chunks.",
                "missing_information": [],
                "ambiguity_level": "medium",
            }
        ),
    )
    monkeypatch.setattr("modules.agent.invoke_json", AsyncMock(side_effect=RuntimeError("planner unavailable")))

    state = {
        "messages": [HumanMessage(content="How to use the twin?")],
        "dialogue_mode": "QA_FACT",
        "retrieved_context": {
            "results": [
                {"text": "Use onboarding and review workflow.", "source_id": "src-1"},
                {"text": "Twin operation starts by connecting sources.", "source_id": "src-2"},
            ]
        },
        "routing_decision": {"intent": "answer", "chosen_workflow": "answer", "output_schema": "workflow.answer.v1"},
        "reasoning_history": [],
    }

    out = await planner_node(state)
    planning = out["planning_output"]

    assert out["routing_decision"]["action"] == "answer"
    assert planning["teaching_questions"] == []
    assert "i don't know" not in " ".join(planning["answer_points"]).lower()


@pytest.mark.asyncio
async def test_planner_insufficient_asks_targeted_not_meta_clarifications(monkeypatch):
    monkeypatch.setattr(
        "modules.agent.build_system_prompt_with_trace",
        lambda _state: (
            "system",
            {
                "intent_label": "factual_with_evidence",
                "module_ids": [],
                "persona_spec_version": "1.0.0",
                "persona_prompt_variant": "baseline_v1",
            },
        ),
    )
    monkeypatch.setattr(
        "modules.agent.evaluate_answerability",
        AsyncMock(
            return_value={
                "answerability": "insufficient",
                "confidence": 0.21,
                "reasoning": "API path and auth requirements are not present.",
                "missing_information": [
                    "context for a conversation",
                    "the required authentication method",
                    "the expected API version",
                ],
                "ambiguity_level": "high",
            }
        ),
    )

    state = {
        "messages": [HumanMessage(content="What API endpoint should I call?")],
        "dialogue_mode": "QA_FACT",
        "retrieved_context": {"results": [{"text": "General architecture notes.", "source_id": "src-1"}]},
        "routing_decision": {"intent": "answer", "chosen_workflow": "answer", "output_schema": "workflow.answer.v1"},
        "reasoning_history": [],
    }

    out = await planner_node(state)
    questions = out["planning_output"]["teaching_questions"]
    assert out["routing_decision"]["action"] == "clarify"
    assert 1 <= len(questions) <= 3
    assert all("context for a conversation" not in q.lower() for q in questions)
    assert any("authentication" in q.lower() or "api version" in q.lower() for q in questions)


@pytest.mark.asyncio
async def test_planner_insufficient_with_evidence_asks_section_scoped_clarification(monkeypatch):
    monkeypatch.setattr(
        "modules.agent.build_system_prompt_with_trace",
        lambda _state: (
            "system",
            {
                "intent_label": "factual_with_evidence",
                "module_ids": [],
                "persona_spec_version": "1.0.0",
                "persona_prompt_variant": "baseline_v1",
            },
        ),
    )
    monkeypatch.setattr(
        "modules.agent.evaluate_answerability",
        AsyncMock(
            return_value={
                "answerability": "insufficient",
                "confidence": 0.2,
                "reasoning": "Need more focus scope.",
                "missing_information": ["the specific evaluation lens to prioritize"],
                "ambiguity_level": "medium",
            }
        ),
    )

    state = {
        "messages": [HumanMessage(content="How should I evaluate this startup?")],
        "dialogue_mode": "QA_FACT",
        "retrieved_context": {
            "results": [
                {"text": "Decision rubric content", "source_id": "src-1", "section_title": "Decision rubric"},
                {"text": "Style guidance", "source_id": "src-2", "section_title": "Communication style rules"},
            ]
        },
        "routing_decision": {"intent": "answer", "chosen_workflow": "answer", "output_schema": "workflow.answer.v1"},
        "reasoning_history": [],
    }

    out = await planner_node(state)
    questions = out["planning_output"]["teaching_questions"]
    joined = " ".join(questions).lower()
    assert out["routing_decision"]["action"] == "clarify"
    assert any(section in joined for section in ["decision rubric", "communication style rules"])


@pytest.mark.asyncio
async def test_planner_insufficient_with_evidence_without_section_titles_stays_document_scoped(monkeypatch):
    monkeypatch.setattr(
        "modules.agent.build_system_prompt_with_trace",
        lambda _state: (
            "system",
            {
                "intent_label": "factual_with_evidence",
                "module_ids": [],
                "persona_spec_version": "1.0.0",
                "persona_prompt_variant": "baseline_v1",
            },
        ),
    )
    monkeypatch.setattr(
        "modules.agent.evaluate_answerability",
        AsyncMock(
            return_value={
                "answerability": "insufficient",
                "confidence": 0.12,
                "reasoning": "Need missing constraints.",
                "missing_information": [
                    "the deployment constraints for this setup",
                    "the expected traffic profile",
                ],
                "ambiguity_level": "high",
            }
        ),
    )

    state = {
        "messages": [HumanMessage(content="Should we ship this to production?")],
        "dialogue_mode": "QA_FACT",
        "retrieved_context": {
            "results": [
                {"text": "General architecture constraints.", "source_id": "src-1"},
                {"text": "Risk checklist and rollout notes.", "source_id": "src-2"},
            ]
        },
        "routing_decision": {"intent": "answer", "chosen_workflow": "answer", "output_schema": "workflow.answer.v1"},
        "reasoning_history": [],
    }

    out = await planner_node(state)
    questions = out["planning_output"]["teaching_questions"]
    joined = " ".join(questions).lower()

    assert out["routing_decision"]["action"] == "clarify"
    assert any("retrieved document sections" in q.lower() for q in questions)
    assert "tell me more" not in joined
    assert "provide context" not in joined


@pytest.mark.asyncio
async def test_planner_insufficient_low_chunk_count_triggers_second_pass_retrieval(monkeypatch):
    monkeypatch.setattr(
        "modules.agent.build_system_prompt_with_trace",
        lambda _state: (
            "system",
            {
                "intent_label": "factual_with_evidence",
                "module_ids": [],
                "persona_spec_version": "1.0.0",
                "persona_prompt_variant": "baseline_v1",
            },
        ),
    )
    evaluate_mock = AsyncMock(
        side_effect=[
            {
                "answerability": "insufficient",
                "confidence": 0.18,
                "reasoning": "Need more evidence.",
                "missing_information": ["the evaluation criteria for the idea"],
                "ambiguity_level": "high",
            },
            {
                "answerability": "derivable",
                "confidence": 0.67,
                "reasoning": "Now derivable with additional rubric chunks.",
                "missing_information": [],
                "ambiguity_level": "medium",
            },
        ]
    )
    monkeypatch.setattr("modules.agent.evaluate_answerability", evaluate_mock)
    second_pass_mock = AsyncMock(
        return_value=[
            {
                "source_id": "src-2",
                "text": "Decision rubric: prioritize practical outcomes and clear tradeoffs.",
                "section_title": "Decision rubric",
                "section_path": "Sai_twin.docx/Decision rubric",
            },
            {
                "source_id": "src-3",
                "text": "Communication style: direct, calm, and recommendation-first.",
                "section_title": "Communication style rules",
                "section_path": "Sai_twin.docx/Communication style rules",
            },
        ]
    )
    monkeypatch.setattr("modules.agent._run_second_pass_retrieval", second_pass_mock)
    monkeypatch.setattr("modules.agent.invoke_json", AsyncMock(side_effect=RuntimeError("planner unavailable")))

    state = {
        "twin_id": "twin-123",
        "messages": [HumanMessage(content="Would this twin like a B2B payroll SaaS?")],
        "dialogue_mode": "QA_FACT",
        "retrieved_context": {"results": [{"source_id": "src-1", "text": "Twin purpose summary."}]},
        "routing_decision": {"intent": "answer", "chosen_workflow": "answer", "output_schema": "workflow.answer.v1"},
        "reasoning_history": [],
        "retrieval_group_id": None,
        "resolve_default_group_filtering": True,
    }

    out = await planner_node(state)
    plan = out["planning_output"]

    assert second_pass_mock.await_count == 1
    assert evaluate_mock.await_count == 2
    assert out["routing_decision"]["action"] == "answer"
    assert plan["answerability"]["answerability"] == "derivable"
    assert plan["teaching_questions"] == []
