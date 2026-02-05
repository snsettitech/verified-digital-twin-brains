# Backend Route Inventory

## Entrypoints And Router Registration
- FastAPI app is defined in `backend/main.py` with CORS and correlation-ID middleware.
- Routers are registered in `backend/main.py` (see the `app.include_router(...)` list).
- Conditional routers:
  - `backend/routers/enhanced_ingestion.py` registered only if `ENABLE_ENHANCED_INGESTION=true` in `backend/main.py`.
  - `backend/api/vc_routes.py` registered only if `ENABLE_VC_ROUTES=true` in `backend/main.py`, with prefix `/api`.
- Uvicorn entrypoints:
  - `backend/Procfile` (`uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}`)
  - `backend/railway.json` (`uvicorn main:app --host 0.0.0.0 --port $PORT`)

## Base Health Endpoints
Defined in `backend/main.py`:
- `GET /health` -> `{ status, service, version }`
- `GET /` -> same as `/health`

## Routes By Router

### `backend/routers/auth.py` (registered in `backend/main.py`)
| Method | Path | Request | Response | Auth/Deps |
| --- | --- | --- | --- | --- |
| POST | `/auth/sync-user` | `SyncUserResponse` (response model) | `SyncUserResponse` | `Depends(get_current_user)` |
| GET | `/auth/whoami` | none | identity dict | `Depends(get_current_user)` |
| GET | `/auth/me` | none | `UserProfile` | `Depends(get_current_user)` |
| GET | `/auth/my-twins` | none | list of twins | `Depends(get_current_user)` |
| GET | `/connectors` | none | `[]` | `Depends(get_current_user)` |
| POST | `/api-keys` | `ApiKeyCreateRequest` (`backend/modules/schemas.py`) | api key dict | `Depends(verify_owner)` |
| GET | `/api-keys` | query `twin_id` | list of keys | `Depends(verify_owner)` |
| PATCH | `/api-keys/{key_id}` | `ApiKeyUpdateRequest` (`backend/modules/schemas.py`) | `{status}` | `Depends(verify_owner)` |
| DELETE | `/api-keys/{key_id}` | none | `{status}` | `Depends(verify_owner)` |
| GET | `/twins/{twin_id}/share-link` | none | share link info | `Depends(verify_owner)` |
| POST | `/twins/{twin_id}/share-link` | none | share link info | `Depends(verify_owner)` |
| PATCH | `/twins/{twin_id}/sharing` | body `{ is_public }` | `{status, is_public}` | `Depends(verify_owner)` |
| GET | `/users` | none | list of users | `Depends(verify_owner)` |
| POST | `/users/invite` | `UserInvitationCreateRequest` (`backend/modules/schemas.py`) | invitation dict | `Depends(verify_owner)` |
| DELETE | `/users/{user_id}` | none | `{status}` | `Depends(verify_owner)` |
| GET | `/public/validate-share/{twin_id}/{token}` | none | `{valid, twin_id, twin_name}` | public |
| POST | `/account/delete` | `DeleteAccountRequest` (local) | `DeleteAccountResponse` | `Depends(get_current_user)` |

### `backend/routers/api_keys.py` (tenant-scoped, registered in `backend/main.py`)
| Method | Path | Request | Response | Auth/Deps |
| --- | --- | --- | --- | --- |
| GET | `/api-keys` | none | `List[ApiKeyResponse]` | `Depends(require_tenant)` |
| POST | `/api-keys` | `ApiKeyCreateRequest` (local) | `ApiKeyCreatedResponse` | `Depends(require_tenant)` |
| DELETE | `/api-keys/{key_id}` | none | `{status}` | `Depends(require_tenant)` |

### `backend/routers/chat.py`
| Method | Path | Request | Response | Auth/Deps |
| --- | --- | --- | --- | --- |
| POST | `/chat/{twin_id}` | `ChatRequest` (`backend/modules/schemas.py`) | SSE stream (`metadata`, `content`, `done`) | `Depends(get_current_user)` + `verify_twin_ownership` |
| GET | `/conversations/{twin_id}` | none | list of conversations | `Depends(get_current_user)` |
| GET | `/conversations/{conversation_id}/messages` | none | list of messages | `Depends(get_current_user)` |
| POST | `/chat-widget/{twin_id}` | `ChatWidgetRequest` (`backend/modules/schemas.py`) | SSE stream | API key validation (`modules/api_keys.py`) |
| POST | `/public/chat/{twin_id}/{token}` | `PublicChatRequest` (`backend/modules/schemas.py`) | JSON answer or queued clarification | public share token (`modules/share_links.py`) |

