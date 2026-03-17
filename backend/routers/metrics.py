"""
Metrics and analytics router for the live product.

The runtime is support-state based:
- no confidence scores
- answerability, source tier, citations, and review state drive UI metrics
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from modules.auth_guard import get_current_user, verify_twin_ownership
from modules.observability import supabase

router = APIRouter(prefix="/metrics", tags=["metrics"])


class EventCreate(BaseModel):
    event_type: str
    twin_id: Optional[str] = None
    event_data: Optional[dict] = {}
    session_id: Optional[str] = None


class AnswerMix(BaseModel):
    direct: int = 0
    derivable: int = 0
    insufficient: int = 0


class DashboardStats(BaseModel):
    conversations: int
    messages: int
    user_messages: int
    assistant_messages: int
    response_rate: float
    review_rate: float
    citation_rate: float
    unsupported_rate: float
    answer_mix: AnswerMix


class DailyMetric(BaseModel):
    date: str
    conversations: int
    messages: int


class TopQuestion(BaseModel):
    question: str
    count: int
    top_answerability_state: str
    review_rate: float
    citation_rate: float


class ConversationSummary(BaseModel):
    id: str
    created_at: str
    message_count: int
    last_message: Optional[str] = None
    last_answerability_state: Optional[str] = None
    last_source_tier: Optional[str] = None
    review_required: bool = False
    citation_rate: float = 0.0


class ActivityItem(BaseModel):
    id: str
    type: str
    title: str
    description: str
    time: str
    metadata: Optional[dict] = {}


def _chunked(items: Iterable[str], size: int = 50) -> Iterable[List[str]]:
    batch: List[str] = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def _normalize_answerability_state(value: Any) -> str:
    state = str(value or "").strip().lower()
    if state not in {"direct", "derivable", "insufficient"}:
        return "direct"
    return state


def _normalize_source_tier(value: Any) -> str:
    tier = str(value or "").strip().lower()
    if tier in {"canonical", "verified", "retrieved", "mixed"}:
        return tier
    return "mixed"


def _has_citations(raw: Any) -> bool:
    if isinstance(raw, list):
        return any(str(item or "").strip() for item in raw)
    if isinstance(raw, str):
        return bool(raw.strip())
    return False


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 1)


def _load_messages_for_conversations(
    conversation_ids: List[str],
    *,
    fields: str,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for batch in _chunked(conversation_ids, size=50):
        result = (
            supabase.table("messages")
            .select(fields)
            .in_("conversation_id", batch)
            .execute()
        )
        rows.extend(result.data or [])
    return rows


def _group_messages_by_conversation(messages: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for message in messages:
        conversation_id = str(message.get("conversation_id") or "").strip()
        if conversation_id:
            grouped[conversation_id].append(message)
    for rows in grouped.values():
        rows.sort(key=lambda row: str(row.get("created_at") or ""))
    return grouped


@router.get("/dashboard/{twin_id}", response_model=DashboardStats)
async def get_dashboard_stats(
    twin_id: str,
    days: int = Query(30, ge=1, le=90),
    user=Depends(get_current_user),
):
    verify_twin_ownership(twin_id, user)
    try:
        start_date = datetime.now() - timedelta(days=days)
        conversations_result = (
            supabase.table("conversations")
            .select("id, created_at")
            .eq("twin_id", twin_id)
            .gte("created_at", start_date.isoformat())
            .execute()
        )
        conversations = conversations_result.data or []
        conversation_ids = [str(row.get("id") or "").strip() for row in conversations if row.get("id")]

        if not conversation_ids:
            return DashboardStats(
                conversations=0,
                messages=0,
                user_messages=0,
                assistant_messages=0,
                response_rate=100.0,
                review_rate=0.0,
                citation_rate=0.0,
                unsupported_rate=0.0,
                answer_mix=AnswerMix(),
            )

        messages = _load_messages_for_conversations(
            conversation_ids,
            fields="id, conversation_id, role, citations, answerability_state, source_tier, review_required",
        )
        user_messages = [row for row in messages if row.get("role") == "user"]
        assistant_messages = [row for row in messages if row.get("role") == "assistant"]
        answer_counter = Counter(
            _normalize_answerability_state(row.get("answerability_state")) for row in assistant_messages
        )
        citation_count = sum(1 for row in assistant_messages if _has_citations(row.get("citations")))
        review_count = sum(1 for row in assistant_messages if bool(row.get("review_required")))
        unsupported_count = answer_counter.get("insufficient", 0)

        return DashboardStats(
            conversations=len(conversation_ids),
            messages=len(messages),
            user_messages=len(user_messages),
            assistant_messages=len(assistant_messages),
            response_rate=min(100.0, _safe_rate(len(assistant_messages), len(user_messages)) if user_messages else 100.0),
            review_rate=_safe_rate(review_count, len(assistant_messages)),
            citation_rate=_safe_rate(citation_count, len(assistant_messages)),
            unsupported_rate=_safe_rate(unsupported_count, len(assistant_messages)),
            answer_mix=AnswerMix(
                direct=answer_counter.get("direct", 0),
                derivable=answer_counter.get("derivable", 0),
                insufficient=answer_counter.get("insufficient", 0),
            ),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/conversations/{twin_id}", response_model=List[ConversationSummary])
async def get_conversations_list(
    twin_id: str,
    limit: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user),
):
    verify_twin_ownership(twin_id, user)
    try:
        conversations_result = (
            supabase.table("conversations")
            .select("id, created_at")
            .eq("twin_id", twin_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        conversations = conversations_result.data or []
        conversation_ids = [str(row.get("id") or "").strip() for row in conversations if row.get("id")]
        if not conversation_ids:
            return []

        messages = _load_messages_for_conversations(
            conversation_ids,
            fields="conversation_id, content, role, citations, answerability_state, source_tier, review_required, created_at",
        )
        grouped = _group_messages_by_conversation(messages)
        results: List[ConversationSummary] = []

        for conversation in conversations:
            conversation_id = str(conversation.get("id") or "")
            rows = grouped.get(conversation_id, [])
            latest_first = list(reversed(rows))
            latest_user = next((row for row in latest_first if row.get("role") == "user"), None)
            latest_assistant = next((row for row in latest_first if row.get("role") == "assistant"), None)
            assistant_rows = [row for row in rows if row.get("role") == "assistant"]
            citation_count = sum(1 for row in assistant_rows if _has_citations(row.get("citations")))

            results.append(
                ConversationSummary(
                    id=conversation_id,
                    created_at=str(conversation.get("created_at") or ""),
                    message_count=len(rows),
                    last_message=(str(latest_user.get("content") or "")[:100] if latest_user else None),
                    last_answerability_state=(
                        _normalize_answerability_state(latest_assistant.get("answerability_state"))
                        if latest_assistant
                        else None
                    ),
                    last_source_tier=(
                        _normalize_source_tier(latest_assistant.get("source_tier"))
                        if latest_assistant
                        else None
                    ),
                    review_required=bool(latest_assistant.get("review_required")) if latest_assistant else False,
                    citation_rate=_safe_rate(citation_count, len(assistant_rows)),
                )
            )

        return results
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/activity/{twin_id}", response_model=List[ActivityItem])
async def get_activity_feed(
    twin_id: str,
    limit: int = Query(10, ge=1, le=50),
    user=Depends(get_current_user),
):
    verify_twin_ownership(twin_id, user)
    try:
        activities: List[ActivityItem] = []
        conversations_result = (
            supabase.table("conversations")
            .select("id, created_at")
            .eq("twin_id", twin_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        conversation_rows = conversations_result.data or []
        conversation_ids = [row["id"] for row in conversation_rows if row.get("id")]

        for conversation in conversation_rows:
            first_user_result = (
                supabase.table("messages")
                .select("content")
                .eq("conversation_id", conversation["id"])
                .eq("role", "user")
                .order("created_at", desc=False)
                .limit(1)
                .execute()
            )
            first_user = first_user_result.data[0] if first_user_result.data else None
            preview = "New conversation"
            if first_user and first_user.get("content"):
                content = str(first_user.get("content") or "")
                preview = content[:50] + "..." if len(content) > 50 else content
            activities.append(
                ActivityItem(
                    id=conversation["id"],
                    type="conversation",
                    title=f"Asked: {preview}",
                    description="Anonymous visitor",
                    time=conversation["created_at"],
                    metadata={"conversation_id": conversation["id"]},
                )
            )

        if conversation_ids:
            message_rows = _load_messages_for_conversations(
                conversation_ids,
                fields="id, conversation_id, content",
            )
            message_map = {row["id"]: row for row in message_rows if row.get("id")}
            if message_map:
                escalations_result = (
                    supabase.table("escalations")
                    .select("id, created_at, status, message_id")
                    .in_("message_id", list(message_map.keys()))
                    .order("created_at", desc=True)
                    .limit(limit)
                    .execute()
                )
                for escalation in escalations_result.data or []:
                    message = message_map.get(escalation.get("message_id"))
                    content = str((message or {}).get("content") or "Question")
                    preview = content[:50] + "..." if len(content) > 50 else content
                    activities.append(
                        ActivityItem(
                            id=escalation["id"],
                            type="escalation",
                            title=f"Flagged: {preview}",
                            description=f"Status: {escalation['status']}",
                            time=escalation["created_at"],
                            metadata={"message_id": escalation.get("message_id")},
                        )
                    )

        sources_result = (
            supabase.table("sources")
            .select("id, filename, created_at, status")
            .eq("twin_id", twin_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        for source in sources_result.data or []:
            activities.append(
                ActivityItem(
                    id=source["id"],
                    type="source",
                    title=f"Uploaded: {source['filename']}",
                    description=f"Status: {source['status']}",
                    time=source["created_at"],
                    metadata={"source_id": source["id"]},
                )
            )

        activities.sort(key=lambda item: item.time, reverse=True)
        return activities[:limit]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/daily/{twin_id}", response_model=List[DailyMetric])
async def get_daily_metrics(
    twin_id: str,
    days: int = Query(7, ge=1, le=30),
    user=Depends(get_current_user),
):
    verify_twin_ownership(twin_id, user)
    try:
        start_date = date.today() - timedelta(days=days)
        conversations_result = (
            supabase.table("conversations")
            .select("id, created_at")
            .eq("twin_id", twin_id)
            .gte("created_at", start_date.isoformat())
            .execute()
        )
        conversations = conversations_result.data or []
        daily: Dict[str, Dict[str, Any]] = {}
        for conversation in conversations:
            day_key = str(conversation.get("created_at") or "")[:10]
            if day_key not in daily:
                daily[day_key] = {"conversations": 0, "messages": 0, "conversation_ids": []}
            daily[day_key]["conversations"] += 1
            daily[day_key]["conversation_ids"].append(conversation["id"])

        for day_key, payload in daily.items():
            if payload["conversation_ids"]:
                rows = _load_messages_for_conversations(payload["conversation_ids"], fields="id, conversation_id")
                payload["messages"] = len(rows)

        output: List[DailyMetric] = []
        current = start_date
        while current <= date.today():
            day_key = current.isoformat()
            payload = daily.get(day_key, {"conversations": 0, "messages": 0})
            output.append(
                DailyMetric(
                    date=day_key,
                    conversations=payload["conversations"],
                    messages=payload["messages"],
                )
            )
            current += timedelta(days=1)

        return output
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/top-questions/{twin_id}", response_model=List[TopQuestion])
async def get_top_questions(
    twin_id: str,
    limit: int = Query(5, ge=1, le=20),
    user=Depends(get_current_user),
):
    verify_twin_ownership(twin_id, user)
    try:
        conversations_result = supabase.table("conversations").select("id").eq("twin_id", twin_id).execute()
        conversation_ids = [row["id"] for row in (conversations_result.data or []) if row.get("id")]
        if not conversation_ids:
            return []

        messages = _load_messages_for_conversations(
            conversation_ids,
            fields="conversation_id, role, content, citations, answerability_state, review_required, created_at",
        )
        grouped = _group_messages_by_conversation(messages)

        aggregates: Dict[str, Dict[str, Any]] = {}
        for rows in grouped.values():
            pending_user: Optional[Dict[str, Any]] = None
            for row in rows:
                role = str(row.get("role") or "")
                if role == "user":
                    pending_user = row
                    continue
                if role != "assistant" or pending_user is None:
                    continue

                question_text = str(pending_user.get("content") or "").strip()
                if not question_text:
                    pending_user = None
                    continue

                key = question_text.lower()[:120]
                aggregate = aggregates.setdefault(
                    key,
                    {
                        "question": question_text[:100] + ("..." if len(question_text) > 100 else ""),
                        "count": 0,
                        "answer_states": Counter(),
                        "citation_count": 0,
                        "review_count": 0,
                    },
                )
                aggregate["count"] += 1
                state = _normalize_answerability_state(row.get("answerability_state"))
                aggregate["answer_states"][state] += 1
                if _has_citations(row.get("citations")):
                    aggregate["citation_count"] += 1
                if bool(row.get("review_required")):
                    aggregate["review_count"] += 1
                pending_user = None

        ranked = sorted(aggregates.values(), key=lambda item: item["count"], reverse=True)[:limit]
        return [
            TopQuestion(
                question=item["question"],
                count=item["count"],
                top_answerability_state=item["answer_states"].most_common(1)[0][0] if item["answer_states"] else "direct",
                review_rate=_safe_rate(item["review_count"], item["count"]),
                citation_rate=_safe_rate(item["citation_count"], item["count"]),
            )
            for item in ranked
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/events")
async def log_event(event: EventCreate, user_id: Optional[str] = None, user=Depends(get_current_user)):
    if event.twin_id:
        verify_twin_ownership(event.twin_id, user)
    try:
        payload: Dict[str, Any] = {
            "event_type": event.event_type,
            "event_data": event.event_data,
            "session_id": event.session_id,
        }
        if user_id:
            payload["user_id"] = user_id
        if event.twin_id:
            payload["twin_id"] = event.twin_id
        result = supabase.table("user_events").insert(payload).execute()
        return {"success": True, "event_id": result.data[0]["id"] if result.data else None}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@router.get("/events/{user_id}")
async def get_user_events(
    user_id: str,
    event_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    user=Depends(get_current_user),
):
    if user.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Unauthorized access to user events")
    try:
        query = (
            supabase.table("user_events")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if event_type:
            query = query.eq("event_type", event_type)
        result = query.execute()
        return result.data or []
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
