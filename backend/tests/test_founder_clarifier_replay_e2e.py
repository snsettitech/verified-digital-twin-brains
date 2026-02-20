from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from modules.agent import planner_node


@pytest.mark.asyncio
async def test_founder_clarifier_replay_all_three_composes_answer_with_citations(monkeypatch):
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
        "modules.agent._run_second_pass_retrieval",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "modules.agent.evaluate_answerability",
        AsyncMock(
            return_value={
                "answerability": "insufficient",
                "confidence": 0.32,
                "reasoning": "Need stronger support.",
                "missing_information": ["founder quality criteria from guidance sections"],
                "ambiguity_level": "medium",
            }
        ),
    )
    monkeypatch.setattr(
        "modules.agent.invoke_json",
        AsyncMock(
            return_value=(
                {
                    "answer_points": [
                        "Founders are assessed on clarity of thinking, execution discipline, and learning velocity."
                    ],
                    "citations": ["kb-founders-1"],
                    "confidence": 0.68,
                    "reasoning_trace": "Composed from founder rubric guidance.",
                },
                {"provider": "test"},
            )
        ),
    )

    first_turn = {
        "twin_id": "twin-sham",
        "messages": [HumanMessage(content="what do you see in the founders")],
        "dialogue_mode": "QA_FACT",
        "query_class": "evaluative",
        "quote_intent": False,
        "retrieved_context": {
            "results": [
                {
                    "source_id": "kb-q1",
                    "text": "1) What do you look for in founders?",
                    "block_type": "prompt_question",
                    "is_answer_text": False,
                },
                {
                    "source_id": "kb-q2",
                    "text": "2) What are red flags?",
                    "block_type": "prompt_question",
                    "is_answer_text": False,
                },
            ]
        },
        "routing_decision": {"intent": "answer", "chosen_workflow": "answer", "output_schema": "workflow.answer.v1"},
        "reasoning_history": [],
        "retrieval_group_id": None,
        "resolve_default_group_filtering": True,
    }
    first_out = await planner_node(first_turn)
    assert first_out["routing_decision"]["action"] == "clarify"
    assert len(first_out["planning_output"]["teaching_questions"]) >= 1

    second_turn = {
        "twin_id": "twin-sham",
        "messages": [
            HumanMessage(content="what do you see in the founders"),
            AIMessage(content="\n".join(first_out["planning_output"]["answer_points"])),
            HumanMessage(content="all three"),
        ],
        "dialogue_mode": "QA_FACT",
        "query_class": "evaluative",
        "quote_intent": False,
        "retrieved_context": {
            "results": [
                {
                    "source_id": "kb-founders-1",
                    "text": "Decision rubric: prioritize founder clarity, execution discipline, and learning velocity.",
                    "block_type": "answer_text",
                    "is_answer_text": True,
                },
                {
                    "source_id": "kb-founders-2",
                    "text": "Communication style: direct and practical feedback with next steps.",
                    "block_type": "answer_text",
                    "is_answer_text": True,
                },
            ]
        },
        "routing_decision": {"intent": "answer", "chosen_workflow": "answer", "output_schema": "workflow.answer.v1"},
        "reasoning_history": [],
        "retrieval_group_id": None,
        "resolve_default_group_filtering": True,
    }
    second_out = await planner_node(second_turn)
    assert second_out["routing_decision"]["action"] == "answer"
    assert second_out["planning_output"]["teaching_questions"] == []
    assert second_out["planning_output"]["citations"]
    assert second_out["planning_output"]["answer_points"]