### `backend/routers/ingestion.py`
| Method | Path | Request | Response | Auth/Deps |
| --- | --- | --- | --- | --- |
| POST | `/ingest/youtube/{twin_id}` | `YouTubeIngestRequest` (local) | `{source_id, status}` | `Depends(verify_owner)` |
| POST | `/ingest/podcast/{twin_id}` | `PodcastIngestRequest` (local) | `{source_id, status}` | `Depends(verify_owner)` |
| POST | `/ingest/x/{twin_id}` | `XThreadIngestRequest` (local) | `{source_id, status}` | `Depends(verify_owner)` |
| POST | `/ingest/file/{twin_id}` | multipart file | `{source_id, status}` | `Depends(verify_owner)` |
| POST | `/ingest/url/{twin_id}` | `URLIngestRequest` (local) | `{source_id, status}` | `Depends(verify_owner)` |
| POST | `/ingest/document` | multipart file + `twin_id` (compat shim) | `{source_id, status}` | `Depends(verify_owner)` |
| POST | `/ingest/url` | `URLIngestWithTwinRequest` (local) | `{source_id, status}` | `Depends(verify_owner)` |
| POST | `/training-jobs/process-queue` | query `twin_id?` | queue processing summary | `Depends(verify_owner)` |
| GET | `/training-jobs/{job_id}` | none | training job row | `Depends(get_current_user)` |
| GET | `/training-jobs` | query `twin_id`, `status?`, `limit?` | list | `Depends(get_current_user)` |
| POST | `/training-jobs/{job_id}/retry` | none | `{status, job_id}` | `Depends(verify_owner)` |
| POST | `/ingest/extract-nodes/{source_id}` | `ExtractNodesRequest` (local) | extraction stats | `Depends(get_current_user)` |

### `backend/routers/enhanced_ingestion.py` (registered only if `ENABLE_ENHANCED_INGESTION=true`)
| Method | Path | Request | Response | Auth/Deps |
| --- | --- | --- | --- | --- |
| POST | `/ingest/website/{twin_id}` | `WebsiteCrawlRequest` | crawl result | `Depends(get_current_user)` |
| POST | `/ingest/website/{twin_id}/single` | `WebsiteCrawlRequest` | scrape + index result | `Depends(get_current_user)` |
| POST | `/ingest/rss/{twin_id}` | `RSSIngestRequest` | RSS result | `Depends(get_current_user)` |
| POST | `/ingest/twitter/{twin_id}` | `TwitterIngestRequest` | Twitter result | `Depends(get_current_user)` |
| POST | `/ingest/linkedin/{twin_id}` | `LinkedInIngestRequest` | LinkedIn result | `Depends(get_current_user)` |
| POST | `/ingest/youtube/{twin_id}` | `YoutubeIngestRequest` | YouTube result | `Depends(get_current_user)` |
| POST | `/pipelines/{twin_id}` | `PipelineCreateRequest` | pipeline result | `Depends(get_current_user)` |
| GET | `/pipelines/{twin_id}` | query `include_paused?` | pipelines | `Depends(get_current_user)` |
| GET | `/pipelines/{twin_id}/{pipeline_id}` | none | pipeline | `Depends(get_current_user)` |
| PUT | `/pipelines/{twin_id}/{pipeline_id}` | `PipelineUpdateRequest` | update result | `Depends(get_current_user)` |
| DELETE | `/pipelines/{twin_id}/{pipeline_id}` | none | delete result | `Depends(get_current_user)` |
| POST | `/pipelines/{twin_id}/{pipeline_id}/run` | none | execution result | `Depends(get_current_user)` |

### `backend/routers/sources.py`
| Method | Path | Request | Response | Auth/Deps |
| --- | --- | --- | --- | --- |
| GET | `/sources/{twin_id}` | query `status?` | list of sources | `Depends(get_current_user)` |
| GET | `/sources/{source_id}/health` | none | `{health_status, logs}` | `Depends(get_current_user)` |
| GET | `/sources/{twin_id}/{source_id}` | none | source row | `Depends(get_current_user)` |
| DELETE | `/sources/{twin_id}/{source_id}` | none | `{status}` | `Depends(verify_owner)` |
| GET | `/sources/{source_id}/logs` | none | ingestion logs | `Depends(get_current_user)` |
| POST | `/sources/{source_id}/re-extract` | none | `{status}` | `Depends(verify_owner)` |

