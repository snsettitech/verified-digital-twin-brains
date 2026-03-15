import os

from fastapi import APIRouter, Depends
from modules.clients import get_pinecone_index, get_openai_client
from modules.auth_guard import get_current_user

router = APIRouter(tags=["observability"])

@router.get("/observability/health")
async def health_check():
    health_status = {
        "status": "online",
        "services": {
            "pinecone": "unknown",
            "openai": "unknown"
        }
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

    return health_status


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
