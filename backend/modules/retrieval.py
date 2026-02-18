import os
import asyncio
import time
import logging
import json
import re
from typing import List, Dict, Any, Optional, Set, Tuple
from contextlib import contextmanager
from modules.clients import get_openai_client, get_pinecone_index, get_cohere_client
from modules.langfuse_sdk import is_enabled as is_langfuse_enabled, langfuse_context, observe
from modules.verified_qna import match_verified_qna
from modules.owner_memory_store import find_owner_memory_candidates
from modules.observability import supabase
from modules.access_groups import get_default_group
from modules.delphi_namespace import (
    build_creator_namespace,
    get_namespace_candidates_for_twin,
    get_primary_namespace_for_twin,
    resolve_creator_id_for_twin,
)

# Embedding generation moved to modules.embeddings
from modules.embeddings import get_embedding, get_embeddings_async

# PHASE 4: Structured logging for observability
logger = logging.getLogger(__name__)
_langfuse_available = is_langfuse_enabled()


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


# Retrieval timing budgets (env-overridable) keep chat responsive under load.
RETRIEVAL_QUERY_PREP_TIMEOUT = _float_env("RETRIEVAL_QUERY_PREP_TIMEOUT_SECONDS", 6.0)
RETRIEVAL_EMBEDDING_TIMEOUT = _float_env("RETRIEVAL_EMBEDDING_TIMEOUT_SECONDS", 10.0)
RETRIEVAL_VECTOR_TIMEOUT = _float_env("RETRIEVAL_VECTOR_TIMEOUT_SECONDS", 20.0)
RETRIEVAL_PER_NAMESPACE_TIMEOUT = _float_env("RETRIEVAL_PER_NAMESPACE_TIMEOUT_SECONDS", 8.0)
RETRIEVAL_INDEX_INIT_TIMEOUT = _float_env("RETRIEVAL_INDEX_INIT_TIMEOUT_SECONDS", 3.0)
# Query augmentation is enabled by default for higher recall. Keep this bounded.
RETRIEVAL_MAX_SEARCH_QUERIES = max(1, _int_env("RETRIEVAL_MAX_SEARCH_QUERIES", 4))
RETRIEVAL_QUERY_EXPANSION_ENABLED = (
    os.getenv("RETRIEVAL_QUERY_EXPANSION_ENABLED", "true").lower() == "true"
)
RETRIEVAL_HYDE_ENABLED = os.getenv("RETRIEVAL_HYDE_ENABLED", "true").lower() == "true"
RETRIEVAL_HYDE_MIN_ANCHORS = max(2, _int_env("RETRIEVAL_HYDE_MIN_ANCHORS", 3))
RETRIEVAL_TOP_K_VERIFIED = max(1, _int_env("RETRIEVAL_TOP_K_VERIFIED", 3))
RETRIEVAL_TOP_K_GENERAL = max(4, _int_env("RETRIEVAL_TOP_K_GENERAL", 8))
RETRIEVAL_PRIMARY_RETRY_ENABLED = os.getenv("RETRIEVAL_PRIMARY_RETRY_ENABLED", "false").lower() == "true"
RETRIEVAL_STRONG_VECTOR_FLOOR = _float_env("RETRIEVAL_STRONG_VECTOR_FLOOR", 0.70)
RETRIEVAL_ANCHOR_MIN_TOKEN_LEN = max(3, _int_env("RETRIEVAL_ANCHOR_MIN_TOKEN_LEN", 4))
RETRIEVAL_ANCHOR_FALLBACK_MAX = max(2, _int_env("RETRIEVAL_ANCHOR_FALLBACK_MAX", 4))
RETRIEVAL_MIN_ACCEPTED_SCORE = _float_env("RETRIEVAL_MIN_ACCEPTED_SCORE", 0.0)
RETRIEVAL_OWNER_MEMORY_MATCH_MIN_SCORE = _float_env("RETRIEVAL_OWNER_MEMORY_MATCH_MIN_SCORE", 0.68)
RETRIEVAL_OWNER_MEMORY_MATCH_MIN_CONFIDENCE = _float_env("RETRIEVAL_OWNER_MEMORY_MATCH_MIN_CONFIDENCE", 0.70)
RETRIEVAL_LENIENT_NON_PUBLIC_GROUP_FILTER = (
    os.getenv("RETRIEVAL_LENIENT_NON_PUBLIC_GROUP_FILTER", "true").lower() == "true"
)
AUTO_APPROVE_OWNER_MEMORY = os.getenv("AUTO_APPROVE_OWNER_MEMORY", "true").lower() == "true"
RETRIEVAL_LEXICAL_FUSION_ENABLED = (
    os.getenv("RETRIEVAL_LEXICAL_FUSION_ENABLED", "true").lower() == "true"
)
RETRIEVAL_LEXICAL_FUSION_ALPHA = min(
    max(_float_env("RETRIEVAL_LEXICAL_FUSION_ALPHA", 0.22), 0.0),
    1.0,
)

_QUERY_STOPWORDS: Set[str] = {
    "a", "an", "and", "are", "as", "ask", "at", "be", "by", "can", "do", "for",
    "from", "have", "hello", "help", "hi", "how", "i", "in", "is", "it", "know",
    "me", "my", "of", "on", "or", "please", "tell", "that", "the", "this", "to",
    "want", "what", "when", "where", "who", "why", "with", "yes", "you", "your",
    "about",
}


def _token_variants(token: str) -> Set[str]:
    t = (token or "").strip().lower()
    if not t:
        return set()
    variants = {t}
    if len(t) > 4 and t.endswith("ies"):
        variants.add(f"{t[:-3]}y")
    if len(t) > 4 and t.endswith("s"):
        variants.add(t[:-1])
    return variants


def _extract_anchor_terms(query: str) -> Set[str]:
    text = (query or "").strip().lower()
    if not text:
        return set()
    tokens = re.findall(r"[a-z0-9][a-z0-9_-]*", text)
    anchors: Set[str] = set()
    for token in tokens:
        if len(token) < RETRIEVAL_ANCHOR_MIN_TOKEN_LEN or token in _QUERY_STOPWORDS:
            continue
        anchors.update(_token_variants(token))
    return anchors


def _normalize_query_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    return normalized.strip(" \t\r\n-")


def _is_entity_lookup_query(query: str) -> bool:
    q = _normalize_query_text(query).lower()
    if not q:
        return False
    patterns = (
        r"^\s*do you know(?: about)?\s+.+",
        r"^\s*what is\s+.+",
        r"^\s*who is\s+.+",
        r"^\s*tell me about\s+.+",
        r"^\s*can you explain\s+.+",
    )
    return any(re.search(p, q) for p in patterns)


def _should_attempt_query_expansion(query: str) -> bool:
    if not RETRIEVAL_QUERY_EXPANSION_ENABLED or RETRIEVAL_MAX_SEARCH_QUERIES <= 1:
        return False
    q = _normalize_query_text(query)
    if not q:
        return False
    # Keep single-token chatter out of expensive expansion calls.
    token_count = len(re.findall(r"[a-z0-9][a-z0-9_-]*", q.lower()))
    return token_count >= 2


def _should_attempt_hyde(query: str) -> bool:
    if not RETRIEVAL_HYDE_ENABLED or RETRIEVAL_MAX_SEARCH_QUERIES <= 1:
        return False
    if _is_entity_lookup_query(query):
        return False

    q = _normalize_query_text(query).lower()
    anchors = _extract_anchor_terms(q)
    if len(anchors) < RETRIEVAL_HYDE_MIN_ANCHORS:
        return False

    reasoning_markers = (
        "should",
        "how",
        "why",
        "tradeoff",
        "trade-off",
        "compare",
        "versus",
        " vs ",
        "recommend",
        "approach",
        "strategy",
        "plan",
    )
    if any(marker in q for marker in reasoning_markers):
        return True

    token_count = len(re.findall(r"[a-z0-9][a-z0-9_-]*", q))
    return token_count >= 7


