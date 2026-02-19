"""
Retrieval Pipeline Test Suite

Comprehensive tests for the chat retrieval system.
Covers unit tests for components and integration tests for the full pipeline.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from typing import List, Dict, Any
from types import SimpleNamespace

# Test configuration
pytestmark = pytest.mark.asyncio


class TestNamespaceResolution:
    """Test namespace resolution functionality."""
    
    async def test_resolve_creator_id_returns_none_for_nonexistent_twin(self):
        """Should return None when twin doesn't exist."""
        from modules.delphi_namespace import resolve_creator_id_for_twin
        
        with patch('modules.delphi_namespace.supabase') as mock_supabase:
            mock_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
            
            result = resolve_creator_id_for_twin("nonexistent-twin", _bypass_cache=True)
            assert result is None
    
    async def test_resolve_creator_id_returns_creator_id(self):
        """Should return creator_id when present in twin record."""
        from modules.delphi_namespace import resolve_creator_id_for_twin, clear_creator_namespace_cache
        
        clear_creator_namespace_cache()
        
        with patch('modules.delphi_namespace.supabase') as mock_supabase:
            mock_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
                {"creator_id": "user.123", "tenant_id": "tenant_456"}
            ]
            
            result = resolve_creator_id_for_twin("test-twin", _bypass_cache=True)
            assert result == "user.123"
    
    async def test_resolve_creator_id_fallback_to_tenant(self):
        """Should fallback to tenant-derived ID when creator_id is null."""
        from modules.delphi_namespace import resolve_creator_id_for_twin, clear_creator_namespace_cache
        
        clear_creator_namespace_cache()
        
        with patch('modules.delphi_namespace.supabase') as mock_supabase:
            mock_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
                {"creator_id": None, "tenant_id": "tenant_789"}
            ]
            
            result = resolve_creator_id_for_twin("test-twin", _bypass_cache=True)
            assert result == "tenant_tenant_789"
    
    async def test_get_namespace_candidates_with_dual_read(self):
        """Should return both namespaces when dual-read is enabled."""
        from modules.delphi_namespace import get_namespace_candidates_for_twin
        
        with patch.dict('os.environ', {'DELPHI_DUAL_READ': 'true'}):
            with patch('modules.delphi_namespace.resolve_creator_id_for_twin', return_value="user.123"):
                result = get_namespace_candidates_for_twin("my-twin", include_legacy=True)
                
                assert len(result) == 2
                assert "creator_user.123_twin_my-twin" in result
                assert "my-twin" in result
    
    async def test_get_namespace_candidates_without_dual_read(self):
        """Should return only primary namespace when dual-read is disabled."""
        from modules.delphi_namespace import get_namespace_candidates_for_twin
        
        with patch.dict('os.environ', {'DELPHI_DUAL_READ': 'false'}):
            with patch('modules.delphi_namespace.resolve_creator_id_for_twin', return_value="user.123"):
                result = get_namespace_candidates_for_twin("my-twin", include_legacy=False)
                
                assert len(result) == 1
                assert result[0] == "creator_user.123_twin_my-twin"


