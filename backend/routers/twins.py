from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from modules.auth_guard import verify_owner, get_current_user, verify_twin_ownership, resolve_tenant_id
from modules.schemas import (
    TwinSettingsUpdate, GroupCreateRequest, GroupUpdateRequest,
    AssignUserRequest, ContentPermissionRequest,
    AccessGroupSchema, GroupMembershipSchema, ContentPermissionSchema,
    GroupLimitSchema, GroupOverrideSchema,
    TrainingMetricsSchema
)
from modules.access_groups import (
    get_user_group, get_default_group, create_group, assign_user_to_group,
    add_content_permission, remove_content_permission, get_group_permissions,
    get_groups_for_content, list_groups, get_group, update_group, delete_group,
    get_group_members, set_group_limit, get_group_limits, set_group_override, get_group_overrides
)
from modules.observability import supabase
from modules.specializations import get_specialization, get_all_specializations
from modules.clients import get_pinecone_index
from modules.graph_context import get_graph_stats
from modules.governance import AuditLogger
from modules.tenant_guard import derive_creator_ids
from datetime import datetime, timezone, timedelta

# =============================================================================
# 5-Layer Persona Imports
# =============================================================================
from modules.persona_bootstrap import bootstrap_persona_from_onboarding
from modules.persona_spec_store_v2 import create_persona_spec_v2

# =============================================================================
# Training Metrics Imports
# =============================================================================
from modules.training_metrics import (
    get_training_metrics_for_api,
    is_training_metrics_enabled,
    update_twin_training_metrics,
    format_number_compact,
    get_mind_score_label,
)
from modules.public_profile_pack import build_public_profile_pack



router = APIRouter(tags=["twins"])


def ensure_twin_owner_or_403(twin_id: str, user: dict) -> Dict[str, Any]:
    """
    Strict ownership check:
    - 404 if twin does not exist
    - 403 if twin exists but caller does not own the profile
    Returns the twin record.
    """
    verify_twin_ownership(twin_id, user)
    twin_res = supabase.table("twins").select("*").eq("id", twin_id).single().execute()
    if not twin_res.data:
        raise HTTPException(status_code=404, detail="Twin not found")
    return twin_res.data


