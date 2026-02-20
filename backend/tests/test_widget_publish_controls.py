"""
Test widget enforces same publish controls as public-share endpoint.
PR6-A: Widget safety parity.
"""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestWidgetPublishControls:
    """Verify widget applies publish controls identically to public-share."""
    
    def test_filter_public_owner_memory_candidates_basic(self):
        """
        Test _filter_public_owner_memory_candidates filters correctly.
        """
        from routers.chat import _filter_public_owner_memory_candidates
        
        # Test data: mix of published and unpublished memories
        candidates = [
            {"id": "mem-1", "topic_normalized": "published-topic", "memory_type": "belief", "value": "visible"},
            {"id": "mem-2", "topic_normalized": "private-topic", "memory_type": "stance", "value": "hidden"},
            {"id": "mem-3", "topic_normalized": "published-policy", "memory_type": "lens", "value": "visible"},
            {"id": "mem-4", "topic_normalized": "another-private", "memory_type": "preference", "value": "hidden"},
        ]
        
        published_identity_topics = {"published-topic"}
        published_policy_topics = {"published-policy"}
        
        result = _filter_public_owner_memory_candidates(
            candidates,
            published_identity_topics=published_identity_topics,
            published_policy_topics=published_policy_topics,
        )
        
        # Should only include mem-1 (published identity) and mem-3 (published policy)
        result_ids = {m["id"] for m in result}
        assert "mem-1" in result_ids, "Published identity topic should be visible"
        assert "mem-3" in result_ids, "Published policy topic should be visible"
        assert "mem-2" not in result_ids, "Private stance should be filtered"
        assert "mem-4" not in result_ids, "Private preference should be filtered"
    
    def test_filter_public_owner_memory_candidates_empty_published(self):
        """
        When nothing is published, all memories should be filtered out.
        """
        from routers.chat import _filter_public_owner_memory_candidates
        
        candidates = [
            {"id": "mem-1", "topic_normalized": "topic-1", "memory_type": "belief", "value": "value"},
        ]
        
        result = _filter_public_owner_memory_candidates(
            candidates,
            published_identity_topics=set(),  # Nothing published
            published_policy_topics=set(),
        )
        
        assert result == [], "Should return empty list when nothing published"
    
    def test_filter_public_owner_memory_candidates_empty_candidates(self):
        """
        Empty candidates should return empty list.
        """
        from routers.chat import _filter_public_owner_memory_candidates
        
        result = _filter_public_owner_memory_candidates(
            [],
            published_identity_topics={"topic-1"},
            published_policy_topics={"policy-1"},
        )
        
        assert result == [], "Should return empty list for empty input"
    
    def test_filter_public_owner_memory_candidates_policy_types(self):
        """
        Policy types (stance, lens, tone_rule) use published_policy_topics.
        Other types use published_identity_topics.
        """
        from routers.chat import _filter_public_owner_memory_candidates
        
        candidates = [
            {"id": "mem-1", "topic_normalized": "ethics", "memory_type": "stance", "value": "visible"},
            {"id": "mem-2", "topic_normalized": "ethics", "memory_type": "belief", "value": "hidden"},
            {"id": "mem-3", "topic_normalized": "style", "memory_type": "tone_rule", "value": "visible"},
            {"id": "mem-4", "topic_normalized": "framework", "memory_type": "lens", "value": "visible"},
        ]
        
        # Only publish policy topics, not identity topics
        published_identity_topics = set()
        published_policy_topics = {"ethics", "style", "framework"}
        
        result = _filter_public_owner_memory_candidates(
            candidates,
            published_identity_topics=published_identity_topics,
            published_policy_topics=published_policy_topics,
        )
        
        result_ids = {m["id"] for m in result}
        # Stance, lens, tone_rule are policy types - should be visible
        assert "mem-1" in result_ids, "Stance should use policy topics"
        assert "mem-3" in result_ids, "Tone_rule should use policy topics"
        assert "mem-4" in result_ids, "Lens should use policy topics"
        # Belief is NOT a policy type - should be hidden (no identity topics published)
        assert "mem-2" not in result_ids, "Belief should use identity topics"
    
    def test_filter_citations_to_allowed_sources(self):
        """
        Test _filter_citations_to_allowed_sources filters correctly.
        """
        from routers.chat import _filter_citations_to_allowed_sources
        
        citations = ["source-1", "source-2", "source-3", "source-4"]
        allowed = {"source-1", "source-3"}
        
        result = _filter_citations_to_allowed_sources(citations, allowed)
        
        assert "source-1" in result
        assert "source-3" in result
        assert "source-2" not in result
        assert "source-4" not in result
    
    def test_filter_citations_empty_allowed(self):
        """
        When no sources are published, all citations should be filtered.
        """
        from routers.chat import _filter_citations_to_allowed_sources
        
        citations = ["source-1", "source-2"]
        result = _filter_citations_to_allowed_sources(citations, set())
        
        assert result == [], "Should return empty list when no sources allowed"
    
    def test_filter_contexts_to_allowed_sources(self):
        """
        Test _filter_contexts_to_allowed_sources filters correctly and counts removed.
        """
        from routers.chat import _filter_contexts_to_allowed_sources
        
        contexts = [
            {"source_id": "source-1", "text": "published content"},
            {"source_id": "source-2", "text": "private content"},
            {"source_id": "source-3", "text": "published content 2"},
            {"source_id": "source-4", "text": "private content 2"},
        ]
        allowed = {"source-1", "source-3"}
        
        filtered, removed = _filter_contexts_to_allowed_sources(contexts, allowed)
        
        assert len(filtered) == 2
        assert removed == 2
        source_ids = {c["source_id"] for c in filtered}
        assert "source-1" in source_ids
        assert "source-3" in source_ids
    
    def test_filter_contexts_empty_allowed(self):
        """
        When no sources are published, all contexts should be filtered.
        """
        from routers.chat import _filter_contexts_to_allowed_sources
        
        contexts = [
            {"source_id": "source-1", "text": "content"},
            {"source_id": "source-2", "text": "content 2"},
        ]
        
        filtered, removed = _filter_contexts_to_allowed_sources(contexts, set())
        
        assert filtered == []
        assert removed == 2
    
    def test_load_public_publish_controls_returns_defaults_on_error(self):
        """
        Test _load_public_publish_controls returns empty sets when DB fails.
        """
        from routers.chat import _load_public_publish_controls
        
        # This will fail because we don't have a real DB connection
        # But it should return the default empty controls, not crash
        result = _load_public_publish_controls("nonexistent-twin")
        
        assert "published_identity_topics" in result
        assert "published_policy_topics" in result
        assert "published_source_ids" in result
        assert isinstance(result["published_identity_topics"], set)


