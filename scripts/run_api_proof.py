import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests


REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = REPO_ROOT / ".env"
PROOF_DIR = REPO_ROOT / "proof"
PROOF_DIR.mkdir(exist_ok=True)


def load_env(path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.strip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def redact(value: Optional[str], keep: int = 6) -> Optional[str]:
    if not value:
        return value
    if len(value) <= keep * 2:
        return f"{value[:keep]}...{value[-keep:]}"
    return f"{value[:keep]}...{value[-keep:]}"


def request_json(method: str, url: str, **kwargs) -> Dict[str, Any]:
    resp = requests.request(method, url, **kwargs)
    if not resp.ok:
        raise RuntimeError(f"{method} {url} failed ({resp.status_code}): {resp.text}")
    try:
        return resp.json()
    except Exception:
        raise RuntimeError(f"{method} {url} returned non-JSON response")


def wait_for_source(backend_url: str, headers: Dict[str, str], twin_id: str, source_id: str, timeout: int = 420) -> Dict[str, Any]:
    start = time.time()
    while time.time() - start < timeout:
        sources = request_json("GET", f"{backend_url}/sources/{twin_id}", headers=headers)
        match = next((s for s in sources if s.get("id") == source_id), None)
        if match:
            status = match.get("status") or match.get("staging_status")
            if status in ["live", "processed"]:
                return match
        time.sleep(5)
    raise TimeoutError(f"Timed out waiting for source {source_id} to become live")


def get_supabase_chunk_count(supabase_url: str, service_key: str, source_id: str) -> Optional[int]:
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Prefer": "count=exact",
        "Accept": "application/json",
    }
    url = f"{supabase_url}/rest/v1/chunks?select=id&source_id=eq.{source_id}"
    resp = requests.get(url, headers=headers)
    if not resp.ok:
        return None
    content_range = resp.headers.get("content-range")
    if not content_range or "/" not in content_range:
        return None
    try:
        return int(content_range.split("/")[-1])
    except ValueError:
        return None