### `backend/routers/knowledge.py`
| Method | Path | Request | Response | Auth/Deps |
| --- | --- | --- | --- | --- |
| GET | `/twins/{twin_id}/knowledge-profile` | none | `KnowledgeProfile` (`backend/modules/schemas.py`) | `Depends(get_current_user)` |
| GET | `/twins/{twin_id}/verified-qna` | query `visibility?` | list of QnA | `Depends(get_current_user)` |
| GET | `/verified-qna/{qna_id}` | none | `VerifiedQnASchema` | `Depends(get_current_user)` |
| PATCH | `/verified-qna/{qna_id}` | `VerifiedQnAUpdateRequest` | `{status}` | `Depends(verify_owner)` |
| DELETE | `/verified-qna/{qna_id}` | none | `{status}` | `Depends(verify_owner)` |

### `backend/routers/verify.py` (prefix `/verify`)
| Method | Path | Request | Response | Auth/Deps |
| --- | --- | --- | --- | --- |
| POST | `/verify/twins/{twin_id}/run` | none | `VerifyResponse` (local) | `Depends(get_current_user)` |

### `backend/routers/twins.py`
| Method | Path | Request | Response | Auth/Deps |
| --- | --- | --- | --- | --- |
| GET | `/specializations` | none | specialization registry | public |
| POST | `/twins` | `TwinCreateRequest` (local) | twin row | `Depends(get_current_user)` |
| GET | `/twins` | none | list of twins | `Depends(get_current_user)` |
| GET | `/twins/{twin_id}` | none | twin row | `Depends(get_current_user)` |
| GET | `/twins/{twin_id}/sidebar-config` | none | specialization sidebar | `Depends(get_current_user)` |
| GET | `/twins/{twin_id}/graph-stats` | none | graph stats | `Depends(get_current_user)` |
| GET | `/twins/{twin_id}/graph-job-status` | none | graph job status | `Depends(get_current_user)` |
| GET | `/twins/{twin_id}/verification-status` | none | readiness info | `Depends(get_current_user)` |
| PATCH | `/twins/{twin_id}` | `TwinSettingsUpdate` (`backend/modules/schemas.py`) | updated twin | `Depends(verify_owner)` |
| POST | `/twins/{twin_id}/archive` | none | `DeleteTwinResponse` | `Depends(verify_owner)` |
| DELETE | `/twins/{twin_id}` | query `hard?` | `DeleteTwinResponse` | `Depends(verify_owner)` |
| GET | `/twins/{twin_id}/export` | none | JSON export bundle | `Depends(verify_owner)` |
| GET | `/twins/{twin_id}/access-groups` | none | list groups | `Depends(verify_owner)` |
| POST | `/twins/{twin_id}/access-groups` | `GroupCreateRequest` | group | `Depends(verify_owner)` |
| GET | `/access-groups/{group_id}` | none | group | `Depends(get_current_user)` |
| PATCH | `/access-groups/{group_id}` | `GroupUpdateRequest` | group | `Depends(verify_owner)` |
| DELETE | `/access-groups/{group_id}` | none | `{message}` | `Depends(verify_owner)` |
| GET | `/access-groups/{group_id}/members` | none | members | `Depends(get_current_user)` |
| POST | `/twins/{twin_id}/group-memberships` | `AssignUserRequest` | `{message}` | `Depends(verify_owner)` |
| DELETE | `/group-memberships/{membership_id}` | none | `{message}` | `Depends(verify_owner)` |
| POST | `/access-groups/{group_id}/permissions` | `ContentPermissionRequest` | `{message}` | `Depends(verify_owner)` |
| DELETE | `/access-groups/{group_id}/permissions/{content_type}/{content_id}` | none | `{message}` | `Depends(verify_owner)` |
| GET | `/access-groups/{group_id}/permissions` | none | permissions | `Depends(get_current_user)` |
| GET | `/content/{content_type}/{content_id}/groups` | none | groups | `Depends(get_current_user)` |
| POST | `/access-groups/{group_id}/limits` | query `limit_type`, `limit_value` | `{message}` | `Depends(verify_owner)` |
| GET | `/access-groups/{group_id}/limits` | none | limits | `Depends(get_current_user)` |
| POST | `/access-groups/{group_id}/overrides` | body `{override_type, override_value}` | `{message}` | `Depends(verify_owner)` |
| GET | `/access-groups/{group_id}/overrides` | none | overrides | `Depends(get_current_user)` |

