import pytest
from langchain_core.messages import HumanMessage

from routers.chat import _build_source_faithful_fallback_answer
from modules.agent import planner_node


_DOC_CONTEXT = """
1) Owner identity and credibility
Who are you (short bio used in the twin)
I'm Sainath Setti. I've led high-stakes cloud troubleshooting and customer engineering work at Microsoft.
Core expertise areas
Cloud: architecture, reliability, incident response.
AI: RAG vs fine-tuning, guardrails, evals.

2) Audience and use cases
Primary audience
Operators who need fast decisions, not theory

3) Non-goals and boundaries
Non-goals (things your twin should NOT do)
Do not pretend certainty when evidence is missing.
Do not use motivational fluff.

5) Communication style rules
Default response template
Answer/Recommendation with rationale
Assumptions
Why
Alternatives
Next steps
Risks + mitigations

8) Example answers (what your twin should sound like)
Recommendation: Start with containers on a managed platform.
Assumptions: Early-stage product, small team.
Why: Serverless can slow debugging in MVP mode.
"""


def _context_rows():
    return [{"source_id": "src-doc", "text": _DOC_CONTEXT, "score": 0.9}]


def test_identity_query_uses_identity_sections_only():
    answer = _build_source_faithful_fallback_answer("who are you?", _context_rows())
    lowered = answer.lower()
    assert "sainath setti" in lowered
    assert "core expertise" in lowered or "cloud:" in lowered
    assert "recommendation:" not in lowered
    assert "operators who need fast decisions" not in lowered


def test_non_goals_query_uses_boundaries_section_only():
    answer = _build_source_faithful_fallback_answer("What are your non-goals?", _context_rows())
    lowered = answer.lower()
    assert "non-goals" in lowered or "should not do" in lowered
    assert "do not pretend certainty" in lowered
    assert "recommendation:" not in lowered
    assert "who are you" not in lowered


def test_default_response_query_returns_style_template():
    answer = _build_source_faithful_fallback_answer("How should you respond by default?", _context_rows())
    lowered = answer.lower()
    assert "answer/recommendation" in lowered
    assert "assumptions" in lowered
    assert "risks + mitigations" in lowered
    assert "who are you" not in lowered


@pytest.mark.asyncio
async def test_decision_query_returns_doc_backed_recommendation_with_citations(monkeypatch):
    def fake_prompt_builder(_state):
        return ("system", {"intent_label": "advice_or_stance", "module_ids": []})

    monkeypatch.setattr("modules.agent.build_system_prompt_with_trace", fake_prompt_builder)

    state = {
        "dialogue_mode": "QA_FACT",
        "messages": [HumanMessage(content="Should we use containers or serverless for MVP?")],
        "retrieved_context": {"results": _context_rows()},
        "target_owner_scope": False,
        "full_settings": {},
        "intent_label": "advice_or_stance",
    }

    result = await planner_node(state)
    plan = result["planning_output"]
    assert plan["citations"] == ["src-doc"]
    assert plan["render_strategy"] == "source_faithful"
    assert any(point.startswith("Recommendation:") for point in plan["answer_points"])
    assert any(point.startswith("Assumptions:") for point in plan["answer_points"])
    assert any(point.startswith("Why:") for point in plan["answer_points"])