def pinecone_vector_count(host: str, api_key: str, namespace: str) -> Optional[int]:
    url = f"{host}/describe_index_stats"
    headers = {"Api-Key": api_key, "Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json={})
    if not resp.ok:
        return None
    data = resp.json()
    namespaces = data.get("namespaces", {})
    ns = namespaces.get(namespace)
    if not ns:
        return 0
    return ns.get("vector_count", 0)


def run() -> Dict[str, Any]:
    env = load_env(ENV_PATH)
    backend_url = os.getenv("BACKEND_URL") or env.get("DEPLOYED_BACKEND_URL")
    supabase_url = env.get("SUPABASE_URL")
    supabase_key = env.get("SUPABASE_KEY")
    supabase_service_key = env.get("SUPABASE_SERVICE_KEY")
    email = env.get("TEST_ACCOUNT_EMAIL")
    password = env.get("TEST_ACCOUNT_PASSWORD")
    pinecone_api_key = env.get("PINECONE_API_KEY")
    pinecone_host = env.get("PINECONE_HOST")

    missing = [k for k in ["DEPLOYED_BACKEND_URL", "SUPABASE_URL", "SUPABASE_KEY", "TEST_ACCOUNT_EMAIL", "TEST_ACCOUNT_PASSWORD"] if not env.get(k)]
    if missing:
        raise RuntimeError(f"Missing required env vars in .env: {', '.join(missing)}")

    auth_url = f"{supabase_url}/auth/v1/token?grant_type=password"
    auth_headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
    }
    auth_body = {"email": email, "password": password}
    auth_resp = requests.post(auth_url, headers=auth_headers, json=auth_body)
    if not auth_resp.ok:
        raise RuntimeError(f"Supabase auth failed ({auth_resp.status_code}): {auth_resp.text}")
    auth_data = auth_resp.json()
    access_token = auth_data.get("access_token")
    if not access_token:
        raise RuntimeError("Supabase auth response missing access_token")

    headers = {"Authorization": f"Bearer {access_token}"}
    request_json("POST", f"{backend_url}/auth/sync-user", headers=headers)

    twin_payload = {
        "name": f"Critical Path Proof Twin {int(time.time())}",
        "description": "Auto-generated for Phase 3/4 proof",
        "specialization": "vanilla",
        "settings": {
            "system_prompt": "You are a helpful assistant.",
            "handle": f"critical-path-{int(time.time())}",
            "tagline": "Critical path proof",
        },
    }
    twin = request_json("POST", f"{backend_url}/twins", headers={**headers, "Content-Type": "application/json"}, json=twin_payload)
    twin_id = twin.get("id")
    if not twin_id:
        raise RuntimeError("Twin creation failed: missing id")

    unique_phrase = f"CRITICAL_PATH_PROOF_{int(time.time())}"
    proof_file = PROOF_DIR / "ingest_proof.txt"
    proof_file.write_text(
        f"Digital Brains critical path proof.\nUnique phrase: {unique_phrase}\n",
        encoding="utf-8"
    )

    with proof_file.open("rb") as handle:
        ingest_file_resp = requests.post(
            f"{backend_url}/ingest/file/{twin_id}",
            headers=headers,
            files={"file": (proof_file.name, handle, "text/plain")},
        )
    if not ingest_file_resp.ok:
        raise RuntimeError(f"File ingest failed ({ingest_file_resp.status_code}): {ingest_file_resp.text}")
    ingest_file_data = ingest_file_resp.json()
    source_id_file = ingest_file_data.get("source_id")

    ingest_url_resp = requests.post(
        f"{backend_url}/ingest/url/{twin_id}",
        headers={**headers, "Content-Type": "application/json"},
        json={"url": "https://example.com"},
    )
    if not ingest_url_resp.ok:
        raise RuntimeError(f"URL ingest failed ({ingest_url_resp.status_code}): {ingest_url_resp.text}")
    ingest_url_data = ingest_url_resp.json()
    source_id_url = ingest_url_data.get("source_id")

    source_file = wait_for_source(backend_url, headers, twin_id, source_id_file)
    source_url = wait_for_source(backend_url, headers, twin_id, source_id_url)

    chunk_count_file = source_file.get("chunk_count") or get_supabase_chunk_count(supabase_url, supabase_service_key, source_id_file)
    chunk_count_url = source_url.get("chunk_count") or get_supabase_chunk_count(supabase_url, supabase_service_key, source_id_url)

    health = request_json("GET", f"{backend_url}/sources/{source_id_file}/health", headers=headers)
    checks_len = len(health.get("checks", []) or [])

    verification = request_json("GET", f"{backend_url}/twins/{twin_id}/verification-status", headers=headers)
    vectors_count = verification.get("vectors_count")

    pinecone_count = None
    if pinecone_api_key and pinecone_host:
        pinecone_count = pinecone_vector_count(pinecone_host, pinecone_api_key, twin_id)

    extract_nodes_resp = request_json(
        "POST",
        f"{backend_url}/ingest/extract-nodes/{source_id_file}",
        headers={**headers, "Content-Type": "application/json"},
        json={"max_chunks": 5},
    )

    graph_data = request_json("GET", f"{backend_url}/twins/{twin_id}/graph?limit=10", headers=headers)
    graph_nodes = len(graph_data.get("nodes", []) or [])
    graph_edges = len(graph_data.get("edges", []) or [])

    training_jobs = request_json("GET", f"{backend_url}/training-jobs?twin_id={twin_id}", headers=headers)

    # Share link flow
    share_info = request_json("GET", f"{backend_url}/twins/{twin_id}/share-link", headers=headers)
    if not share_info.get("public_share_enabled"):
        request_json(
            "PATCH",
            f"{backend_url}/twins/{twin_id}/sharing",
            headers={**headers, "Content-Type": "application/json"},
            json={"is_public": True},
        )
    if not share_info.get("share_token"):
        request_json("POST", f"{backend_url}/twins/{twin_id}/share-link", headers=headers)
    share_info = request_json("GET", f"{backend_url}/twins/{twin_id}/share-link", headers=headers)
    share_token = share_info.get("share_token")
    share_url = share_info.get("share_url")

    validate_share = request_json("GET", f"{backend_url}/public/validate-share/{twin_id}/{share_token}")
    public_validate_path = PROOF_DIR / "public_validate_share.json"
    public_validate_path.write_text(json.dumps(validate_share, indent=2), encoding="utf-8")

    question = f"What is the unique phrase in the critical path proof file?"
    public_chat = request_json(
        "POST",
        f"{backend_url}/public/chat/{twin_id}/{share_token}",
        headers={**headers, "Content-Type": "application/json"},
        json={
            "message": question,
            "conversation_history": [
                {"role": "user", "content": "Hello there", "extra": "ignored"}
            ],
        },
    )
    # Clarification path (queued) proof
    queued_tag = f"orion-policy-{int(time.time())}"
    queued_question = f"What is your stance on the {queued_tag} escalation framework for incidents?"
    public_chat_queued = request_json(
        "POST",
        f"{backend_url}/public/chat/{twin_id}/{share_token}",
        headers={**headers, "Content-Type": "application/json"},
        json={
            "message": queued_question,
            "conversation_history": [
                {"role": "user", "content": "Hello", "extra": "ignored"}
            ],
        },
    )
    public_chat_queued_path = PROOF_DIR / "public_chat_queued.json"
    public_chat_queued_path.write_text(json.dumps(public_chat_queued, indent=2), encoding="utf-8")

    # Widget API key + stream
    api_key_resp = request_json(
        "POST",
        f"{backend_url}/api-keys",
        headers={**headers, "Content-Type": "application/json"},
        json={"twin_id": twin_id, "group_id": None, "name": "Proof Widget Key", "allowed_domains": ["*"]},
    )
    widget_key = api_key_resp.get("key")

    widget_stream = requests.post(
        f"{backend_url}/chat-widget/{twin_id}",
        headers={"Content-Type": "application/json"},
        json={"query": question, "api_key": widget_key},
        stream=True,
    )
    stream_lines = []
    if widget_stream.ok:
        for line in widget_stream.iter_lines(decode_unicode=True):
            if not line:
                continue
            stream_lines.append(line)
            if '"type": "done"' in line or '"type":"done"' in line:
                break
    else:
        raise RuntimeError(f"Widget chat failed ({widget_stream.status_code}): {widget_stream.text}")

    widget_stream_path = PROOF_DIR / "widget_stream.txt"
    widget_stream_path.write_text("\n".join(stream_lines[:20]), encoding="utf-8")

    results = {
        "twin_id": twin_id,
        "unique_phrase": unique_phrase,
        "file_source_id": source_id_file,
        "url_source_id": source_id_url,
        "file_status": source_file.get("status") or source_file.get("staging_status"),
        "url_status": source_url.get("status") or source_url.get("staging_status"),
        "chunk_count_file": chunk_count_file,
        "chunk_count_url": chunk_count_url,
        "checks_len": checks_len,
        "vectors_count": vectors_count,
        "pinecone_vector_count": pinecone_count,
        "graph_nodes_created": extract_nodes_resp.get("nodes_created"),
        "graph_edges_created": extract_nodes_resp.get("edges_created"),
        "graph_nodes": graph_nodes,
        "graph_edges": graph_edges,
        "training_jobs_count": len(training_jobs) if isinstance(training_jobs, list) else None,
        "share_token": share_token,
        "share_url": share_url,
        "share_public_enabled": share_info.get("public_share_enabled"),
        "share_validation": validate_share,
        "public_chat": public_chat,
        "widget_stream_snippet": stream_lines[:6],
        "widget_key_prefix": api_key_resp.get("key_prefix"),
    }

    output = {
        "twin_id": twin_id,
        "unique_phrase": unique_phrase,
        "file_source_id": source_id_file,
        "url_source_id": source_id_url,
        "file_status": results["file_status"],
        "url_status": results["url_status"],
        "chunk_count_file": chunk_count_file,
        "chunk_count_url": chunk_count_url,
        "checks_len": checks_len,
        "vectors_count": vectors_count,
        "pinecone_vector_count": pinecone_count,
        "graph_nodes_created": results["graph_nodes_created"],
        "graph_edges_created": results["graph_edges_created"],
        "graph_nodes": graph_nodes,
        "graph_edges": graph_edges,
        "training_jobs_count": results["training_jobs_count"],
        "share_token_redacted": redact(share_token),
        "share_url": share_url,
        "share_public_enabled": share_info.get("public_share_enabled"),
        "public_chat_status": public_chat.get("status"),
        "public_chat_response_snippet": (public_chat.get("response") or "")[:200],
        "public_chat_used_owner_memory": public_chat.get("used_owner_memory"),
        "public_chat_queued_status": public_chat_queued.get("status"),
        "widget_stream_snippet": results["widget_stream_snippet"],
        "widget_key_prefix": results["widget_key_prefix"],
    }

    (PROOF_DIR / "api_proof.json").write_text(json.dumps(output, indent=2), encoding="utf-8")

    # Write raw public chat response (sans secrets)
    public_chat_path = PROOF_DIR / "public_chat_response.json"
    public_chat_path.write_text(json.dumps(public_chat, indent=2), encoding="utf-8")

    return results


if __name__ == "__main__":
    data = run()
    print("API proof run complete.")
    print(json.dumps({
        "twin_id": data.get("twin_id"),
        "share_url": data.get("share_url"),
        "file_source_id": data.get("file_source_id"),
        "url_source_id": data.get("url_source_id"),
    }, indent=2))