class TestWidgetCodeChanges:
    """
    Verify the PR6-A code changes are in place by inspecting the source.
    """
    
    def test_widget_loads_publish_controls(self):
        """
        Verify chat_widget function loads publish controls.
        """
        import inspect
        from routers.chat import chat_widget
        
        source = inspect.getsource(chat_widget)
        
        # Should call _load_public_publish_controls
        assert "_load_public_publish_controls" in source, "Widget should load publish controls"
        assert "published_identity_topics" in source, "Widget should extract identity topics"
        assert "published_policy_topics" in source, "Widget should extract policy topics"
        assert "published_source_ids" in source, "Widget should extract source ids"
    
    def test_widget_filters_owner_memory(self):
        """
        Verify chat_widget function filters owner memories.
        """
        import inspect
        from routers.chat import chat_widget
        
        source = inspect.getsource(chat_widget)
        
        # Should call _filter_public_owner_memory_candidates
        assert "_filter_public_owner_memory_candidates" in source, "Widget should filter memories"
        assert "published_identity_topics=published_identity_topics" in source
        assert "published_policy_topics=published_policy_topics" in source
    
    def test_widget_filters_citations_and_contexts(self):
        """
        Verify widget_stream_generator filters citations and contexts.
        """
        import inspect
        from routers.chat import chat_widget
        
        source = inspect.getsource(chat_widget)
        
        # Should call filter functions in the generator
        assert "_filter_contexts_to_allowed_sources" in source, "Widget should filter contexts"
        assert "_filter_citations_to_allowed_sources" in source, "Widget should filter citations"
        assert "published_source_ids" in source
    
    def test_widget_trace_includes_publish_counts(self):
        """
        Verify widget includes publish control counts in context_trace.
        """
        import inspect
        from routers.chat import chat_widget
        
        source = inspect.getsource(chat_widget)
        
        assert "published_identity_topics_count" in source
        assert "published_policy_topics_count" in source
        assert "published_source_ids_count" in source


class TestParityWithPublicShare:
    """
    Verify widget and public-share use the same filtering logic.
    """
    
    def test_both_use_same_filter_functions(self):
        """
        Both endpoints should use the same filter functions.
        """
        import inspect
        from routers.chat import chat_widget, public_chat_endpoint
        
        widget_source = inspect.getsource(chat_widget)
        public_source = inspect.getsource(public_chat_endpoint)
        
        # Both should use the same key functions
        key_functions = [
            "_load_public_publish_controls",
            "_filter_public_owner_memory_candidates",
            "_filter_contexts_to_allowed_sources",
            "_filter_citations_to_allowed_sources",
        ]
        
        for func in key_functions:
            assert func in widget_source, f"Widget should use {func}"
            assert func in public_source, f"Public-share should use {func}"
    
    def test_both_emit_violation_metrics(self):
        """
        Both endpoints should emit public_scope_violation metrics.
        """
        import inspect
        from routers.chat import chat_widget, public_chat_endpoint
        
        widget_source = inspect.getsource(chat_widget)
        public_source = inspect.getsource(public_chat_endpoint)
        
        assert "public_scope_violation" in widget_source, "Widget should track violations"
        assert "public_scope_removed_context_count" in widget_source
        assert "public_scope_violation" in public_source, "Public-share should track violations"
