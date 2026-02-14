import os
import asyncio
import time
import logging
import json
from typing import List, Dict, Any, Optional, Set
from contextlib import contextmanager
from modules.clients import get_openai_client, get_pinecone_index, get_cohere_client
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
RETRIEVAL_EMBEDDING_TIMEOUT = _float_env("RETRIEVAL_EMBEDDING_TIMEOUT_SECONDS", 8.0)
RETRIEVAL_VECTOR_TIMEOUT = _float_env("RETRIEVAL_VECTOR_TIMEOUT_SECONDS", 8.0)
RETRIEVAL_PER_NAMESPACE_TIMEOUT = _float_env("RETRIEVAL_PER_NAMESPACE_TIMEOUT_SECONDS", 5.0)
RETRIEVAL_MAX_SEARCH_QUERIES = max(1, _int_env("RETRIEVAL_MAX_SEARCH_QUERIES", 3))


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

# FlashRank for local reranking
try:
    from flashrank import Ranker, RerankRequest
    _flashrank_available = True
    # Cache the ranker instance
    _ranker_instance = None
except ImportError:
    _flashrank_available = False
    _ranker_instance = None

def get_ranker():
    """Lazy load FlashRank to avoid startup overhead."""
    global _ranker_instance
    if _flashrank_available and _ranker_instance is None:
        try:
            # Use a lightweight model
            _ranker_instance = Ranker(model_name="ms-marco-MiniLM-L-12-v2", cache_dir="./.model_cache")
        except Exception as e:
            print(f"Failed to initialize FlashRank: {e}")
    return _ranker_instance


# Langfuse v3 tracing
try:
    from langfuse import observe
    import langfuse
    _langfuse_available = True
