from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app
from modules.auth_guard import get_current_user
from modules.persona_spec import PersonaSpec


client = TestClient(app)


def _owner_user():
    return {
        "user_id": "owner-1",
        "tenant_id": "tenant-1",
        "role": "owner",
    }


def test_create_persona_spec_endpoint():
    app.dependency_overrides[get_current_user] = _owner_user
    try:
        with patch("routers.persona_specs.verify_twin_ownership"), patch(
            "routers.persona_specs.ensure_twin_active"
        ), patch(
            "routers.persona_specs.get_next_spec_version", return_value="1.0.0"
        ), patch(
            "routers.persona_specs.create_persona_spec",
            return_value={"id": "ps-1", "version": "1.0.0", "status": "draft"},
        ):
            resp = client.post(
                "/twins/twin-1/persona-specs",
                json={
                    "spec": {
                        "identity_voice": {"tone": "direct"},
                        "decision_policy": {"clarify_when_ambiguous": True},
                        "stance_values": {},
                        "interaction_style": {"brevity_default": "concise"},
                        "constitution": ["Never fabricate sources."],
                        "canonical_examples": [],
                        "anti_examples": [],
                        "procedural_modules": [],
                        "deterministic_rules": {},
                    }
                },
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "draft"
            assert body["persona_spec"]["version"] == "1.0.0"
            assert body["prompt_plan_preview"]["persona_spec_version"] == "1.0.0"
    finally:
        app.dependency_overrides = {}


def test_generate_persona_spec_endpoint():
    app.dependency_overrides[get_current_user] = _owner_user
    generated = PersonaSpec(
        version="2.0.0",
        identity_voice={"tone": "direct"},
        decision_policy={"clarify_when_ambiguous": True},
        stance_values={},
        interaction_style={"brevity_default": "concise"},
        constitution=["Never fabricate sources."],
        canonical_examples=[],
        anti_examples=[],
        procedural_modules=[],
        deterministic_rules={},
    )
    try:
        with patch("routers.persona_specs.verify_twin_ownership"), patch(
            "routers.persona_specs.ensure_twin_active"
        ), patch(
            "routers.persona_specs.bootstrap_persona_spec_from_user_data",
            return_value=generated,
        ), patch(
            "routers.persona_specs.create_persona_spec",
            return_value={"id": "ps-2", "version": "2.0.0", "status": "draft"},
        ):
            resp = client.post("/twins/twin-1/persona-specs/generate", json={})
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "draft"
            assert body["persona_spec"]["version"] == "2.0.0"
            assert body["generated_from"] == "twins.settings+owner_memory"
    finally:
        app.dependency_overrides = {}


def test_publish_persona_spec_endpoint():
    app.dependency_overrides[get_current_user] = _owner_user
    try:
        with patch("routers.persona_specs.verify_twin_ownership"), patch(
            "routers.persona_specs.ensure_twin_active"
        ), patch(
            "routers.persona_specs.publish_persona_spec",
            return_value={"id": "ps-3", "version": "1.0.0", "status": "active"},
        ):
            resp = client.post("/twins/twin-1/persona-specs/1.0.0/publish")
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "active"
            assert body["persona_spec"]["version"] == "1.0.0"
    finally:
        app.dependency_overrides = {}


def test_list_persona_prompt_variants_endpoint():
    app.dependency_overrides[get_current_user] = _owner_user
    try:
        with patch("routers.persona_specs.verify_twin_ownership"), patch(
            "routers.persona_specs.ensure_twin_active"
        ), patch(
            "routers.persona_specs.list_persona_prompt_variants",
            return_value=[{"variant_id": "baseline_v1", "status": "active"}],
        ), patch(
            "routers.persona_specs.get_active_persona_prompt_variant",
            return_value={"variant_id": "baseline_v1", "status": "active"},
        ):
            resp = client.get("/twins/twin-1/persona-prompt-variants")
            assert resp.status_code == 200
            body = resp.json()
            assert body["active_variant"]["variant_id"] == "baseline_v1"
            assert len(body["variants"]) == 1
    finally:
        app.dependency_overrides = {}


def test_activate_persona_prompt_variant_endpoint():
    app.dependency_overrides[get_current_user] = _owner_user
    try:
        with patch("routers.persona_specs.verify_twin_ownership"), patch(
            "routers.persona_specs.ensure_twin_active"
        ), patch(
            "routers.persona_specs.activate_persona_prompt_variant",
            return_value={"variant_id": "compact_v1", "status": "active"},
        ):
            resp = client.post("/twins/twin-1/persona-prompt-variants/compact_v1/activate")
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "active"
            assert body["variant"]["variant_id"] == "compact_v1"
    finally:
        app.dependency_overrides = {}


def test_run_persona_prompt_optimization_endpoint():
    app.dependency_overrides[get_current_user] = _owner_user
    try:
        with patch("routers.persona_specs.verify_twin_ownership"), patch(
            "routers.persona_specs.ensure_twin_active"
        ), patch(
            "routers.persona_specs.optimize_persona_prompts",
            return_value={
                "status": "completed",
                "best_variant": {"variant_id": "compact_v1"},
                "best_objective_score": 0.91,
                "ranking": [],
                "candidate_count": 1,
            },
        ):
            resp = client.post(
                "/twins/twin-1/persona-prompt-optimization/runs",
                json={"mode": "heuristic", "apply_best": True},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "completed"
            assert body["best_variant"]["variant_id"] == "compact_v1"
    finally:
        app.dependency_overrides = {}


def test_list_persona_feedback_learning_runs_endpoint():
    app.dependency_overrides[get_current_user] = _owner_user
    try:
        with patch("routers.persona_specs.verify_twin_ownership"), patch(
            "routers.persona_specs.ensure_twin_active"
        ), patch(
            "routers.persona_specs.list_feedback_learning_runs",
            return_value=[{"id": "run-1", "status": "completed"}],
        ):
            resp = client.get("/twins/twin-1/persona-feedback-learning/runs")
            assert resp.status_code == 200
            body = resp.json()
            assert len(body["runs"]) == 1
            assert body["runs"][0]["id"] == "run-1"
    finally:
        app.dependency_overrides = {}


def test_run_persona_feedback_learning_endpoint():
    app.dependency_overrides[get_current_user] = _owner_user
    try:
        with patch("routers.persona_specs.verify_twin_ownership"), patch(
            "routers.persona_specs.ensure_twin_active"
        ), patch(
            "routers.persona_specs.run_feedback_learning_cycle",
            return_value={
                "status": "completed",
                "run_id": "run-2",
                "modules_updated": 3,
                "publish_decision": "held",
            },
        ):
            resp = client.post(
                "/twins/twin-1/persona-feedback-learning/runs",
                json={"auto_publish": True, "run_regression_gate": True},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "completed"
            assert body["run_id"] == "run-2"
            assert body["modules_updated"] == 3
    finally:
        app.dependency_overrides = {}
