# backend/routers/feedback.py
"""User Feedback Router

Allows users to provide feedback on chat responses with thumbs up/down.
Stores feedback as Langfuse scores for quality tracking.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Literal, List
from enum import Enum

from modules.auth_guard import get_current_user, verify_conversation_ownership, verify_twin_ownership
from modules.observability import supabase
from modules.persona_feedback_learning import record_feedback_training_event
from modules.persona_feedback_learning_jobs import enqueue_feedback_learning_job

router = APIRouter(tags=["feedback"])


class FeedbackReason(str, Enum):
    INCORRECT = "incorrect"
    HALLUCINATION = "hallucination"
    OFF_TOPIC = "off_topic"
    INCOMPLETE = "incomplete"
    GREAT_ANSWER = "great_answer"
    HELPFUL = "helpful"
    OTHER = "other"


class FeedbackRequest(BaseModel):
    score: Literal[-1, 1] = Field(..., description="Thumbs down (-1) or up (+1)")
    reason: FeedbackReason = Field(..., description="Reason for feedback")
    comment: Optional[str] = Field(None, max_length=500, description="Optional additional comment")
    message_id: Optional[str] = Field(None, description="Optional message ID for context")
    twin_id: Optional[str] = Field(None, description="Twin ID for feedback-learning ingestion")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for context resolution")
    intent_label: Optional[str] = Field(None, description="Runtime intent label from chat metadata")
    module_ids: List[str] = Field(default_factory=list, description="Persona module IDs used for the answer")
    interaction_context: Optional[str] = Field(None, description="owner_training|owner_chat|public_share|public_widget")


class FeedbackResponse(BaseModel):
    success: bool
    message: str
    trace_id: str


@router.post("/feedback/{trace_id}", response_model=FeedbackResponse)
async def submit_feedback(
    trace_id: str,
    request: FeedbackRequest,
    user=Depends(get_current_user),
):
    """
    Submit user feedback for a chat response.
    
    Args:
        trace_id: Langfuse trace ID to associate feedback with
        request: Feedback details (score, reason, comment)
    
    Returns:
        Confirmation of feedback submission
    """
    if not user or not user.get("user_id"):
        raise HTTPException(status_code=401, detail="Authentication required")
    if user.get("role") == "visitor":
        raise HTTPException(status_code=403, detail="Feedback requires authenticated owner/member context")

    langfuse_error: Optional[str] = None
    try:
        from langfuse import get_client

        client = get_client()
        if client:
            # Log score to Langfuse
            client.score(
                trace_id=trace_id,
                name="user_feedback",
                value=request.score,
                comment=f"{request.reason.value}: {request.comment}" if request.comment else request.reason.value,
                data_type="NUMERIC",
            )

            # Also log reason as separate score for filtering
            client.score(
                trace_id=trace_id,
                name="feedback_reason",
                value=1 if request.score > 0 else 0,
                comment=request.reason.value,
                data_type="CATEGORICAL",
            )
            client.flush()
        else:
            langfuse_error = "Langfuse client not available"
    except ImportError:
        langfuse_error = "Langfuse SDK not installed"
    except Exception as e:
        langfuse_error = str(e)

    resolved_twin_id = request.twin_id
    if request.conversation_id:
        try:
            verify_conversation_ownership(request.conversation_id, user)
            conv_res = (
                supabase.table("conversations")
                .select("twin_id")
                .eq("id", request.conversation_id)
                .single()
                .execute()
            )
            if conv_res.data:
                conv_twin_id = conv_res.data.get("twin_id")
                if request.twin_id and conv_twin_id and str(request.twin_id) != str(conv_twin_id):
                    raise HTTPException(status_code=403, detail="conversation_id does not belong to twin_id")
                if not resolved_twin_id:
                    resolved_twin_id = conv_twin_id
        except HTTPException:
            raise
        except Exception:
            resolved_twin_id = request.twin_id

    if resolved_twin_id:
        verify_twin_ownership(resolved_twin_id, user)

    try:
        record_feedback_training_event(
            trace_id=trace_id,
            score=float(request.score),
            reason=request.reason.value,
            comment=request.comment,
            twin_id=resolved_twin_id,
            tenant_id=user.get("tenant_id"),
            conversation_id=request.conversation_id,
            message_id=request.message_id,
            intent_label=request.intent_label,
            module_ids=request.module_ids,
            interaction_context=request.interaction_context,
            created_by=user.get("user_id"),
        )
    except Exception:
        # Non-blocking; response remains successful if core feedback logging succeeded.
        pass

    try:
        if resolved_twin_id:
            enqueue_feedback_learning_job(
                twin_id=resolved_twin_id,
                tenant_id=user.get("tenant_id"),
                created_by=user.get("user_id"),
                trigger="feedback_event",
                force=False,
            )
    except Exception:
        # Non-blocking; feedback response should not fail if job enqueueing fails.
        pass

    if langfuse_error and not resolved_twin_id:
        raise HTTPException(
            status_code=503,
            detail=f"Feedback capture unavailable: {langfuse_error}. Provide twin_id/conversation_id to store locally.",
        )

    message = "Feedback submitted successfully"
    if langfuse_error:
        message = f"Feedback stored locally; Langfuse logging unavailable ({langfuse_error})"

    return FeedbackResponse(
        success=True,
        message=message,
        trace_id=trace_id
    )


@router.get("/feedback/reasons")
async def get_feedback_reasons():
    """Get available feedback reason options for the UI."""
    return {
        "positive": [
            {"value": "great_answer", "label": "Great answer"},
            {"value": "helpful", "label": "Helpful"},
        ],
        "negative": [
            {"value": "incorrect", "label": "Incorrect information"},
            {"value": "hallucination", "label": "Made up facts"},
            {"value": "off_topic", "label": "Off topic"},
            {"value": "incomplete", "label": "Incomplete answer"},
            {"value": "other", "label": "Other"},
        ]
    }