class TestRetrievalPipeline:
    """Test the full retrieval pipeline."""
    
    async def test_retrieve_context_empty_query(self):
        """Should handle empty queries gracefully."""
        from modules.retrieval import retrieve_context
        
        with patch('modules.retrieval.get_embeddings_async', return_value=[]):
            result = await retrieve_context("", "test-twin")
            assert isinstance(result, list)
    
    async def test_retrieve_context_with_owner_memory_match(self):
        """Should return owner memory when match found."""
        from modules.retrieval import retrieve_context_with_verified_first
        
        mock_memory = {
            "id": "mem-123",
            "value": "Owner's important memory",
            "topic": "Important Topic"
        }
        
        with patch('modules.retrieval._match_owner_memory', return_value=mock_memory):
            with patch('modules.retrieval.get_default_group', side_effect=Exception("No group")):
                result = await retrieve_context_with_verified_first(
                    "test query", "test-twin", group_id=None
                )
                
                assert len(result) == 1
                assert result[0]["is_owner_memory"] is True
                assert result[0]["text"] == "Owner's important memory"
    
    async def test_retrieve_context_with_verified_qna_match(self):
        """Should return verified QnA when high-confidence match found."""
        from modules.retrieval import retrieve_context_with_verified_first
        
        mock_verified = {
            "id": "qna-456",
            "question": "What is the answer?",
            "answer": "The answer is 42",
            "similarity_score": 0.85,
            "citations": []
        }
        
        with patch('modules.retrieval._match_owner_memory', return_value=None):
            with patch('modules.retrieval.match_verified_qna', return_value=mock_verified):
                with patch('modules.retrieval.get_default_group', side_effect=Exception("No group")):
                    result = await retrieve_context_with_verified_first(
                        "test query", "test-twin", group_id=None
                    )
                    
                    assert len(result) == 1
                    assert result[0]["is_verified"] is True
                    assert result[0]["text"] == "The answer is 42"
    
    async def test_retrieve_context_falls_back_to_vectors(self):
        """Should fallback to vector search when no verified match."""
        from modules.retrieval import retrieve_context_with_verified_first
        
        with patch('modules.retrieval._match_owner_memory', return_value=None):
            with patch('modules.retrieval.match_verified_qna', return_value=None):
                with patch('modules.retrieval.retrieve_context_vectors', return_value=[
                    {"text": "Vector result 1", "score": 0.8, "source_id": "src-1"},
                    {"text": "Vector result 2", "score": 0.7, "source_id": "src-2"}
                ]):
                    with patch('modules.retrieval.get_default_group', side_effect=Exception("No group")):
                        result = await retrieve_context_with_verified_first(
                            "test query", "test-twin", group_id=None
                        )
                        
                        assert len(result) == 2
                        assert result[0]["text"] == "Vector result 1"

    async def test_match_owner_memory_accepts_proposed_when_auto_approve_enabled(self, monkeypatch):
        """Should accept proposed owner memories in auto-approve mode."""
        from modules import retrieval

        monkeypatch.setattr(retrieval, "AUTO_APPROVE_OWNER_MEMORY", True)
        monkeypatch.setattr(
            retrieval,
            "find_owner_memory_candidates",
            lambda **_kwargs: [
                {"id": "mem-1", "status": "proposed", "_score": 0.95, "confidence": 0.95}
            ],
        )

        with patch("modules.identity_gate.classify_query", return_value={"requires_owner": True}):
            result = retrieval._match_owner_memory("What is your stance on remote work?", "twin-1")

        assert result is not None
        assert result["id"] == "mem-1"

    async def test_match_owner_memory_rejects_proposed_when_auto_approve_disabled(self, monkeypatch):
        """Should reject proposed owner memories when auto-approve mode is off."""
        from modules import retrieval

        monkeypatch.setattr(retrieval, "AUTO_APPROVE_OWNER_MEMORY", False)
        monkeypatch.setattr(
            retrieval,
            "find_owner_memory_candidates",
            lambda **_kwargs: [
                {"id": "mem-1", "status": "proposed", "_score": 0.95, "confidence": 0.95}
            ],
        )

        with patch("modules.identity_gate.classify_query", return_value={"requires_owner": True}):
            result = retrieval._match_owner_memory("What is your stance on remote work?", "twin-1")

        assert result is None


class TestPineconeQueries:
    """Test Pinecone query execution."""
    
    async def test_execute_pinecone_queries_with_timeout(self):
        """Should handle timeout gracefully."""
        from modules.retrieval import _execute_pinecone_queries
        
        mock_index = Mock()
        mock_index.query = Mock(side_effect=asyncio.TimeoutError("Query timed out"))
        
        with patch('modules.retrieval.get_pinecone_index', return_value=mock_index):
            with patch('modules.retrieval.get_namespace_candidates_for_twin', return_value=["ns-1"]):
                result = await _execute_pinecone_queries(
                    [[0.1, 0.2, 0.3]], "test-twin", timeout=0.1
                )
                # Should return empty list on timeout
                assert result == []
    
    async def test_execute_pinecone_queries_merges_results(self):
        """Should merge results from multiple namespaces."""
        from modules.retrieval import _execute_pinecone_queries
        
        mock_response = Mock()
        mock_response.matches = [
            Mock(id="doc-1", score=0.9, metadata={"text": "Match 1"}),
            Mock(id="doc-2", score=0.8, metadata={"text": "Match 2"})
        ]
        
        mock_index = Mock()
        mock_index.query = Mock(return_value=mock_response)
        
        with patch('modules.retrieval.get_pinecone_index', return_value=mock_index):
            with patch('modules.retrieval.get_namespace_candidates_for_twin', return_value=["ns-1"]):
                result = await _execute_pinecone_queries(
                    [[0.1, 0.2, 0.3]], "test-twin"
                )
                
                assert len(result) > 0
                # First result is verified query, others are general
                assert "matches" in result[0]
                assert mock_index.query.call_count >= 2
                filters = [call.kwargs.get("filter") for call in mock_index.query.call_args_list]
                assert any(f == {"twin_id": {"$eq": "test-twin"}} for f in filters)
                assert any(
                    isinstance(f, dict)
                    and "$and" in f
                    and {"twin_id": {"$eq": "test-twin"}} in f.get("$and", [])
                    and {"is_verified": {"$eq": True}} in f.get("$and", [])
                    for f in filters
                )