### `backend/routers/owner_memory.py`
| Method | Path | Request | Response | Auth/Deps |
| --- | --- | --- | --- | --- |
| GET | `/twins/{twin_id}/owner-memory` | query `status?` | list | `Depends(verify_owner)` |
| DELETE | `/twins/{twin_id}/owner-memory/{memory_id}` | none | `{status}` | `Depends(verify_owner)` |
| GET | `/twins/{twin_id}/clarifications` | query `status?` | list | `Depends(verify_owner)` |
| POST | `/twins/{twin_id}/clarifications/{clarification_id}/resolve` | `ClarificationResolveRequest` | `{status}` | `Depends(verify_owner)` |

### `backend/routers/til.py`
| Method | Path | Request | Response | Auth/Deps |
| --- | --- | --- | --- | --- |
| GET | `/twins/{twin_id}/til` | query `days?` | `{events}` | `Depends(get_current_user)` |
| GET | `/twins/{twin_id}/memory-events` | query `limit?`, `event_type?` | `{events}` | `Depends(get_current_user)` |
| POST | `/twins/{twin_id}/til/{node_id}/confirm` | `ConfirmMemoryRequest` | `{success}` | `Depends(get_current_user)` |
| PUT | `/twins/{twin_id}/til/{node_id}` | `EditMemoryRequest` | `{success}` | `Depends(get_current_user)` |
| DELETE | `/twins/{twin_id}/til/{node_id}` | none | `{success}` | `Depends(get_current_user)` |

### `backend/routers/metrics.py` (prefix `/metrics`)
| Method | Path | Request | Response | Auth/Deps |
| --- | --- | --- | --- | --- |
| GET | `/metrics/dashboard/{twin_id}` | query `days?` | `DashboardStats` | `Depends(get_current_user)` |
| GET | `/metrics/conversations/{twin_id}` | query `limit?` | `List[ConversationSummary]` | `Depends(get_current_user)` |
| GET | `/metrics/activity/{twin_id}` | query `limit?` | `List[ActivityItem]` | `Depends(get_current_user)` |
| GET | `/metrics/daily/{twin_id}` | query `days?` | `List[DailyMetric]` | `Depends(get_current_user)` |
| GET | `/metrics/top-questions/{twin_id}` | query `limit?` | `List[TopQuestion]` | `Depends(get_current_user)` |
| POST | `/metrics/events` | `EventCreate` | `{success}` | `Depends(get_current_user)` |
| GET | `/metrics/events/{user_id}` | query `event_type?`, `limit?` | `{events}` | `Depends(get_current_user)` |
| GET | `/metrics/system` | query `days?` | `{summary, usage_by_twin}` | `Depends(verify_owner)` |
| GET | `/metrics/usage/{twin_id}` | query `days?` | usage summary | `Depends(get_current_user)` |
| GET | `/metrics/health` | none | service health | `Depends(verify_owner)` |
| GET | `/metrics/quota/{tenant_id}` | none | quota status | `Depends(get_current_user)` |
| POST | `/metrics/quota/{tenant_id}/set` | query `quota_type`, `limit_value` | `{success}` | `Depends(verify_owner)` |

### `backend/routers/jobs.py` (prefix `/jobs`)
| Method | Path | Request | Response | Auth/Deps |
| --- | --- | --- | --- | --- |
| GET | `/jobs` | query `status?`, `job_type?`, `twin_id?`, `limit?`, `offset?` | `List[JobResponse]` | `Depends(get_current_user)` |
| GET | `/jobs/{job_id}` | none | `JobResponse` | `Depends(get_current_user)` |
| GET | `/jobs/{job_id}/logs` | query `log_level?`, `limit?` | `List[JobLogResponse]` | `Depends(get_current_user)` |
| POST | `/jobs` | `CreateJobRequest` | `JobResponse` | `Depends(get_current_user)` |