def get_twin_verification_status(twin_id: str) -> Dict[str, Any]:
    """
    Return coarse readiness from the latest verification run.

    This is intentionally lightweight and separate from publish quality-gating,
    which requires a full quality-suite record.
    """
    try:
        result = (
            supabase.table("twin_verifications")
            .select("status, created_at, details")
            .eq("twin_id", twin_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        latest = (result.data or [None])[0]
        if not latest:
            return {
                "is_ready": False,
                "issues": ["No verification record found. Run verification before publishing."],
            }
        return {
            "is_ready": latest.get("status") == "PASS",
            "issues": [],
            "latest": latest,
        }
    except Exception as e:
        return {
            "is_ready": False,
            "issues": [f"Verification status check failed: {e}"],
        }


def _is_recent_quality_suite_pass(verification: Dict[str, Any], max_age_days: int = 30) -> bool:
    """Check whether a verification row is a PASS from the quality-suite format."""
    if not isinstance(verification, dict):
        return False
    if verification.get("status") != "PASS":
        return False

    details = verification.get("details")
    if not isinstance(details, dict):
        return False

    tests_run = details.get("tests_run")
    tests_passed = details.get("tests_passed")
    test_results = details.get("test_results")
    if not isinstance(tests_run, int) or tests_run <= 0:
        return False
    if tests_passed != tests_run:
        return False
    if not isinstance(test_results, list) or len(test_results) != tests_run:
        return False
    if any(not bool((r or {}).get("passed")) for r in test_results):
        return False

    created_at = verification.get("created_at")
    if created_at:
        try:
            created_dt = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
            now_utc = datetime.now(timezone.utc)
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=timezone.utc)
            if (now_utc - created_dt) > timedelta(days=max_age_days):
                return False
        except Exception:
            return False

    return True


def _require_authenticated_user(user: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Ensure private twin endpoints fail closed with 401 when auth is missing/invalid."""
    if not isinstance(user, dict) or not user.get("user_id"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def _is_missing_column_error(error: Exception, column_name: str) -> bool:
    """Detect Supabase/PostgREST schema-cache errors for missing columns."""
    message = str(error).lower()
    col = (column_name or "").lower()
    return (
        bool(col)
        and col in message
        and (
            "pgrst204" in message
            or "could not find" in message
            or "column" in message
            or "does not exist" in message
        )
    )


def _normalize_twin_status_shape(twin: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure twin payloads always expose a status field, even on legacy schemas
    where the physical `twins.status` column does not exist yet.
    """
    if not isinstance(twin, dict):
        return twin

    if twin.get("status"):
        return twin

    settings = twin.get("settings") if isinstance(twin.get("settings"), dict) else {}
    derived_status = (
        settings.get("link_first_state")
        or ("active" if twin.get("is_active") is True else None)
        or ("draft" if settings.get("creation_mode") == "link_first" else None)
    )
    if derived_status:
        twin["status"] = derived_status
    return twin


def _normalize_name_key(value: Any) -> str:
    """Normalize a name-like field for fuzzy equality checks."""
    text = str(value or "").strip().lower()
    if not text:
        return ""
    return " ".join(text.split())


def _to_non_negative_int(value: Any, default: int = 0) -> int:
    """Best-effort numeric coercion for metrics values."""
    try:
        return max(0, int(float(value)))
    except Exception:
        return default


def _coerce_training_metrics_payload(raw: Any) -> Dict[str, Any]:
    """
    Normalize arbitrary training metrics payloads to a UI-safe shape.

    Keeps compatibility with both twin.settings.training_metrics and
    name_deep_research result_json.training_metrics.
    """
    data = raw if isinstance(raw, dict) else {}
    words_processed = _to_non_negative_int(data.get("words_processed"), 0)
    questions_answerable_est = _to_non_negative_int(data.get("questions_answerable_est"), 0)
    mind_score = min(100, _to_non_negative_int(data.get("mind_score"), 0))

    return {
        "words_processed": words_processed,
        "words_processed_display": str(data.get("words_processed_display") or format_number_compact(words_processed)),
        "questions_answerable_est": questions_answerable_est,
        "questions_answerable_display": str(
            data.get("questions_answerable_display") or format_number_compact(questions_answerable_est)
        ),
        "mind_score": mind_score,
        "mind_score_label": str(data.get("mind_score_label") or get_mind_score_label(mind_score)),
        "method_version": str(data.get("method_version") or "v1_heuristic"),
        "notes": str(
            data.get("notes")
            or "Estimated metrics based on ingested content volume, diversity, and extraction quality."
        ),
        "last_computed_at": data.get("last_computed_at"),
    }


def _dedupe_questions(values: List[Any], limit: int = 12) -> List[str]:
    """Deduplicate while preserving order."""
    seen = set()
    out: List[str] = []
    for raw in values:
        question = str(raw or "").strip()
        if not question:
            continue
        key = " ".join(question.lower().split())
        if key in seen:
            continue
        seen.add(key)
        out.append(question)
        if len(out) >= limit:
            break
    return out


def _extract_name_research_questions(result_json: Dict[str, Any], combined_questions_estimate: int) -> List[str]:
    """Build chat-ready suggested questions from name deep research artifacts."""
    collected: List[Any] = []

    follow_ups = result_json.get("suggested_followup_questions")
    if isinstance(follow_ups, list):
        collected.extend(follow_ups)

    prepared = result_json.get("prepared_question_answers")
    if isinstance(prepared, list):
        for item in prepared:
            if isinstance(item, dict):
                collected.append(item.get("question"))

    # Generic "capacity discovery" prompts to let users ask broad questions.
    if combined_questions_estimate > 0:
        top_n = min(max(combined_questions_estimate, 5), 20)
        collected.append(f"What are the top {top_n} questions you can answer about me right now?")
    collected.append("Which parts of my profile still need stronger evidence?")
    collected.append("Show me your confidence and source citations for your next answer.")

    return _dedupe_questions(collected, limit=12)


# ============================================================================
# Twin Create Schema (Updated for 5-Layer Persona)
# ============================================================================

class TwinCreateRequest(BaseModel):
    name: str
    tenant_id: Optional[str] = None  # IGNORED: server always resolves tenant_id
    description: Optional[str] = None
    specialization: str = "vanilla"
    settings: Optional[Dict[str, Any]] = None
    # NEW: Structured 5-Layer Persona data from onboarding
    persona_v2_data: Optional[Dict[str, Any]] = None
    # NEW: Mode selector for Link-First vs Manual onboarding
    mode: Optional[str] = None  # "link_first" | "manual" (default: "manual")
    links: Optional[List[str]] = None  # URLs for link-first mode (Mode C)


class DeleteTwinResponse(BaseModel):
    """Response for archive/delete twin operations."""
    status: str  # "archived" | "deleted" | "already_archived" | "not_found"
    twin_id: str
    deleted_at: Optional[str] = None
    cleanup_status: str = "done"  # "done" | "pending"
    message: Optional[str] = None


# ============================================================================
# Specialization Endpoints
# ============================================================================


@router.get("/specializations")
async def list_specializations():
    """List all available specializations for UI selection."""
    return get_all_specializations()


# ============================================================================
# Twin CRUD Endpoints
# ============================================================================

@router.post("/twins")
async def create_twin(request: TwinCreateRequest, user=Depends(get_current_user)):
    """
    Create a new twin with 5-Layer Persona Spec v2.
    
    Supports TWO modes:
    1. MANUAL mode (default): Traditional onboarding flow with 6-step persona builder
       - Creates twin with status="active"
       - Auto-bootstraps 5-Layer Persona from onboarding data
       
    2. LINK-FIRST mode: Ingests external content to build persona from claims
       - Creates twin with status="draft"
       - Skips persona bootstrap (will be built from claims)
       - Links are queued for ingestion via /persona/link-compile endpoints
    
    SECURITY: Client-provided tenant_id is IGNORED.
    Server uses resolve_tenant_id() to determine the correct tenant.
    """
    try:
        user = _require_authenticated_user(user)
        user_id = user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        email = user.get("email", "")
        
        # CRITICAL: Always use resolve_tenant_id - NEVER trust client tenant_id
        # This auto-creates tenant if missing
        tenant_id = resolve_tenant_id(user_id, email)
        requested_name = (request.name or "").strip()
        if not requested_name:
            raise HTTPException(status_code=400, detail="Twin name is required")

        # Log if client sent a different tenant_id (for debugging)
        if request.tenant_id and request.tenant_id != tenant_id:
            print(f"[TWINS] WARNING: Ignoring client tenant_id={request.tenant_id}, using resolved={tenant_id}")

        def _find_existing_active_twin() -> Optional[Dict[str, Any]]:
            existing_res = (
                supabase.table("twins")
                .select("*")
                .eq("tenant_id", tenant_id)
                .eq("name", requested_name)
                .order("created_at", desc=True)
                .limit(25)
                .execute()
            )

            active_rows: List[Dict[str, Any]] = []
            for row in existing_res.data or []:
                if not (row.get("settings") or {}).get("deleted_at"):
                    active_rows.append(row)
            if not active_rows:
                return None

            user_owned_rows: List[Dict[str, Any]] = []
            for row in active_rows:
                settings = row.get("settings") if isinstance(row.get("settings"), dict) else {}
                owner_user_id = str(settings.get("owner_user_id") or "").strip()
                creator_id = str(row.get("creator_id") or "").strip()
                if owner_user_id == str(user_id) or creator_id == str(user_id):
                    user_owned_rows.append(row)

            if user_owned_rows:
                return user_owned_rows[0]

            # Legacy fallback for tenant-scoped old rows.
            if len(active_rows) == 1:
                only = active_rows[0]
                settings = only.get("settings") if isinstance(only.get("settings"), dict) else {}
                owner_user_id = str(settings.get("owner_user_id") or "").strip()
                creator_id = str(only.get("creator_id") or "").strip()
                if not owner_user_id and creator_id == f"tenant_{tenant_id}":
                    return only
            return None

        # Idempotency guard: retries from onboarding/network should not create duplicates.
        existing = _find_existing_active_twin()
        if existing:
            print(f"[TWINS] Reusing existing twin {existing.get('id')} for tenant={tenant_id}, name='{requested_name}'")
            return _normalize_twin_status_shape(existing)
        
        # ====================================================================
        # STEP 1: Create the twin with 5-Layer Persona enabled
        # ====================================================================
        
        # Determine mode: link_first vs manual (default: manual)
        is_link_first = request.mode == "link_first"
        creation_mode = "link_first" if is_link_first else "manual"
        
        # Enhanced settings with 5-Layer Persona configuration
        settings = request.settings or {}
        settings["use_5layer_persona"] = True  # NEW: Always true for new twins
        settings["persona_v2_version"] = "2.0.0"  # NEW: Track persona version
        
        # Persist mode metadata in settings for compatibility with legacy schemas.
        settings["creation_mode"] = creation_mode

        # Store links in settings for link-first mode
        if is_link_first and request.links:
            settings["link_first_urls"] = request.links[:10]  # Max 10 links
        
        # Status based on mode:
        # - manual: active (ready to chat immediately)
        # - link_first: draft (requires ingestion → claims → clarification → active)
        twin_status = "draft" if is_link_first else "active"
        settings["link_first_state"] = twin_status
        
        data = {
            "name": requested_name,
            "tenant_id": tenant_id,  # Always from resolve_tenant_id
            # Creator ID is the isolation root for creator namespace strategy.
            # Use authenticated creator claim first; fallback is deterministic tenant mapping.
            "creator_id": (derive_creator_ids(user) or [f"tenant_{tenant_id}"])[0],
            "description": request.description or f"{requested_name}'s digital twin",
            "specialization": request.specialization,
            "settings": settings,
            "status": twin_status,  # Preferred: lifecycle column when migrated.
            "creation_mode": creation_mode,  # Preferred: explicit creation path.
            "is_active": not is_link_first,  # Legacy-friendly readiness flag.
        }

        print(f"[TWINS] Creating twin '{requested_name}' for user={user_id}, tenant={tenant_id}")
        insert_payload = dict(data)
        removed_legacy_columns: set[str] = set()

        while True:
            try:
                response = supabase.table("twins").insert(insert_payload).execute()
                break
            except Exception as insert_error:
                insert_msg = str(insert_error).lower()

                removed_column = None
                for column in ("status", "creation_mode", "is_active"):
                    if column in insert_payload and _is_missing_column_error(insert_error, column):
                        removed_column = column
                        break

                if removed_column:
                    removed_legacy_columns.add(removed_column)
                    insert_payload.pop(removed_column, None)
                    print(
                        f"[TWINS] Legacy twins schema detected (missing `{removed_column}`); "
                        "retrying insert without that column"
                    )
                    continue

                if "duplicate key" in insert_msg or "already exists" in insert_msg:
                    existing_after_race = _find_existing_active_twin()
                    if existing_after_race:
                        print(
                            "[TWINS] Detected duplicate create race; returning existing twin "
                            f"{existing_after_race.get('id')}"
                        )
                        return _normalize_twin_status_shape(existing_after_race)
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "A twin with this name already exists for another profile in your tenant. "
                            "Use a distinct name or reuse your existing profile."
                        ),
                    )
                raise
        
        if response.data:
            twin = response.data[0]
            if removed_legacy_columns:
                # Keep API shape stable regardless of physical table schema.
                twin.setdefault("status", twin_status)
                twin.setdefault("creation_mode", creation_mode)
                twin.setdefault("is_active", not is_link_first)
            twin = _normalize_twin_status_shape(twin)
            twin_id = twin.get('id')
            print(f"[TWINS] Twin created: {twin_id}")
            
            # ====================================================================
            # STEP 2: Auto-Create 5-Layer Persona Spec v2 (MANUAL MODE ONLY)
            # ====================================================================
            
            if not is_link_first:
                # MANUAL MODE: Bootstrap persona from onboarding answers
                try:
                    # Merge persona data from request with defaults
                    onboarding_data = request.persona_v2_data or {}
                    onboarding_data["twin_name"] = requested_name
                    onboarding_data["specialization"] = request.specialization
                    
                    # Bootstrap the structured persona spec
                    persona_spec = bootstrap_persona_from_onboarding(onboarding_data)
                    
                    # Store in persona_specs table as ACTIVE
                    persona_record = await create_persona_spec_v2(
                        twin_id=twin_id,
                        tenant_id=tenant_id,
                        created_by=user_id,
                        spec=persona_spec,
                        status="active",  # Auto-publish
                        source="onboarding_v2",
                        notes=(
                            f"onboarding_version=2.0; specialization={request.specialization}; "
                            "auto_published=true"
                        ),
                    )
                    
                    print(f"[TWINS] 5-Layer Persona Spec v2 created and activated: {(persona_record or {}).get('id')}")
                    
                    # Add persona info to twin response
                    twin["persona_v2"] = {
                        "id": (persona_record or {}).get("id"),
                        "version": "2.0.0",
                        "status": "active",
                        "auto_created": True,
                    }
                    
                except Exception as persona_error:
                    # Log but don't fail twin creation - persona can be created later
                    print(f"[TWINS] WARNING: Failed to auto-create persona spec for twin {twin_id}: {persona_error}")
                    twin["persona_v2_error"] = str(persona_error)
            else:
                # LINK-FIRST MODE: Skip bootstrap - persona will be built from claims
                print(f"[TWINS] Link-first mode: Skipping persona bootstrap for twin {twin_id}")
                print(f"[TWINS] Use /persona/link-compile endpoints to ingest content and build persona")
                twin["link_first"] = {
                    "status": "draft",
                    "links": request.links or [],
                    "next_step": "POST /persona/link-compile/jobs/mode-c (web fetch) or mode-b (paste/import)"
                }
            
            # ====================================================================
            # STEP 3: Auto-Create Default Group
            # ====================================================================
            
            try:
                await create_group(
                    twin_id=twin_id,
                    name="Default Group",
                    description="Standard access group for all content",
                    is_default=True
                )
                print(f"[TWINS] Default group created for twin: {twin_id}")
            except Exception as ge:
                print(f"[TWINS] WARNING: Failed to create default group for twin {twin_id}: {ge}")
                
            return twin
        else:
            raise HTTPException(status_code=400, detail="Failed to create twin")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/twins")
