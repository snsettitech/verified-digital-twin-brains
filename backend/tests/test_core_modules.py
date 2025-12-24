# backend/tests/test_core_modules.py
"""Unit tests for core feature-base modules.

Tests cover:
1. host_engine: get_next_slot, process_turn
2. scribe_engine: extract_structured_output, score_confidence, detect_contradictions
3. artifact_pipeline: extract_text_from_file, process_artifact
4. ontology_loader: load_ontology, register_ontology
5. registry_loader: load_registry, get_specialization_manifest
"""
import pytest
import tempfile
import os
from pathlib import Path


# ---------------------------------------------------------------------------
# Tests: host_engine
# ---------------------------------------------------------------------------

class TestHostEngine:
    """Tests for host_engine.py"""

    def test_get_next_slot_returns_highest_priority_unfilled(self):
        from modules._core.host_engine import get_next_slot

        slot_priority = ["thesis", "rubric", "moat"]
        conversation_state = {}

        next_slot = get_next_slot(conversation_state, slot_priority)
        assert next_slot == "thesis"

    def test_get_next_slot_skips_filled(self):
        from modules._core.host_engine import get_next_slot

        slot_priority = ["thesis", "rubric", "moat"]
        conversation_state = {"thesis": "AI-first startups"}

        next_slot = get_next_slot(conversation_state, slot_priority)
        assert next_slot == "rubric"

    def test_get_next_slot_returns_empty_when_all_filled(self):
        from modules._core.host_engine import get_next_slot

        slot_priority = ["thesis"]
        conversation_state = {"thesis": "AI-first startups"}

        next_slot = get_next_slot(conversation_state, slot_priority)
        assert next_slot == ""

    def test_process_turn_updates_state(self):
        from modules._core.host_engine import process_turn

        state = {}
        user_input = "Our thesis is AI-first startups."
        current_slot = "thesis"

        new_state = process_turn(state, user_input, current_slot)
        assert new_state["thesis"] == user_input


# ---------------------------------------------------------------------------
# Tests: scribe_engine
# ---------------------------------------------------------------------------

class TestScribeEngine:
    """Tests for scribe_engine.py"""

    def test_extract_structured_output_returns_dict(self):
        from modules._core.scribe_engine import extract_structured_output

        text = "Our investment thesis focuses on AI."
        schema = {}
        result = extract_structured_output(text, schema)

        assert isinstance(result, dict)
        assert "node_updates" in result
        assert "edge_updates" in result

    def test_score_confidence_returns_dict(self):
        from modules._core.scribe_engine import score_confidence

        extracted = {
            "node_updates": [{"label": "thesis", "confidence": 0.8}],
            "edge_updates": [],
        }
        score = score_confidence(extracted)

        assert isinstance(score, dict)

    def test_detect_contradictions_finds_conflict(self):
        from modules._core.scribe_engine import detect_contradictions

        node_updates = [
            {"node_type": "check_size", "value": "$5M"},
            {"node_type": "check_size", "value": "$1M"},  # Conflicting value
        ]

        contradictions = detect_contradictions(node_updates)
        assert isinstance(contradictions, list)
        assert len(contradictions) > 0


# ---------------------------------------------------------------------------
# Tests: artifact_pipeline
# ---------------------------------------------------------------------------

class TestArtifactPipeline:
    """Tests for artifact_pipeline.py"""

    def test_extract_text_from_txt_file(self):
        from modules._core.artifact_pipeline import extract_text_from_file

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("This is test content.")
            temp_path = f.name

        try:
            text = extract_text_from_file(temp_path)
            assert "This is test content" in text
        finally:
            os.unlink(temp_path)

    def test_extract_text_from_md_file(self):
        from modules._core.artifact_pipeline import extract_text_from_file

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Heading\n\nParagraph content.")
            temp_path = f.name

        try:
            text = extract_text_from_file(temp_path)
            assert "Heading" in text
            assert "Paragraph" in text
        finally:
            os.unlink(temp_path)

    def test_extract_text_unsupported_raises(self):
        from modules._core.artifact_pipeline import extract_text_from_file

        with tempfile.NamedTemporaryFile(mode="w", suffix=".xyz", delete=False) as f:
            f.write("content")
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Unsupported file type"):
                extract_text_from_file(temp_path)
        finally:
            os.unlink(temp_path)

    def test_process_artifact_returns_structured_output(self):
        from modules._core.artifact_pipeline import process_artifact

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Investment thesis: AI-first B2B SaaS.")
            temp_path = f.name

        try:
            result = process_artifact(temp_path, {})
            assert "node_updates" in result
            assert "confidence" in result
        finally:
            os.unlink(temp_path)


# ---------------------------------------------------------------------------
# Tests: ontology_loader
# ---------------------------------------------------------------------------

class TestOntologyLoader:
    """Tests for ontology_loader.py"""

    def test_load_ontology_parses_json(self):
        from modules._core.ontology_loader import load_ontology

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"nodes": [], "edges": [], "allowed_edge_types": ["belongs_to"]}')
            temp_path = f.name

        try:
            ontology = load_ontology(temp_path)
            assert "nodes" in ontology
            assert "allowed_edge_types" in ontology
        finally:
            os.unlink(temp_path)

    def test_load_ontology_validates_edge_types(self):
        from modules._core.ontology_loader import load_ontology

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"nodes": [], "edges": [], "allowed_edge_types": ["belongs_to", "related_to"]}')
            temp_path = f.name

        try:
            ontology = load_ontology(temp_path)
            assert "belongs_to" in ontology["allowed_edge_types"]
        finally:
            os.unlink(temp_path)


# ---------------------------------------------------------------------------
# Tests: registry_loader
# ---------------------------------------------------------------------------

class TestRegistryLoader:
    """Tests for registry_loader.py"""

    def test_load_registry_returns_dict(self):
        from modules._core.registry_loader import load_registry

        registry = load_registry()
        assert isinstance(registry, dict)
        assert "specializations" in registry

    def test_get_specialization_manifest_returns_vc(self):
        from modules._core.registry_loader import get_specialization_manifest

        manifest = get_specialization_manifest("vc")
        assert manifest["id"] == "vc"
        assert "feature_flags" in manifest

    def test_get_specialization_manifest_raises_for_unknown(self):
        from modules._core.registry_loader import get_specialization_manifest

        with pytest.raises(KeyError, match="not found in registry"):
            get_specialization_manifest("nonexistent")
