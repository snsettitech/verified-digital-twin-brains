from modules.retrieval import _process_general_matches


def test_process_general_matches_adds_page_fallback_metadata():
    rows = _process_general_matches(
        [
            {
                "score": 0.81,
                "rrf_score": 0.12,
                "metadata": {
                    "text": "Install step details.",
                    "source_id": "src-1",
                    "filename": "Manual.pdf",
                    "page_number": 3,
                },
            }
        ]
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["source_id"] == "src-1"
    assert row["section_title"] == "page_3"
    assert row["section_path"] == "Manual.pdf/page_3"
    assert row["page_number"] == 3
