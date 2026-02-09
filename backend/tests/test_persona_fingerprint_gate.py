from modules.persona_fingerprint_gate import run_persona_fingerprint_gate


def test_fingerprint_gate_detects_banned_phrase_and_length_violation():
    result = run_persona_fingerprint_gate(
        answer="As an AI language model, maybe this answer is too long for the rule.",
        intent_label="factual_with_evidence",
        deterministic_rules={
            "banned_phrases": ["As an AI language model"],
            "length_bands": {"factual_with_evidence": {"min_words": 1, "max_words": 6}},
            "strict_hedges": True,
            "allowed_hedges": ["maybe"],
        },
        interaction_style={"brevity_default": "concise"},
    )
    assert result["passed"] is False
    assert "POL_DET_BANNED_PHRASE" in result["violated_clauses"]
    assert "POL_DET_LENGTH_BAND" in result["violated_clauses"]


def test_fingerprint_gate_respects_required_bullet_structure():
    result = run_persona_fingerprint_gate(
        answer="This is a paragraph without bullets.",
        intent_label="advice_or_stance",
        deterministic_rules={"format_by_intent": {"advice_or_stance": "bullets"}},
        interaction_style={},
    )
    assert result["checks"]["format_signature"]["required"] == "bullets"
    assert result["checks"]["format_signature"]["passed"] is False
    assert "POL_DET_FORMAT_SIGNATURE" in result["violated_clauses"]