async def list_twins(user=Depends(get_current_user)):
    """List all twins for the authenticated user's tenant (excludes archived)."""
    try:
        user = _require_authenticated_user(user)
        tenant_id = user.get("tenant_id")
        if not tenant_id:
            # User has no tenant - return empty list (not an error)
            return []
        
        # Get twins where tenant_id matches user's tenant
        response = supabase.table("twins").select("*").eq("tenant_id", tenant_id).order("created_at", desc=True).execute()
        
        twins_list = response.data if response.data else []
        
        # Filter out archived twins (those with deleted_at in settings)
        twins_list = [t for t in twins_list if not (t.get("settings") or {}).get("deleted_at")]
        twins_list = [_normalize_twin_status_shape(t) for t in twins_list]
        
        print(f"[TWINS] Listing twins for tenant {tenant_id}: found {len(twins_list)}")
        
        return twins_list
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR listing twins: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/twins/{twin_id}")
async def get_twin(twin_id: str, include_metrics: bool = True, user=Depends(get_current_user)):
    """
    Get a specific twin. Verifies ownership.
    
    Args:
        twin_id: Twin ID
        include_metrics: If True, include training metrics in response (default: True)
    """
    user = _require_authenticated_user(user)
    # Verify user has access to this twin
    verify_twin_ownership(twin_id, user)
    
    # Use RPC to bypass RLS for system lookup
    response = supabase.rpc("get_twin_system", {"t_id": twin_id}).single().execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Twin not found or access denied")
    
    twin = _normalize_twin_status_shape(response.data)
    
    # Add training metrics if enabled
    if include_metrics and is_training_metrics_enabled():
        try:
            # Check if cached metrics exist in settings
            settings = twin.get("settings") or {}
            cached_metrics = settings.get("training_metrics")
            
            # Use cached metrics if available and recent (within 1 hour)
            use_cached = False
            if cached_metrics and cached_metrics.get("last_computed_at"):
                try:
                    last_computed = datetime.fromisoformat(cached_metrics["last_computed_at"].replace("Z", "+00:00"))
                    now = datetime.now(timezone.utc)
                    if last_computed.tzinfo is None:
                        last_computed = last_computed.replace(tzinfo=timezone.utc)
                    # Cache valid for 1 hour
                    if (now - last_computed).total_seconds() < 3600:
                        use_cached = True
                        twin["training_metrics"] = {
                            "words_processed": cached_metrics.get("words_processed", 0),
                            "words_processed_display": cached_metrics.get("words_processed_display", "0"),
                            "questions_answerable_est": cached_metrics.get("questions_answerable_est", 0),
                            "questions_answerable_display": cached_metrics.get("questions_answerable_display", "0"),
                            "mind_score": cached_metrics.get("mind_score", 0),
                            "mind_score_label": cached_metrics.get("mind_score_label", "Early"),
                            "method_version": cached_metrics.get("method_version", "v1_heuristic"),
                            "last_computed_at": cached_metrics.get("last_computed_at"),
                            "notes": cached_metrics.get("notes", ""),
                        }
                except Exception:
                    use_cached = False
            
            if not use_cached:
                # Compute fresh metrics
                metrics = get_training_metrics_for_api(twin_id)
                twin["training_metrics"] = metrics["training_metrics"]
                
                # Cache metrics in background (don't await)
                try:
                    update_twin_training_metrics(twin_id)
                except Exception as cache_err:
                    print(f"[TWINS] Non-critical error caching metrics: {cache_err}")
                    
        except Exception as metrics_err:
            # Don't fail the request if metrics computation fails
            print(f"[TWINS] Error computing metrics for twin {twin_id}: {metrics_err}")
            twin["training_metrics"] = TrainingMetricsSchema().model_dump()
    
    return twin


