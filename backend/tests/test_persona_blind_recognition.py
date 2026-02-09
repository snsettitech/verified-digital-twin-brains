from eval.persona_blind_recognition import (
    PersonaFingerprint,
    TranscriptSample,
    evaluate_blind_recognition,
)


def test_blind_recognition_distinguishes_personas():
    personas = [
        PersonaFingerprint(
            persona_id="exec",
            display_name="Exec",
            signature_keywords=["constraint", "tradeoff", "next step"],
            structure_preference="bullets",
            question_style="low",
            target_words_min=10,
            target_words_max=80,
        ),
        PersonaFingerprint(
            persona_id="coach",
            display_name="Coach",
            signature_keywords=["context", "assumption", "reflection"],
            structure_preference="paragraph",
            question_style="medium",
            target_words_min=15,
            target_words_max=110,
        ),
    ]
    transcripts = [
        TranscriptSample(
            transcript_id="t1",
            persona_id="exec",
            text="- Constraint first.\n- Tradeoff is explicit.\n- Next step ships this week.",
        ),
        TranscriptSample(
            transcript_id="t2",
            persona_id="coach",
            text=(
                "I start with context and one assumption. "
                "Then I compare options and add reflection before a recommendation."
            ),
        ),
        TranscriptSample(
            transcript_id="t3",
            persona_id="exec",
            text="- Decision with a clear tradeoff.\n- Next step is assigned.",
        ),
        TranscriptSample(
            transcript_id="t4",
            persona_id="coach",
            text=(
                "Given the context, my assumption is moderate risk tolerance. "
                "One option stands out after reflection."
            ),
        ),
    ]

    summary = evaluate_blind_recognition(
        personas=personas,
        transcripts=transcripts,
        min_accuracy=0.80,
    )

    assert summary["total"] == 4
    assert summary["accuracy"] >= 0.80
    assert summary["passed"] is True