### `backend/routers/governance.py`
| Method | Path | Request | Response | Auth/Deps |
| --- | --- | --- | --- | --- |
| GET | `/governance/audit-logs` | query `twin_id?`, `event_type?` | `List[AuditLogSchema]` | `Depends(require_tenant)` |
| GET | `/governance/policies` | none | `List[GovernancePolicySchema]` | `Depends(require_tenant)` |
| POST | `/governance/policies` | `GovernancePolicyCreateRequest` | `GovernancePolicySchema` | `Depends(require_tenant)` |
| POST | `/twins/{twin_id}/governance/verify` | `TwinVerificationRequest` | `{status}` | `Depends(require_tenant)` |
| DELETE | `/twins/{twin_id}/sources/{source_id}/deep-scrub` | `DeepScrubRequest` | `{status}` | `Depends(require_tenant)` |

### `backend/routers/actions.py`
| Method | Path | Request | Response | Auth/Deps |
| --- | --- | --- | --- | --- |
| GET | `/twins/{twin_id}/events` | query `event_type?`, `limit?` | `List[EventSchema]` | `Depends(verify_owner)` |
| POST | `/twins/{twin_id}/events` | `EventEmitRequest` | `{status}` | `Depends(verify_owner)` |
| GET | `/twins/{twin_id}/triggers` | query `include_inactive?` | `List[ActionTriggerSchema]` | `Depends(verify_owner)` |
| POST | `/twins/{twin_id}/triggers` | `TriggerCreateRequest` | `{status}` | `Depends(verify_owner)` |
| PUT | `/twins/{twin_id}/triggers/{trigger_id}` | `TriggerUpdateRequest` | `{status}` | `Depends(verify_owner)` |
| DELETE | `/twins/{twin_id}/triggers/{trigger_id}` | none | `{status}` | `Depends(verify_owner)` |
| GET | `/twins/{twin_id}/action-drafts` | none | `List[ActionDraftSchema]` | `Depends(verify_owner)` |
| GET | `/twins/{twin_id}/action-drafts-all` | query `status?`, `limit?` | list | `Depends(verify_owner)` |
| GET | `/twins/{twin_id}/action-drafts/{draft_id}` | none | draft | `Depends(verify_owner)` |
| POST | `/twins/{twin_id}/action-drafts/{draft_id}/approve` | `DraftApproveRequest` | `{status}` | `Depends(verify_owner)` |
| POST | `/twins/{twin_id}/action-drafts/{draft_id}/reject` | `DraftRejectRequest` | `{status}` | `Depends(verify_owner)` |
| POST | `/twins/{twin_id}/action-drafts/{draft_id}/respond` | `DraftRespondRequest` | result | `Depends(verify_owner)` |
| GET | `/twins/{twin_id}/executions` | query `action_type?`, `status?`, `limit?` | `List[ActionExecutionSchema]` | `Depends(verify_owner)` |
| GET | `/twins/{twin_id}/executions/{execution_id}` | none | execution | `Depends(verify_owner)` |
| GET | `/twins/{twin_id}/connectors` | none | `List[ToolConnectorSchema]` | `Depends(verify_owner)` |
| POST | `/twins/{twin_id}/connectors` | `ConnectorCreateRequest` | `{status}` | `Depends(verify_owner)` |
| DELETE | `/twins/{twin_id}/connectors/{connector_id}` | none | `{status}` | `Depends(verify_owner)` |
| POST | `/twins/{twin_id}/connectors/{connector_id}/test` | none | `ConnectorTestResponse` | `Depends(verify_owner)` |

### `backend/routers/escalations.py`
| Method | Path | Request | Response | Auth/Deps |
| --- | --- | --- | --- | --- |
| GET | `/twins/{twin_id}/escalations` | none | list | `Depends(require_tenant)` |
| GET | `/escalations` | none | list | `Depends(require_admin)` |
| POST | `/twins/{twin_id}/escalations/{escalation_id}/resolve` | `ResolutionRequest` | `{status}` | `Depends(require_tenant)` |
| POST | `/escalations/{escalation_id}/resolve` | `ResolutionRequest` | `{status}` | `Depends(require_admin)` |

### `backend/routers/graph.py`
| Method | Path | Request | Response | Auth/Deps |
| --- | --- | --- | --- | --- |
| GET | `/twins/{twin_id}/graph` | query `limit?` | `{nodes, edges}` | `Depends(verify_tenant_access)` + `verify_twin_access` |
| POST | `/twins/{twin_id}/nodes` | `NodeCreate` | node | `Depends(verify_tenant_access)` + `verify_twin_access` |

