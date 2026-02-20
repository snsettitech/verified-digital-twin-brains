from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from modules.agent import planner_node


@pytest.mark.asyncio
async def test_e2e_founders_clarify_then_all_three_answers_without_loop(monkeypatch):
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
    monkeypatch.setattr("modules.agent._run_second_pass_retrieval", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        "modules.agent.evaluate_answerability",
        AsyncMock(
            return_value={
                "answerability": "insufficient",
                "confidence": 0.31,
                "reasoning": "Need stronger support before composing.",
                "missing_information": ["founder criteria from rubric"],
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
                        "Founders are evaluated on clarity, execution discipline, and learning velocity."
                    ],
                    "citations": ["kb-founders-1"],
                    "confidence": 0.7,
                    "reasoning_trace": "Derived from founder rubric and style guidance.",
                },
                {"provider": "test"},
            )
        ),
    )

    first_turn = {
        "twin_id": "twin-e2e",
        "messages": [HumanMessage(content="what do you see in the founders")],
        "dialogue_mode": "QA_FACT",
        "query_class": "evaluative",
        "quote_intent": False,
        "retrieved_context": {
            "results": [
                {
                    "source_id": "q1",
                    "text": "1) What do you look for in founders?",
                    "block_type": "prompt_question",
                    "is_answer_text": False,
                }
            ]
        },
        "routing_decision": {"intent": "answer", "chosen_workflow": "answer", "output_schema": "workflow.answer.v1"},
        "reasoning_history": [],
        "retrieval_group_id": None,
        "resolve_default_group_filtering": True,
    }
    first_out = await planner_node(first_turn)
    assert first_out["routing_decision"]["action"] == "clarify"
    assert first_out["planning_output"]["teaching_questions"]

    second_turn = {
        "twin_id": "twin-e2e",
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
                    "text": "Communication style: direct and practical feedback with clear next steps.",
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
    assert second_out["planning_output"]["answer_points"]
    assert second_out["planning_output"]["citations"]