@router.get("/twins/{twin_id}/profile-insights")
async def get_twin_profile_insights(twin_id: str, user=Depends(get_current_user)):
    """
    Aggregate profile-facing metrics and starter questions for chat.

    Combines:
    - Twin onboarding training metrics (settings.training_metrics)
    - Latest matching name-deep-research metrics (if available)
    - Suggested follow-up chat questions from deep research artifacts
    """
    user = _require_authenticated_user(user)
    verify_twin_ownership(twin_id, user)

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=403, detail="User has no tenant association")

    twin_res = supabase.table("twins").select("id,name,settings").eq("id", twin_id).single().execute()
    if not twin_res.data:
        raise HTTPException(status_code=404, detail="Twin not found")

    twin = twin_res.data
    settings = twin.get("settings") or {}
    twin_metrics = _coerce_training_metrics_payload(settings.get("training_metrics"))

    # Resolve best identity name from latest twin research run, fallback to twin name.
    identity_name = str(twin.get("name") or "").strip()
    latest_twin_research_run_id = None
    try:
        research_run_res = (
            supabase.table("research_runs")
            .select("id,claimed_identity,created_at")
            .eq("twin_id", twin_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if research_run_res.data:
            latest = research_run_res.data[0]
            latest_twin_research_run_id = latest.get("id")
            claimed_identity = latest.get("claimed_identity") or {}
            if isinstance(claimed_identity, dict):
                claimed_name = str(claimed_identity.get("full_name") or "").strip()
                if claimed_name:
                    identity_name = claimed_name
    except Exception as e:
        print(f"[TWINS] Warning: failed to resolve latest research run for {twin_id}: {e}")

    normalized_identity_name = _normalize_name_key(identity_name)

    name_research_summary: Optional[Dict[str, Any]] = None
    name_research_metrics: Optional[Dict[str, Any]] = None
    question_suggestions: List[str] = []

    try:
        # Pull a small candidate window for tenant and match by normalized input name.
        candidate_runs_res = (
            supabase.table("name_deep_research_runs")
            .select("id,status,input_name,input_company,run_completed_at,created_at")
            .eq("tenant_id", tenant_id)
            .order("created_at", desc=True)
            .limit(25)
            .execute()
        )
        candidate_runs = candidate_runs_res.data or []

        matched = [
            row for row in candidate_runs
            if _normalize_name_key(row.get("input_name")) == normalized_identity_name
        ]
        if not matched and candidate_runs:
            # Fallback to most recent tenant run when identity name is unavailable/missing.
            matched = candidate_runs

        selected_run = None
        for row in matched:
            if str(row.get("status") or "").lower() == "completed":
                selected_run = row
                break
        if not selected_run and matched:
            selected_run = matched[0]

        if selected_run:
            run_id = selected_run.get("id")
            name_research_summary = {
                "run_id": run_id,
                "status": selected_run.get("status"),
                "input_name": selected_run.get("input_name"),
                "run_completed_at": selected_run.get("run_completed_at"),
            }

            artifact_res = (
                supabase.table("name_deep_research_artifacts")
                .select("result_json")
                .eq("tenant_id", tenant_id)
                .eq("run_id", run_id)
                .limit(1)
                .execute()
            )
            if artifact_res.data:
                result_json = artifact_res.data[0].get("result_json") or {}
                if isinstance(result_json, dict):
                    if isinstance(result_json.get("training_metrics"), dict):
                        name_research_metrics = _coerce_training_metrics_payload(result_json.get("training_metrics"))
                    else:
                        # Fallback when artifact predates embedded training_metrics.
                        words_extracted = _to_non_negative_int(
                            (result_json.get("crawl_stats") or {}).get("words_extracted"), 0
                        )
                        fallback_questions = _to_non_negative_int(words_extracted / 90, 0)
                        fallback_mind = min(100, _to_non_negative_int(words_extracted / 1000, 0))
                        name_research_metrics = _coerce_training_metrics_payload(
                            {
                                "words_processed": words_extracted,
                                "questions_answerable_est": fallback_questions,
                                "mind_score": fallback_mind,
                                "mind_score_label": get_mind_score_label(fallback_mind),
                                "method_version": "name_research_fallback_v1",
                                "notes": "Estimated from name deep research crawl stats.",
                            }
                        )
                    preview_combined_questions = (
                        _to_non_negative_int(twin_metrics.get("questions_answerable_est"), 0)
                        + _to_non_negative_int((name_research_metrics or {}).get("questions_answerable_est"), 0)
                    )
                    question_suggestions = _extract_name_research_questions(result_json, preview_combined_questions)
    except Exception as e:
        print(f"[TWINS] Warning: failed to load name deep research insights for twin {twin_id}: {e}")

    twin_words = _to_non_negative_int(twin_metrics.get("words_processed"), 0)
    twin_questions = _to_non_negative_int(twin_metrics.get("questions_answerable_est"), 0)
    twin_mind = _to_non_negative_int(twin_metrics.get("mind_score"), 0)

    name_words = _to_non_negative_int((name_research_metrics or {}).get("words_processed"), 0)
    name_questions = _to_non_negative_int((name_research_metrics or {}).get("questions_answerable_est"), 0)
    name_mind = _to_non_negative_int((name_research_metrics or {}).get("mind_score"), 0)

    combined_words = twin_words + name_words
    combined_questions = twin_questions + name_questions
    combined_mind = min(100, max(twin_mind, name_mind))
    combined_metrics = _coerce_training_metrics_payload(
        {
            "words_processed": combined_words,
            "questions_answerable_est": combined_questions,
            "mind_score": combined_mind,
            "mind_score_label": get_mind_score_label(combined_mind),
            "method_version": "combined_v1",
            "notes": (
                "Combined estimate from twin onboarding training metrics and latest name deep research run. "
                "Counts may overlap across sources."
            ),
        }
    )

    # If name-research suggestions are unavailable, fall back to pinned profile questions.
    if not question_suggestions:
        public_profile = settings.get("public_profile") if isinstance(settings.get("public_profile"), dict) else {}
        pinned = public_profile.get("pinned_questions") if isinstance(public_profile.get("pinned_questions"), list) else []
        question_suggestions = _dedupe_questions(
            [
                *pinned,
                "What are the top questions you can answer about me right now?",
                "What details in my profile should I verify next?",
            ],
            limit=12,
        )

    capacity_prompt = (
        f"What are the top {min(max(combined_questions, 5), 20)} questions you can answer about me right now?"
        if combined_questions > 0
        else "What can you confidently answer about me right now?"
    )

    return {
        "twin_id": twin_id,
        "identity_name": identity_name,
        "latest_twin_research_run_id": latest_twin_research_run_id,
        "profile_pack": build_public_profile_pack(twin),
        "name_deep_research": name_research_summary,
        "metrics": {
            "combined": combined_metrics,
            "twin_onboarding": twin_metrics,
            "name_deep_research": name_research_metrics,
        },
        "question_suggestions": question_suggestions,
        "question_capacity_estimate": combined_questions,
        "question_capacity_prompt": capacity_prompt,
    }


@router.get("/twins/{twin_id}/metrics/debug")
async def get_twin_metrics_debug(twin_id: str, user=Depends(get_current_user)):
    """
    Get detailed training metrics breakdown for debugging/explainability.
    
    Returns component scores and internal calculations for the Mind Score.
    This endpoint is for debugging purposes and may expose internal details.
    
    Args:
        twin_id: Twin ID to get metrics for
        
    Returns:
        Detailed metrics breakdown including:
        - Component scores (volume, diversity, quality, etc.)
        - Source counts and statistics
        - Calculation metadata
    """
    user = _require_authenticated_user(user)
    verify_twin_ownership(twin_id, user)
    
    if not is_training_metrics_enabled():
        raise HTTPException(status_code=403, detail="Training metrics feature is disabled")
    
    try:
        from modules.training_metrics import compute_training_metrics
        
        metrics = compute_training_metrics(twin_id)
        
        return {
            "twin_id": twin_id,
            "public_metrics": {
                "words_processed": metrics.words_processed,
                "words_processed_display": metrics.words_processed_display,
                "questions_answerable_est": metrics.questions_answerable_est,
                "questions_answerable_display": metrics.questions_answerable_display,
                "mind_score": metrics.mind_score,
                "mind_score_label": metrics.mind_score_label,
                "method_version": metrics.method_version,
                "last_computed_at": metrics.last_computed_at,
            },
            "debug": {
                "component_scores": metrics.component_scores,
                "source_count": metrics.source_count,
                "failed_source_count": metrics.failed_source_count,
                "source_type_diversity": metrics.source_type_diversity,
                "calculation_notes": metrics.notes,
            },
            "formulas": {
                "mind_score": "0.25*volume + 0.20*diversity + 0.20*quality + 0.10*freshness + 0.15*structure + 0.10*verification",
                "volume_score": "logarithmic tiers (0-100)",
                "diversity_score": "unique_source_types * 20 (max 100)",
                "quality_score": "extraction_success_rate * 100",
                "questions_estimate": "(words/90) * quality * diversity * 0.85",
            }
        }
    except Exception as e:
        print(f"[TWINS] Error getting debug metrics for twin {twin_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to compute metrics: {str(e)}")


@router.post("/twins/{twin_id}/metrics/recompute")
async def recompute_twin_metrics(twin_id: str, user=Depends(verify_owner)):
    """
    Manually trigger metrics recomputation for a twin.
    
    This is useful for:
    - Debugging metrics issues
    - Forcing refresh after data corrections
    - Admin maintenance
    
    Args:
        twin_id: Twin ID to recompute metrics for
        
    Returns:
        Updated training metrics
    """
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    if not is_training_metrics_enabled():
        raise HTTPException(status_code=403, detail="Training metrics feature is disabled")
    
    try:
        from modules.training_metrics import (
            update_twin_training_metrics,
            get_training_metrics_for_api
        )
        
        # Force recompute by updating stored metrics
        success = update_twin_training_metrics(twin_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update metrics")
        
        # Return fresh metrics
        metrics = get_training_metrics_for_api(twin_id)
        
        return {
            "status": "success",
            "message": "Metrics recomputed successfully",
            "training_metrics": metrics["training_metrics"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] Error recomputing metrics for twin {twin_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to recompute metrics: {str(e)}")


@router.patch("/twins/{twin_id}")
async def patch_twin(
    twin_id: str,
    update: TwinSettingsUpdate,
    user=Depends(verify_owner),
):
    """
    Partial update endpoint used by dashboard profile/settings/share pages.
    Supports top-level name/description and merged settings updates.
    """
    user = _require_authenticated_user(user)
    verify_twin_ownership(twin_id, user)

    update_payload: Dict[str, Any] = {}
    if update.name is not None:
        normalized_name = update.name.strip()
        if not normalized_name:
            raise HTTPException(status_code=400, detail="Twin name cannot be empty")
        update_payload["name"] = normalized_name

    if update.description is not None:
        update_payload["description"] = update.description

    if update.specialization_id is not None:
        update_payload["specialization"] = update.specialization_id

    settings_changed = False
    merged_settings: Dict[str, Any] = {}

    if isinstance(update.settings, dict):
        settings_changed = True

    if update.is_public is not None:
        settings_changed = True

    if settings_changed:
        if update.is_public:
            verification_status = get_twin_verification_status(twin_id)
            if not verification_status.get("is_ready", False):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": "Verification required before publishing. Run verify retrieval first.",
                        "issues": verification_status.get("issues", []),
                    },
                )

            verification_res = (
                supabase.table("twin_verifications")
                .select("status, created_at, details")
                .eq("twin_id", twin_id)
                .order("created_at", desc=True)
                .limit(5)
                .execute()
            )
            verification_rows = verification_res.data or []
            has_quality_pass = any(_is_recent_quality_suite_pass(row) for row in verification_rows)
            if not has_quality_pass:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": "Quality verification required before publishing. Run /verify/twins/{twin_id}/quality-suite and pass all tests.",
                    },
                )

        twin_res = (
            supabase.table("twins")
            .select("settings")
            .eq("id", twin_id)
            .single()
            .execute()
        )
        if not twin_res.data:
            raise HTTPException(status_code=404, detail="Twin not found")

        merged_settings = dict(twin_res.data.get("settings") or {})

        if isinstance(update.settings, dict):
            merged_settings.update(update.settings)

        if update.is_public is not None:
            widget_settings = dict(merged_settings.get("widget_settings") or {})
            widget_settings["public_share_enabled"] = bool(update.is_public)
            merged_settings["widget_settings"] = widget_settings
            merged_settings["is_public"] = bool(update.is_public)

        update_payload["settings"] = merged_settings

    if not update_payload:
        twin_res = supabase.table("twins").select("*").eq("id", twin_id).single().execute()
        if not twin_res.data:
            raise HTTPException(status_code=404, detail="Twin not found")
        return twin_res.data

    update_payload["updated_at"] = datetime.utcnow().isoformat()
    response = supabase.table("twins").update(update_payload).eq("id", twin_id).execute()

    if not response.data:
        raise HTTPException(status_code=404, detail="Twin not found or update failed")

    return response.data


@router.get("/twins/{twin_id}/sidebar-config")
async def get_sidebar_config(twin_id: str, user=Depends(get_current_user)):
    """Get sidebar configuration based on twin's specialization."""
    user = _require_authenticated_user(user)
    # Verify user has access to this twin
    verify_twin_ownership(twin_id, user)
    
    try:
        # Get twin to find its specialization
        response = supabase.table("twins").select("specialization").eq("id", twin_id).execute()
        if not response.data:
            spec_name = "vanilla"
        else:
            spec_name = response.data[0].get("specialization", "vanilla")
        
        # Get specialization config
        spec = get_specialization(spec_name)
        
        return {
            "sidebar": spec.get("sidebar", []),
            "specialization": spec_name,
            "name": spec.get("name", spec_name)
        }
    except Exception as e:
        print(f"[TWINS] ERROR getting sidebar config: {e}")
        # Return default config on error
        return {
            "sidebar": [
                {"type": "section", "title": "Navigation", "items": [
                    {"type": "link", "label": "Chat", "href": f"/twins/{twin_id}/chat"},
                    {"type": "link", "label": "Knowledge", "href": f"/twins/{twin_id}/knowledge"}
                ]}
            ],
            "specialization": "vanilla",
            "name": "Vanilla"
        }


@router.post("/twins/{twin_id}/settings")
async def update_twin_settings(
    twin_id: str,
    update: TwinSettingsUpdate,
    user=Depends(get_current_user)
):
    """Update twin settings with strict ownership verification."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        # Merge with existing settings
        twin_res = supabase.table("twins").select("settings").eq("id", twin_id).single().execute()
        if not twin_res.data:
            raise HTTPException(status_code=404, detail="Twin not found")
        
        existing_settings = twin_res.data.get("settings") or {}
        updated_settings = {**existing_settings}
        
        if update.system_prompt is not None:
            updated_settings["system_prompt"] = update.system_prompt
        if update.handle is not None:
            updated_settings["handle"] = update.handle
        if update.tagline is not None:
            updated_settings["tagline"] = update.tagline
        if update.expertise is not None:
            updated_settings["expertise"] = update.expertise
        if update.personality is not None:
            updated_settings["personality"] = update.personality
        if update.intent_profile is not None:
            updated_settings["intent_profile"] = update.intent_profile
        
        # Update the settings
        response = supabase.table("twins").update({
            "settings": updated_settings
        }).eq("id", twin_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Twin not found or update failed")
        
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR updating settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/twins/{twin_id}/settings")
async def get_twin_settings(twin_id: str, user=Depends(get_current_user)):
    """Get twin settings."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        response = supabase.table("twins").select("settings").eq("id", twin_id).single().execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Twin not found")
        
        return response.data.get("settings") or {}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR getting settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/twins/{twin_id}/graph-stats")
