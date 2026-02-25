from fastapi.testclient import TestClient

from main import app
from modules.auth_guard import require_tenant
from routers.deep_research import get_name_deep_research_service


class _FakeService:
    async def create_run(self, **kwargs):
        return {
            "id": "run-123",
            "status": "created",
            "created_at": "2026-02-25T00:00:00+00:00",
            "run_started_at": "2026-02-25T00:00:00+00:00",
        }

    async def get_run(self, *, run_id: str, tenant_id: str):
        if run_id != "run-123":
            return None
        return {
            "id": run_id,
            "status": "completed",
            "input_name": "Ada Lovelace",
            "input_location": None,
            "input_company": None,
            "input_website": None,
            "queries_used": ["Ada Lovelace biography"],
            "urls_considered": 3,
            "urls_crawled": 2,
            "urls_blocked": 1,
            "sources_used_in_final": 2,
            "words_extracted": 900,
            "selected_model": "o3",
            "error_message": None,
            "created_at": "2026-02-25T00:00:00+00:00",
            "updated_at": "2026-02-25T00:01:00+00:00",
            "run_started_at": "2026-02-25T00:00:00+00:00",
            "run_completed_at": "2026-02-25T00:01:00+00:00",
        }

    async def get_result(self, *, run_id: str, tenant_id: str):
        if run_id != "run-123":
            return None
        return {
            "run_id": "run-123",
            "input": {
                "name": "Ada Lovelace",
                "hints": {"location": None, "company": None, "website": None},
            },
            "claimed_identity": {
                "canonical_name": "Ada Lovelace",
                "is_match_confidence": 0.9,
                "disambiguation_notes": ["single profile"],
                "possible_duplicates": [],
            },
            "bio": {"short": "Ada [src-1]", "medium": "Ada [src-1]", "long": "Ada [src-1]"},
            "profile_summary": {
                "what_they_do": ["Math [src-1]"],
                "expertise_topics": [{"topic": "math", "confidence": 0.9, "evidence_count": 1}],
                "organizations": [],
                "locations": [],
                "public_roles": [],
            },
            "timeline": [{"date_or_range": "1843", "event": "notes", "confidence": 0.8, "citations": ["src-1"]}],
            "claims": [
                {
                    "claim_id": "claim-1",
                    "text": "notes",
                    "claim_type": "project",
                    "status": "verified",
                    "confidence": 0.8,
                    "citations": ["src-1"],
                    "notes": "",
                }
            ],
            "known_unknowns": [{"question": "q", "why_missing": "w"}],
            "suggested_followup_questions": ["f"],
            "crawl_stats": {
                "queries_used": ["Ada Lovelace biography"],
                "urls_considered": 3,
                "urls_crawled": 2,
                "urls_blocked": 1,
                "sources_used_in_final": 1,
                "words_extracted": 900,
                "run_started_at": "2026-02-25T00:00:00+00:00",
                "run_completed_at": "2026-02-25T00:01:00+00:00",
            },
            "quality": {
                "overall_confidence": 0.8,
                "freshness_score": 0.4,
                "coverage_score": 0.5,
                "hallucination_risk": "low",
                "warnings": [],
            },
            "sources": [
                {
                    "source_id": "src-1",
                    "url": "https://example.com",
                    "title": "Ada",
                    "source_type": "profile",
                    "published_at": None,
                    "retrieved_at": "2026-02-25T00:00:30+00:00",
                    "content_quality": "full",
                    "identity_match_confidence": 0.9,
                    "used_in_final": True,
                }
            ],
        }


def _override_user():
    return {
        "user_id": "user-1",
        "tenant_id": "tenant-1",
        "email": "test@example.com",
    }


def test_name_deep_research_routes_contract(monkeypatch):
    monkeypatch.setattr("routers.deep_research.is_name_only_deep_research_enabled", lambda: True)

    app.dependency_overrides[require_tenant] = _override_user
    app.dependency_overrides[get_name_deep_research_service] = lambda: _FakeService()
    client = TestClient(app)

    create = client.post(
        "/deep-research/runs",
        json={"name": "Ada Lovelace", "hints": {"location": None, "company": None, "website": None}},
    )
    assert create.status_code == 200
    payload = create.json()
    assert payload["run_id"] == "run-123"

    get_status = client.get("/deep-research/runs/run-123")
    assert get_status.status_code == 200
    status_payload = get_status.json()
    assert status_payload["status"] == "completed"
    assert "crawl_stats" in status_payload

    get_result = client.get("/deep-research/runs/run-123/result.json")
    assert get_result.status_code == 200
    result_payload = get_result.json()
    assert result_payload["run_id"] == "run-123"
    assert "sources" in result_payload

    app.dependency_overrides.clear()


def test_name_deep_research_feature_flag_off(monkeypatch):
    monkeypatch.setattr("routers.deep_research.is_name_only_deep_research_enabled", lambda: False)
    app.dependency_overrides[require_tenant] = _override_user
    app.dependency_overrides[get_name_deep_research_service] = lambda: _FakeService()
    client = TestClient(app)

    response = client.post(
        "/deep-research/runs",
        json={"name": "Ada Lovelace", "hints": {"location": None, "company": None, "website": None}},
    )
    assert response.status_code == 503
    app.dependency_overrides.clear()