def _build_search_query_plan(
    query: str,
    expanded_queries: List[str],
    hyde_answer: str,
    max_queries: int,
) -> List[Dict[str, Any]]:
    """
    Build weighted search plan:
    - keep original query dominant
    - include expansions for recall
    - include HyDE only as a low-weight auxiliary query
    """
    plan: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    def _add(candidate: str, *, kind: str, weight: float) -> None:
        normalized = _normalize_query_text(candidate)
        if not normalized:
            return
        key = normalized.lower()
        if key in seen:
            return
        seen.add(key)
        plan.append({"text": normalized, "kind": kind, "weight": float(weight)})

    _add(query, kind="original", weight=1.0)

    for candidate in expanded_queries:
        if len(plan) >= max_queries:
            break
        _add(candidate, kind="expansion", weight=0.88)

    if len(plan) < max_queries and hyde_answer and _should_attempt_hyde(query):
        _add(hyde_answer, kind="hyde", weight=0.72)

    return plan[:max(1, max_queries)] if plan else [{"text": _normalize_query_text(query), "kind": "original", "weight": 1.0}]


def _deterministic_query_expansions(query: str) -> List[str]:
    """
    Fast, local rewrites used even when LLM query expansion is unavailable.
    """
    q = _normalize_query_text(query)
    if not q:
        return []

    expansions: List[str] = []
    lowered = q.lower()

    # Entity probe normalization.
    m_entity = re.search(
        r"^\s*(?:do you know(?: about)?|tell me about|can you explain)\s+(.+?)\s*\??$",
        lowered,
    )
    if m_entity:
        entity = _normalize_query_text(m_entity.group(1))
        if entity:
            expansions.append(f"what is {entity}")
            expansions.append(f"{entity} overview")

    # Comparison normalization for "X or Y" style queries.
    if " or " in lowered:
        parts = [p.strip(" ?.,") for p in re.split(r"\bor\b", q, maxsplit=1, flags=re.IGNORECASE)]
        if len(parts) == 2 and all(parts):
            left, right = parts[0], parts[1]
            expansions.append(f"{left} vs {right}")
            expansions.append(f"tradeoffs {left} versus {right}")

    # Anchor-only compressed query for lexical recall.
    anchors = sorted(_extract_anchor_terms(q))
    if anchors:
        expansions.append(" ".join(anchors[:6]))

    deduped: List[str] = []
    seen: Set[str] = set()
    for candidate in expansions:
        normalized = _normalize_query_text(candidate)
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped[:3]


def _text_has_anchor_overlap(text: str, anchors: Set[str]) -> bool:
    if not anchors:
        return False
    text_tokens = re.findall(r"[a-z0-9][a-z0-9_-]*", (text or "").lower())
    normalized_tokens: Set[str] = set()
    for token in text_tokens:
        normalized_tokens.update(_token_variants(token))
    return bool(anchors.intersection(normalized_tokens))


