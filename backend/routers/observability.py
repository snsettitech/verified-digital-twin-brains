import os
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from modules.auth_guard import get_current_user, verify_twin_ownership
from modules.clients import get_openai_client, get_pinecone_index
from modules.graph_memory_config import get_graph_memory_config
from modules.graph_memory_core import GraphMemoryCore
from modules.graph_outbox import get_graph_outbox
from modules.graph_snapshot_manager import refresh_twin_snapshot
from modules.name_deep_research_service import get_name_deep_research_service
from modules.observability import supabase

router = APIRouter(tags=["observability"])


class GraphSeedRequest(BaseModel):
    label: Optional[str] = None
    body: Optional[str] = None


def _neo4j_probe() -> Dict[str, Any]:
    uri = str(os.getenv("NEO4J_URI") or "").strip()
    user = str(os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME") or "").strip()
    password = str(os.getenv("NEO4J_PASSWORD") or "").strip()
    database = str(os.getenv("NEO4J_DATABASE") or "").strip() or None

    if not (uri and user and password):
        return {
            "status": "not_configured",
            "message": "Neo4j credentials are not configured in this environment.",
        }

    try:
        from neo4j import GraphDatabase
    except Exception as exc:
        return {
            "status": "error",
            "message": f"Neo4j driver unavailable: {exc}",
        }

    candidate_uris = [uri]
    if uri.startswith("neo4j+s://"):
        candidate_uris.append(uri.replace("neo4j+s://", "bolt+s://", 1))
    elif uri.startswith("neo4j+ssc://"):
        candidate_uris.append(uri.replace("neo4j+ssc://", "bolt+ssc://", 1))
    elif uri.startswith("neo4j://"):
        candidate_uris.append(uri.replace("neo4j://", "bolt://", 1))

    last_error = None
    for candidate in candidate_uris:
        driver = None
        started = time.perf_counter()
        try:
            driver = GraphDatabase.driver(candidate, auth=(user, password))
            driver.verify_connectivity()
            with driver.session(database=database) as session:
                total_nodes = session.run("MATCH (n) RETURN count(n) AS c").single().get("c")
                total_episodes = session.run(
                    "MATCH (e:Episode) RETURN count(e) AS c"
                ).single().get("c")
            return {
                "status": "connected",
                "uri_scheme": candidate.split(":", 1)[0],
                "database": database or None,
                "probe_ms": round((time.perf_counter() - started) * 1000, 1),
                "total_nodes": int(total_nodes or 0),
                "total_episodes": int(total_episodes or 0),
            }
        except Exception as exc:
            last_error = f"{candidate.split(':', 1)[0]}: {exc}"
        finally:
            if driver is not None:
                try:
                    driver.close()
                except Exception:
                    pass

    return {
        "status": "error",
        "message": str(last_error or "Neo4j probe failed"),
    }


def _require_authenticated_user(user: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not user or not user.get("user_id"):
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def _load_owned_twin(twin_id: str, user: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    auth_user = _require_authenticated_user(user)
    verify_twin_ownership(twin_id, auth_user)
    twin_res = (
        supabase.table("twins")
        .select("id,name,tenant_id,creator_id,settings,created_at")
        .eq("id", twin_id)
        .single()
        .execute()
    )
    if not twin_res.data:
        raise HTTPException(status_code=404, detail="Twin not found")

    twin = twin_res.data
    tenant_id = str(twin.get("tenant_id") or "")
    creator_id = str(twin.get("creator_id") or f"tenant_{tenant_id}")
    config = get_graph_memory_config()
    twin["scope_id"] = config.make_scope_id(tenant_id, creator_id)
    twin["tenant_id"] = tenant_id
    twin["creator_id"] = creator_id
    return twin


def _count_rows(
    table: str,
    *,
    tenant_id: str,
    twin_id: str,
    scope_id: Optional[str],
    count_field: str = "id",
) -> int:
    query = supabase.table(table).select(count_field, count="exact").eq("tenant_id", tenant_id)
    if scope_id:
        query = query.eq("scope_id", scope_id)
    else:
        query = query.eq("twin_id", twin_id)
    result = query.limit(1).execute()
    return int(result.count or 0)


def _recent_outbox_rows(*, tenant_id: str, twin_id: str, scope_id: Optional[str]) -> List[Dict[str, Any]]:
    query = (
        supabase.table("graph_outbox")
        .select("id,operation,status,created_at,updated_at,error_message,scope_id")
        .eq("tenant_id", tenant_id)
    )
    if scope_id:
        query = query.eq("scope_id", scope_id)
    else:
        query = query.eq("twin_id", twin_id)
    result = query.order("created_at", desc=True).limit(10).execute()
    return result.data or []


def _recent_claim_rows(*, tenant_id: str, twin_id: str, scope_id: Optional[str]) -> List[Dict[str, Any]]:
    query = (
        supabase.table("graph_claims")
        .select("claim_id,claim_text,claim_type,confidence,source_type,source_ref,extracted_at")
        .eq("tenant_id", tenant_id)
    )
    if scope_id:
        query = query.eq("scope_id", scope_id)
    else:
        query = query.eq("twin_id", twin_id)
    result = query.order("extracted_at", desc=True).limit(5).execute()
    return result.data or []


def _latest_snapshot_row(*, twin_id: str, scope_id: Optional[str]) -> Optional[Dict[str, Any]]:
    query = (
        supabase.table("graph_context_snapshots")
        .select("scope_id,group_id,episode_count,claim_count,created_at,expires_at,snapshot_data")
        .eq("twin_id", twin_id)
    )
    if scope_id:
        query = query.eq("scope_id", scope_id)
    result = query.order("created_at", desc=True).limit(1).execute()
    rows = result.data or []
    return rows[0] if rows else None


def _latest_name_research_run(twin_id: str) -> Optional[Dict[str, Any]]:
    result = (
        supabase.table("name_deep_research_runs")
        .select("id,status,input_name,run_completed_at,created_at")
        .eq("twin_id", twin_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else None


def _latest_name_research_result(run_id: str) -> Optional[Dict[str, Any]]:
    result = (
        supabase.table("name_deep_research_artifacts")
        .select("result_json")
        .eq("run_id", run_id)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    if not rows:
        return None
    payload = rows[0].get("result_json")
    return payload if isinstance(payload, dict) else None


@router.get("/observability/health")
async def health_check():
    health_status = {
        "status": "online",
        "services": {
            "pinecone": "unknown",
            "openai": "unknown",
            "neo4j": "unknown",
        },
    }

    try:
        get_pinecone_index()
        health_status["services"]["pinecone"] = "connected"
    except Exception as e:
        health_status["services"]["pinecone"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    try:
        get_openai_client().models.list()
        health_status["services"]["openai"] = "connected"
    except Exception as e:
        health_status["services"]["openai"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    neo4j_probe = _neo4j_probe()
    if neo4j_probe["status"] == "connected":
        health_status["services"]["neo4j"] = "connected"
    else:
        health_status["services"]["neo4j"] = f"{neo4j_probe['status']}: {neo4j_probe.get('message', 'unknown')}"
        health_status["status"] = "degraded"

    return health_status


@router.get("/observability/neo4j/health")
async def neo4j_health_check():
    return _neo4j_probe()


@router.get("/admin/pinecone/describe")
async def describe_pinecone_index(user=Depends(get_current_user)):
    _require_authenticated_user(user)
    index = get_pinecone_index()
    stats = index.describe_index_stats()
    namespaces = {}
    raw_namespaces = getattr(stats, "namespaces", None)
    if isinstance(raw_namespaces, dict):
        for namespace, info in raw_namespaces.items():
            vector_count = None
            if isinstance(info, dict):
                vector_count = info.get("vector_count")
            else:
                vector_count = getattr(info, "vector_count", None)
            namespaces[namespace] = {"vector_count": vector_count}
    return {
        "status": "ok",
        "index": os.getenv("PINECONE_INDEX_NAME"),
        "index_fullness": getattr(stats, "index_fullness", None),
        "dimension": getattr(stats, "dimension", None),
        "total_vector_count": getattr(stats, "total_vector_count", None),
        "namespaces": namespaces,
    }


@router.get("/admin/graph/diagnostics/{twin_id}")
async def graph_diagnostics(twin_id: str, user=Depends(get_current_user)):
    twin = _load_owned_twin(twin_id, user)
    neo4j_status = _neo4j_probe()
    outbox = get_graph_outbox()
    config = get_graph_memory_config()

    recent_episodes: List[Dict[str, Any]] = []
    if neo4j_status.get("status") == "connected" and config.is_read_allowed():
        client = GraphMemoryCore(
            tenant_id=twin["tenant_id"],
            twin_id=twin_id,
            correlation_id=f"graph-diagnostics:{twin_id}",
            creator_id=twin["creator_id"],
            scope_id=twin["scope_id"],
        )
        recent_episodes = await client.search("*", num_results=5)

    snapshot_row = _latest_snapshot_row(twin_id=twin_id, scope_id=twin["scope_id"])
    latest_run = _latest_name_research_run(twin_id)

    return {
        "twin": {
            "id": twin["id"],
            "name": twin.get("name"),
            "tenant_id": twin["tenant_id"],
            "creator_id": twin["creator_id"],
            "scope_id": twin["scope_id"],
            "created_at": twin.get("created_at"),
        },
        "neo4j": neo4j_status,
        "graph_config": {
            "enabled": config.enabled,
            "read_enabled": config.read_enabled,
            "write_enabled": config.write_enabled,
            "database": config.neo4j_database,
        },
        "outbox": {
            "stats": outbox.get_stats(scope_id=twin["scope_id"]),
            "recent_jobs": _recent_outbox_rows(
                tenant_id=twin["tenant_id"],
                twin_id=twin_id,
                scope_id=twin["scope_id"],
            ),
        },
        "claims": {
            "count": _count_rows(
                "graph_claims",
                tenant_id=twin["tenant_id"],
                twin_id=twin_id,
                scope_id=twin["scope_id"],
                count_field="claim_id",
            ),
            "recent": _recent_claim_rows(
                tenant_id=twin["tenant_id"],
                twin_id=twin_id,
                scope_id=twin["scope_id"],
            ),
        },
        "snapshot": snapshot_row,
        "recent_episodes": recent_episodes,
        "latest_name_research_run": latest_run,
    }


@router.post("/admin/graph/seed/{twin_id}")
async def seed_graph_diagnostics(twin_id: str, request: GraphSeedRequest, user=Depends(get_current_user)):
    twin = _load_owned_twin(twin_id, user)
    seed_token = f"graph-seed-{int(time.time())}"
    correlation_id = f"graph-seed:{twin_id}:{seed_token}"
    episode_name = request.label or f"Diagnostics Seed for {twin.get('name') or twin_id}"
    episode_body = (
        request.body
        or f"Graph diagnostics seed for {twin.get('name') or twin_id}. Verification token: {seed_token}. "
        "This entry proves Neo4j episode write and read are working end to end."
    )

    client = GraphMemoryCore(
        tenant_id=twin["tenant_id"],
        twin_id=twin_id,
        correlation_id=correlation_id,
        creator_id=twin["creator_id"],
        scope_id=twin["scope_id"],
    )
    episode_id = await client.create_episode(
        name=episode_name,
        body=episode_body,
        source_type="graph_diagnostics",
        source_ref=seed_token,
        async_write=False,
    )
    matched_results = await client.search(seed_token, num_results=3)
    snapshot_refreshed = await refresh_twin_snapshot(
        tenant_id=twin["tenant_id"],
        twin_id=twin_id,
        correlation_id=correlation_id,
        creator_id=twin["creator_id"],
    )

    return {
        "status": "ok",
        "seed_token": seed_token,
        "episode_id": episode_id,
        "match_count": len(matched_results),
        "matched_results": matched_results,
        "snapshot_refreshed": snapshot_refreshed,
        "neo4j": _neo4j_probe(),
    }


@router.post("/admin/graph/replay-name-research/{twin_id}")
async def replay_name_research_graph_materialization(twin_id: str, user=Depends(get_current_user)):
    twin = _load_owned_twin(twin_id, user)
    latest_run = _latest_name_research_run(twin_id)
    if not latest_run:
        raise HTTPException(status_code=404, detail="No name deep research run found for this twin")

    run_id = str(latest_run.get("id") or "").strip()
    result_doc = _latest_name_research_result(run_id)
    if not result_doc:
        raise HTTPException(status_code=404, detail="No name deep research artifact found for this twin")

    service = get_name_deep_research_service()
    await service._enqueue_graph_memory_jobs(
        run_id=run_id,
        tenant_id=twin["tenant_id"],
        twin_id=twin_id,
        result_doc=result_doc,
    )

    return {
        "status": "queued",
        "twin_id": twin_id,
        "run_id": run_id,
        "scope_id": twin["scope_id"],
        "message": "Graph materialization jobs were re-enqueued from the latest research artifact.",
    }
