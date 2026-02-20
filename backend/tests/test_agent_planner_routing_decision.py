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


@pytest.mark.asyncio
async def test_planner_confidence_is_calibrated_from_retrieval_stats(monkeypatch):
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
                "answerability": "direct",
                "confidence": 0.9,
                "reasoning": "Directly answerable.",
                "missing_information": [],
                "ambiguity_level": "low",
            }
        ),
    )
    monkeypatch.setattr(
        "modules.agent.invoke_json",
        AsyncMock(
            return_value=(
                {
                    "answer_points": ["Use containers first for predictable operations."],
                    "citations": ["src-1"],
                    "confidence": 0.95,
                    "reasoning_trace": "High-level recommendation.",
                },
                {"provider": "test"},
            )
        ),
    )

    state = {
        "messages": [HumanMessage(content="Containers or serverless?")],
        "dialogue_mode": "QA_FACT",
        "query_class": "evaluative",
        "quote_intent": False,
        "retrieved_context": {
            "results": [
                {
                    "source_id": "src-1",
                    "text": "Recommendation: Start with containers.",
                    "block_type": "answer_text",
                    "is_answer_text": True,
                    "retrieval_stats": {
                        "dense_top1": 0.12,
                        "dense_top5_avg": 0.1,
                        "sparse_top1": 0.08,
                        "sparse_top5_avg": 0.06,
                        "rerank_top1": 0.0,
                        "rerank_top5_avg": 0.0,
                        "evidence_block_counts": {"answer_text": 1},
                    },
                }
            ]
        },
        "routing_decision": {"intent": "answer", "chosen_workflow": "answer", "output_schema": "workflow.answer.v1"},
        "reasoning_history": [],
    }

    out = await planner_node(state)
    confidence = float(out["planning_output"]["confidence"])

    assert 0.0 < confidence < 0.90
    assert out["confidence_score"] == confidence


@pytest.mark.asyncio
async def test_planner_confidence_prefers_rerank_signal_when_present(monkeypatch):
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
                "confidence": 0.72,
                "reasoning": "Derivable from multiple chunks.",
                "missing_information": [],
                "ambiguity_level": "medium",
            }
        ),
    )
    monkeypatch.setattr(
        "modules.agent.invoke_json",
        AsyncMock(
            return_value=(
                {
                    "answer_points": ["Recommendation: containers first, then revisit serverless when traffic pattern stabilizes."],
                    "citations": ["src-1"],
                    "confidence": 0.74,
                    "reasoning_trace": "Reranked evidence is strong.",
                },
                {"provider": "test"},
            )
        ),
    )

    state = {
        "messages": [HumanMessage(content="Containers or serverless?")],
        "dialogue_mode": "QA_FACT",
        "query_class": "evaluative",
        "quote_intent": False,
        "retrieved_context": {
            "results": [
                {
                    "source_id": "src-1",
                    "text": "Recommendation: Start with containers on a managed platform.",
                    "block_type": "answer_text",
                    "is_answer_text": True,
                    "retrieval_stats": {
                        "dense_top1": 0.35,
                        "dense_top5_avg": 0.29,
                        "sparse_top1": 0.22,
                        "sparse_top5_avg": 0.17,
                        "rerank_top1": 0.91,
                        "rerank_top5_avg": 0.82,
                        "evidence_block_counts": {"answer_text": 1},
                    },
                }
            ]
        },
        "routing_decision": {"intent": "answer", "chosen_workflow": "answer", "output_schema": "workflow.answer.v1"},
        "reasoning_history": [],
    }

    out = await planner_node(state)
    confidence = float(out["planning_output"]["confidence"])

    assert 0.70 <= confidence <= 0.97


@pytest.mark.asyncio
async def test_planner_identity_insufficient_triggers_second_pass_with_rich_context(monkeypatch):
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
                "confidence": 0.2,
                "reasoning": "Need clearer identity evidence.",
                "missing_information": ["the twin's identity bio and core expertise"],
                "ambiguity_level": "medium",
            },
            {
                "answerability": "direct",
                "confidence": 0.76,
                "reasoning": "Identity evidence found in second pass.",
                "missing_information": [],
                "ambiguity_level": "low",
            },
        ]
    )
    monkeypatch.setattr("modules.agent.evaluate_answerability", evaluate_mock)

    second_pass_mock = AsyncMock(
        return_value=[
            {
                "source_id": "src-id-1",
                "text": "I am a twin focused on pragmatic founder support and decision clarity.",
                "section_title": "Owner identity and credibility",
                "doc_name": "Identity.docx",
                "block_type": "answer_text",
                "is_answer_text": True,
            }
        ]
    )
    monkeypatch.setattr("modules.agent._run_second_pass_retrieval", second_pass_mock)
    monkeypatch.setattr("modules.agent.invoke_json", AsyncMock(side_effect=RuntimeError("planner unavailable")))

    state = {
        "twin_id": "twin-identity",
        "messages": [HumanMessage(content="Tell me about yourself")],
        "dialogue_mode": "QA_FACT",
        "query_class": "identity",
        "quote_intent": False,
        "retrieved_context": {
            "results": [
                {"source_id": "s1", "text": "Questionnaire item one", "section_title": "mean", "block_type": "prompt_question", "is_answer_text": False},
                {"source_id": "s2", "text": "Questionnaire item two", "section_title": "E) > mean", "block_type": "prompt_question", "is_answer_text": False},
                {"source_id": "s3", "text": "Questionnaire item three", "section_title": "H) constraints", "block_type": "prompt_question", "is_answer_text": False},
                {"source_id": "s4", "text": "Questionnaire item four", "section_title": "I) style", "block_type": "prompt_question", "is_answer_text": False},
            ]
        },
        "routing_decision": {"intent": "answer", "chosen_workflow": "answer", "output_schema": "workflow.answer.v1"},
        "reasoning_history": [],
        "retrieval_group_id": None,
        "resolve_default_group_filtering": True,
    }

    out = await planner_node(state)
    assert second_pass_mock.await_count == 1
    assert evaluate_mock.await_count == 2
    assert out["routing_decision"]["action"] == "answer"
    assert out["planning_output"]["answerability"]["answerability"] == "direct"