def _apply_anchor_relevance_filter(contexts: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    """
    Remove clearly off-topic retrieval hits.

    Weak semantic matches can still return nearest-neighbor chunks that are unrelated.
    We keep contexts when:
    - they match explicit query anchors (keyword overlap), or
    - they are extremely strong semantic matches.
    """
    if not contexts:
        return contexts

    anchors = _extract_anchor_terms(query)
    if not anchors:
        return contexts

    filtered: List[Dict[str, Any]] = []
    for ctx in contexts:
        if ctx.get("is_verified"):
            filtered.append(ctx)
            continue

        text = str(ctx.get("text", ""))
        vector_score = float(ctx.get("vector_score", ctx.get("score", 0.0)) or 0.0)
        if _text_has_anchor_overlap(text, anchors) or vector_score >= RETRIEVAL_STRONG_VECTOR_FLOOR:
            filtered.append(ctx)

    if len(filtered) != len(contexts):
        print(
            "[Retrieval] Anchor relevance filter dropped "
            f"{len(contexts) - len(filtered)} context(s). anchors={sorted(anchors)}"
        )

    if not filtered and contexts:
        fallback = sorted(
            contexts,
            key=lambda c: float(c.get("vector_score", c.get("score", 0.0)) or 0.0),
            reverse=True,
        )[: min(RETRIEVAL_ANCHOR_FALLBACK_MAX, len(contexts))]
        print(
            "[Retrieval] Anchor relevance filter removed all contexts; "
            f"restoring top-{len(fallback)} by vector score as fallback."
        )
        return fallback

    return filtered


def _lexical_overlap_score(query: str, text: str) -> float:
    anchors = _extract_anchor_terms(query)
    if not anchors:
        return 0.0
    text_tokens = set(re.findall(r"[a-z0-9][a-z0-9_-]*", (text or "").lower()))
    normalized_tokens: Set[str] = set()
    for token in text_tokens:
        normalized_tokens.update(_token_variants(token))
    if not normalized_tokens:
        return 0.0
    overlap = len(anchors.intersection(normalized_tokens))
    return overlap / float(max(len(anchors), 1))


def _apply_lexical_fusion(query: str, contexts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Blend semantic/reranker scores with lexical overlap to reduce misses on
    direct phrase queries while keeping dense retrieval signal dominant.
    """
    if not RETRIEVAL_LEXICAL_FUSION_ENABLED or not contexts:
        return contexts

    fused: List[Dict[str, Any]] = []
    for ctx in contexts:
        current_score = float(ctx.get("score", ctx.get("vector_score", 0.0)) or 0.0)
        lexical_score = _lexical_overlap_score(query, str(ctx.get("text", "")))
        blended = ((1.0 - RETRIEVAL_LEXICAL_FUSION_ALPHA) * current_score) + (
            RETRIEVAL_LEXICAL_FUSION_ALPHA * lexical_score
        )

        enriched = dict(ctx)
        enriched.setdefault("semantic_score", current_score)
        enriched["lexical_score"] = lexical_score
        enriched["score"] = blended
        fused.append(enriched)

    fused.sort(key=lambda c: float(c.get("score", 0.0) or 0.0), reverse=True)
    return fused


def log_retrieval_event(event_type: str, data: Dict[str, Any]):
    """Log structured retrieval events for monitoring."""
    log_entry = {
        "timestamp": time.time(),
        "component": "retrieval",
        "event": event_type,
        **data
    }
    logger.info(json.dumps(log_entry))


@contextmanager
def measure_phase(phase_name: str, twin_id: str):
    """Context manager to measure and log phase timing."""
    start = time.time()
    try:
        yield
    finally:
        elapsed = time.time() - start
        log_retrieval_event("phase_timing", {
            "phase": phase_name,
            "twin_id": twin_id,
            "duration_ms": round(elapsed * 1000, 2)
        })

# =============================================================================
# NAMESPACE FORMAT (Delphi.ai Architecture)
# =============================================================================
# New format: creator_{creator_id}_twin_{twin_id}
# Legacy format: {twin_id} (UUID or custom string)
# 
# Migration: Phase 1 complete - All data migrated to creator-based namespaces
# =============================================================================

def get_namespace(creator_id: Optional[str], twin_id: str) -> str:
    """
    Generate Pinecone namespace following Delphi architecture.
    
    Args:
        creator_id: Creator ID (e.g., 'sainath.no.1') or None for legacy
        twin_id: Twin ID (e.g., 'coach', 'assistant', or UUID)
        
    Returns:
        Namespace string for Pinecone
        
    Examples:
        >>> get_namespace("sainath.no.1", "coach")
        'creator_sainath.no.1_twin_coach'
        >>> get_namespace(None, "5698a809-87a5-4169-ab9b-c4a6222ae2dd")
        '5698a809-87a5-4169-ab9b-c4a6222ae2dd'
    """
    if creator_id:
        return build_creator_namespace(creator_id, twin_id)
    return get_primary_namespace_for_twin(twin_id)


def parse_namespace(namespace: str) -> tuple[Optional[str], str]:
    """
    Parse a namespace into creator_id and twin_id.
    
    Args:
        namespace: Pinecone namespace string
        
    Returns:
        Tuple of (creator_id, twin_id) - creator_id is None for legacy
        
    Examples:
        >>> parse_namespace("creator_sainath.no.1_twin_coach")
        ('sainath.no.1', 'coach')
        >>> parse_namespace("5698a809-87a5-4169-ab9b-c4a6222ae2dd")
        (None, '5698a809-87a5-4169-ab9b-c4a6222ae2dd')
    """
    if namespace.startswith("creator_"):
        parts = namespace.replace("creator_", "").split("_twin_", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
    return None, namespace

# FlashRank reranking is opt-in to avoid startup/runtime regressions in production.
_flashrank_enabled = os.getenv("ENABLE_FLASHRANK", "false").lower() == "true"
if _flashrank_enabled:
    try:
        from flashrank import Ranker, RerankRequest
        _flashrank_available = True
        _ranker_instance = None
    except ImportError:
        _flashrank_available = False
        _ranker_instance = None
else:
    Ranker = None  # type: ignore[assignment]
    RerankRequest = None  # type: ignore[assignment]
    _flashrank_available = False
    _ranker_instance = None

_cohere_rerank_enabled = os.getenv("ENABLE_COHERE_RERANK", "true").lower() == "true"
_cohere_rerank_model = os.getenv("COHERE_RERANK_MODEL", "rerank-v3.5")

def get_ranker():
    """Lazy load FlashRank to avoid startup overhead."""
    global _ranker_instance
    if _flashrank_enabled and _flashrank_available and _ranker_instance is None:
        try:
            # Use a lightweight model
            _ranker_instance = Ranker(model_name="ms-marco-MiniLM-L-12-v2", cache_dir="./.model_cache")
        except Exception as e:
            print(f"Failed to initialize FlashRank: {e}")
    return _ranker_instance


def _rerank_with_cohere(
    query: str,
    contexts: List[Dict[str, Any]],
    top_k: int,
) -> Optional[List[Dict[str, Any]]]:
    """
    Rerank contexts with Cohere when configured.
    Returns None when unavailable or rerank fails.
    """
    if not _cohere_rerank_enabled or not contexts:
        return None

    cohere_client = get_cohere_client()
    if cohere_client is None:
        return None

    try:
        response = cohere_client.rerank(
            model=_cohere_rerank_model,
            query=query,
            documents=[c.get("text", "") for c in contexts],
            top_n=min(max(1, top_k), len(contexts)),
        )
        results = getattr(response, "results", None)
        if results is None and isinstance(response, dict):
            results = response.get("results")
        if not isinstance(results, list):
            return None

        reranked: List[Dict[str, Any]] = []
        for item in results:
            if isinstance(item, dict):
                idx = item.get("index")
                score = item.get("relevance_score", item.get("score", 0.0))
            else:
                idx = getattr(item, "index", None)
                score = getattr(item, "relevance_score", getattr(item, "score", 0.0))

            if idx is None:
                continue
            try:
                original_idx = int(idx)
                if original_idx < 0 or original_idx >= len(contexts):
                    continue
                ctx = dict(contexts[original_idx])
                ctx["vector_score"] = float(ctx.get("vector_score", ctx.get("score", 0.0)) or 0.0)
                ctx["score"] = float(score or 0.0)
                reranked.append(ctx)
            except Exception:
                continue

        if not reranked:
            return None

        max_rerank_score = max((float(c.get("score", 0.0) or 0.0) for c in reranked), default=0.0)
        if max_rerank_score < 0.001:
            print("[Retrieval] Cohere rerank scores too low. Falling back.")
            return None

        print(f"[Retrieval] Cohere reranked {len(contexts)} -> {len(reranked[:top_k])} contexts")
        return reranked[:top_k]
    except Exception as e:
        print(f"[Retrieval] Cohere reranking failed: {e}. Falling back.")
        return None


def _rerank_with_flashrank(
    query: str,
    contexts: List[Dict[str, Any]],
    top_k: int,
) -> Optional[List[Dict[str, Any]]]:
    """
    Rerank contexts with FlashRank when configured.
    Returns None when unavailable or rerank fails.
    """
    ranker = get_ranker()
    if ranker is None or not contexts:
        return None

    try:
        passages = [{"id": str(i), "text": c["text"], "meta": c} for i, c in enumerate(contexts)]
        rerank_request = RerankRequest(query=query, passages=passages)
        results = ranker.rerank(rerank_request)

        max_rerank_score = max((float(res.get("score", 0) or 0) for res in results), default=0.0)
        if max_rerank_score < 0.001:
            print("[Retrieval] FlashRank scores too low. Falling back.")
            return None

        reranked: List[Dict[str, Any]] = []
        for res in results:
            original_idx = int(res["id"])
            ctx = dict(contexts[original_idx])
            ctx["vector_score"] = float(ctx.get("vector_score", ctx.get("score", 0.0)) or 0.0)
            ctx["score"] = float(res.get("score", 0.0) or 0.0)
            reranked.append(ctx)

        print(f"[Retrieval] FlashRank reranked {len(contexts)} -> {len(reranked[:top_k])} contexts")
        return reranked[:top_k]
    except Exception as e:
        print(f"[Retrieval] FlashRank reranking failed: {e}. Falling back.")
        return None


async def expand_query(query: str) -> List[str]:
    """
    Generates 3 variations of the user query for better retrieval using a more capable model.
    """
    client = get_openai_client()
    try:
        loop = asyncio.get_event_loop()
        def _fetch():
            return client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that generates 3 search query variations based on the user's input to improve RAG retrieval. Provide the variations as a bulleted list. Focus on different aspects and synonyms."},
                    {"role": "user", "content": f"Original query: {query}"}
                ],
                max_tokens=150,
                temperature=0.7,
                timeout=RETRIEVAL_QUERY_PREP_TIMEOUT
            )
            
        response = await loop.run_in_executor(None, _fetch)
        content = response.choices[0].message.content
        variations = [line.strip().lstrip("-*123. ").strip() for line in content.split("\n") if line.strip()]
        return variations[:3]
    except Exception as e:
        print(f"Error expanding query: {e}")
        return [query]

async def generate_hyde_answer(query: str) -> str:
    """
    Generates a hypothetical answer to be used for embedding search (HyDE).
    """
    client = get_openai_client()
    try:
        loop = asyncio.get_event_loop()
        def _fetch():
            return client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a knowledgeable assistant. Write a brief, factual hypothetical answer to the user's question. This answer will be used for vector similarity search, so focus on relevant keywords and concepts that would appear in a document."},
                    {"role": "user", "content": query}
                ],
                max_tokens=250,
                temperature=0.3,
                timeout=RETRIEVAL_QUERY_PREP_TIMEOUT
            )
            
        response = await loop.run_in_executor(None, _fetch)
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error generating HyDE answer: {e}")
        return query


def rrf_merge(
    results_list: List[List[Dict[str, Any]]],
    k: int = 60,
    weights: Optional[List[float]] = None,
) -> List[Dict[str, Any]]:
    """
    Reciprocal Rank Fusion (RRF) merge of multiple result lists.
    
    Args:
        results_list: List of result lists from different queries
        k: RRF constant (default 60)
        
    Returns:
        Merged and ranked results by RRF score
    """
    # Build score map: {doc_id: rrf_score}
    score_map: Dict[str, float] = {}
    
    for idx, results in enumerate(results_list):
        weight = 1.0
        if weights and idx < len(weights):
            try:
                weight = max(0.05, float(weights[idx]))
            except Exception:
                weight = 1.0
        for rank, hit in enumerate(results, start=1):
            doc_id = hit.get("id", str(hit))
            score_map[doc_id] = score_map.get(doc_id, 0.0) + (weight / (k + rank))
    
    # Build reverse index: {doc_id: hit}
    doc_map: Dict[str, Dict[str, Any]] = {}
    for results in results_list:
        for hit in results:
            doc_id = hit.get("id", str(hit))
            if doc_id not in doc_map:
                doc_map[doc_id] = hit
    
    # Sort by RRF score (descending)
    sorted_docs = sorted(score_map.items(), key=lambda x: x[1], reverse=True)
    
    # Build final results with RRF scores
    final_results = []
    for doc_id, rrf_score in sorted_docs:
        raw_hit = doc_map[doc_id]
        if raw_hit is None:
            print(f"DEBUG: doc_id {doc_id} has NONE hit in doc_map")
            continue
        
        try:
            if hasattr(raw_hit, "to_dict"):
                hit = raw_hit.to_dict()
            elif isinstance(raw_hit, dict):
                hit = raw_hit.copy()
            else:
                print(f"DEBUG: doc_id {doc_id} has unknown type {type(raw_hit)}")
                hit = dict(raw_hit)
            
            hit["rrf_score"] = rrf_score
            final_results.append(hit)
        except Exception as e:
            print(f"DEBUG ERROR in rrf_merge loop for doc_id {doc_id}: {e} (type: {type(raw_hit)})")
            continue
        
    return final_results


def _format_verified_match_context(verified_match: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format a verified QnA match as a context entry.
    
    Args:
        verified_match: Verified QnA match result
        
    Returns:
        Formatted context dictionary
    """
    return {
        "text": verified_match["answer"],
        "score": 1.0,  # Perfect confidence for verified answers
        "source_id": f"verified_qna_{verified_match['id']}",
        "is_verified": True,
        "verified_qna_match": True,
        "question": verified_match["question"],
        "category": "FACT",
        "tone": "Assertive",
        "citations": verified_match.get("citations", [])
    }


def _format_owner_memory_match_context(owner_memory_match: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format an owner-approved memory match as a context entry.
    This has highest precedence because it is directly owner-authored.
    """
    memory_id = owner_memory_match.get("id")
    return {
        "text": owner_memory_match.get("value", ""),
        "score": 1.0,
        "source_id": f"owner_memory_{memory_id}" if memory_id else "owner_memory",
        "is_owner_memory": True,
        "owner_memory_match": True,
        "verified_qna_match": False,
        "memory_type": owner_memory_match.get("memory_type"),
        "topic_normalized": owner_memory_match.get("topic_normalized"),
        "category": "FACT",
        "tone": "Assertive",
        "citations": [],
    }


def _match_owner_memory(query: str, twin_id: str) -> Optional[Dict[str, Any]]:
    """
    Find a high-confidence owner memory candidate for this query.
    Only active/verified memories with strong similarity are eligible.
    """
    try:
        # Limit owner-memory override to owner-specific/stance-like questions.
        from modules.identity_gate import classify_query

        if not classify_query(query).get("requires_owner"):
            return None

        candidates = find_owner_memory_candidates(
            query=query,
            twin_id=twin_id,
            topic_normalized=None,
            memory_type=None,
            limit=1,
        )
        if not candidates:
            return None
        best = candidates[0]
        status = str(best.get("status") or "").lower()
        allowed_statuses = {"active", "verified"}
        if AUTO_APPROVE_OWNER_MEMORY:
            allowed_statuses.add("proposed")
        if status not in allowed_statuses:
            return None

        score = float(best.get("_score", 0.0) or 0.0)
        confidence = float(best.get("confidence", 0.0) or 0.0)
        if (
            score < RETRIEVAL_OWNER_MEMORY_MATCH_MIN_SCORE
            and confidence < RETRIEVAL_OWNER_MEMORY_MATCH_MIN_CONFIDENCE
        ):
            return None
        return best
    except Exception as e:
        print(f"[Retrieval] Owner memory lookup failed: {e}")
        return None


def _prepare_search_queries(query: str) -> List[str]:
    """
    Prepare search queries using query expansion and HyDE.
    
    Args:
        query: Original query
        
    Returns:
        List of search queries (including original, HyDE, and expansions)
    """
    async def _prepare():
        expanded_task = expand_query(query)
        hyde_task = generate_hyde_answer(query)
        expanded_queries, hyde_answer = await asyncio.gather(expanded_task, hyde_task)
        return list(set([query, hyde_answer] + expanded_queries))
    
    # Run async function
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # If loop is already running, we need to handle this differently
        # For now, just use the original query
        return [query]
    else:
        return loop.run_until_complete(_prepare())


async def _execute_pinecone_queries(
    embeddings: List[List[float]],
    twin_id: str,
    creator_id: Optional[str] = None,
    timeout: float = 5.0
) -> List[Dict[str, Any]]:
    """
    Execute Pinecone queries for all embeddings.
    
    Args:
        embeddings: List of embedding vectors
        twin_id: Twin ID
        creator_id: Creator ID (for Delphi namespace format) - None for legacy
        timeout: Timeout in seconds
        
    Returns:
        List of query results
    """
    if not embeddings:
        return []

    resolved_creator = creator_id or resolve_creator_id_for_twin(twin_id)
    dual_read_enabled = os.getenv("DELPHI_DUAL_READ", "true").lower() == "true"
    namespace_candidates = get_namespace_candidates_for_twin(
        twin_id=twin_id,
        creator_id=resolved_creator,
        include_legacy=dual_read_enabled,
    )
    if not namespace_candidates:
        print("[Retrieval] No namespace candidates available, returning empty contexts")
        return []

    try:
        index = await asyncio.wait_for(
            asyncio.to_thread(get_pinecone_index),
            timeout=max(1.0, RETRIEVAL_INDEX_INIT_TIMEOUT),
        )
    except Exception as e:
        print(f"[Retrieval] Pinecone index unavailable: {e}")
        return []

    def _extract_matches(response: Any) -> List[Dict[str, Any]]:
        if isinstance(response, dict):
            return response.get("matches", []) or []
        raw = getattr(response, "matches", []) or []
        normalized = []
        for match in raw:
            if isinstance(match, dict):
                normalized.append(match)
            else:
                normalized.append(
                    {
                        "id": getattr(match, "id", None),
                        "score": getattr(match, "score", 0.0),
                        "metadata": getattr(match, "metadata", {}) or {},
                    }
                )
        return normalized

    def _merge_matches(matches: List[Dict[str, Any]]) -> Dict[str, Any]:
        # Keep best score for duplicate ids across namespaces.
        dedup: Dict[str, Dict[str, Any]] = {}
        for m in matches:
            mid = str(m.get("id"))
            score = float(m.get("score", 0.0) or 0.0)
            if mid not in dedup or score > float(dedup[mid].get("score", 0.0) or 0.0):
                dedup[mid] = m
        merged = sorted(dedup.values(), key=lambda x: float(x.get("score", 0.0) or 0.0), reverse=True)
        return {"matches": merged}

    async def pinecone_query(embedding: List[float], is_verified: bool = False) -> Dict[str, Any]:
        """Execute one query across namespace candidates and merge."""
        top_k = RETRIEVAL_TOP_K_VERIFIED if is_verified else RETRIEVAL_TOP_K_GENERAL
        primary_ns = namespace_candidates[0]

        async def query_namespace(namespace: str):
            def _fetch():
                query_params = {
                    "vector": embedding,
                    "top_k": top_k,
                    "include_metadata": True,
                    "namespace": namespace,
                }
                if is_verified:
                    query_params["filter"] = {"is_verified": {"$eq": True}}
                return index.query(**query_params)

            attempts: List[float] = [RETRIEVAL_PER_NAMESPACE_TIMEOUT]
            # Optional retry for primary namespace only (disabled by default to avoid long tail timeouts).
            if RETRIEVAL_PRIMARY_RETRY_ENABLED and namespace == primary_ns:
                attempts.append(max(RETRIEVAL_PER_NAMESPACE_TIMEOUT * 2.0, 12.0))

            last_error: Optional[Exception] = None
            for attempt_idx, attempt_timeout in enumerate(attempts, start=1):
                try:
                    return await asyncio.wait_for(
                        asyncio.to_thread(_fetch),
                        timeout=attempt_timeout,
                    )
                except asyncio.TimeoutError as e:
                    last_error = e
                    if attempt_idx < len(attempts):
                        print(
                            f"[Retrieval] Namespace {namespace} timed out after {attempt_timeout:.1f}s "
                            f"(attempt {attempt_idx}/{len(attempts)}), retrying."
                        )
                        continue
                    raise
                except Exception as e:
                    last_error = e
                    raise

            if last_error:
                raise last_error
            raise RuntimeError(f"Unexpected namespace query failure for {namespace}")

        namespace_results = await asyncio.gather(
            *[query_namespace(ns) for ns in namespace_candidates],
            return_exceptions=True,
        )

        merged_matches: List[Dict[str, Any]] = []
        failed_namespaces = []
        success_count = 0
        
        for ns, ns_result in zip(namespace_candidates, namespace_results):
            if isinstance(ns_result, Exception):
                failed_namespaces.append(ns)
                print(f"[Retrieval] Namespace query failed ({ns}): {type(ns_result).__name__}: {ns_result}")
                continue
            
            matches = _extract_matches(ns_result)
            if matches:
                success_count += 1
                print(f"[Retrieval] Namespace {ns}: {len(matches)} matches")
            merged_matches.extend(matches)
        
        # PHASE 2 FIX: Better logging for debugging
        if failed_namespaces:
            print(f"[Retrieval] Warning: {len(failed_namespaces)}/{len(namespace_candidates)} namespaces failed: {failed_namespaces}")

        # Optional hotfix retry only when explicitly enabled.
        if (
            RETRIEVAL_PRIMARY_RETRY_ENABLED
            and not merged_matches
            and failed_namespaces
            and len(failed_namespaces) == len(namespace_candidates)
        ):
            primary_ns = namespace_candidates[0]
            try:
                print(
                    f"[Retrieval] All namespace queries failed; retrying primary namespace "
                    f"{primary_ns} with extended timeout"
                )

                def _retry_fetch():
                    query_params = {
                        "vector": embedding,
                        "top_k": top_k,
                        "include_metadata": True,
                        "namespace": primary_ns,
                    }
                    if is_verified:
                        query_params["filter"] = {"is_verified": {"$eq": True}}
                    return index.query(**query_params)

                retry_result = await asyncio.wait_for(
                    asyncio.to_thread(_retry_fetch),
                    timeout=max(RETRIEVAL_PER_NAMESPACE_TIMEOUT * 2.5, 14.0),
                )
                retry_matches = _extract_matches(retry_result)
                if retry_matches:
                    merged_matches.extend(retry_matches)
                    success_count = max(success_count, 1)
                    print(f"[Retrieval] Primary namespace retry succeeded: {len(retry_matches)} matches")
            except Exception as retry_error:
                print(f"[Retrieval] Primary namespace retry failed ({primary_ns}): {type(retry_error).__name__}: {retry_error}")
        
        if not merged_matches:
            print(f"[Retrieval] No matches found in any namespace. Checked: {namespace_candidates}")
        else:
            print(f"[Retrieval] Total matches from {success_count} namespaces: {len(merged_matches)}")

        return _merge_matches(merged_matches)

    verified_task = pinecone_query(embeddings[0], is_verified=True)
    general_tasks = [pinecone_query(emb, is_verified=False) for emb in embeddings]

    try:
        results = await asyncio.wait_for(
            asyncio.gather(verified_task, *general_tasks),
            timeout=timeout,
        )
        if not results:
            return []
        if all(not (r.get("matches") if isinstance(r, dict) else None) for r in results):
            return []
        return results
    except asyncio.TimeoutError:
        print(f"[Retrieval] Vector search timed out after {timeout}s, returning empty contexts")
        return []
    except Exception as e:
        print(f"[Retrieval] Vector search failed: {e}, returning empty contexts")
        return []


def _process_verified_matches(verified_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Process verified vector matches into context entries.
    
    Args:
        verified_results: Pinecone query results for verified vectors
        
    Returns:
        List of formatted context entries
    """
    contexts = []
    for match in verified_results.get("matches", []):
        if match["score"] > 0.3:
            contexts.append({
                "text": match["metadata"]["text"],
                "score": 1.0,  # Boost verified
                "vector_score": 1.0,
                "source_id": match["metadata"].get("source_id", "verified_memory"),
                "is_verified": True,
                "category": match["metadata"].get("category", "FACT"),
                "tone": match["metadata"].get("tone", "Assertive"),
                "opinion_topic": match["metadata"].get("opinion_topic"),
                "opinion_stance": match["metadata"].get("opinion_stance"),
                "opinion_intensity": match["metadata"].get("opinion_intensity"),
                "section_title": match["metadata"].get("section_title"),
                "section_path": match["metadata"].get("section_path"),
                "chunk_type": match["metadata"].get("chunk_type"),
            })
    return contexts


def _process_general_matches(merged_general_hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Process general vector matches into context entries.
    
    Args:
        merged_general_hits: RRF-merged general search results
        
    Returns:
        List of formatted context entries
    """
    raw_general_chunks = []
    for match in merged_general_hits:
        raw_score = match.get("score", 0.0)
        raw_rrf_score = match.get("rrf_score", 0.0)
        try:
            score = float(raw_score)
        except Exception:
            score = 0.0
        try:
            rrf_score = float(raw_rrf_score)
        except Exception:
            rrf_score = 0.0
        raw_general_chunks.append({
            "text": match["metadata"]["text"],
            "score": score,
            "vector_score": score,
            "rrf_score": rrf_score,
            "source_id": match["metadata"].get("source_id", "unknown"),
            "chunk_id": match["metadata"].get("chunk_id", "unknown"),
            "is_verified": False,
            "category": match["metadata"].get("category", "FACT"),
            "tone": match["metadata"].get("tone", "Neutral"),
            "opinion_topic": match["metadata"].get("opinion_topic"),
            "opinion_stance": match["metadata"].get("opinion_stance"),
            "opinion_intensity": match["metadata"].get("opinion_intensity"),
            "section_title": match["metadata"].get("section_title"),
            "section_path": match["metadata"].get("section_path"),
            "chunk_type": match["metadata"].get("chunk_type"),
        })
    return raw_general_chunks


def _filter_by_group_permissions(
    contexts: List[Dict[str, Any]],
    group_id: Optional[str]
) -> List[Dict[str, Any]]:
    """
    Filter contexts by group permissions.
    
    Args:
        contexts: List of context entries
        group_id: Optional group ID to filter by
        
    Returns:
        Filtered list of contexts
    """
    if not group_id:
        return contexts
    
    # Get allowed source_ids for this group
    permissions_response = supabase.table("content_permissions").select("content_id").eq(
        "group_id", group_id
    ).eq("content_type", "source").execute()
    
    allowed_source_ids = {str(perm["content_id"]) for perm in (permissions_response.data or [])}

    # Backward compatibility: legacy twins may have no content_permissions rows yet.
    # In that case, do not hard-deny all contexts.
    if not allowed_source_ids:
        print(
            f"[Retrieval] Group filtering bypassed: no content_permissions rows for group {group_id}. "
            "Allowing contexts for legacy compatibility."
        )
        return contexts
    
    # Filter contexts to only include chunks from allowed sources
    # Also allow verified memory (is_verified=True chunks) - they're always accessible
    filtered_contexts = []
    rejected_count = 0
    
    for c in contexts:
        source_id = str(c.get("source_id", ""))
        is_verified = c.get("is_verified", False)
        
        # Allow if verified memory OR if source_id matches an allowed source
        if is_verified or source_id in allowed_source_ids:
            filtered_contexts.append(c)
        else:
            rejected_count += 1
    
    # PHASE 2 FIX: Log filtering results
    if rejected_count > 0:
        print(f"[Retrieval] Group filtering: {len(filtered_contexts)} allowed, {rejected_count} rejected (group: {group_id})")

    # Pragmatic fallback: if non-public group permissions are misconfigured and all
    # contexts were rejected, keep chat responsive by returning unfiltered results.
    if (
        RETRIEVAL_LENIENT_NON_PUBLIC_GROUP_FILTER
        and contexts
        and not filtered_contexts
    ):
        try:
            group_res = (
                supabase.table("access_groups")
                .select("is_public")
                .eq("id", group_id)
                .single()
                .execute()
            )
            is_public_group = bool((group_res.data or {}).get("is_public"))
        except Exception:
            is_public_group = False

        if not is_public_group:
            print(
                f"[Retrieval] Group filtering fallback applied for non-public group {group_id}; "
                "returning unfiltered contexts."
            )
            return contexts

    return filtered_contexts


def _deduplicate_and_limit(
    contexts: List[Dict[str, Any]],
    top_k: int
) -> List[Dict[str, Any]]:
    """
    Deduplicate contexts by text and limit to top_k.
    
    Args:
        contexts: List of context entries
        top_k: Maximum number of contexts to return
        
    Returns:
        Deduplicated and limited list of contexts
    """
    seen = set()
    final_contexts = []
    
    for c in contexts:
        text = c["text"]
        if text not in seen:
            seen.add(text)
            final_contexts.append(c)
    
    return final_contexts[:top_k]


@observe(name="rag_retrieval")
async def retrieve_context_with_verified_first(
    query: str,
    twin_id: str,
    creator_id: Optional[str] = None,
    group_id: Optional[str] = None,
    top_k: int = 5,
    resolve_default_group: bool = True,
) -> List[Dict[str, Any]]:
    """
    Retrieval pipeline with verified-first order: Check verified QnA → vectors → tools.
    Returns contexts with verified_qna_match flag if verified answer found.
    If group_id is None, uses default group for backward compatibility.
    
    Args:
        query: Search query
        twin_id: Twin ID
        creator_id: Creator ID (for Delphi namespace format) - None for legacy
        group_id: Access group for filtering (optional)
        top_k: Number of results to return
    """
    query = (query or "").strip()
    if not query:
        return []

    # PHASE 4: Start tracking retrieval metrics
    retrieval_start = time.time()
    
    # Resolve group_id to default if None (public/group-filtered paths only).
    if group_id is None and resolve_default_group:
        try:
            with measure_phase("group_resolution", twin_id):
                default_group = await get_default_group(twin_id)
                group_id = default_group["id"]
                print(f"[Retrieval] Using default group: {group_id}")
        except Exception as e:
            # PHASE 2 FIX: Better logging for group resolution failure
            print(f"[Retrieval] No default group for twin {twin_id}: {e}")
            print(f"[Retrieval] Proceeding without group filtering (all sources accessible)")
            group_id = None
    
    # STEP 1: Check owner-approved memory first (highest priority).
    owner_memory_match = None
    try:
        with measure_phase("owner_memory_lookup", twin_id):
            owner_memory_match = await asyncio.wait_for(
                asyncio.to_thread(_match_owner_memory, query, twin_id),
                timeout=1.0,
            )
    except asyncio.TimeoutError:
        log_retrieval_event("timeout", {"phase": "owner_memory_lookup", "twin_id": twin_id})
        print("[Retrieval] Owner memory lookup timed out after 1s, continuing.")
    except Exception as e:
        log_retrieval_event("error", {"phase": "owner_memory_lookup", "twin_id": twin_id, "error": str(e)})
        print(f"[Retrieval] Owner memory lookup failed: {e}, continuing.")

    if owner_memory_match:
        total_time = time.time() - retrieval_start
        log_retrieval_event("retrieval_complete", {
            "twin_id": twin_id,
            "source": "owner_memory",
            "contexts_found": 1,
            "total_duration_ms": round(total_time * 1000, 2)
        })
        return [_format_owner_memory_match_context(owner_memory_match)]

    # STEP 2: Check Verified QnA (next priority) - P1-C: 2s timeout
    verified_match = None
    try:
        with measure_phase("verified_qna_lookup", twin_id):
            verified_match = await asyncio.wait_for(
                match_verified_qna(
                    query,
                    twin_id,
                    group_id=group_id,
                    use_exact=True,
                    use_semantic=True,
                    exact_threshold=0.80,
                    semantic_threshold=0.84,
                ),
                timeout=2.0
            )
    except asyncio.TimeoutError:
        log_retrieval_event("timeout", {"phase": "verified_qna_lookup", "twin_id": twin_id})
        print(f"[Retrieval] Verified QnA lookup timed out after 2s, falling back to vector retrieval")
    except Exception as e:
        log_retrieval_event("error", {"phase": "verified_qna_lookup", "twin_id": twin_id, "error": str(e)})
        print(f"[Retrieval] Verified QnA lookup failed: {e}, falling back to vector retrieval")
    
    if verified_match:
        match_type = str(verified_match.get("match_type") or "semantic")
        similarity = float(verified_match.get("similarity_score", 0.0) or 0.0)
        min_similarity = 0.80 if match_type == "exact" else 0.84
        if similarity < min_similarity:
            print(
                f"[Retrieval] Verified QnA rejected: type={match_type} "
                f"similarity={similarity:.3f} < {min_similarity:.2f}"
            )
            verified_match = None

    if verified_match:
        total_time = time.time() - retrieval_start
        log_retrieval_event("retrieval_complete", {
            "twin_id": twin_id,
            "source": "verified_qna",
            "contexts_found": 1,
            "total_duration_ms": round(total_time * 1000, 2),
            "similarity_score": verified_match.get("similarity_score"),
            "match_type": verified_match.get("match_type", "unknown"),
        })
        return [_format_verified_match_context(verified_match)]
    
    # STEP 3: No high-priority match - proceed with vector retrieval
    with measure_phase("vector_retrieval", twin_id):
        vector_results = await retrieve_context_vectors(query, twin_id, creator_id=creator_id, group_id=group_id, top_k=top_k)
    
    total_time = time.time() - retrieval_start
    log_retrieval_event("retrieval_complete", {
        "twin_id": twin_id,
        "source": "vector_search",
        "contexts_found": len(vector_results),
        "total_duration_ms": round(total_time * 1000, 2)
    })
    
    return vector_results


@observe(name="rag_vector_retrieval")
async def retrieve_context_vectors(
    query: str,
    twin_id: str,
    creator_id: Optional[str] = None,
    group_id: Optional[str] = None,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Optimized retrieval pipeline using HyDE, Query Expansion, and RRF (vector-only).
    Used when no verified QnA match is found.
    If group_id is provided, filters results by group permissions.
    
    Args:
        query: Search query
        twin_id: Twin ID
        creator_id: Creator ID (for Delphi namespace format) - None for legacy
        group_id: Access group for filtering (optional)
        top_k: Number of results to return
    """
    query = (query or "").strip()
    if not query:
        return []

    # 1. Query prep under a strict timeout budget.
    expanded_queries: List[str] = _deterministic_query_expansions(query)
    hyde_answer = ""
    prep_tasks: List[Any] = []
    prep_labels: List[str] = []

    if _should_attempt_query_expansion(query):
        prep_tasks.append(expand_query(query))
        prep_labels.append("expand")

    if _should_attempt_hyde(query):
        prep_tasks.append(generate_hyde_answer(query))
        prep_labels.append("hyde")

    if prep_tasks:
        try:
            prep_results = await asyncio.wait_for(
                asyncio.gather(*prep_tasks, return_exceptions=True),
                timeout=RETRIEVAL_QUERY_PREP_TIMEOUT,
            )
            for label, raw in zip(prep_labels, prep_results):
                if isinstance(raw, Exception):
                    continue
                if label == "expand" and isinstance(raw, list):
                    llm_expansions = [
                        _normalize_query_text(q)
                        for q in raw
                        if isinstance(q, str) and _normalize_query_text(q)
                    ]
                    expanded_queries.extend(llm_expansions)
                elif label == "hyde" and isinstance(raw, str) and raw.strip():
                    hyde_answer = _normalize_query_text(raw)
        except asyncio.TimeoutError:
            print(
                f"[Retrieval] Query preparation timed out after {RETRIEVAL_QUERY_PREP_TIMEOUT}s, "
                "using reduced query plan."
            )
        except Exception as e:
            print(f"[Retrieval] Query preparation failed: {e}, using reduced query plan")

    search_plan = _build_search_query_plan(
        query=query,
        expanded_queries=expanded_queries,
        hyde_answer=hyde_answer,
        max_queries=RETRIEVAL_MAX_SEARCH_QUERIES,
    )
    search_queries = [entry["text"] for entry in search_plan if isinstance(entry, dict)]
    search_weights = [float(entry.get("weight", 1.0) or 1.0) for entry in search_plan if isinstance(entry, dict)]
    search_kinds = [str(entry.get("kind", "original")) for entry in search_plan if isinstance(entry, dict)]

    if not search_queries:
        search_queries = [query]
        search_weights = [1.0]
        search_kinds = ["original"]

    print(
        "[Retrieval] Search plan: "
        + " | ".join(
            f"{kind}:{weight:.2f}:{text[:80]}"
            for kind, weight, text in zip(search_kinds, search_weights, search_queries)
        )
    )
    
    # 2. Embeddings under timeout with single-query fallback.
    all_embeddings: List[List[float]] = []
    try:
        all_embeddings = await asyncio.wait_for(
            get_embeddings_async(search_queries),
            timeout=RETRIEVAL_EMBEDDING_TIMEOUT,
        )
    except asyncio.TimeoutError:
        print(f"[Retrieval] Embedding batch timed out after {RETRIEVAL_EMBEDDING_TIMEOUT}s, falling back to single embedding")
    except Exception as e:
        print(f"[Retrieval] Embedding batch failed: {e}, falling back to single embedding")

    if not all_embeddings:
        try:
            one = await asyncio.wait_for(
                asyncio.to_thread(get_embedding, query),
                timeout=min(RETRIEVAL_EMBEDDING_TIMEOUT, 4.0),
            )
            if one:
                all_embeddings = [one]
        except Exception as e:
            print(f"[Retrieval] Single-embedding fallback failed: {e}")
            return []

    if len(all_embeddings) != len(search_queries):
        aligned = min(len(all_embeddings), len(search_queries))
        if aligned > 0:
            all_embeddings = all_embeddings[:aligned]
            search_queries = search_queries[:aligned]
            search_weights = search_weights[:aligned]
            search_kinds = search_kinds[:aligned]
        else:
            all_embeddings = []
    if not all_embeddings:
        return []
    
    # 3. Parallel Vector Search with bounded timeout.
    all_results = await _execute_pinecone_queries(
        all_embeddings,
        twin_id,
        creator_id=creator_id,
        timeout=RETRIEVAL_VECTOR_TIMEOUT,
    )

    # Fallback pass: if the full pipeline failed, retry a single direct query embedding.
    if not all_results:
        print(
            "[Retrieval] Primary vector pipeline returned no results; attempting minimal "
            "single-query fallback."
        )
        try:
            fallback_embedding = await asyncio.wait_for(
                asyncio.to_thread(get_embedding, query),
                timeout=min(RETRIEVAL_EMBEDDING_TIMEOUT, 8.0),
            )
            all_results = await _execute_pinecone_queries(
                [fallback_embedding],
                twin_id,
                creator_id=creator_id,
                timeout=max(RETRIEVAL_VECTOR_TIMEOUT, RETRIEVAL_PER_NAMESPACE_TIMEOUT * 2.5),
            )
        except Exception as e:
            print(f"[Retrieval] Minimal fallback retrieval failed: {e}")

    if not all_results:
        return []
    
    verified_results = all_results[0]
    general_results_list = [res["matches"] for res in all_results[1:]]
    
    # 4. RRF Merge general results
    merged_general_hits = rrf_merge(
        general_results_list,
        weights=search_weights[: len(general_results_list)],
    )
    
    # 5. Process matches into contexts
    contexts = _process_verified_matches(verified_results)
    raw_general_chunks = _process_general_matches(merged_general_hits)
    contexts.extend(raw_general_chunks)
    
    # 6. Filter by group permissions if group_id is provided
    contexts = _filter_by_group_permissions(contexts, group_id)
    print(f"DEBUG: After permissions: {len(contexts)} (Group: {group_id})")
    
    # 7. Deduplicate (keep all candidates first)
    unique_contexts = _deduplicate_and_limit(contexts, top_k=top_k * 3)
    print(f"DEBUG: Unique contexts before rerank: {len(unique_contexts)}")
    
    # 8. Rerank
    # Priority: Cohere (remote) -> FlashRank (local) -> vector score fallback.
    final_contexts: List[Dict[str, Any]] = []
    rerank_provider_used = "vector"

    if unique_contexts:
        cohere_reranked = _rerank_with_cohere(query, unique_contexts, top_k)
        if cohere_reranked:
            final_contexts = cohere_reranked
            rerank_provider_used = "cohere"
        else:
            flashrank_reranked = _rerank_with_flashrank(query, unique_contexts, top_k)
            if flashrank_reranked:
                final_contexts = flashrank_reranked
                rerank_provider_used = "flashrank"

    if not final_contexts:
        final_contexts = [dict(c) for c in unique_contexts[:top_k]]

    # Keep raw vector score available after reranking updates score.
    for ctx in final_contexts:
        if "vector_score" not in ctx:
            ctx["vector_score"] = float(ctx.get("score", 0.0) or 0.0)

    # Hybrid lexical fusion: blend lexical overlap with semantic/rerank score.
    final_contexts = _apply_lexical_fusion(query, final_contexts)
    final_contexts = final_contexts[:top_k]

    # Drop weak off-topic hits before handing context to the planner.
    final_contexts = _apply_anchor_relevance_filter(final_contexts, query)
    
    
    namespace = get_namespace(creator_id, twin_id)
    print(f"[Retrieval] Found {len(final_contexts)} contexts for twin_id={twin_id} (namespace={namespace})")
    if final_contexts:
        top_scores = [round(float(c.get("score", 0.0) or 0.0), 3) for c in final_contexts[:3]]
        print(f"[Retrieval] Top scores: {top_scores}")
    
    # Optional weak-score cutoff (disabled by default for better recall under constrained plans).
    max_score = max([float(c.get("score", 0.0) or 0.0) for c in final_contexts], default=0.0)
    if RETRIEVAL_MIN_ACCEPTED_SCORE > 0 and max_score < RETRIEVAL_MIN_ACCEPTED_SCORE and len(final_contexts) > 0:
        print(
            f"[Retrieval] Max score {max_score} < {RETRIEVAL_MIN_ACCEPTED_SCORE}. "
            "Triggering 'I don't know' logic."
        )
        return []
    elif len(final_contexts) == 0:
        return []

    
    # Add verified_qna_match flag (False since we didn't find verified match)
    for c in final_contexts:
        c["verified_qna_match"] = False
    
    # Log RAG metrics to Langfuse
    if _langfuse_available and final_contexts:
        try:
            langfuse_context.update_current_observation(
                metadata={
                    "doc_ids": [c.get("source_id", "unknown")[:50] for c in final_contexts],
                    "similarity_scores": [round(c.get("score", 0.0), 3) for c in final_contexts],
                    "chunk_lengths": [len(c.get("text", "")) for c in final_contexts],
                    "reranked": rerank_provider_used != "vector",
                    "rerank_provider": rerank_provider_used,
                    "cohere_rerank_enabled": _cohere_rerank_enabled,
                    "flashrank_enabled": _flashrank_enabled,
                    "lexical_fusion_enabled": RETRIEVAL_LEXICAL_FUSION_ENABLED,
                    "lexical_fusion_alpha": RETRIEVAL_LEXICAL_FUSION_ALPHA,
                    "top_k": top_k,
                    "total_retrieved": len(final_contexts),
                    "search_query_count": len(search_queries),
                    "search_queries": [q[:120] for q in search_queries],
                    "search_query_kinds": search_kinds,
                    "search_query_weights": [round(float(w), 3) for w in search_weights],
                }
            )
        except Exception as e:
            print(f"Langfuse observation update failed: {e}")
    
    return final_contexts


@observe(name="retrieval")
async def retrieve_context(
    query: str, 
    twin_id: str, 
    creator_id: Optional[str] = None,
    group_id: Optional[str] = None, 
    top_k: int = 5,
    resolve_default_group: bool = True,
):
    """
    Main retrieval function - uses verified-first order.
    Backward compatible wrapper around retrieve_context_with_verified_first.
    
    Args:
        query: Search query
        twin_id: Twin ID
        creator_id: Creator ID (for Delphi namespace format) - None for legacy
        group_id: Access group for filtering (optional)
        top_k: Number of results to return
    """
    return await retrieve_context_with_verified_first(
        query,
        twin_id,
        creator_id=creator_id,
        group_id=group_id,
        top_k=top_k,
        resolve_default_group=resolve_default_group,
    )


# =============================================================================
# PHASE 2 FIX: Health Check Function for Monitoring
# =============================================================================

async def get_retrieval_health_status(twin_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Get health status of the retrieval system.
    
    Args:
        twin_id: Optional twin ID to check namespace-specific health
        
    Returns:
        Dict with health status information
    """
    status = {
        "healthy": True,
        "components": {},
        "warnings": [],
        "errors": []
    }
    stats = None
    
    # Check 1: Pinecone connection
    try:
        index = get_pinecone_index()
        stats = index.describe_index_stats()
        status["components"]["pinecone"] = {
            "connected": True,
            "total_vectors": getattr(stats, "total_vector_count", 0),
            "namespaces": len(getattr(stats, "namespaces", {}) or {})
        }
    except Exception as e:
        status["healthy"] = False
        status["components"]["pinecone"] = {"connected": False, "error": str(e)}
        status["errors"].append(f"Pinecone connection failed: {e}")
    
    # Check 2: Embedding generation
    try:
        emb = await asyncio.wait_for(
            asyncio.to_thread(get_embedding, "health check"),
            timeout=min(RETRIEVAL_EMBEDDING_TIMEOUT, 5.0),
        )
        status["components"]["embeddings"] = {
            "working": True,
            "dimension": len(emb)
        }
    except Exception as e:
        status["healthy"] = False
        status["components"]["embeddings"] = {"working": False, "error": str(e)}
        status["errors"].append(f"Embedding generation failed: {e}")
    
    # Check 3: Namespace resolution (if twin_id provided)
    if twin_id:
        try:
            creator_id = resolve_creator_id_for_twin(twin_id)
            namespaces = get_namespace_candidates_for_twin(twin_id, include_legacy=True)
            
            # Check vector counts per namespace
            namespace_counts = {}
            namespace_stats = getattr(stats, "namespaces", {}) if stats is not None else {}
            for ns in namespaces:
                ns_obj = namespace_stats.get(ns) if isinstance(namespace_stats, dict) else None
                if isinstance(ns_obj, dict):
                    count = int(ns_obj.get("vector_count", 0) or 0)
                elif ns_obj is not None:
                    count = int(getattr(ns_obj, "vector_count", 0) or 0)
                else:
                    count = 0
                namespace_counts[ns] = count
            
            status["components"]["namespaces"] = {
                "creator_id": creator_id,
                "candidates": namespaces,
                "vector_counts": namespace_counts
            }
            
            # Warning if no vectors in any namespace
            if all(count == 0 for count in namespace_counts.values()):
                status["warnings"].append(f"No vectors found for twin {twin_id} in any namespace")
        except Exception as e:
            status["warnings"].append(f"Namespace resolution check failed: {e}")
    
    # Check 4: Configuration
    dual_read = os.getenv("DELPHI_DUAL_READ", "true").lower() == "true"
    status["configuration"] = {
        "delphi_dual_read": dual_read,
        "flashrank_enabled": _flashrank_enabled,
        "flashrank_available": _flashrank_available,
        "cohere_rerank_enabled": _cohere_rerank_enabled,
        "cohere_rerank_model": _cohere_rerank_model,
        "lexical_fusion_enabled": RETRIEVAL_LEXICAL_FUSION_ENABLED,
        "lexical_fusion_alpha": RETRIEVAL_LEXICAL_FUSION_ALPHA,
        "query_prep_timeout_s": RETRIEVAL_QUERY_PREP_TIMEOUT,
        "embedding_timeout_s": RETRIEVAL_EMBEDDING_TIMEOUT,
        "vector_timeout_s": RETRIEVAL_VECTOR_TIMEOUT,
        "per_namespace_timeout_s": RETRIEVAL_PER_NAMESPACE_TIMEOUT,
        "index_init_timeout_s": RETRIEVAL_INDEX_INIT_TIMEOUT,
    }
    
    if not dual_read:
        status["warnings"].append("DELPHI_DUAL_READ is disabled - legacy namespaces may not be queried")
    
    return status
