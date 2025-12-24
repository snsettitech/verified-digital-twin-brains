import os
import asyncio
from typing import List, Dict, Any, Optional
from modules.clients import get_openai_client, get_pinecone_index, get_cohere_client
from modules.verified_qna import match_verified_qna
from modules.observability import supabase
from modules.access_groups import get_default_group

def get_embedding(text: str):
    """
    Synchronous embedding call for backward compatibility if needed.
    """
    client = get_openai_client()
    response = client.embeddings.create(
        input=text,
        model="text-embedding-3-large",
        dimensions=3072
    )
    return response.data[0].embedding

async def get_embeddings_async(texts: List[str]) -> List[List[float]]:
    """
    Batch gets embeddings for a list of texts asynchronously.
    """
    client = get_openai_client()
    loop = asyncio.get_event_loop()
    
    # OpenAI client is thread-safe, we use run_in_executor for the blocking network call
    def _fetch():
        response = client.embeddings.create(
            input=texts,
            model="text-embedding-3-large",
            dimensions=3072
        )
        return [d.embedding for d in response.data]
        
    return await loop.run_in_executor(None, _fetch)

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
    Reciprocal Rank Fusion to merge multiple ranked lists.
    """
    rrf_scores = {}
    doc_map = {}
    
    for results in results_list:
        for rank, hit in enumerate(results):
            # Use text content as key for deduplication
            doc_id = hit["metadata"].get("text", "")
            if not doc_id:
                continue
                
            if doc_id not in rrf_scores:
                rrf_scores[doc_id] = 0
                doc_map[doc_id] = hit
                
            rrf_scores[doc_id] += 1.0 / (k + rank + 1)
            
    # Sort by RRF score
    sorted_docs = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
    
    final_results = []
    for doc_id in sorted_docs:
        hit = doc_map[doc_id]
        hit["rrf_score"] = rrf_scores[doc_id]
        final_results.append(hit)
        
    return final_results

async def retrieve_context_with_verified_first(query: str, twin_id: str, group_id: Optional[str] = None, top_k: int = 5):
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
    
    # STEP 1: Check Verified QnA first (highest priority)
    verified_match = await match_verified_qna(query, twin_id, group_id=group_id, use_exact=True, use_semantic=False, exact_threshold=0.7)
    
    if verified_match and verified_match.get("similarity_score", 0) >= 0.7:
        # Found a high-confidence verified answer - return immediately
        return [{
            "text": verified_match["answer"],
            "score": 1.0,  # Perfect confidence for verified answers
            "source_id": f"verified_qna_{verified_match['id']}",
            "is_verified": True,
            "verified_qna_match": True,
            "question": verified_match["question"],
            "category": "FACT",
            "tone": "Assertive",
            "citations": verified_match.get("citations", [])
        }]
    
    # STEP 2: No verified match - proceed with vector retrieval
    return await retrieve_context_vectors(query, twin_id, group_id=group_id, top_k=top_k)


async def retrieve_context_vectors(query: str, twin_id: str, group_id: Optional[str] = None, top_k: int = 5):
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
    
    # 3. Parallel Vector Search
    index = get_pinecone_index()
    loop = asyncio.get_event_loop()
    
    async def pinecone_query(embedding, is_verified=False):
        tk = 5 if is_verified else 20
        filter_dict = {"is_verified": {"$eq": True}} if is_verified else {"is_verified": {"$ne": True}}
        
        def _fetch():
            return index.query(
                vector=embedding,
                top_k=tk,
                include_metadata=True,
                namespace=twin_id,
                filter=filter_dict
            )
        return await loop.run_in_executor(None, _fetch)

    # Use original query for verified search
    verified_task = pinecone_query(all_embeddings[0], is_verified=True)
    
    # Use all variations for general search
    general_tasks = [pinecone_query(emb, is_verified=False) for emb in all_embeddings]
    
    all_results = await asyncio.gather(verified_task, *general_tasks)
    
    verified_results = all_results[0]
    general_results_list = [res["matches"] for res in all_results[1:]]
    
    # 4. RRF Merge general results
    merged_general_hits = rrf_merge(general_results_list)
    
    contexts = []
    
    # Process verified matches
    for match in verified_results["matches"]:
        if match["score"] > 0.3:
            contexts.append({
                "text": match["metadata"]["text"],
                "score": 1.0, # Boost verified
                "source_id": match["metadata"].get("source_id", "verified_memory"),
                "is_verified": True,
                "category": match["metadata"].get("category", "FACT"),
                "tone": match["metadata"].get("tone", "Assertive"),
                "opinion_topic": match["metadata"].get("opinion_topic"),
                "opinion_stance": match["metadata"].get("opinion_stance"),
                "opinion_intensity": match["metadata"].get("opinion_intensity")
            })
    
    # Process general matches for reranking
    raw_general_chunks = []
    for match in merged_general_hits:
        raw_general_chunks.append({
            "text": match["metadata"]["text"],
            "score": match.get("score", 0.0),
            "rrf_score": match.get("rrf_score", 0.0),
            "source_id": match["metadata"].get("source_id", "unknown"),
            "is_verified": False,
            "category": match["metadata"].get("category", "FACT"),
            "tone": match["metadata"].get("tone", "Neutral"),
            "opinion_topic": match["metadata"].get("opinion_topic"),
            "opinion_stance": match["metadata"].get("opinion_stance"),
            "opinion_intensity": match["metadata"].get("opinion_intensity")
        })
    
    # Filter by group permissions if group_id is provided
    if group_id:
        # Get allowed source_ids for this group (convert to strings for comparison)
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
        
        contexts = filtered_contexts
        
        # Also filter raw_general_chunks for reranking
        filtered_raw_chunks = []
        for c in raw_general_chunks:
            source_id = str(c.get("source_id", ""))
            is_verified = c.get("is_verified", False)
            
            if is_verified or source_id in allowed_source_ids:
                filtered_raw_chunks.append(c)
        
        raw_general_chunks = filtered_raw_chunks
    
    # 5. Reranking Step
    cohere_client = get_cohere_client()
    if cohere_client and raw_general_chunks:
        try:
            print(f"Reranking {len(raw_general_chunks[:30])} chunks with Cohere...")
            documents = [c["text"] for c in raw_general_chunks[:30]]
            
            def _rerank():
                return cohere_client.rerank(
                    model="rerank-v3.5",
                    query=query,
                    documents=documents,
                    top_n=top_k
                )
                
            rerank_res = await loop.run_in_executor(None, _rerank)
            
            reranked_contexts = []
            for result in rerank_res.results:
                original_chunk = raw_general_chunks[result.index]
                original_chunk["score"] = result.relevance_score
                reranked_contexts.append(original_chunk)
            
            contexts.extend(reranked_contexts)
        except Exception as e:
            print(f"Error during reranking: {e}. Falling back to RRF order.")
            contexts.extend(raw_general_chunks[:top_k])
    else:
        contexts.extend(raw_general_chunks[:top_k])
    
    # Final Deduplicate and limit
    final_contexts = []
    seen_final = set()
    for c in contexts:
        if c["text"] not in seen_final:
            seen_final.add(c["text"])
            final_contexts.append(c)
            
    final_contexts = final_contexts[:top_k]
    
    print(f"Found {len(final_contexts)} contexts for {twin_id}")
    
    # Check if retrieval is too weak - signal for "I don't know" response
    max_score = max([c.get("score", 0.0) for c in final_contexts], default=0.0)
    if max_score < 0.5 and len(final_contexts) == 0:
        # Return empty with flag for "I don't know"
        return []
    
    # Add verified_qna_match flag (False since we didn't find verified match)
    for c in final_contexts:
        c["verified_qna_match"] = False
    
    return final_contexts


async def retrieve_context(query: str, twin_id: str, group_id: Optional[str] = None, top_k: int = 5):
    """
    Main retrieval function - uses verified-first order.
    Backward compatible wrapper around retrieve_context_with_verified_first.
    """
    return await retrieve_context_with_verified_first(query, twin_id, group_id=group_id, top_k=top_k)
