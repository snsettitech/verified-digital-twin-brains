import os
import time

from fastapi import APIRouter, Depends

from modules.auth_guard import get_current_user
from modules.clients import get_openai_client, get_pinecone_index

router = APIRouter(tags=["observability"])


def _neo4j_probe():
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
