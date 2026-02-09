import pytest

from modules.persona_auditor import audit_persona_response


@pytest.mark.asyncio
async def test_persona_auditor_rewrites_when_structure_fails(monkeypatch):
    monkeypatch.setattr(
        "modules.persona_auditor.get_active_persona_spec",
        lambda twin_id: {
            "version": "1.0.0",
            "spec": {
                "version": "1.0.0",
                "identity_voice": {"tone": "direct"},
                "decision_policy": {"cite_when_factual": True},
                "interaction_style": {"brevity_default": "concise"},
                "constitution": ["Never fabricate sources."],
                "procedural_modules": [],
                "deterministic_rules": {"banned_phrases": ["forbidden phrase"]},
            },
        },
    )
    monkeypatch.setattr(
        "modules.persona_auditor.list_runtime_modules_for_intent",
        lambda **kwargs: [],
    )
    async def noop_persist(**kwargs):
        return None

    monkeypatch.setattr("modules.persona_auditor._persist_judge_result", noop_persist)

    async def fake_structure(**kwargs):
        answer = kwargs["answer"]
        if "rewritten" in answer:
            return {
                "score": 0.95,
                "verdict": "pass",
                "violated_clauses": [],
                "rewrite_directives": [],
                "reasoning": "ok",
            }
        return {
            "score": 0.4,
            "verdict": "fail",
            "violated_clauses": ["POL_CITATION_REQUIRED"],
            "rewrite_directives": ["Add concise cited statement."],
            "reasoning": "missing citation",
        }

    async def fake_voice(**kwargs):
        return {
            "score": 0.9,
            "verdict": "pass",
            "violated_clauses": [],
            "rewrite_directives": [],
            "reasoning": "aligned",
        }

    async def fake_rewrite(**kwargs):
        return {
            "rewritten_answer": "rewritten answer with citation [1]",
            "applied": True,
            "reasoning": "fixed",
        }

    monkeypatch.setattr("modules.persona_auditor.judge_persona_structure_policy", fake_structure)
    monkeypatch.setattr("modules.persona_auditor.judge_persona_voice_fidelity", fake_voice)
    monkeypatch.setattr("modules.persona_auditor.rewrite_with_clause_directives", fake_rewrite)

    result = await audit_persona_response(
        twin_id="twin-1",
        user_query="What happened?",
        draft_response="forbidden phrase answer",
        intent_label="factual_with_evidence",
        module_ids=["procedural.factual.cite_or_disclose_uncertainty"],
        citations=["src-1"],
        tenant_id="tenant-1",
        conversation_id="conv-1",
        interaction_context="owner_chat",
    )

    assert result.rewrite_applied is True
    assert result.final_response == "rewritten answer with citation [1]"
    assert result.intent_label == "factual_with_evidence"
    assert result.persona_spec_version == "1.0.0"
    assert result.final_persona_score >= result.draft_persona_score


@pytest.mark.asyncio
async def test_persona_auditor_passthrough_when_no_active_spec(monkeypatch):
    monkeypatch.setattr("modules.persona_auditor.get_active_persona_spec", lambda twin_id: None)
    async def noop_persist(**kwargs):
        return None

    monkeypatch.setattr("modules.persona_auditor._persist_judge_result", noop_persist)

    result = await audit_persona_response(
        twin_id="twin-1",
        user_query="Hello there",
        draft_response="Hello there!",
        intent_label="meta_or_system",
        module_ids=[],
        citations=[],
    )
    assert result.final_response == "Hello there!"
    assert result.rewrite_applied is False
    assert result.intent_label == "meta_or_system"