except ImportError:
    _langfuse_available = False
    def observe(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

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


def rrf_merge(results_list: List[List[Dict[str, Any]]], k: int = 60) -> List[Dict[str, Any]]:
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
    
    for results in results_list:
        for rank, hit in enumerate(results, start=1):
            doc_id = hit.get("id", str(hit))
            score_map[doc_id] = score_map.get(doc_id, 0.0) + 1.0 / (k + rank)
    
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
        if status not in {"active", "verified"}:
            return None

        score = float(best.get("_score", 0.0) or 0.0)
        confidence = float(best.get("confidence", 0.0) or 0.0)
        # Keep threshold strict to avoid accidental overreach on weak matches.
        if score < 0.82 and confidence < 0.85:
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

    index = get_pinecone_index()

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
        top_k = 5 if is_verified else 20

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

            return await asyncio.wait_for(
                asyncio.to_thread(_fetch),
                timeout=RETRIEVAL_PER_NAMESPACE_TIMEOUT,
            )

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

        # Hotfix: if all namespaces timed out/failed, retry once against primary namespace
        # with an extended timeout to avoid false "no knowledge" responses.
        if not merged_matches and failed_namespaces and len(failed_namespaces) == len(namespace_candidates):
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
                    timeout=max(RETRIEVAL_PER_NAMESPACE_TIMEOUT * 2.0, 8.0),
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
                "source_id": match["metadata"].get("source_id", "verified_memory"),
                "is_verified": True,
                "category": match["metadata"].get("category", "FACT"),
                "tone": match["metadata"].get("tone", "Assertive"),
                "opinion_topic": match["metadata"].get("opinion_topic"),
                "opinion_stance": match["metadata"].get("opinion_stance"),
                "opinion_intensity": match["metadata"].get("opinion_intensity")
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
            "rrf_score": rrf_score,
            "source_id": match["metadata"].get("source_id", "unknown"),
            "chunk_id": match["metadata"].get("chunk_id", "unknown"),
            "is_verified": False,
            "category": match["metadata"].get("category", "FACT"),
            "tone": match["metadata"].get("tone", "Neutral"),
            "opinion_topic": match["metadata"].get("opinion_topic"),
            "opinion_stance": match["metadata"].get("opinion_stance"),
            "opinion_intensity": match["metadata"].get("opinion_intensity")
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
    top_k: int = 5
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
    
    # Resolve group_id to default if None
    if group_id is None:
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
    expanded_queries: List[str] = [query]
    hyde_answer = query
    try:
        prep_results = await asyncio.wait_for(
            asyncio.gather(
                expand_query(query),
                generate_hyde_answer(query),
                return_exceptions=True,
            ),
            timeout=RETRIEVAL_QUERY_PREP_TIMEOUT,
        )
        expanded_raw, hyde_raw = prep_results
        if isinstance(expanded_raw, list):
            expanded_queries = [q for q in expanded_raw if isinstance(q, str) and q.strip()] or [query]
        if isinstance(hyde_raw, str) and hyde_raw.strip():
            hyde_answer = hyde_raw.strip()
    except asyncio.TimeoutError:
        print(f"[Retrieval] Query preparation timed out after {RETRIEVAL_QUERY_PREP_TIMEOUT}s, using original query")
    except Exception as e:
        print(f"[Retrieval] Query preparation failed: {e}, using original query")

    search_queries: List[str] = []
    for candidate in [query, hyde_answer] + expanded_queries:
        c = (candidate or "").strip()
        if c and c not in search_queries:
            search_queries.append(c)
        if len(search_queries) >= RETRIEVAL_MAX_SEARCH_QUERIES:
            break
    if not search_queries:
        search_queries = [query]
    
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
    
    # 3. Parallel Vector Search with bounded timeout.
    all_results = await _execute_pinecone_queries(
        all_embeddings,
        twin_id,
        creator_id=creator_id,
        timeout=RETRIEVAL_VECTOR_TIMEOUT,
    )
    
    if not all_results:
        return []
    
    verified_results = all_results[0]
    general_results_list = [res["matches"] for res in all_results[1:]]
    
    # 4. RRF Merge general results
    merged_general_hits = rrf_merge(general_results_list)
    
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

    final_contexts = []
    ranker = get_ranker()
    # ranker = None # FORCE DISABLE
    
    if ranker and unique_contexts:
        try:
            # Prepare for reranking
            passages = [
                {"id": str(i), "text": c["text"], "meta": c} 
                for i, c in enumerate(unique_contexts)
            ]
            
            rerank_request = RerankRequest(query=query, passages=passages)
            results = ranker.rerank(rerank_request)

            max_rerank_score = max((float(res.get("score", 0) or 0) for res in results), default=0)
            if max_rerank_score < 0.001:
                print("[Retrieval] Rerank scores too low. Using vector scores.")
                final_contexts = unique_contexts[:top_k]
            else:
                # Reconstruct sorted contexts
                for res in results:
                    original_idx = int(res["id"])
                    ctx = unique_contexts[original_idx]
                    ctx["score"] = float(res.get("score", 0.0) or 0.0) # Update score with rerank score
                    final_contexts.append(ctx)
                
                # Limit to requested top_k
                final_contexts = final_contexts[:top_k]
                print(f"[Retrieval] Reranked {len(unique_contexts)} -> {len(final_contexts)} contexts")
        except Exception as e:
            print(f"[Retrieval] Reranking failed: {e}. Falling back to vector scores.")
            final_contexts = unique_contexts[:top_k]
    else:
        # Fallback if no ranker
        final_contexts = unique_contexts[:top_k]

    
    namespace = get_namespace(creator_id, twin_id)
    print(f"[Retrieval] Found {len(final_contexts)} contexts for twin_id={twin_id} (namespace={namespace})")
    if final_contexts:
        top_scores = [round(float(c.get("score", 0.0) or 0.0), 3) for c in final_contexts[:3]]
        print(f"[Retrieval] Top scores: {top_scores}")
    
    # Check if retrieval is too weak - signal for "I don't know" response
    # Threshold lowered to 0.001 for calibration (FlashRank scores might be low logits or unnormalized)
    max_score = max([float(c.get("score", 0.0) or 0.0) for c in final_contexts], default=0.0)
    if max_score < 0.001 and len(final_contexts) > 0:
        print(f"[Retrieval] Max score {max_score} < 0.001. Triggering 'I don't know' logic.")
        return []
    elif len(final_contexts) == 0:
        return []

    
    # Add verified_qna_match flag (False since we didn't find verified match)
    for c in final_contexts:
        c["verified_qna_match"] = False
    
    # Log RAG metrics to Langfuse
    cohere_client = get_cohere_client()
    if _langfuse_available and final_contexts:
        try:
            langfuse.update_current_observation(
                metadata={
                    "doc_ids": [c.get("source_id", "unknown")[:50] for c in final_contexts],
                    "similarity_scores": [round(c.get("score", 0.0), 3) for c in final_contexts],
                    "chunk_lengths": [len(c.get("text", "")) for c in final_contexts],
                    "reranked": cohere_client is not None,
                    "top_k": top_k,
                    "total_retrieved": len(final_contexts),
                }
            )
        except Exception as e:
            print(f"Langfuse observation update failed: {e}")
    
    return final_contexts


async def retrieve_context(
    query: str, 
    twin_id: str, 
    creator_id: Optional[str] = None,
    group_id: Optional[str] = None, 
    top_k: int = 5
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
        query, twin_id, creator_id=creator_id, group_id=group_id, top_k=top_k
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
        "flashrank_available": _flashrank_available,
        "query_prep_timeout_s": RETRIEVAL_QUERY_PREP_TIMEOUT,
        "embedding_timeout_s": RETRIEVAL_EMBEDDING_TIMEOUT,
        "vector_timeout_s": RETRIEVAL_VECTOR_TIMEOUT,
        "per_namespace_timeout_s": RETRIEVAL_PER_NAMESPACE_TIMEOUT,
    }
    
    if not dual_read:
        status["warnings"].append("DELPHI_DUAL_READ is disabled - legacy namespaces may not be queried")
    
    return status
