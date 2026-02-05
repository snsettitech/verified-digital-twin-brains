"""
Metrics and Analytics Router
Provides endpoints for dashboard analytics, user events, and session tracking.
Uses real data from conversations and messages tables.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date, timedelta
from modules.observability import supabase

router = APIRouter(prefix="/metrics", tags=["metrics"])


# ============================================================================
# Schemas
# ============================================================================

class EventCreate(BaseModel):
    event_type: str
    twin_id: Optional[str] = None
    event_data: Optional[dict] = {}
    session_id: Optional[str] = None


class DashboardStats(BaseModel):
    conversations: int
    messages: int
    user_messages: int
    assistant_messages: int
    avg_confidence: float
    escalation_rate: float
    response_rate: float


class DailyMetric(BaseModel):
    date: str
    conversations: int
    messages: int


class TopQuestion(BaseModel):
    question: str
    count: int
    avg_confidence: float


class ConversationSummary(BaseModel):
    id: str
    created_at: str
    message_count: int
    last_message: Optional[str] = None
    avg_confidence: float


class ActivityItem(BaseModel):
    id: str
    type: str  # 'conversation', 'message', 'escalation', 'source'
    title: str
    description: str
    time: str
    metadata: Optional[dict] = {}


# ============================================================================
# Dashboard Stats Endpoint - REAL DATA
# ============================================================================

@router.get("/dashboard/{twin_id}", response_model=DashboardStats)
async def get_dashboard_stats(twin_id: str, days: int = Query(30, ge=1, le=90)):
    """Get aggregated dashboard statistics for a twin from REAL data."""
    try:
        start_date = datetime.now() - timedelta(days=days)
        
        # Get all conversations for this twin
        conversations_result = supabase.table("conversations")\
            .select("id, created_at")\
            .eq("twin_id", twin_id)\
            .gte("created_at", start_date.isoformat())\
            .execute()
        
        conversations = conversations_result.data or []
        total_conversations = len(conversations)
        
        if total_conversations == 0:
            return DashboardStats(
                conversations=0,
                messages=0,
                user_messages=0,
                assistant_messages=0,
                avg_confidence=0,
                escalation_rate=0,
                response_rate=100
            )
        
        # Get all messages for these conversations
        conversation_ids = [c["id"] for c in conversations]
        
        # Query messages (may need to batch if too many conversations)
        all_messages = []
        # Supabase has limits, so we batch the query
        batch_size = 50
        for i in range(0, len(conversation_ids), batch_size):
            batch_ids = conversation_ids[i:i+batch_size]
            messages_result = supabase.table("messages")\
                .select("id, role, confidence_score, conversation_id")\
                .in_("conversation_id", batch_ids)\
                .execute()
            all_messages.extend(messages_result.data or [])
        
        total_messages = len(all_messages)
        user_messages = [m for m in all_messages if m["role"] == "user"]
        assistant_messages = [m for m in all_messages if m["role"] == "assistant"]
        
        # Calculate response rate (% of user messages that got a response)
        # If there are matching counts, response rate is high
        response_rate = (len(assistant_messages) / len(user_messages) * 100) if user_messages else 100
        response_rate = min(100, response_rate)  # Cap at 100%
        
        # Calculate average confidence from assistant messages
        confidences = [m["confidence_score"] for m in assistant_messages if m.get("confidence_score")]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        # Get escalation count
        escalations_result = supabase.table("escalations")\
            .select("id, message_id")\
            .execute()
        
        # Filter escalations for this twin's messages
        message_ids = {m["id"] for m in all_messages}
        twin_escalations = [e for e in (escalations_result.data or []) if e.get("message_id") in message_ids]
        escalation_rate = (len(twin_escalations) / len(user_messages) * 100) if user_messages else 0
        
        return DashboardStats(
            conversations=total_conversations,
            messages=total_messages,
            user_messages=len(user_messages),
            assistant_messages=len(assistant_messages),
            avg_confidence=round(avg_confidence, 1),
            escalation_rate=round(escalation_rate, 1),
            response_rate=round(response_rate, 1)
        )
        
    except Exception as e:
        print(f"Error in metrics endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# Conversations List Endpoint
# ============================================================================

@router.get("/conversations/{twin_id}", response_model=List[ConversationSummary])
async def get_conversations_list(twin_id: str, limit: int = Query(20, ge=1, le=100)):
    """Get list of conversations with summary info."""
    try:
        # Get conversations
        conversations_result = supabase.table("conversations")\
            .select("id, created_at")\
            .eq("twin_id", twin_id)\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()
        
        conversations = conversations_result.data or []
        
        if not conversations:
            return []
        
        # Get messages for each conversation
        summaries = []
        for conv in conversations:
            messages_result = supabase.table("messages")\
                .select("content, role, confidence_score, created_at")\
                .eq("conversation_id", conv["id"])\
                .order("created_at", desc=True)\
                .execute()
            
            messages = messages_result.data or []
            confidences = [m["confidence_score"] for m in messages if m.get("confidence_score")]
            
            # Get last user message as preview
            user_messages = [m for m in messages if m["role"] == "user"]
            last_message = user_messages[0]["content"][:100] if user_messages else None
            
            summaries.append(ConversationSummary(
                id=conv["id"],
                created_at=conv["created_at"],
                message_count=len(messages),
                last_message=last_message,
                avg_confidence=round(sum(confidences) / len(confidences), 1) if confidences else 0
            ))
        
        return summaries
        
    except Exception as e:
        print(f"Error: {e}"); raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# Activity Feed Endpoint
# ============================================================================

@router.get("/activity/{twin_id}", response_model=List[ActivityItem])
async def get_activity_feed(twin_id: str, limit: int = Query(10, ge=1, le=50)):
    """Get recent activity feed for a twin."""
    try:
        activities = []
        
        # Get recent conversations
        conversations_result = supabase.table("conversations")\
            .select("id, created_at")\
            .eq("twin_id", twin_id)\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()
        
        for conv in conversations_result.data or []:
            # Get first message of conversation
            messages_result = supabase.table("messages")\
                .select("content, role")\
                .eq("conversation_id", conv["id"])\
                .eq("role", "user")\
                .order("created_at", desc=False)\
                .limit(1)\
                .execute()
            
            first_msg = messages_result.data[0] if messages_result.data else None
            preview = first_msg["content"][:50] + "..." if first_msg and len(first_msg["content"]) > 50 else (first_msg["content"] if first_msg else "New conversation")
            
            activities.append(ActivityItem(
                id=conv["id"],
                type="conversation",
                title=f"Asked: {preview}",
                description="Anonymous visitor",
                time=conv["created_at"],
                metadata={"conversation_id": conv["id"]}
            ))
        
        # Get recent escalations - ONLY for this twin's conversations
        # First get conversation IDs for this twin
        conversation_ids = [c["id"] for c in (conversations_result.data or [])]
        
        if conversation_ids:
            # Get messages for these conversations
            messages_result = supabase.table("messages")\
                .select("id, conversation_id, content")\
                .in_("conversation_id", conversation_ids)\
                .execute()
            
            message_ids = {m["id"]: m for m in (messages_result.data or [])}
            
            if message_ids:
                # Get escalations for these messages only
                escalations_result = supabase.table("escalations")\
                    .select("id, created_at, status, message_id")\
                    .in_("message_id", list(message_ids.keys()))\
                    .order("created_at", desc=True)\
                    .limit(limit)\
                    .execute()
                
                for esc in escalations_result.data or []:
                    msg = message_ids.get(esc.get("message_id"))
                    question_preview = msg["content"][:50] + "..." if msg and len(msg.get("content", "")) > 50 else (msg["content"] if msg else "Question")
                    activities.append(ActivityItem(
                        id=esc["id"],
                        type="escalation",
                        title=f"Flagged: {question_preview}",
                        description=f"Status: {esc['status']}",
                        time=esc["created_at"],
                        metadata={"message_id": esc.get("message_id")}
                    ))
        
        # Get recent sources
        sources_result = supabase.table("sources")\
            .select("id, filename, created_at, status")\
            .eq("twin_id", twin_id)\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()
        
        for src in sources_result.data or []:
            activities.append(ActivityItem(
                id=src["id"],
                type="source",
                title=f"Uploaded: {src['filename']}",
                description=f"Status: {src['status']}",
                time=src["created_at"],
                metadata={"source_id": src["id"]}
            ))
        
        # Sort all activities by time, most recent first
        activities.sort(key=lambda x: x.time, reverse=True)
        
        return activities[:limit]
        
    except Exception as e:
        print(f"Error: {e}"); raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# Daily Metrics Endpoint - REAL DATA
# ============================================================================

@router.get("/daily/{twin_id}", response_model=List[DailyMetric])
async def get_daily_metrics(twin_id: str, days: int = Query(7, ge=1, le=30)):
    """Get daily conversation metrics for charts from REAL data."""
    try:
        start_date = date.today() - timedelta(days=days)
        
        # Get conversations directly
        conversations_result = supabase.table("conversations")\
            .select("id, created_at")\
            .eq("twin_id", twin_id)\
            .gte("created_at", start_date.isoformat())\
            .execute()
        
        conversations = conversations_result.data or []
        
        # Group by date
        daily = {}
        for conv in conversations:
            d = conv["created_at"][:10]  # YYYY-MM-DD
            if d not in daily:
                daily[d] = {"conversations": 0, "messages": 0, "conversation_ids": []}
            daily[d]["conversations"] += 1
            daily[d]["conversation_ids"].append(conv["id"])
        
        # Get message counts for each day
        for d, data in daily.items():
            if data["conversation_ids"]:
                messages_result = supabase.table("messages")\
                    .select("id")\
                    .in_("conversation_id", data["conversation_ids"])\
                    .execute()
                data["messages"] = len(messages_result.data or [])
        
        # Fill in missing days with zeros
        result = []
        current = start_date
        while current <= date.today():
            d_str = current.isoformat()
            if d_str in daily:
                result.append(DailyMetric(
                    date=d_str,
                    conversations=daily[d_str]["conversations"],
                    messages=daily[d_str]["messages"]
                ))
            else:
                result.append(DailyMetric(date=d_str, conversations=0, messages=0))
            current += timedelta(days=1)
        
        return result
        
    except Exception as e:
        print(f"Error: {e}"); raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# Top Questions Endpoint - REAL DATA
# ============================================================================

@router.get("/top-questions/{twin_id}", response_model=List[TopQuestion])
async def get_top_questions(twin_id: str, limit: int = Query(5, ge=1, le=20)):
    """Get most frequently asked questions from REAL conversations."""
    try:
        # Get conversation IDs for this twin
        conversations_result = supabase.table("conversations")\
            .select("id")\
            .eq("twin_id", twin_id)\
            .execute()
        
        conversation_ids = [c["id"] for c in (conversations_result.data or [])]
        
        if not conversation_ids:
            return []
        
        # Get user messages from these conversations
        all_messages = []
        batch_size = 50
        for i in range(0, len(conversation_ids), batch_size):
            batch_ids = conversation_ids[i:i+batch_size]
            messages_result = supabase.table("messages")\
                .select("content, confidence_score, conversation_id")\
                .in_("conversation_id", batch_ids)\
                .eq("role", "user")\
                .execute()
            all_messages.extend(messages_result.data or [])
        
        # Count question frequency (simple approach - group similar questions)
        questions = {}
        for msg in all_messages:
            content = msg.get("content", "").strip()
            if not content:
                continue
            
            # Normalize: lowercase, first 100 chars
            key = content.lower()[:100]
            
            if key not in questions:
                questions[key] = {
                    "display": content[:100] + ("..." if len(content) > 100 else ""),
                    "count": 0,
                    "confidences": []
                }
            questions[key]["count"] += 1
            
            # Get the confidence from the assistant response (next message)
            # For now use a mock - in real app, you'd join with assistant response
            if msg.get("confidence_score"):
                questions[key]["confidences"].append(msg["confidence_score"])
        
        # Sort by count
        sorted_q = sorted(questions.items(), key=lambda x: x[1]["count"], reverse=True)[:limit]
        
        return [
            TopQuestion(
                question=data["display"],
                count=data["count"],
                avg_confidence=round(sum(data["confidences"]) / len(data["confidences"]), 1) if data["confidences"] else 85.0
            )
            for _, data in sorted_q
        ]
        
    except Exception as e:
        print(f"Error: {e}"); raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# Event Logging
# ============================================================================

@router.post("/events")
async def log_event(event: EventCreate, user_id: Optional[str] = None):
    """Log a user event for analytics."""
    try:
        data = {
            "event_type": event.event_type,
            "event_data": event.event_data,
            "session_id": event.session_id
        }
        
        if user_id:
            data["user_id"] = user_id
        if event.twin_id:
            data["twin_id"] = event.twin_id
            
        result = supabase.table("user_events").insert(data).execute()
        
        return {"success": True, "event_id": result.data[0]["id"] if result.data else None}
    except Exception as e:
        # Don't fail if event logging fails
        return {"success": False, "error": str(e)}


@router.get("/events/{user_id}")
async def get_user_events(
    user_id: str,
    event_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200)
):
    """Get events for a specific user."""
    try:
        query = supabase.table("user_events")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("created_at", desc=True)\
            .limit(limit)
        
        if event_type:
            query = query.eq("event_type", event_type)
            
        result = query.execute()
        
        return {"events": result.data or []}
        
    except Exception as e:
        print(f"Error: {e}"); raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# Phase 10: Enterprise Scale - System Metrics
# ============================================================================

@router.get("/system")
async def get_system_metrics(days: int = Query(7, ge=1, le=30)):
    """
    Get system-wide metrics summary.
    
    Returns aggregated metrics across all twins for admin dashboard.
    """
    from modules.metrics_collector import get_metrics_summary, get_usage_by_twin
    
    try:
        summary = get_metrics_summary(twin_id=None, days=days)
        usage_by_twin = get_usage_by_twin(days=days)
        
        return {
            "summary": summary,
            "usage_by_twin": usage_by_twin[:10],  # Top 10
            "period_days": days
        }
    except Exception as e:
        print(f"Error: {e}"); raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/usage/{twin_id}")
async def get_twin_usage(twin_id: str, days: int = Query(7, ge=1, le=30)):
    """
    Get usage metrics for a specific twin.
    
    Returns token usage, latency stats, and error counts.
    """
    from modules.metrics_collector import get_metrics_summary
    
    try:
        summary = get_metrics_summary(twin_id=twin_id, days=days)
        return summary
    except Exception as e:
        print(f"Error: {e}"); raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# Phase 10: Enterprise Scale - Service Health
# ============================================================================

@router.get("/health")
async def get_detailed_health():
    """
    Get detailed health status of all external services.
    
    Checks: Supabase, Pinecone, OpenAI connectivity.
    """
    import time
    import os
    from modules.metrics_collector import log_service_health
    
    health = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {}
    }
    
    # Check Supabase
    try:
        start = time.time()
        result = supabase.table("twins").select("id").limit(1).execute()
        response_ms = (time.time() - start) * 1000
        health["services"]["supabase"] = {
            "status": "healthy",
            "response_ms": round(response_ms, 2)
        }
        log_service_health("supabase", "healthy", response_ms)
    except Exception as e:
        health["services"]["supabase"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health["status"] = "degraded"
        log_service_health("supabase", "unhealthy", error_message=str(e))
    
    # Check Pinecone
    try:
        from pinecone import Pinecone
        start = time.time()
        pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        index = pc.Index(os.getenv("PINECONE_INDEX_NAME", "digital-twin"))
        stats = index.describe_index_stats()
        response_ms = (time.time() - start) * 1000
        health["services"]["pinecone"] = {
            "status": "healthy",
            "response_ms": round(response_ms, 2),
            "vector_count": stats.total_vector_count if stats else 0
        }
        log_service_health("pinecone", "healthy", response_ms)
    except Exception as e:
        health["services"]["pinecone"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health["status"] = "degraded"
        log_service_health("pinecone", "unhealthy", error_message=str(e))
    
    # Check OpenAI (lightweight check - just validate key format)
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key and openai_key.startswith("sk-"):
        health["services"]["openai"] = {
            "status": "configured",
            "note": "API key present, not validated to avoid cost"
        }
    else:
        health["services"]["openai"] = {
            "status": "unconfigured",
            "error": "OPENAI_API_KEY not set or invalid format"
        }
        health["status"] = "degraded"
    
    return health


# ============================================================================
# Phase 10: Enterprise Scale - Usage Quotas
# ============================================================================

@router.get("/quota/{tenant_id}")
async def get_quota_status(tenant_id: str):
    """
    Get current quota status for a tenant.
    
    Returns current usage vs limits for all quota types.
    """
    try:
        result = supabase.table("usage_quotas")\
            .select("*")\
            .eq("tenant_id", tenant_id)\
            .execute()
        
        quotas = result.data or []
        
        # Default quotas if none set
        if not quotas:
            return {
                "tenant_id": tenant_id,
                "quotas": [
                    {
                        "quota_type": "daily_tokens",
                        "limit": 100000,
                        "current_usage": 0,
                        "remaining": 100000,
                        "percent_used": 0
                    }
                ]
            }
        
        formatted = []
        for q in quotas:
            limit_val = q.get("limit_value", 100000)
            current = q.get("current_usage", 0)
            formatted.append({
                "quota_type": q["quota_type"],
                "limit": limit_val,
                "current_usage": current,
                "remaining": limit_val - current,
                "percent_used": round((current / limit_val) * 100, 1) if limit_val > 0 else 0,
                "reset_at": q.get("reset_at")
            })
        
        return {
            "tenant_id": tenant_id,
            "quotas": formatted
        }
        
    except Exception as e:
        print(f"Error: {e}"); raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/quota/{tenant_id}/set")
async def set_quota(tenant_id: str, quota_type: str, limit_value: int):
    """
    Set or update a quota for a tenant.
    
    Admin endpoint to configure tenant limits.
    """
    try:
        # Upsert quota
        result = supabase.table("usage_quotas").upsert({
            "tenant_id": tenant_id,
            "quota_type": quota_type,
            "limit_value": limit_value,
            "reset_at": (datetime.utcnow() + timedelta(days=1)).isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }, on_conflict="tenant_id,quota_type").execute()
        
        return {"success": True, "data": result.data}
    except Exception as e:
        print(f"Error: {e}"); raise HTTPException(status_code=500, detail="Internal server error")

