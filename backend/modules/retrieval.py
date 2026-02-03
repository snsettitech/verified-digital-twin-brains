import os
import asyncio
from typing import List, Dict, Any, Optional, Set
from modules.clients import get_openai_client, get_pinecone_index, get_cohere_client
from modules.verified_qna import match_verified_qna
from modules.observability import supabase
from modules.access_groups import get_default_group

# Embedding generation moved to modules.embeddings
# Embedding generation moved to modules.embeddings
from modules.embeddings import get_embedding, get_embeddings_async

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
                temperature=0.7
            )
            
        response = await loop.run_in_executor(None, _fetch)
        content = response.choices[0].message.content
        variations = [line.strip().lstrip("-*•123. ").strip() for line in content.split("\n") if line.strip()]
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
                temperature=0.3
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
    timeout: float = 5.0
) -> List[Dict[str, Any]]:
    """
    Execute Pinecone queries for all embeddings.
    
    Args:
        embeddings: List of embedding vectors
        twin_id: Twin ID (namespace)
        timeout: Timeout in seconds
        
    Returns:
        List of query results
    """
    index = get_pinecone_index()
    loop = asyncio.get_event_loop()
    
    async def pinecone_query(embedding: List[float], is_verified: bool = False) -> Dict[str, Any]:
        """Execute a single Pinecone query."""
        top_k = 5 if is_verified else 20
        
        def _fetch():
            query_params = {
                "vector": embedding,
                "top_k": top_k,
                "include_metadata": True,
                "namespace": twin_id,
            }
            # Only filter for verified search
            # For general search, don't filter - search all vectors in namespace
            # This ensures sources without is_verified field are included
            if is_verified:
                query_params["filter"] = {"is_verified": {"$eq": True}}
            
            return index.query(**query_params)
        return await loop.run_in_executor(None, _fetch)
    
    # Use original query for verified search
    verified_task = pinecone_query(embeddings[0], is_verified=True)
    
    # Use all variations for general search
    general_tasks = [pinecone_query(emb, is_verified=False) for emb in embeddings]
    
    try:
        all_results = await asyncio.wait_for(
            asyncio.gather(verified_task, *general_tasks),
            timeout=timeout
        )
        return all_results
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
        raw_general_chunks.append({
            "text": match["metadata"]["text"],
            "score": match.get("score", 0.0),
            "rrf_score": match.get("rrf_score", 0.0),
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
    
    # Filter contexts to only include chunks from allowed sources
    # Also allow verified memory (is_verified=True chunks) - they're always accessible
    filtered_contexts = []
    for c in contexts:
        source_id = str(c.get("source_id", ""))
        is_verified = c.get("is_verified", False)
        
        # Allow if verified memory OR if source_id matches an allowed source
        if is_verified or source_id in allowed_source_ids:
            filtered_contexts.append(c)
    
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
    group_id: Optional[str] = None,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Retrieval pipeline with verified-first order: Check verified QnA → vectors → tools.
    Returns contexts with verified_qna_match flag if verified answer found.
    If group_id is None, uses default group for backward compatibility.
    """
    # Resolve group_id to default if None
    if group_id is None:
        try:
            default_group = await get_default_group(twin_id)
            group_id = default_group["id"]
        except Exception:
            # If no default group exists, proceed without group filtering (backward compatibility)
            group_id = None
    
    # STEP 1: Check Verified QnA first (highest priority) - P1-C: 2s timeout
    try:
        verified_match = await asyncio.wait_for(
            match_verified_qna(query, twin_id, group_id=group_id, use_exact=True, use_semantic=True, exact_threshold=0.7, semantic_threshold=0.75),
            timeout=2.0
        )
    except asyncio.TimeoutError:
        print(f"[Retrieval] Verified QnA lookup timed out after 2s, falling back to vector retrieval")
        verified_match = None
    except Exception as e:
        print(f"[Retrieval] Verified QnA lookup failed: {e}, falling back to vector retrieval")
        verified_match = None
    
    if verified_match and verified_match.get("similarity_score", 0) >= 0.7:
        # Found a high-confidence verified answer - return immediately
        return [_format_verified_match_context(verified_match)]
    
    # STEP 2: No verified match - proceed with vector retrieval
    return await retrieve_context_vectors(query, twin_id, group_id=group_id, top_k=top_k)


@observe(name="rag_vector_retrieval")
async def retrieve_context_vectors(
    query: str,
    twin_id: str,
    group_id: Optional[str] = None,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Optimized retrieval pipeline using HyDE, Query Expansion, and RRF (vector-only).
    Used when no verified QnA match is found.
    If group_id is provided, filters results by group permissions.
    """
    # 1. Parallel Query Expansion & HyDE
    expanded_task = expand_query(query)
    hyde_task = generate_hyde_answer(query)
    
    expanded_queries, hyde_answer = await asyncio.gather(expanded_task, hyde_task)
    
    search_queries = list(set([query, hyde_answer] + expanded_queries))
    
    # 2. Parallel Embedding Generation (Batch)
    all_embeddings = await get_embeddings_async(search_queries)
    
    # 3. Parallel Vector Search - P1-C: 20s timeout (increased for debugging)
    all_results = await _execute_pinecone_queries(all_embeddings, twin_id, timeout=20.0)
    
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

            max_rerank_score = max((res.get("score", 0) for res in results), default=0)
            if max_rerank_score < 0.001:
                print("[Retrieval] Rerank scores too low. Using vector scores.")
                final_contexts = unique_contexts[:top_k]
            else:
                # Reconstruct sorted contexts
                for res in results:
                    original_idx = int(res["id"])
                    ctx = unique_contexts[original_idx]
                    ctx["score"] = res["score"] # Update score with rerank score
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

    
    print(f"[Retrieval] Found {len(final_contexts)} contexts for twin_id={twin_id} (namespace={twin_id})")
    if final_contexts:
        top_scores = [round(c.get("score", 0.0), 3) for c in final_contexts[:3]]
        print(f"[Retrieval] Top scores: {top_scores}")
    
    # Check if retrieval is too weak - signal for "I don't know" response
    # Threshold lowered to 0.001 for calibration (FlashRank scores might be low logits or unnormalized)
    max_score = max([c.get("score", 0.0) for c in final_contexts], default=0.0)
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


async def retrieve_context(query: str, twin_id: str, group_id: Optional[str] = None, top_k: int = 5):
    """
    Main retrieval function - uses verified-first order.
    Backward compatible wrapper around retrieve_context_with_verified_first.
    """
    return await retrieve_context_with_verified_first(query, twin_id, group_id=group_id, top_k=top_k)
