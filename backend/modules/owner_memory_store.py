"""
Owner Memory Store

Structured storage and retrieval for owner beliefs, preferences, stances, lens, and tone rules.
All writes are explicit and auditable. No auto-writes from public users.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import json
import re

from modules.observability import supabase
from modules.embeddings import get_embedding, cosine_similarity


STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "else", "when", "what", "how", "why",
    "is", "are", "was", "were", "be", "been", "being", "do", "does", "did", "should", "would",
    "could", "can", "will", "my", "your", "their", "our", "about", "on", "in", "for", "to",
    "of", "with", "by", "at", "from", "as", "this", "that", "it", "we", "i", "you"
}


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"[^a-zA-Z0-9\s-]", " ", text.lower())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _tokenize(text: str) -> List[str]:
    tokens = [t for t in _normalize_text(text).split() if t and t not in STOPWORDS]
    return tokens[:12]


def extract_topic_from_query(query: str, history: Optional[List[Dict[str, Any]]] = None) -> str:
    """
    Deterministic topic extraction for identity gating.
    Uses simple regex + keyword fallback + recent history.
    """
    query = query or ""
    lower = query.lower()

    # Try explicit "about/on/regarding" phrases
    match = re.search(r"\\b(about|on|regarding|toward|towards|re:|around)\\b\\s+(.+)$", lower)
    if match:
        topic = match.group(2)
        return _normalize_text(topic)

    # Try "should I/should we <verb> <topic>"
    match = re.search(r"(should\s+(i|we|you)\s+)(.+)$", lower)
    if match:
        return _normalize_text(match.group(3))

    # Fallback: use recent history if query is vague
    vague_terms = {"this", "that", "it", "there", "here", "topic", "idea", "thing"}
    tokens = _tokenize(lower)
    if not tokens or all(t in vague_terms for t in tokens):
        if history:
            for msg in reversed(history[-6:]):
                if msg.get("role") == "user":
                    hist_tokens = _tokenize(msg.get("content", ""))
                    if hist_tokens:
                        return " ".join(hist_tokens[:6])

    # Default: top keywords
    if tokens:
        return " ".join(tokens[:6])
    return _normalize_text(query)[:80]


def list_owner_memories(twin_id: str, status: str = "active", limit: int = 200) -> List[Dict[str, Any]]:
    try:
        query = supabase.table("owner_beliefs").select("*").eq("twin_id", twin_id)
        if status:
            query = query.eq("status", status)
        res = query.order("created_at", desc=True).limit(limit).execute()
        return res.data or []
    except Exception as e:
        # Table may not exist yet if migration not applied
        print(f"[OwnerMemory] list_owner_memories failed: {e}")
        return []


def _lexical_overlap(a: str, b: str) -> float:
    a_tokens = set(_tokenize(a))
    b_tokens = set(_tokenize(b))
    if not a_tokens or not b_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / float(len(a_tokens | b_tokens))


def find_owner_memory_candidates(
    query: str,
    twin_id: str,
    topic_normalized: Optional[str] = None,
    memory_type: Optional[str] = None,
    limit: int = 6
) -> List[Dict[str, Any]]:
    memories = list_owner_memories(twin_id, status="active", limit=200)
    if not memories:
        return []

    # Precompute embedding for query if any memory has embedding
    has_embedding = any(m.get("embedding") for m in memories)
    query_embedding = None
    if has_embedding:
        try:
            query_embedding = get_embedding(query)
        except Exception as e:
            print(f"[OwnerMemory] embedding failed: {e}")
            query_embedding = None

    scored = []
    for mem in memories:
        if memory_type and mem.get("memory_type") and mem["memory_type"] != memory_type:
            # Allow stance to match belief/lens if needed
            if not (memory_type == "stance" and mem["memory_type"] in {"belief", "lens", "preference"}):
                continue

        topic = mem.get("topic_normalized") or ""
        value = mem.get("value") or ""

        lexical = 0.0
        if topic_normalized:
            lexical = _lexical_overlap(topic_normalized, topic)
        lexical = max(lexical, _lexical_overlap(query, value))

        embed_score = 0.0
        if query_embedding and mem.get("embedding"):
            try:
                mem_emb = mem.get("embedding")
                if isinstance(mem_emb, str):
                    mem_emb = json.loads(mem_emb)
                embed_score = cosine_similarity(query_embedding, mem_emb)
            except Exception:
                embed_score = 0.0

        score = max(lexical, embed_score)
        mem["_score"] = score
        scored.append(mem)

    scored.sort(key=lambda m: (m.get("_score", 0), m.get("confidence", 0)), reverse=True)
    return scored[:limit]


def detect_conflicts(memories: List[Dict[str, Any]]) -> bool:
    if len(memories) < 2:
        return False
    stances = set()
    for mem in memories:
        stance = (mem.get("stance") or "").lower().strip()
        if stance:
            stances.add(stance)
    if len(stances) > 1:
        return True
    return False


def format_owner_memory_context(memories: List[Dict[str, Any]], max_items: int = 5) -> str:
    if not memories:
        return ""
    lines = []
    for mem in memories[:max_items]:
        stance = mem.get("stance")
        intensity = mem.get("intensity")
        conf = mem.get("confidence")
        meta = []
        if stance:
            meta.append(f"stance={stance}")
        if intensity:
            meta.append(f"intensity={intensity}/10")
        if conf is not None:
            meta.append(f"confidence={round(conf, 2)}")
        meta_str = f" ({', '.join(meta)})" if meta else ""
        lines.append(f"- [{mem.get('memory_type', 'memory')}] {mem.get('topic_normalized')}: {mem.get('value')}{meta_str}")
    return "\n".join(lines)


def _get_tenant_id_for_twin(twin_id: str) -> Optional[str]:
    try:
        res = supabase.table("twins").select("tenant_id").eq("id", twin_id).single().execute()
        return res.data.get("tenant_id") if res.data else None
    except Exception:
        return None


def create_owner_memory(
    twin_id: str,
    tenant_id: str,
    topic_normalized: str,
    memory_type: str,
    value: str,
    stance: Optional[str] = None,
    intensity: Optional[int] = None,
    confidence: float = 0.7,
    provenance: Optional[Dict[str, Any]] = None,
    supersede_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    try:
        embedding = None
        try:
            embedding = get_embedding(f"{topic_normalized}. {value}")
        except Exception as e:
            print(f"[OwnerMemory] embedding generation failed: {e}")

        insert_data = {
            "tenant_id": tenant_id,
            "twin_id": twin_id,
            "topic_normalized": topic_normalized or "general",
            "memory_type": memory_type,
            "value": value,
            "stance": stance,
            "intensity": intensity,
            "confidence": max(0.0, min(1.0, confidence)),
            "status": "active",
            "embedding": embedding,
            "provenance": provenance or {},
            "updated_at": datetime.utcnow().isoformat()
        }
        res = supabase.table("owner_beliefs").insert(insert_data).execute()
        if not res.data:
            return None
        new_mem = res.data[0]

        if supersede_id:
            supersede_owner_memory(supersede_id, new_mem["id"])

        return new_mem
    except Exception as e:
        print(f"[OwnerMemory] create_owner_memory failed: {e}")
        return None


def supersede_owner_memory(old_id: str, new_id: str) -> bool:
    try:
        supabase.table("owner_beliefs").update({
            "status": "superseded",
            "superseded_by": new_id,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", old_id).execute()
        return True
    except Exception as e:
        print(f"[OwnerMemory] supersede failed: {e}")
        return False


def retract_owner_memory(mem_id: str, reason: Optional[str] = None) -> bool:
    try:
        supabase.table("owner_beliefs").update({
            "status": "retracted",
            "updated_at": datetime.utcnow().isoformat(),
            "provenance": {"retract_reason": reason or "owner_request"}
        }).eq("id", mem_id).execute()
        return True
    except Exception as e:
        print(f"[OwnerMemory] retract failed: {e}")
        return False


def create_clarification_thread(
    twin_id: str,
    tenant_id: Optional[str],
    question: str,
    options: List[Dict[str, Any]],
    memory_write_proposal: Dict[str, Any],
    original_query: Optional[str] = None,
    conversation_id: Optional[str] = None,
    mode: str = "owner",
    requested_by: str = "owner",
    created_by: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    try:
        if not tenant_id:
            tenant_id = _get_tenant_id_for_twin(twin_id)

        insert_data = {
            "tenant_id": tenant_id,
            "twin_id": twin_id,
            "conversation_id": conversation_id,
            "mode": mode,
            "status": "pending_owner",
            "original_query": original_query,
            "question": question,
            "options": options or [],
            "memory_write_proposal": memory_write_proposal or {},
            "requested_by": requested_by,
            "created_by": created_by,
            "updated_at": datetime.utcnow().isoformat()
        }
        res = supabase.table("clarification_threads").insert(insert_data).execute()
        if not res.data:
            return None
        return res.data[0]
    except Exception as e:
        print(f"[OwnerMemory] create_clarification_thread failed: {e}")
        return None


def list_clarification_threads(
    twin_id: str,
    status: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    try:
        query = supabase.table("clarification_threads").select("*").eq("twin_id", twin_id)
        if status:
            query = query.eq("status", status)
        res = query.order("created_at", desc=True).limit(limit).execute()
        return res.data or []
    except Exception as e:
        print(f"[OwnerMemory] list_clarification_threads failed: {e}")
        return []


def get_clarification_thread(clarification_id: str) -> Optional[Dict[str, Any]]:
    try:
        res = supabase.table("clarification_threads").select("*").eq("id", clarification_id).single().execute()
        return res.data if res.data else None
    except Exception as e:
        print(f"[OwnerMemory] get_clarification_thread failed: {e}")
        return None


def resolve_clarification_thread(
    clarification_id: str,
    answer_text: str,
    owner_memory_id: Optional[str],
    answered_by: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    try:
        update_data = {
            "status": "answered",
            "answer_text": answer_text,
            "answered_by": answered_by,
            "answered_at": datetime.utcnow().isoformat(),
            "owner_memory_id": owner_memory_id,
            "updated_at": datetime.utcnow().isoformat()
        }
        res = supabase.table("clarification_threads").update(update_data).eq("id", clarification_id).execute()
        if not res.data:
            return None
        return res.data[0]
    except Exception as e:
        print(f"[OwnerMemory] resolve_clarification_thread failed: {e}")
        return None
