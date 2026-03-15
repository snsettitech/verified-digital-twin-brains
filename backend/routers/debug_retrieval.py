
from fastapi import APIRouter, Depends, HTTPException, Body, Response
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from modules.retrieval import retrieve_context
from modules.auth_guard import get_current_user, verify_twin_ownership, ensure_twin_active
from modules.observability import supabase
import asyncio
import time
import os

router = APIRouter(
    prefix="/debug",
    tags=["debug"]
)

class RetrievalDebugRequest(BaseModel):
    query: str
    twin_id: str
    top_k: int = 10


def _normalize_json(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if (
        hasattr(value, "item")
        and callable(getattr(value, "item", None))
        and type(value).__module__.startswith("numpy")
    ):
        try:
            return _normalize_json(value.item())
        except Exception:
            pass
    if isinstance(value, list):
        return [_normalize_json(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalize_json(v) for k, v in value.items()}
    return str(value)


@router.post("/retrieval")
async def debug_retrieval(
    request: RetrievalDebugRequest,
    current_user: dict = Depends(get_current_user)
):
    print(f"[Debug Retrieval] Query: {request.query}, Twin: {request.twin_id}")
    
    try:
        verify_twin_ownership(request.twin_id, current_user)
        ensure_twin_active(request.twin_id)

        # Call the actual retrieval function
        contexts = await retrieve_context(request.query, request.twin_id, top_k=request.top_k)
        
        # Diagnostics: Check Group ID
        from modules.access_groups import get_default_group
        diagnostics = {}
        try:
            default_group = await get_default_group(request.twin_id)
            diagnostics["default_group_id"] = default_group["id"] if default_group else "None"
        except Exception as e:
            diagnostics["default_group_error"] = str(e)
            
        # Enrich with source filenames
        source_ids = list(set([c.get("source_id") for c in contexts if c.get("source_id") and c.get("source_id") != "verified_memory"]))
        
        source_map = {}
        if source_ids:
            try:
                # Use in_ filter for multiple IDs
                res = supabase.table("sources").select("id, filename").in_("id", source_ids).execute()
                for item in res.data:
                    source_map[item["id"]] = item["filename"]
            except Exception as e:
                print(f"[Debug Retrieval] Error fetching sources: {e}")
                
        # Add filenames and raw metadata to contexts for inspection
        for c in contexts:
            sid = c.get("source_id")
            if sid in source_map:
                c["source_filename"] = source_map[sid]
            
            # If verified memory, add virtual filename
            if c.get("is_verified") and not c.get("source_filename"):
                 c["source_filename"] = "🧠 Verified Memory (Q&A)"

        return {
            "query": request.query,
            "twin_id": request.twin_id,
            "results_count": len(contexts),
            "diagnostics": _normalize_json(diagnostics),
            "contexts": _normalize_json(contexts)
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# PHASE 2 FIX: Add health check endpoint
@router.get("/retrieval/health")
async def retrieval_health_check(
    twin_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Get health status of the retrieval system.
    
    Optionally provide a twin_id to check namespace-specific health.
    """
    from modules.retrieval import get_retrieval_health_status
    
    try:
        status = await get_retrieval_health_status(twin_id)
        return {
            "status": "healthy" if status["healthy"] else "unhealthy",
            "details": status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


# PHASE 3: Add namespace inspection endpoint
@router.get("/retrieval/namespaces/{twin_id}")
async def debug_namespaces(
    twin_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Inspect namespace configuration and vector counts for a twin.
    """
    from modules.twin_namespace import (
        resolve_creator_id_for_twin,
        get_namespace_candidates_for_twin,
        get_primary_namespace_for_twin,
        clear_creator_namespace_cache
    )
    from modules.clients import get_pinecone_index
    
    try:
        verify_twin_ownership(twin_id, current_user)
        
        # Clear cache for fresh lookup
        clear_creator_namespace_cache()
        
        # Resolve creator
        creator_id = resolve_creator_id_for_twin(twin_id, _bypass_cache=True)
        
        # Get namespace candidates
        candidates = get_namespace_candidates_for_twin(twin_id, include_legacy=True)
        primary = get_primary_namespace_for_twin(twin_id)
        
        # Get Pinecone stats
        index = get_pinecone_index()
        stats = index.describe_index_stats()
        
        # Check each namespace
        namespace_details = []
        for ns in candidates:
            ns_stats = stats.namespaces.get(ns, None)
            namespace_details.append({
                "namespace": ns,
                "vector_count": ns_stats.vector_count if ns_stats else 0,
                "exists": ns_stats is not None
            })
        
        return {
            "twin_id": twin_id,
            "creator_id": creator_id,
            "primary_namespace": primary,
            "dual_read_enabled": os.getenv("CREATOR_NAMESPACE_DUAL_READ", "true").lower() == "true",
            "namespaces": namespace_details,
            "pinecone_total_vectors": stats.total_vector_count,
            "pinecone_dimension": stats.dimension
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# PHASE 3: Add raw vector search endpoint
class VectorSearchRequest(BaseModel):
    query: str
    twin_id: str
    namespaces: Optional[List[str]] = None
    top_k: int = 10


@router.post("/retrieval/vector-search")
async def debug_vector_search(
    request: VectorSearchRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Perform raw vector search without the full retrieval pipeline.
    Useful for debugging embedding and Pinecone issues.
    """
    from modules.embeddings import get_embedding
    from modules.clients import get_pinecone_index
    from modules.twin_namespace import get_namespace_candidates_for_twin
    
    try:
        verify_twin_ownership(request.twin_id, current_user)
        
        results = {
            "query": request.query,
            "embedding": {},
            "searches": []
        }
        
        # Generate embedding
        start_time = asyncio.get_event_loop().time()
        embedding = get_embedding(request.query)
        embed_time = asyncio.get_event_loop().time() - start_time
        
        results["embedding"] = {
            "dimension": len(embedding),
            "time_seconds": embed_time,
            "sample": embedding[:5]
        }
        
        # Determine namespaces to search
        namespaces = request.namespaces
        if not namespaces:
            namespaces = get_namespace_candidates_for_twin(request.twin_id, include_legacy=True)
        
        # Search each namespace
        index = get_pinecone_index()
        
        for ns in namespaces:
            start_time = asyncio.get_event_loop().time()
            try:
                response = index.query(
                    vector=embedding,
                    top_k=request.top_k,
                    include_metadata=True,
                    namespace=ns
                )
                query_time = asyncio.get_event_loop().time() - start_time
                
                matches = []
                for match in response.matches:
                    matches.append({
                        "id": match.id,
                        "score": match.score,
                        "text_preview": match.metadata.get("text", "")[:100] if match.metadata else "",
                        "source_id": match.metadata.get("source_id", "unknown") if match.metadata else "unknown"
                    })
                
                results["searches"].append({
                    "namespace": ns,
                    "status": "success",
                    "time_seconds": query_time,
                    "matches_found": len(matches),
                    "matches": matches
                })
            except Exception as e:
                results["searches"].append({
                    "namespace": ns,
                    "status": "error",
                    "error": str(e)
                })
        
        return results
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# PHASE 3: Add embedding test endpoint
@router.post("/retrieval/test-embedding")
async def test_embedding(
    text: str = Body(..., embed=True),
    current_user: dict = Depends(get_current_user)
):
    """
    Test embedding generation for a given text.
    """
    from modules.embeddings import get_embedding, EMBEDDING_PROVIDER
    import time
    
    try:
        start = time.time()
        embedding = get_embedding(text)
        elapsed = time.time() - start
        
        return {
            "text": text,
            "provider": EMBEDDING_PROVIDER,
            "dimension": len(embedding),
            "time_seconds": elapsed,
            "embedding_sample": embedding[:10],
            "embedding_norm": sum(x**2 for x in embedding) ** 0.5
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding failed: {str(e)}")


# PHASE 4: Add metrics endpoint
@router.get("/retrieval/metrics")
async def retrieval_metrics(
    current_user: dict = Depends(get_current_user)
):
    """
    Get retrieval system metrics.
    """
    from modules.retrieval_metrics import get_metrics, get_phase_timing_stats, get_health_status
    
    return {
        "metrics": get_metrics(),
        "phase_timing": get_phase_timing_stats(),
        "health": get_health_status(),
        "timestamp": time.time()
    }


# PHASE 4: Add Prometheus metrics endpoint
@router.get("/retrieval/metrics/prometheus")
async def retrieval_metrics_prometheus(
    current_user: dict = Depends(get_current_user)
):
    """
    Get retrieval metrics in Prometheus format.
    """
    from modules.retrieval_metrics import get_prometheus_metrics
    
    from fastapi import Response
    return Response(
        content=get_prometheus_metrics(),
        media_type="text/plain"
    )


# PHASE 4: Reset metrics endpoint (for testing)
@router.post("/retrieval/metrics/reset")
async def reset_retrieval_metrics(
    current_user: dict = Depends(get_current_user)
):
    """
    Reset retrieval metrics (useful for testing).
    """
    from modules.retrieval_metrics import reset_metrics
    
    reset_metrics()
    return {"status": "metrics_reset"}