### `backend/routers/cognitive.py`
| Method | Path | Request | Response | Auth/Deps |
| --- | --- | --- | --- | --- |
| POST | `/cognitive/interview/{twin_id}` | `InterviewRequest` | `InterviewResponse` | `Depends(require_tenant)` |
| GET | `/cognitive/graph/{twin_id}` | none | placeholder graph | `Depends(require_tenant)` |
| POST | `/cognitive/profiles/{twin_id}/approve` | `ApproveRequest` | `{success}` | `Depends(require_tenant)` |
| GET | `/cognitive/profiles/{twin_id}/versions` | none | versions | `Depends(require_tenant)` |
| GET | `/cognitive/profiles/{twin_id}/versions/{version}` | none | snapshot | `Depends(require_tenant)` |
| DELETE | `/cognitive/profiles/{twin_id}/versions/{version}` | none | `{success}` | `Depends(require_tenant)` |
| DELETE | `/cognitive/profiles/{twin_id}/versions` | none | `{success}` | `Depends(get_current_user)` |

### `backend/routers/interview.py` (prefix `/api/interview`)
| Method | Path | Request | Response | Auth/Deps |
| --- | --- | --- | --- | --- |
| POST | `/api/interview/sessions` | `CreateSessionRequest` | `CreateSessionResponse` | `Depends(get_current_user)` |
| POST | `/api/interview/sessions/{session_id}/finalize` | `FinalizeSessionRequest` | `FinalizeSessionResponse` | `Depends(get_current_user)` |
| POST | `/api/interview/realtime/sessions` | `RealtimeSessionRequest` | `RealtimeSessionResponse` | `Depends(get_current_user)` |
| GET | `/api/interview/context` | query `task?` | `ContextBundleResponse` | `Depends(get_current_user)` |

### `backend/routers/reasoning.py`
| Method | Path | Request | Response | Auth/Deps |
| --- | --- | --- | --- | --- |
| POST | `/reason/predict/{twin_id}` | `PredictionRequest` | decision trace | `Depends(get_current_user)` |

### `backend/routers/audio.py`
| Method | Path | Request | Response | Auth/Deps |
| --- | --- | --- | --- | --- |
| POST | `/audio/tts/{twin_id}` | `TTSRequest` | MP3 bytes | `Depends(get_current_user)` |
| POST | `/audio/tts/{twin_id}/stream` | `TTSRequest` | streaming MP3 | `Depends(get_current_user)` |
| GET | `/audio/voices` | none | `{voices}` | `Depends(get_current_user)` |
| GET | `/audio/settings/{twin_id}` | none | `{settings}` | `Depends(get_current_user)` |
| PUT | `/audio/settings/{twin_id}` | `VoiceSettingsRequest` | `{success}` | `Depends(get_current_user)` |

### `backend/routers/specializations.py`
| Method | Path | Request | Response | Auth/Deps |
| --- | --- | --- | --- | --- |
| GET | `/config/specialization` | none | specialization config | public |
| GET | `/twins/{twin_id}/specialization` | none | specialization config | `Depends(get_current_user)` |
| GET | `/config/specializations` | none | list of specializations | public |

### `backend/routers/youtube_preflight.py` (prefix `/youtube`)
| Method | Path | Request | Response | Auth/Deps |
| --- | --- | --- | --- | --- |
| POST | `/youtube/preflight` | `YouTubePreflight` | `PreflightResponse` | `Depends(get_current_user)` |

### `backend/routers/debug_retrieval.py` (prefix `/debug`)
| Method | Path | Request | Response | Auth/Deps |
| --- | --- | --- | --- | --- |
| POST | `/debug/retrieval` | `RetrievalDebugRequest` | contexts + diagnostics | `Depends(get_current_user)` |

### `backend/routers/observability.py`
| Method | Path | Request | Response | Auth/Deps |
| --- | --- | --- | --- | --- |
| GET | `/observability/health` | none | `{status, services}` | public |

### `backend/routers/feedback.py`
| Method | Path | Request | Response | Auth/Deps |
| --- | --- | --- | --- | --- |
| POST | `/feedback/{trace_id}` | `FeedbackRequest` | `FeedbackResponse` | public |
| GET | `/feedback/reasons` | none | reasons list | public |

### `backend/api/vc_routes.py` (registered only if `ENABLE_VC_ROUTES=true` in `backend/main.py` with prefix `/api`)
| Method | Path | Request | Response | Auth/Deps |
| --- | --- | --- | --- | --- |
| POST | `/api/vc/artifact/upload/{twin_id}` | multipart file | placeholder response | `Depends(get_current_user)` + `verify_twin_ownership` |
