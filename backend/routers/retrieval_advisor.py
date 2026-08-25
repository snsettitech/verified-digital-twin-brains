"""
Retrieval Router with advisor creator-based namespaces.

This router keeps strict tenant isolation while enabling creator-scoped
namespace operations.
"""
from typing import Any, Dict, List, Optional
import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from modules.auth_guard import require_tenant, verify_twin_ownership
from modules.embeddings_advisor import get_advisor_client
from modules.retrieval import retrieve_context_with_verified_first
from modules.tenant_guard import (
    TenantAuditLogger,
    TenantGuard,
    require_creator_access,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/retrieval", tags=["retrieval"])
audit_logger = TenantAuditLogger()


class RetrievalRequest(BaseModel):
    twin_id: Optional[str] = None
    creator_id: Optional[str] = None
    query: Optional[str] = None
    vector: Optional[List[float]] = None
    top_k: int = 10
    strategy_hint: Optional[str] = None
    namespace: Optional[str] = None
    filter: Optional[dict] = None

    @model_validator(mode="after")
    def check_input(self):
        if self.query is None and self.vector is None:
            raise ValueError("Either query or vector must be provided")
        # Legacy compatibility for callers that still send creator_id where twin_id is expected.
        if self.query is not None and self.twin_id is None and self.creator_id is not None:
            self.twin_id = self.creator_id
        return self


class QueryAcrossTwinsRequest(BaseModel):
    vector: List[float]
    creator_id: str
    twin_ids: List[str]
    top_k: int = 10


class RetrievalResult(BaseModel):
    source_id: Optional[str] = None
    text: str = ""
    score: float = 0.0
    strategy_name: Optional[str] = Field(default="vector")
    namespace: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class QueryResponse(BaseModel):
    results: List[RetrievalResult]
    query_used: str
    total: int


class DeletionRequest(BaseModel):
    creator_id: str
    twin_id: Optional[str] = None
    gdpr_request: bool = False


class DeletionResponse(BaseModel):
    success: bool
    deleted_count: int
    namespace: str


def _match_to_dict(match: Any) -> Dict[str, Any]:
    """
    Normalize Pinecone match object to dict.
    """
    if isinstance(match, dict):
        return {
            "id": match.get("id"),
            "score": match.get("score"),
            "metadata": match.get("metadata"),
        }
    return {
        "id": getattr(match, "id", None),
        "score": getattr(match, "score", None),
        "metadata": getattr(match, "metadata", None),
    }


def _extract_matches(result: Any) -> List[Any]:
    if isinstance(result, dict):
        return result.get("matches", []) or []
    return getattr(result, "matches", []) or []


def _normalize_result_row(
    row: Dict[str, Any],
    *,
    default_namespace: Optional[str] = None,
    default_strategy: str = "vector",
) -> Dict[str, Any]:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    namespace = (
        row.get("namespace")
        or metadata.get("namespace")
        or default_namespace
    )
    text = (
        row.get("text")
        or metadata.get("text")
        or metadata.get("chunk_text")
        or metadata.get("content")
        or ""
    )
    source_id = (
        row.get("source_id")
        or metadata.get("source_id")
        or row.get("id")
        or metadata.get("id")
    )
    strategy_name = (
        row.get("strategy_name")
        or metadata.get("strategy_name")
        or default_strategy
    )
    return {
        "source_id": source_id,
        "text": text,
        "score": float(row.get("score") or metadata.get("score") or 0.0),
        "strategy_name": strategy_name,
        "namespace": namespace,
        "metadata": metadata,
    }


def _apply_strategy_hint(
    results: List[Dict[str, Any]],
    strategy_hint: Optional[str],
) -> List[Dict[str, Any]]:
    if not strategy_hint:
        return results
    filtered = [
        row for row in results
        if str(row.get("strategy_name") or "").strip().lower() == strategy_hint.strip().lower()
    ]
    return filtered


@router.post("/query", response_model=QueryResponse)
async def query_vectors(
    request: RetrievalRequest,
    current_user: dict = Depends(require_tenant),
):
    """
    Query retrieval results with either a text query or a precomputed vector.
    """
    start_time = time.time()

    try:
        guard = TenantGuard(current_user)
        query_used = (request.query or "").strip()

        if request.query is not None:
            if not request.twin_id:
                raise HTTPException(status_code=422, detail="twin_id is required when query is provided")
            verify_twin_ownership(request.twin_id, current_user)
            raw_results = await retrieve_context_with_verified_first(
                query=request.query,
                twin_id=request.twin_id,
                creator_id=request.creator_id,
                top_k=request.top_k,
                resolve_default_group=False,
            )
            normalized_results = [
                _normalize_result_row(result, default_strategy="vector")
                for result in raw_results
            ]
        else:
            creator_scope = request.creator_id or request.twin_id
            if not creator_scope:
                raise HTTPException(status_code=422, detail="creator_id or twin_id is required when vector is provided")
            if request.creator_id:
                guard.validate_creator_access(request.creator_id)
            client = get_advisor_client()
            vector_result = client.query(
                vector=request.vector,
                creator_id=creator_scope,
                twin_id=request.twin_id if request.creator_id else None,
                top_k=request.top_k,
                filter=request.filter,
                include_metadata=True,
            )
            raw_matches = _extract_matches(vector_result)
            filtered_matches = guard.filter_results_by_tenant(raw_matches)
            default_namespace = request.namespace or client.get_namespace(creator_scope, request.twin_id if request.creator_id else None)
            normalized_results = [
                _normalize_result_row(_match_to_dict(match), default_namespace=default_namespace, default_strategy="vector")
                for match in filtered_matches
            ]

        normalized_results = _apply_strategy_hint(normalized_results, request.strategy_hint)

        latency_ms = (time.time() - start_time) * 1000
        audit_logger.log_vector_query(
            user_id=current_user.get("user_id") or current_user.get("id"),
            creator_id=request.creator_id or request.twin_id or "unknown",
            twin_id=request.twin_id,
            top_k=request.top_k,
            result_count=len(normalized_results),
            latency_ms=latency_ms,
        )

        return QueryResponse(
            results=normalized_results,
            query_used=query_used,
            total=len(normalized_results),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"advisor query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.post("/query-across-twins")
@require_creator_access(creator_id_param="creator_id")
async def query_across_twins(
    request: QueryAcrossTwinsRequest,
    current_user: dict = Depends(require_tenant),
):
    """
    Query across multiple twin namespaces for a creator.
    """
    start_time = time.time()
    client = get_advisor_client()

    try:
        matches = client.query_across_twins(
            vector=request.vector,
            creator_id=request.creator_id,
            twin_ids=request.twin_ids,
            top_k=request.top_k,
            include_metadata=True,
        )
        guard = TenantGuard(current_user)
        filtered = guard.filter_results_by_tenant(matches)
        normalized = [_match_to_dict(m) for m in filtered]

        latency_ms = (time.time() - start_time) * 1000
        audit_logger.log_vector_query(
            user_id=current_user.get("user_id") or current_user.get("id"),
            creator_id=request.creator_id,
            twin_id=f"multiple:{len(request.twin_ids)}",
            top_k=request.top_k,
            result_count=len(normalized),
            latency_ms=latency_ms,
        )

        return {
            "matches": normalized,
            "twins_queried": len(request.twin_ids),
            "latency_ms": round(latency_ms, 2),
        }
    except Exception as e:
        logger.error(f"advisor multi-twin query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.delete("/delete-twin", response_model=DeletionResponse)
@require_creator_access(creator_id_param="creator_id")
async def delete_twin(
    request: DeletionRequest,
    current_user: dict = Depends(require_tenant),
):
    if not request.twin_id:
        raise HTTPException(status_code=400, detail="twin_id is required")

    client = get_advisor_client()
    try:
        stats = client.get_twin_stats(request.creator_id, request.twin_id)
        count_before = stats.get("vector_count", 0)
        success = client.delete_twin(request.creator_id, request.twin_id)
        if not success:
            raise HTTPException(status_code=500, detail="Deletion failed")

        audit_logger.log_data_deletion(
            user_id=current_user.get("user_id") or current_user.get("id"),
            creator_id=request.creator_id,
            twin_id=request.twin_id,
            vector_count=count_before,
            gdpr_request=request.gdpr_request,
        )
        return DeletionResponse(
            success=True,
            deleted_count=count_before,
            namespace=client.get_namespace(request.creator_id, request.twin_id),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"advisor twin deletion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")


@router.delete("/delete-creator")
@require_creator_access(creator_id_param="creator_id")
async def delete_creator_data(
    request: DeletionRequest,
    current_user: dict = Depends(require_tenant),
):
    """
    Delete all creator namespaces (GDPR).
    """
    client = get_advisor_client()
    try:
        twins = client.list_creator_twins(request.creator_id)
        vector_count = sum(int(t.get("vector_count", 0)) for t in twins)
        success = client.delete_creator_data(request.creator_id)
        verified = client.verify_gdpr_deletion(request.creator_id)

        if not success or not verified:
            raise HTTPException(status_code=500, detail="Creator deletion verification failed")

        audit_logger.log_data_deletion(
            user_id=current_user.get("user_id") or current_user.get("id"),
            creator_id=request.creator_id,
            twin_id=None,
            vector_count=vector_count,
            gdpr_request=True,
        )
        return {
            "success": True,
            "creator_id": request.creator_id,
            "namespaces_deleted": len(twins),
            "vectors_deleted": vector_count,
            "gdpr_verified": verified,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"advisor creator deletion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")


@router.get("/twins/{creator_id}")
async def list_creator_twins(
    creator_id: str,
    current_user: dict = Depends(require_tenant),
):
    guard = TenantGuard(current_user)
    try:
        guard.validate_creator_access(creator_id)
        client = get_advisor_client()
        twins = client.list_creator_twins(creator_id)
        return {
            "creator_id": creator_id,
            "twins": twins,
            "count": len(twins),
        }
    except Exception as e:
        logger.error(f"List creator twins failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list twins: {str(e)}")


@router.get("/stats/{creator_id}")
async def get_creator_stats(
    creator_id: str,
    current_user: dict = Depends(require_tenant),
):
    guard = TenantGuard(current_user)
    try:
        guard.validate_creator_access(creator_id)
        client = get_advisor_client()
        twins = client.list_creator_twins(creator_id)
        total_vectors = sum(int(t.get("vector_count", 0)) for t in twins)
        return {
            "creator_id": creator_id,
            "total_twins": len(twins),
            "total_vectors": total_vectors,
            "namespaces": [t["namespace"] for t in twins],
        }
    except Exception as e:
        logger.error(f"Get creator stats failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.get("/health")
async def advisor_health():
    """
    Minimal health check for creator namespace retrieval service.
    """
    try:
        client = get_advisor_client()
        client.index.describe_index_stats()
        return {
            "status": "healthy",
        }
    except Exception as e:
        logger.warning("advisor health check failed: %s", e)
        raise HTTPException(status_code=503, detail="Service unhealthy")
