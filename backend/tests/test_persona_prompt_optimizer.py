import pytest

from eval.persona_prompt_optimizer import optimize_persona_prompts


@pytest.mark.asyncio
async def test_optimize_persona_prompts_heuristic_mode_returns_ranked_summary():
    summary = await optimize_persona_prompts(
        twin_id=None,
        tenant_id=None,
        created_by=None,
        dataset_path=None,
        spec_path=None,
        candidates=None,
        generator_mode="heuristic",
        model="gpt-4o-mini",
        apply_best=False,
        persist=False,
    )

    assert summary["status"] == "completed"
    assert summary["run_mode"] == "heuristic"
    assert summary["candidate_count"] > 0
    assert summary["best_variant"]["variant_id"]
    assert summary["best_objective_score"] >= 0
    assert len(summary["ranking"]) == summary["candidate_count"]


@pytest.mark.asyncio
async def test_optimize_persona_prompts_persist_activates_selected_candidate_row(monkeypatch):
    # Reuse real fallback spec object while bypassing store lookups by twin id.
    from eval.persona_prompt_optimizer import _fallback_spec

    monkeypatch.setattr(
        "eval.persona_prompt_optimizer._load_spec",
        lambda **_kwargs: (_fallback_spec(), "1.0.0"),
    )
    monkeypatch.setattr(
        "eval.persona_prompt_optimizer.create_prompt_optimization_run",
        lambda **_kwargs: {"id": "run-1"},
    )
    monkeypatch.setattr(
        "eval.persona_prompt_optimizer.finalize_prompt_optimization_run",
        lambda **_kwargs: {"id": "run-1", "status": "completed"},
    )

    created_rows = []

    def _fake_create_variant(**kwargs):
        row = {
            "id": f"row-{len(created_rows) + 1}",
            "variant_id": kwargs["variant_id"],
            "render_options": kwargs.get("render_options") or {},
        }
        created_rows.append(row)
        return row

    monkeypatch.setattr("eval.persona_prompt_optimizer.create_persona_prompt_variant", _fake_create_variant)

    activated = {}

    def _fake_activate_record(**kwargs):
        activated["record_id"] = kwargs["record_id"]
        return {"id": kwargs["record_id"], "status": "active"}

    monkeypatch.setattr(
        "eval.persona_prompt_optimizer.activate_persona_prompt_variant_record",
        _fake_activate_record,
    )
    monkeypatch.setattr(
        "eval.persona_prompt_optimizer.activate_persona_prompt_variant",
        lambda **_kwargs: {"id": "fallback", "status": "active"},
    )

    summary = await optimize_persona_prompts(
        twin_id="twin-1",
        tenant_id=None,
        created_by=None,
        dataset_path=None,
        spec_path=None,
        candidates=None,
        generator_mode="heuristic",
        model="gpt-4o-mini",
        apply_best=True,
        persist=True,
    )

    assert summary["status"] == "completed"
    assert summary["activated_variant"]["id"] == activated["record_id"]
    assert activated["record_id"] in {row["id"] for row in created_rows}