async def get_twin_graph_stats(twin_id: str, user=Depends(get_current_user)):
    """Get graph statistics for a twin's content."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        stats = await get_graph_stats(twin_id)
        return stats
    except Exception as e:
        print(f"[TWINS] ERROR getting graph stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Archive / Soft Delete Endpoints
# ============================================================================


@router.post("/twins/{twin_id}/archive", response_model=DeleteTwinResponse)
async def archive_twin(twin_id: str, user=Depends(get_current_user)):
    """
    Archive (soft-delete) a twin.
    Sets deleted_at timestamp in settings; twin remains queryable but hidden from listings.
    """
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        # Get current settings
        twin_res = supabase.table("twins").select("settings").eq("id", twin_id).single().execute()
        if not twin_res.data:
            return DeleteTwinResponse(
                status="not_found",
                twin_id=twin_id,
                message="Twin not found"
            )
        
        settings = twin_res.data.get("settings") or {}
        
        # Check if already archived
        if settings.get("deleted_at"):
            return DeleteTwinResponse(
                status="already_archived",
                twin_id=twin_id,
                deleted_at=settings.get("deleted_at"),
                message="Twin is already archived"
            )
        
        # Set deleted_at timestamp
        deleted_at = datetime.utcnow().isoformat()
        settings["deleted_at"] = deleted_at
        
        # Update
        update_res = supabase.table("twins").update({
            "settings": settings
        }).eq("id", twin_id).execute()
        
        if not update_res.data:
            raise HTTPException(status_code=500, detail="Failed to archive twin")
        
        return DeleteTwinResponse(
            status="archived",
            twin_id=twin_id,
            deleted_at=deleted_at,
            message="Twin archived successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR archiving twin: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/twins/{twin_id}", response_model=DeleteTwinResponse)
async def delete_twin(
    twin_id: str, 
    hard: bool = Query(False, description="Perform hard delete (permanent)"),
    user=Depends(get_current_user)
):
    """
    Delete a twin. 
    - If hard=false (default): Archive (soft-delete) the twin
    - If hard=true: Hard-delete the twin and all associated data
    WARNING: Hard delete is destructive and cannot be undone.
    """
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        # Get twin info for audit log
        twin_res = supabase.table("twins").select("*").eq("id", twin_id).single().execute()
        if not twin_res.data:
            return DeleteTwinResponse(
                status="not_found",
                twin_id=twin_id,
                message="Twin not found"
            )
        
        twin_name = twin_res.data.get("name", "Unknown")
        # Capture tenant_id from the verified twin record — used to scope all deletes
        twin_tenant_id = twin_res.data.get("tenant_id") or user.get("tenant_id")

        # If not hard delete, perform archive instead
        if not hard:
            settings = twin_res.data.get("settings") or {}
            
            # Check if already archived
            if settings.get("deleted_at"):
                return DeleteTwinResponse(
                    status="already_archived",
                    twin_id=twin_id,
                    deleted_at=settings.get("deleted_at"),
                    message="Twin is already archived"
                )
            
            # Set deleted_at timestamp
            deleted_at = datetime.utcnow().isoformat()
            settings["deleted_at"] = deleted_at
            
            # Update
            update_res = supabase.table("twins").update({
                "settings": settings
            }).eq("id", twin_id).execute()
            
            if not update_res.data:
                raise HTTPException(status_code=500, detail="Failed to archive twin")
            
            return DeleteTwinResponse(
                status="archived",
                twin_id=twin_id,
                deleted_at=deleted_at,
                message="Twin archived successfully"
            )
        
        # Hard delete - delete related data first, then the twin
        # Most tables have ON DELETE CASCADE, but we need to handle those that don't
        
        # Use a transaction-like approach with proper error handling
        try:
            # Delete from tables that might not have CASCADE set up correctly
            # Order matters - delete child tables before parents
            
            # 0. Delete from escalations (does NOT have ON DELETE CASCADE)
            try:
                supabase.table("escalations").delete().eq("twin_id", twin_id).execute()
            except Exception as e:
                print(f"[TWINS] Note: Could not delete escalations: {e}")
            
            # 1. Delete from persona_specs (has ON DELETE CASCADE, but be explicit)
            try:
                supabase.table("persona_specs").delete().eq("twin_id", twin_id).execute()
            except Exception as e:
                print(f"[TWINS] Note: Could not delete persona_specs: {e}")
            
            # 2. Delete from persona_prompt_optimization_runs
            try:
                supabase.table("persona_prompt_optimization_runs").delete().eq("twin_id", twin_id).execute()
            except Exception as e:
                print(f"[TWINS] Note: Could not delete optimization runs: {e}")
            
            # 3. Delete from persona_prompt_optimization_results  
            try:
                supabase.table("persona_prompt_optimization_results").delete().eq("twin_id", twin_id).execute()
            except Exception as e:
                print(f"[TWINS] Note: Could not delete optimization results: {e}")
            
            # 4. Delete from memory_events
            try:
                supabase.table("memory_events").delete().eq("twin_id", twin_id).execute()
            except Exception as e:
                print(f"[TWINS] Note: Could not delete memory events: {e}")
            
            # 5. Delete from twin_verifications
            try:
                supabase.table("twin_verifications").delete().eq("twin_id", twin_id).execute()
            except Exception as e:
                print(f"[TWINS] Note: Could not delete verifications: {e}")
            
            # 6. Delete from access_groups (this will cascade to memberships and permissions)
            try:
                supabase.table("access_groups").delete().eq("twin_id", twin_id).execute()
            except Exception as e:
                print(f"[TWINS] Note: Could not delete access groups: {e}")
            
            # 7. Delete from owner_memory_entries and owner_memory_snapshots
            try:
                supabase.table("owner_memory_snapshots").delete().eq("twin_id", twin_id).execute()
                supabase.table("owner_memory_entries").delete().eq("twin_id", twin_id).execute()
            except Exception as e:
                print(f"[TWINS] Note: Could not delete owner memory: {e}")
            
            # 8. Delete from training_sessions and related tables
            try:
                # These have CASCADE, but be explicit for clarity
                supabase.table("training_decisions").delete().eq("twin_id", twin_id).execute()
                supabase.table("training_interactions").delete().eq("twin_id", twin_id).execute()
                supabase.table("training_sessions").delete().eq("twin_id", twin_id).execute()
            except Exception as e:
                print(f"[TWINS] Note: Could not delete training data: {e}")
            
            # 9. Delete sources (this should cascade to chunks via FK)
            try:
                supabase.table("sources").delete().eq("twin_id", twin_id).execute()
            except Exception as e:
                print(f"[TWINS] Note: Could not delete sources: {e}")
            
            # 10. Delete conversations (this should cascade to messages)
            try:
                supabase.table("conversations").delete().eq("twin_id", twin_id).execute()
            except Exception as e:
                print(f"[TWINS] Note: Could not delete conversations: {e}")
            
            # 11. Delete Pinecone vectors for this twin (external to Postgres)
            try:
                from modules.clients import get_pinecone_index
                from modules.twin_namespace import get_namespace_candidates_for_twin
                index = get_pinecone_index()
                for namespace in get_namespace_candidates_for_twin(twin_id=twin_id, include_legacy=True):
                    try:
                        index.delete(delete_all=True, namespace=namespace)
                        print(f"[TWINS] Deleted Pinecone namespace: {namespace}")
                    except Exception as ns_e:
                        print(f"[TWINS] Note: Could not delete Pinecone namespace {namespace}: {ns_e}")
            except Exception as e:
                print(f"[TWINS] Note: Could not delete Pinecone vectors: {e}")
            
            # 11. Finally delete the twin — scope by BOTH id AND tenant_id for defence-in-depth
            delete_res = (
                supabase.table("twins")
                .delete()
                .eq("id", twin_id)
                .eq("tenant_id", twin_tenant_id)
                .execute()
            )
            
            if not delete_res.data:
                raise HTTPException(status_code=500, detail="Failed to delete twin from database")
            
            # Audit log
            try:
                audit_logger = AuditLogger(supabase)
                await audit_logger.log(
                    event_type="twin_deleted",
                    user_id=user.get("user_id"),
                    twin_id=twin_id,
                    details={"twin_name": twin_name, "hard_delete": True}
                )
            except Exception as e:
                print(f"[TWINS] Warning: Could not write audit log: {e}")
            
            return DeleteTwinResponse(
                status="deleted",
                twin_id=twin_id,
                cleanup_status="done",
                message="Twin permanently deleted"
            )
            
        except Exception as inner_e:
            error_msg = str(inner_e).lower()
            if "foreign key" in error_msg or "constraint" in error_msg:
                print(f"[TWINS] Foreign key constraint error deleting twin {twin_id}: {inner_e}")
                raise HTTPException(
                    status_code=409, 
                    detail="Cannot delete twin: related data exists. Please try archiving instead."
                )
            raise
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR deleting twin {twin_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# ============================================================================
# Access Group Endpoints
# ============================================================================


@router.post("/twins/{twin_id}/groups")
async def create_twin_group(
    twin_id: str,
    request: GroupCreateRequest,
    user=Depends(get_current_user)
):
    """Create a new access group for a twin."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        group = await create_group(
            twin_id=twin_id,
            name=request.name,
            description=request.description,
            is_default=request.is_default
        )
        return group
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR creating group: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/twins/{twin_id}/groups")
async def list_twin_groups(twin_id: str, user=Depends(get_current_user)):
    """List all access groups for a twin."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        groups = await list_groups(twin_id)
        return {"groups": groups}
    except Exception as e:
        print(f"[TWINS] ERROR listing groups: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/twins/{twin_id}/groups/{group_id}")
async def get_twin_group(twin_id: str, group_id: str, user=Depends(get_current_user)):
    """Get a specific access group."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        group = await get_group(group_id)
        if not group or group.get("twin_id") != twin_id:
            raise HTTPException(status_code=404, detail="Group not found")
        return group
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR getting group: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/twins/{twin_id}/groups/{group_id}")
async def update_twin_group(
    twin_id: str,
    group_id: str,
    request: GroupUpdateRequest,
    user=Depends(get_current_user)
):
    """Update an access group."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        # Verify group belongs to this twin
        group = await get_group(group_id)
        if not group or group.get("twin_id") != twin_id:
            raise HTTPException(status_code=404, detail="Group not found")
        
        updated = await update_group(
            group_id=group_id,
            name=request.name,
            description=request.description,
            is_default=request.is_default
        )
        return updated
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR updating group: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/twins/{twin_id}/groups/{group_id}")
async def delete_twin_group(twin_id: str, group_id: str, user=Depends(get_current_user)):
    """Delete an access group."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        # Verify group belongs to this twin
        group = await get_group(group_id)
        if not group or group.get("twin_id") != twin_id:
            raise HTTPException(status_code=404, detail="Group not found")
        
        success = await delete_group(group_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete group")
        
        return {"status": "deleted", "group_id": group_id}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR deleting group: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/twins/{twin_id}/groups/{group_id}/assign")
async def assign_user_to_twin_group(
    twin_id: str,
    group_id: str,
    request: AssignUserRequest,
    user=Depends(get_current_user)
):
    """Assign a user to an access group."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        # Verify group belongs to this twin
        group = await get_group(group_id)
        if not group or group.get("twin_id") != twin_id:
            raise HTTPException(status_code=404, detail="Group not found")
        
        membership = await assign_user_to_group(
            group_id=group_id,
            user_id=request.user_id,
            role=request.role,
            permissions=request.permissions
        )
        return membership
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR assigning user to group: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/twins/{twin_id}/groups/{group_id}/members")
async def get_group_members_list(twin_id: str, group_id: str, user=Depends(get_current_user)):
    """Get members of an access group."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        # Verify group belongs to this twin
        group = await get_group(group_id)
        if not group or group.get("twin_id") != twin_id:
            raise HTTPException(status_code=404, detail="Group not found")
        
        members = await get_group_members(group_id)
        return {"members": members}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR getting group members: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Content Permission Endpoints
# ============================================================================


@router.post("/twins/{twin_id}/content/{content_id}/permissions")
async def add_content_permissions(
    twin_id: str,
    content_id: str,
    request: ContentPermissionRequest,
    user=Depends(get_current_user)
):
    """Add content permission for a group."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        permission = await add_content_permission(
            content_id=content_id,
            group_id=request.group_id,
            permission_type=request.permission_type,
            config=request.config
        )
        return permission
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR adding content permission: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/twins/{twin_id}/content/{content_id}/permissions")
async def get_content_permissions(twin_id: str, content_id: str, user=Depends(get_current_user)):
    """Get permissions for a content item."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        permissions = await get_group_permissions(content_id)
        return {"permissions": permissions}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR getting content permissions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/twins/{twin_id}/content/{content_id}/permissions/{permission_id}")
async def remove_content_perm(
    twin_id: str,
    content_id: str,
    permission_id: str,
    user=Depends(get_current_user)
):
    """Remove a content permission."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        success = await remove_content_permission(permission_id)
        if not success:
            raise HTTPException(status_code=404, detail="Permission not found")
        return {"status": "removed", "permission_id": permission_id}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR removing content permission: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Group Limits Endpoints
# ============================================================================


@router.post("/twins/{twin_id}/groups/{group_id}/limits")
async def set_group_limit_endpoint(
    twin_id: str,
    group_id: str,
    request: GroupLimitSchema,
    user=Depends(get_current_user)
):
    """Set rate and token limits for a group."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        # Verify group belongs to this twin
        group = await get_group(group_id)
        if not group or group.get("twin_id") != twin_id:
            raise HTTPException(status_code=404, detail="Group not found")
        
        limit = await set_group_limit(
            group_id=group_id,
            rate_limit=request.rate_limit,
            token_limit=request.token_limit,
            reset_period=request.reset_period
        )
        return limit
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR setting group limit: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/twins/{twin_id}/groups/{group_id}/limits")
async def get_group_limit_endpoint(twin_id: str, group_id: str, user=Depends(get_current_user)):
    """Get rate and token limits for a group."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        # Verify group belongs to this twin
        group = await get_group(group_id)
        if not group or group.get("twin_id") != twin_id:
            raise HTTPException(status_code=404, detail="Group not found")
        
        limits = await get_group_limits(group_id)
        return {"limits": limits}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR getting group limits: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/twins/{twin_id}/groups/{group_id}/overrides")
async def set_group_override_endpoint(
    twin_id: str,
    group_id: str,
    request: GroupOverrideSchema,
    user=Depends(get_current_user)
):
    """Set model override for a group."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        # Verify group belongs to this twin
        group = await get_group(group_id)
        if not group or group.get("twin_id") != twin_id:
            raise HTTPException(status_code=404, detail="Group not found")
        
        override = await set_group_override(
            group_id=group_id,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        return override
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR setting group override: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/twins/{twin_id}/groups/{group_id}/overrides")
async def get_group_override_endpoint(twin_id: str, group_id: str, user=Depends(get_current_user)):
    """Get model override for a group."""
    user = _require_authenticated_user(user)
    ensure_twin_owner_or_403(twin_id, user)
    
    try:
        # Verify group belongs to this twin
        group = await get_group(group_id)
        if not group or group.get("twin_id") != twin_id:
            raise HTTPException(status_code=404, detail="Group not found")
        
        overrides = await get_group_overrides(group_id)
        return {"overrides": overrides}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TWINS] ERROR getting group overrides: {e}")
        raise HTTPException(status_code=500, detail=str(e))
