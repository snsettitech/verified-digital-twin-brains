from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class ChatRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None
    group_id: Optional[str] = None  # NEW: Allow group override
    metadata: Optional[Dict[str, Any]] = None
    mode: Optional[str] = None  # Deprecated: ignored for auth/routing decisions
    training_session_id: Optional[str] = None
    # Compatibility: accept legacy {message} payloads for one release window
    message: Optional[str] = None

class ChatMetadata(BaseModel):
    type: str = "metadata"
    confidence_score: float
    citations: List[str]
    conversation_id: str

class ChatContent(BaseModel):
    type: str = "content"
    content: str

class ChatDone(BaseModel):
    type: str = "done"
    escalated: bool

class IngestionResponse(BaseModel):
    status: str
    chunks_ingested: int
    source_id: str

class SourceSchema(BaseModel):
    id: str
    twin_id: str
    filename: Optional[str]
    file_size: Optional[int]
    status: str
    created_at: Optional[datetime]

class MessageSchema(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    confidence_score: Optional[float]
    citations: Optional[List[str]]
    created_at: Optional[datetime]

class ConversationSchema(BaseModel):
    id: str
    twin_id: str
    user_id: Optional[str]
    created_at: Optional[datetime]

class EscalationSchema(BaseModel):
    id: str
    message_id: str
    status: str
    created_at: datetime
    messages: Optional[MessageSchema] = None

class TwinSettingsUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    specialization_id: Optional[str] = None  # NEW: Gate 1
    is_public: Optional[bool] = None  # NEW: Publish Gating
    settings: Optional[Dict[str, Any]] = None

class YouTubeIngestRequest(BaseModel):
    url: str

class PodcastIngestRequest(BaseModel):
    url: str # RSS feed or direct audio link

class XThreadIngestRequest(BaseModel):
    url: str

class KnowledgeProfile(BaseModel):
    total_chunks: int
    total_sources: int
    fact_count: int
    opinion_count: int
    tone_distribution: Dict[str, int]
    top_tone: str

class CitationSchema(BaseModel):
    id: str
    verified_qna_id: str
    source_id: Optional[str] = None
    chunk_id: Optional[str] = None
    citation_url: Optional[str] = None
    created_at: Optional[datetime] = None

class AnswerPatchSchema(BaseModel):
    id: str
    verified_qna_id: str
    previous_answer: str
    new_answer: str
    reason: Optional[str] = None
    patched_by: Optional[str] = None
    patched_at: Optional[datetime] = None

class VerifiedQnASchema(BaseModel):
    id: str
    twin_id: str
    question: str
    answer: str
    visibility: str
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_active: bool
    citations: Optional[List[CitationSchema]] = None
    patches: Optional[List[AnswerPatchSchema]] = None

class VerifiedQnACreateRequest(BaseModel):
    question: str
    answer: str
    citations: Optional[List[str]] = None
    visibility: Optional[str] = "private"

class VerifiedQnAUpdateRequest(BaseModel):
    answer: str
    reason: str

# Access Groups Schemas
class AccessGroupSchema(BaseModel):
    id: str
    twin_id: str
    name: str
    description: Optional[str] = None
    is_default: bool
    is_public: bool
    settings: Dict[str, Any]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class GroupMembershipSchema(BaseModel):
    id: str
    group_id: str
    user_id: str
    twin_id: str
    is_active: bool
    created_at: Optional[datetime] = None

class ContentPermissionSchema(BaseModel):
    id: str
    group_id: str
    twin_id: str
    content_type: str
    content_id: str
    created_at: Optional[datetime] = None

class GroupCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    is_public: bool = False
    settings: Optional[Dict[str, Any]] = None

class GroupUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None

class AssignUserRequest(BaseModel):
    user_id: str
    group_id: str

class ContentPermissionRequest(BaseModel):
    content_type: str  # 'source' or 'verified_qna'
    content_ids: List[str]  # List of IDs to grant access

class GroupLimitSchema(BaseModel):
    id: str
    group_id: str
    limit_type: str
    limit_value: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class GroupOverrideSchema(BaseModel):
    id: str
    group_id: str
    override_type: str
    override_value: Dict[str, Any]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# Phase 6: Mind Ops Layer Schemas

class SourceHealthCheckSchema(BaseModel):
    id: str
    source_id: str
    check_type: str
    status: str
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class TrainingJobSchema(BaseModel):
    id: str
    source_id: str
    twin_id: str
    status: str
    job_type: str
    priority: int
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class IngestionLogSchema(BaseModel):
    id: str
    source_id: str
    twin_id: str
    log_level: str
    message: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None

class BulkUpdateRequest(BaseModel):
    source_ids: List[str]
    metadata: Dict[str, Any]  # Can include: publish_date, author, citation_url

# Phase 7: Omnichannel Distribution Schemas

class ApiKeyCreateRequest(BaseModel):
    twin_id: str
    name: str
    group_id: Optional[str] = None
    allowed_domains: Optional[List[str]] = None
    expires_at: Optional[datetime] = None

class ApiKeyUpdateRequest(BaseModel):
    name: Optional[str] = None
    allowed_domains: Optional[List[str]] = None
    is_active: Optional[bool] = None
    expires_at: Optional[datetime] = None

class ApiKeySchema(BaseModel):
    id: str
    twin_id: str
    name: str
    key_prefix: str
    group_id: Optional[str] = None
    allowed_domains: List[str]
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

class ShareLinkResponse(BaseModel):
    twin_id: str
    share_token: Optional[str]
    share_url: Optional[str]
    public_share_enabled: bool

class SessionCreateRequest(BaseModel):
    twin_id: str
    group_id: Optional[str] = None
    session_type: str  # 'anonymous' or 'authenticated'
    user_id: Optional[str] = None

class SessionSchema(BaseModel):
    id: str
    twin_id: str
    group_id: Optional[str] = None
    session_type: str
    user_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime
    last_active_at: datetime
    expires_at: datetime

class RateLimitStatusResponse(BaseModel):
    requests_per_hour: Optional[Dict[str, Any]] = None
    requests_per_day: Optional[Dict[str, Any]] = None

class UserInvitationCreateRequest(BaseModel):
    email: str
    role: str # 'owner' or 'viewer'

class UserInvitationSchema(BaseModel):
    id: str
    tenant_id: str
    email: str
    invitation_token: str
    invitation_url: str
    role: str
    status: str
    expires_at: datetime
    created_at: datetime

class ChatWidgetRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    api_key: str
    # Compatibility: accept legacy {message} payloads for one release window
    message: Optional[str] = None

class PublicChatRequest(BaseModel):
    message: str
    conversation_history: Optional[List[Dict[str, Any]]] = None

# Owner Memory + Clarifications

class OwnerMemorySchema(BaseModel):
    id: str
    twin_id: str
    tenant_id: str
    topic_normalized: str
    memory_type: str
    value: str
    stance: Optional[str] = None
    intensity: Optional[int] = None
    confidence: Optional[float] = None
    status: str
    created_at: Optional[datetime] = None

class ClarificationThreadSchema(BaseModel):
    id: str
    twin_id: str
    tenant_id: str
    status: str
    mode: str
    original_query: Optional[str] = None
    question: str
    options: Optional[List[Dict[str, Any]]] = None
    memory_write_proposal: Optional[Dict[str, Any]] = None
    owner_memory_id: Optional[str] = None
    created_at: Optional[datetime] = None

class ClarificationResolveRequest(BaseModel):
    answer: str
    selected_option: Optional[str] = None

# Phase 9: Verification & Governance Schemas

class AuditLogSchema(BaseModel):
    id: str
    twin_id: str
    actor_id: Optional[str] = None
    event_type: str
    action: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

class GovernancePolicySchema(BaseModel):
    id: str
    twin_id: str
    policy_type: str
    name: str
    content: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

class GovernancePolicyCreateRequest(BaseModel):
    policy_type: str
    name: str
    content: str
    is_active: bool = True

class TwinVerificationSchema(BaseModel):
    id: str
    twin_id: str
    status: str
    verification_method: str
    metadata: Optional[Dict[str, Any]] = None
    requested_at: datetime
    verified_at: Optional[datetime] = None
    verified_by: Optional[str] = None

class TwinVerificationRequest(BaseModel):
    verification_method: str = "MANUAL_REVIEW"
    metadata: Optional[Dict[str, Any]] = None

class DeepScrubRequest(BaseModel):
    source_id: str
    reason: Optional[str] = None

# Phase 8: Actions Engine Schemas

class EventSchema(BaseModel):
    id: str
    twin_id: str
    event_type: str
    payload: Dict[str, Any]
    source_context: Optional[Dict[str, Any]] = None
    created_at: datetime

class TriggerConditions(BaseModel):
    intent_contains: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    confidence_below: Optional[float] = None
    group_id: Optional[str] = None

class ActionTriggerSchema(BaseModel):
    id: str
    twin_id: str
    name: str
    description: Optional[str] = None
    event_type: str
    conditions: Dict[str, Any]
    connector_id: Optional[str] = None
    action_type: str
    action_config: Dict[str, Any]
    requires_approval: bool
    is_active: bool
    priority: int
    created_at: datetime
    updated_at: datetime

class TriggerCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    event_type: str
    conditions: Optional[Dict[str, Any]] = None
    connector_id: Optional[str] = None
    action_type: str
    action_config: Optional[Dict[str, Any]] = None
    requires_approval: bool = True

class TriggerUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None
    action_config: Optional[Dict[str, Any]] = None
    requires_approval: Optional[bool] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None

class ActionDraftSchema(BaseModel):
    id: str
    trigger_id: Optional[str] = None
    event_id: Optional[str] = None
    twin_id: str
    status: str
    proposed_action: Dict[str, Any]
    context: Dict[str, Any]
    approval_note: Optional[str] = None
    approved_by: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

class DraftApproveRequest(BaseModel):
    approval_note: Optional[str] = None

class DraftRejectRequest(BaseModel):
    rejection_note: Optional[str] = None

class DraftRespondRequest(BaseModel):
    """Owner response to a triggered action - creates a saved response"""
    response_message: str
    save_as_verified: bool = False  # If true, save as verified QnA for future use

class ActionExecutionSchema(BaseModel):
    id: str
    draft_id: Optional[str] = None
    trigger_id: Optional[str] = None
    twin_id: str
    connector_id: Optional[str] = None
    action_type: str
    status: str
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    error_message: Optional[str] = None
    execution_duration_ms: Optional[int] = None
    executed_by: Optional[str] = None
    executed_at: datetime

class ToolConnectorSchema(BaseModel):
    id: str
    twin_id: str
    connector_type: str
    name: str
    config: Dict[str, Any]
    is_active: bool
    last_used_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime

class ConnectorCreateRequest(BaseModel):
    connector_type: str
    name: str
    config: Optional[Dict[str, Any]] = None

class ConnectorTestResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None

class EventEmitRequest(BaseModel):
    event_type: str
    payload: Dict[str, Any]
    source_context: Optional[Dict[str, Any]] = None


# ============================================================================
# Governance & Audit Schemas
# ============================================================================

class AuditLogSchema(BaseModel):
    id: str
    twin_id: Optional[str] = None
    tenant_id: Optional[str] = None
    actor_id: Optional[str] = None
    event_type: str
    action: str
    metadata: Dict[str, Any]
    created_at: datetime
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class GovernancePolicySchema(BaseModel):
    id: str
    tenant_id: Optional[str] = None
    twin_id: Optional[str] = None
    policy_type: str
    name: str
    content: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None


class GovernancePolicyCreateRequest(BaseModel):
    policy_type: str = "refusal_rule"
    name: str
    content: str


class TwinVerificationRequest(BaseModel):
    verification_method: str = "MANUAL_REVIEW"
    metadata: Optional[Dict[str, Any]] = None


class DeepScrubRequest(BaseModel):
    reason: Optional[str] = None
