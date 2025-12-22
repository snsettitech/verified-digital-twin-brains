from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class ChatRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None
    group_id: Optional[str] = None  # NEW: Allow group override

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

class BulkApproveRequest(BaseModel):
    source_ids: List[str]

class BulkUpdateRequest(BaseModel):
    source_ids: List[str]
    metadata: Dict[str, Any]  # Can include: publish_date, author, citation_url

class SourceRejectRequest(BaseModel):
    reason: str

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