class TestGroupFiltering:
    """Test group permission filtering."""
    
    async def test_filter_by_group_allows_verified_memory(self):
        """Should always allow verified memory regardless of group."""
        from modules.retrieval import _filter_by_group_permissions
        
        contexts = [
            {"text": "Verified answer", "source_id": "verified-1", "is_verified": True},
            {"text": "Regular doc", "source_id": "doc-1", "is_verified": False}
        ]
        
        with patch('modules.retrieval.supabase') as mock_supabase:
            # Only doc-1 is allowed
            mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
                {"content_id": "doc-1"}
            ]
            
            result = _filter_by_group_permissions(contexts, "group-123")
            
            assert len(result) == 2  # Both allowed (verified + permitted)
    
    async def test_filter_by_group_rejects_unauthorized(self):
        """Should reject contexts not in allowed group."""
        from modules.retrieval import _filter_by_group_permissions
        
        contexts = [
            {"text": "Doc 1", "source_id": "doc-1", "is_verified": False},
            {"text": "Doc 2", "source_id": "doc-2", "is_verified": False}
        ]
        
        with patch('modules.retrieval.supabase') as mock_supabase:
            # Only doc-1 is allowed
            mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
                {"content_id": "doc-1"}
            ]
            
            result = _filter_by_group_permissions(contexts, "group-123")
            
            assert len(result) == 1
            assert result[0]["source_id"] == "doc-1"

    async def test_filter_by_group_lenient_non_public_when_all_rejected(self, monkeypatch):
        """Should fallback for non-public groups when all contexts are rejected."""
        from modules import retrieval

        contexts = [
            {"text": "Doc 2", "source_id": "doc-2", "is_verified": False}
        ]

        class _Query:
            def __init__(self, table_name):
                self.table_name = table_name
            def select(self, *args, **kwargs):
                return self
            def eq(self, *args, **kwargs):
                return self
            def single(self):
                return self
            def execute(self):
                if self.table_name == "content_permissions":
                    return SimpleNamespace(data=[{"content_id": "doc-1"}])
                if self.table_name == "access_groups":
                    return SimpleNamespace(data={"is_public": False})
                return SimpleNamespace(data=[])

        class _Supabase:
            def table(self, name):
                return _Query(name)

        monkeypatch.setattr(retrieval, "supabase", _Supabase())
        monkeypatch.setattr(retrieval, "RETRIEVAL_LENIENT_NON_PUBLIC_GROUP_FILTER", True)

        result = retrieval._filter_by_group_permissions(contexts, "group-123")
        assert len(result) == 1
        assert result[0]["source_id"] == "doc-2"

    async def test_filter_by_group_keeps_public_group_strict_when_all_rejected(self, monkeypatch):
        """Should keep strict filtering for public groups."""
        from modules import retrieval

        contexts = [
            {"text": "Doc 2", "source_id": "doc-2", "is_verified": False}
        ]

        class _Query:
            def __init__(self, table_name):
                self.table_name = table_name
            def select(self, *args, **kwargs):
                return self
            def eq(self, *args, **kwargs):
                return self
            def single(self):
                return self
            def execute(self):
                if self.table_name == "content_permissions":
                    return SimpleNamespace(data=[{"content_id": "doc-1"}])
                if self.table_name == "access_groups":
                    return SimpleNamespace(data={"is_public": True})
                return SimpleNamespace(data=[])

        class _Supabase:
            def table(self, name):
                return _Query(name)

        monkeypatch.setattr(retrieval, "supabase", _Supabase())
        monkeypatch.setattr(retrieval, "RETRIEVAL_LENIENT_NON_PUBLIC_GROUP_FILTER", True)

        result = retrieval._filter_by_group_permissions(contexts, "group-123")
        assert result == []


