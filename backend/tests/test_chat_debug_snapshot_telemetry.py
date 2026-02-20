def test_debug_snapshot_includes_planner_telemetry_fields():
    import routers.chat as chat_router

    snapshot = chat_router._build_debug_snapshot(
        query="What do you see in the founders?",
        requires_evidence=True,
        planning_output={
            "answerability": {"answerability": "insufficient"},
            "telemetry": {
                "retrieval.retry_reason": "low_quality_evidence,prompt_question_dominance",
                "retrieval.prompt_question_dominance": True,
                "retrieval.answer_text_ratio": 0.21,
                "planner.intent_recovered": True,
                "clarify.noisy_section_filtered_count": 3,
                "clarify.option_count": 2,
            },
        },
        routing_decision={"action": "clarify"},
        contexts=[
            {
                "source_id": "s1",
                "text": "Q1: What do you optimize for?",
                "block_type": "prompt_question",
                "retrieval_stats": {
                    "dense_top1": 0.41,
                    "dense_top5_avg": 0.37,
                    "confidence_floor_value": 0.41,
                    "confidence_floor_threshold": 0.55,
                    "meets_confidence_floor": False,
                    "evidence_block_counts": {"prompt_question": 1},
                    "retry_applied": True,
                },
            }
        ],
    )

    assert snapshot["retrieval.retry_reason"] == "low_quality_evidence,prompt_question_dominance"
    assert snapshot["retrieval.prompt_question_dominance"] is True
    assert snapshot["retrieval.answer_text_ratio"] == 0.21
    assert snapshot["planner.intent_recovered"] is True
    assert snapshot["clarify.noisy_section_filtered_count"] == 3
    assert snapshot["clarify.option_count"] == 2


def test_langfuse_turn_telemetry_emits_required_fields(monkeypatch):
    import routers.chat as chat_router

    observed = {"observation": None, "trace": None}

    class _Ctx:
        def update_current_observation(self, metadata=None, **_kwargs):
            observed["observation"] = metadata

        def update_current_trace(self, metadata=None, **_kwargs):
            observed["trace"] = metadata

    monkeypatch.setattr(chat_router, "langfuse_context", _Ctx())

    chat_router._emit_langfuse_turn_telemetry(
        {
            "retrieval.retry_reason": "low_quality_evidence",
            "retrieval.prompt_question_dominance": True,
            "retrieval.answer_text_ratio": 0.3,
            "planner.intent_recovered": True,
            "clarify.noisy_section_filtered_count": 1,
            "clarify.option_count": 2,
        }
    )

    assert observed["observation"] is not None
    assert observed["trace"] is not None
    assert observed["trace"]["retrieval.retry_reason"] == "low_quality_evidence"
    assert observed["trace"]["clarify.option_count"] == 2
