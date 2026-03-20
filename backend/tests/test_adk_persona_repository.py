from adk_core.repositories.persona_repository import PersonaRepository
from adk_core.repositories import persona_repository as persona_repository_module


def test_index_for_retrieval_uses_integrated_text_records(monkeypatch):
    captured = {}

    class FakeAdapter:
        def __init__(self, index):
            assert index == "fake-index"
            self.mode = "integrated"

        def upsert(self, *, vectors, namespace):
            captured["vectors"] = vectors
            captured["namespace"] = namespace
            return {"upserted_count": len(vectors)}

    monkeypatch.setattr(persona_repository_module, "get_pinecone_index", lambda: "fake-index")
    monkeypatch.setattr(persona_repository_module, "PineconeIndexAdapter", FakeAdapter)

    repository = PersonaRepository()
    repository._index_for_retrieval(
        twin_id="twin-1",
        artifact_id="artifact-1",
        artifact={
            "claims": [
                {"text": "Build from first principles.", "source_ids": ["src-claim"]},
            ],
            "quote_pack": [
                {"quote": "Ship with conviction.", "source_id": "src-quote"},
            ],
            "timeline": [
                {
                    "date_or_range": "2024",
                    "event": "Launched a major product.",
                    "source_ids": ["src-timeline"],
                }
            ],
            "retrieval_seeds": ["product strategy"],
        },
    )

    assert captured["namespace"] == "adk-persona-twin-1"
    assert [row["id"] for row in captured["vectors"]] == [
        "artifact-1-claim-1",
        "artifact-1-quote-1",
        "artifact-1-timeline-1",
        "artifact-1-seed-1",
    ]
    assert all("values" not in row for row in captured["vectors"])
    assert captured["vectors"][0]["metadata"]["doc_type"] == "claim"
    assert captured["vectors"][1]["metadata"]["doc_type"] == "quote"
    assert captured["vectors"][2]["metadata"]["doc_type"] == "timeline"
    assert captured["vectors"][3]["metadata"]["doc_type"] == "seed"


def test_index_for_retrieval_skips_non_integrated_mode(monkeypatch):
    called = {"upsert": False}

    class FakeAdapter:
        def __init__(self, index):
            del index
            self.mode = "vector"

        def upsert(self, *, vectors, namespace):
            del vectors, namespace
            called["upsert"] = True
            return {}

    monkeypatch.setattr(persona_repository_module, "get_pinecone_index", lambda: "fake-index")
    monkeypatch.setattr(persona_repository_module, "PineconeIndexAdapter", FakeAdapter)

    repository = PersonaRepository()
    repository._index_for_retrieval(
        twin_id="twin-1",
        artifact_id="artifact-1",
        artifact={"claims": [{"text": "Ignored in vector mode."}]},
    )

    assert called["upsert"] is False
