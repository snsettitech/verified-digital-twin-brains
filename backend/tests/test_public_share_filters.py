from routers.chat import (
    _filter_citations_to_allowed_sources,
    _filter_contexts_to_allowed_sources,
    _filter_public_owner_memory_candidates,
)


def test_filter_public_owner_memory_candidates_respects_identity_and_policy_sets():
    rows = [
        {"id": "m1", "topic_normalized": "bio", "memory_type": "belief", "value": "Founder bio"},
        {"id": "m2", "topic_normalized": "extension_policy", "memory_type": "stance", "value": "No late extensions"},
        {"id": "m3", "topic_normalized": "private_topic", "memory_type": "belief", "value": "Private"},
    ]

    filtered = _filter_public_owner_memory_candidates(
        rows,
        published_identity_topics={"bio"},
        published_policy_topics={"extension_policy"},
    )

    assert [row["id"] for row in filtered] == ["m1", "m2"]


def test_filter_contexts_to_allowed_sources_discards_out_of_scope_rows():
    contexts = [
        {"source_id": "allowed-1", "text": "Allowed evidence"},
        {"source_id": "blocked-1", "text": "Blocked evidence"},
        {"source_id": "allowed-2", "text": "Allowed evidence 2"},
    ]

    filtered, removed = _filter_contexts_to_allowed_sources(contexts, {"allowed-1", "allowed-2"})

    assert removed == 1
    assert [row["source_id"] for row in filtered] == ["allowed-1", "allowed-2"]


def test_filter_citations_to_allowed_sources_keeps_only_allowlisted_ids():
    citations = ["allowed-1", "blocked-1", "allowed-2", ""]

    filtered = _filter_citations_to_allowed_sources(citations, {"allowed-1", "allowed-2"})

    assert filtered == ["allowed-1", "allowed-2"]