class TestTwinScopedGuardrails:
    """Test strict per-twin source scoping."""

    async def test_sham_twin_chat_excludes_sai_doc_chunks(self, monkeypatch):
        from modules import retrieval

        sham_source = "11111111-1111-1111-1111-111111111111"
        sai_source = "22222222-2222-2222-2222-222222222222"
        contexts = [
            {
                "text": "Sham profile and usage guidance.",
                "source_id": sham_source,
                "doc_name": "Sham's Knowledge Base.pdf",
                "twin_id": "sham-twin",
                "is_verified": False,
            },
            {
                "text": "Sai recommendation and architecture note.",
                "source_id": sai_source,
                "doc_name": "Sai_twin.docx",
                "twin_id": "sai-twin",
                "is_verified": False,
            },
        ]

        monkeypatch.setattr(
            retrieval,
            "_fetch_source_ownership",
            lambda _ids: {
                sham_source: {"twin_id": "sham-twin", "filename": "Sham's Knowledge Base.pdf"},
                sai_source: {"twin_id": "sai-twin", "filename": "Sai_twin.docx"},
            },
        )
        audit_calls = []
        monkeypatch.setattr(
            retrieval,
            "_log_cross_twin_guardrail_audit",
            lambda twin_id, rows: audit_calls.append((twin_id, rows)),
        )

        filtered = retrieval._enforce_twin_source_scope(contexts, "sham-twin")

        assert len(filtered) == 1
        assert filtered[0]["source_id"] == sham_source
        assert "Sai_twin.docx" not in (filtered[0].get("doc_name") or "")
        assert audit_calls
        assert audit_calls[0][0] == "sham-twin"
        assert any(
            (row.get("doc_name") or "").lower().startswith("sai_twin.docx")
            for row in audit_calls[0][1]
        )

    async def test_sai_twin_chat_excludes_sham_pdf_chunks(self, monkeypatch):
        from modules import retrieval

        sham_source = "33333333-3333-3333-3333-333333333333"
        sai_source = "44444444-4444-4444-4444-444444444444"
        contexts = [
            {
                "text": "Sham onboarding workflow notes.",
                "source_id": sham_source,
                "doc_name": "Sham's Knowledge Base.pdf",
                "twin_id": "sham-twin",
                "is_verified": False,
            },
            {
                "text": "Sai identity and credibility details.",
                "source_id": sai_source,
                "doc_name": "Sai_twin.docx",
                "twin_id": "sai-twin",
                "is_verified": False,
            },
        ]

        monkeypatch.setattr(
            retrieval,
            "_fetch_source_ownership",
            lambda _ids: {
                sham_source: {"twin_id": "sham-twin", "filename": "Sham's Knowledge Base.pdf"},
                sai_source: {"twin_id": "sai-twin", "filename": "Sai_twin.docx"},
            },
        )
        audit_calls = []
        monkeypatch.setattr(
            retrieval,
            "_log_cross_twin_guardrail_audit",
            lambda twin_id, rows: audit_calls.append((twin_id, rows)),
        )

        filtered = retrieval._enforce_twin_source_scope(contexts, "sai-twin")

        assert len(filtered) == 1
        assert filtered[0]["source_id"] == sai_source
        assert "knowledge base.pdf" not in (filtered[0].get("doc_name") or "").lower()
        assert audit_calls
        assert audit_calls[0][0] == "sai-twin"
        assert any(
            "knowledge base.pdf" in (row.get("doc_name") or "").lower()
            for row in audit_calls[0][1]
        )


class TestAnchorRelevanceFiltering:
    """Test off-topic filtering for weak retrieval matches."""

    async def test_anchor_filter_drops_off_topic_contexts(self):
        from modules.retrieval import _apply_anchor_relevance_filter

        contexts = [
            {
                "text": "This chunk is about AI agents and workflows.",
                "score": 0.02,
                "vector_score": 0.02,
                "is_verified": False,
            },
            {
                "text": "Antler is a global early-stage VC firm backing founders.",
                "score": 0.03,
                "vector_score": 0.03,
                "is_verified": False,
            },
        ]

        filtered = _apply_anchor_relevance_filter(contexts, "do you know antler")
        assert len(filtered) == 1
        assert "Antler" in filtered[0]["text"]

    async def test_anchor_filter_keeps_strong_semantic_match_even_without_keyword(self):
        from modules.retrieval import _apply_anchor_relevance_filter

        contexts = [
            {
                "text": "Y Combinator supports founders at seed stage.",
                "score": 0.21,
                "vector_score": 0.91,
                "is_verified": False,
            }
        ]

        filtered = _apply_anchor_relevance_filter(contexts, "do you know antler")
        assert len(filtered) == 1

    async def test_anchor_filter_matches_plural_singular_variants(self):
        from modules.retrieval import _apply_anchor_relevance_filter

        contexts = [
            {
                "text": "We discussed building a specialist agent for social media ops.",
                "score": 0.03,
                "vector_score": 0.03,
                "is_verified": False,
            }
        ]
        filtered = _apply_anchor_relevance_filter(contexts, "what did I say about specialist agents?")
        assert len(filtered) == 1

    async def test_lexical_fusion_boosts_keyword_aligned_context(self, monkeypatch):
        from modules import retrieval

        monkeypatch.setattr(retrieval, "RETRIEVAL_LEXICAL_FUSION_ENABLED", True)
        monkeypatch.setattr(retrieval, "RETRIEVAL_LEXICAL_FUSION_ALPHA", 0.4)

        contexts = [
            {"text": "This discusses board meeting cadence.", "score": 0.80, "source_id": "s1"},
            {"text": "Incident response runbook for pager alerts.", "score": 0.74, "source_id": "s2"},
        ]

        fused = retrieval._apply_lexical_fusion("incident response approach", contexts)
        assert fused[0]["source_id"] == "s2"
        assert fused[0]["lexical_score"] > fused[1]["lexical_score"]


class TestEmbeddingGeneration:
    """Test embedding generation."""
    
    async def test_get_embeddings_async_batch(self):
        """Should generate embeddings for multiple texts."""
        from modules.embeddings import get_embeddings_async
        
        texts = ["Query 1", "Query 2", "Query 3"]
        
        with patch('modules.embeddings.get_embedding') as mock_get:
            mock_get.return_value = [0.1] * 3072  # Mock 3072-dim embedding
            
            # For batch, it calls get_embedding multiple times
            result = await get_embeddings_async(texts)
            
            assert len(result) == len(texts)
            assert all(len(emb) == 3072 for emb in result)


class TestHealthCheck:
    """Test retrieval health check functionality."""
    
    async def test_get_retrieval_health_status_healthy(self):
        """Should return healthy status when all components work."""
        from modules.retrieval import get_retrieval_health_status
        
        with patch('modules.retrieval.get_pinecone_index') as mock_pc:
            mock_stats = Mock()
            mock_stats.total_vector_count = 1000
            mock_stats.namespaces = {"ns-1": Mock(vector_count=500)}
            mock_pc.return_value.describe_index_stats.return_value = mock_stats
            
            with patch('modules.retrieval.get_embedding', return_value=[0.1] * 3072):
                with patch.dict('os.environ', {'DELPHI_DUAL_READ': 'true'}):
                    result = await get_retrieval_health_status()
                    
                    assert result["healthy"] is True
                    assert result["components"]["pinecone"]["connected"] is True
                    assert result["components"]["embeddings"]["working"] is True
    
    async def test_get_retrieval_health_status_unhealthy(self):
        """Should return unhealthy status when components fail."""
        from modules.retrieval import get_retrieval_health_status
        
        with patch('modules.retrieval.get_pinecone_index', side_effect=Exception("Connection failed")):
            result = await get_retrieval_health_status()
            
            assert result["healthy"] is False
            assert len(result["errors"]) > 0


class TestRRFMerge:
    """Test Reciprocal Rank Fusion merging."""
    
    async def test_rrf_merge_combines_results(self):
        """Should combine multiple result lists using RRF."""
        from modules.retrieval import rrf_merge
        
        results_list = [
            [
                {"id": "doc-1", "score": 0.9, "metadata": {"text": "A"}},
                {"id": "doc-2", "score": 0.8, "metadata": {"text": "B"}}
            ],
            [
                {"id": "doc-2", "score": 0.85, "metadata": {"text": "B"}},
                {"id": "doc-3", "score": 0.7, "metadata": {"text": "C"}}
            ]
        ]
        
        result = rrf_merge(results_list)
        
        # Should have 3 unique documents
        assert len(result) == 3
        # doc-2 appears in both lists, should have higher RRF score
        doc2 = next(r for r in result if r["id"] == "doc-2")
        assert "rrf_score" in doc2

    async def test_rrf_merge_respects_query_weights(self):
        """Higher-weight query lists should dominate fused ranking."""
        from modules.retrieval import rrf_merge

        results_list = [
            [
                {"id": "doc-original", "score": 0.81, "metadata": {"text": "Original query match"}},
                {"id": "doc-shared", "score": 0.79, "metadata": {"text": "Shared"}},
            ],
            [
                {"id": "doc-hyde", "score": 0.99, "metadata": {"text": "HyDE-only"}},
                {"id": "doc-shared", "score": 0.77, "metadata": {"text": "Shared"}},
            ],
        ]

        # Original query should be weighted more than auxiliary query.
        result = rrf_merge(results_list, weights=[1.0, 0.35])
        assert result[0]["id"] in {"doc-original", "doc-shared"}
        assert result[0]["id"] != "doc-hyde"


class TestQueryPlanning:
    """Test query-plan generation and augmentation gates."""

    async def test_build_search_query_plan_keeps_original_first(self):
        from modules.retrieval import _build_search_query_plan

        plan = _build_search_query_plan(
            query="Should we use containers or serverless for our MVP?",
            expanded_queries=[
                "MVP deployment architecture containers serverless tradeoff",
                "startup infra decision containers vs serverless",
            ],
            hyde_answer="For MVPs, teams often start with managed containers for predictable debugging.",
            max_queries=4,
        )

        assert len(plan) >= 1
        assert plan[0]["kind"] == "original"
        assert plan[0]["weight"] >= 1.0
        assert any(item["kind"] == "expansion" for item in plan)

    async def test_entity_lookup_query_skips_hyde(self):
        from modules.retrieval import _build_search_query_plan

        plan = _build_search_query_plan(
            query="Do you know Antler?",
            expanded_queries=["What is Antler VC firm"],
            hyde_answer="Antler is a global early-stage VC and startup generator.",
            max_queries=4,
        )

        assert all(item["kind"] != "hyde" for item in plan)

    async def test_deterministic_expansions_cover_comparison_queries(self):
        from modules.retrieval import _deterministic_query_expansions

        expansions = _deterministic_query_expansions(
            "Should we use containers or serverless for our MVP?"
        )

        joined = " | ".join(expansions).lower()
        assert "vs" in joined or "tradeoffs" in joined
        assert len(expansions) >= 1

    async def test_deterministic_expansions_cover_entity_probe_queries(self):
        from modules.retrieval import _deterministic_query_expansions

        expansions = _deterministic_query_expansions("Do you know Antler?")
        joined = " | ".join(expansions).lower()
        assert "what is antler" in joined or "antler overview" in joined


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    async def test_retrieve_context_handles_exception(self):
        """Should handle exceptions gracefully and return empty list."""
        from modules.retrieval import retrieve_context_with_verified_first
        
        with patch('modules.retrieval._match_owner_memory', side_effect=Exception("DB error")):
            with patch('modules.retrieval.get_default_group', side_effect=Exception("No group")):
                # Should not raise, should return empty list
                result = await retrieve_context_with_verified_first("query", "twin")
                assert isinstance(result, list)
    
    async def test_empty_namespace_list(self):
        """Should handle empty namespace list."""
        from modules.retrieval import _execute_pinecone_queries
        
        with patch('modules.retrieval.get_namespace_candidates_for_twin', return_value=[]):
            result = await _execute_pinecone_queries([[0.1, 0.2]], "twin")
            assert result == []
    
    async def test_all_namespaces_fail(self):
        """Should handle when all namespace queries fail."""
        from modules.retrieval import _execute_pinecone_queries
        
        mock_index = Mock()
        mock_index.query = Mock(side_effect=Exception("Query failed"))
        
        with patch('modules.retrieval.get_pinecone_index', return_value=mock_index):
            with patch('modules.retrieval.get_namespace_candidates_for_twin', return_value=["ns-1", "ns-2"]):
                result = await _execute_pinecone_queries([[0.1, 0.2]], "twin")

                # Fail-fast behavior: if no namespace succeeds, return [].
                assert result == []


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
