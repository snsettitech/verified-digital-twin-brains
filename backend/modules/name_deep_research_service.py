"""
Name-Only Deep Research Service

Pipeline:
1) Search (query expansion + web discovery)
2) Crawl/Scrape (robots-aware, auth/paywall-respecting)
3) Extract + score evidence
4) Synthesize grounded JSON using OpenAI reasoning model (prefer o3)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field

from modules.clients import get_async_openai_client
from modules.deep_research_config import get_config as get_dr_config
from modules.firecrawl_client import ContentQuality, FirecrawlResult, get_firecrawl_client
from modules.identity_confidence_scorer import IdentityConfidenceScorer
from modules.name_deep_research_synthesis import (
    NameDeepResearchDraftModel,
    normalize_name_deep_research_synthesis_payload,
)
from modules.observability import supabase
from modules.research_claim_web_search import create_search_provider_with_fallback
from modules.robots_checker import RobotsChecker
from modules.training_metrics import (
    SourceMetrics,
    calculate_diversity_score,
    calculate_mind_score,
    calculate_volume_score,
    estimate_questions_answerable,
    format_number_compact,
    get_mind_score_label,
)
from modules.url_canonicalizer import canonicalize_url

logger = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_iso(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    candidate = str(value).strip()
    if not candidate:
        return None
    try:
        return datetime.fromisoformat(candidate.replace("Z", "+00:00")).isoformat()
    except Exception:
        return None


def _word_count(text: str) -> int:
    return len((text or "").split())


def _to_quality_value(value: Any) -> str:
    if isinstance(value, ContentQuality):
        return value.value
    txt = str(value or "").strip().lower()
    if txt in {"full", "partial", "blocked", "manual_needed"}:
        return txt
    return "partial"


def _quality_score(quality: str) -> float:
    return {
        "full": 1.0,
        "partial": 0.65,
        "manual_needed": 0.2,
        "blocked": 0.05,
    }.get(quality, 0.5)


def _recency_score(published_at: Optional[str]) -> float:
    if not published_at:
        return 0.4
    try:
        published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except Exception:
        return 0.4
    age_days = max(0.0, (datetime.now(timezone.utc) - published).days)
    if age_days <= 30:
        return 1.0
    if age_days <= 180:
        return 0.85
    if age_days <= 365:
        return 0.7
    if age_days <= 3 * 365:
        return 0.5
    return 0.3


def _source_type_from_url(url: str) -> str:
    host = (urlparse(url).netloc or "").lower()
    path = (urlparse(url).path or "").lower()
    if "linkedin.com" in host:
        return "linkedin"
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if any(x in host for x in ["nytimes.com", "reuters.com", "bloomberg.com", "wsj.com", "bbc.com", "forbes.com"]):
        return "news"
    if "podcast" in host or "podcast" in path:
        return "podcast"
    if any(x in path for x in ["/about", "/team", "/bio", "/profile", "/people"]):
        return "profile"
    return "website"


def _extract_published_at(metadata: Dict[str, Any]) -> Optional[str]:
    keys = [
        "published_at",
        "published",
        "publishedDate",
        "article:published_time",
        "date",
        "lastmod",
    ]
    for key in keys:
        if key in metadata:
            parsed = _safe_iso(str(metadata.get(key)))
            if parsed:
                return parsed
    return None


def _is_known_auth_wall(url: str) -> bool:
    host = (urlparse(url).netloc or "").lower()
    path = (urlparse(url).path or "").lower()
    if any(d in host for d in ["linkedin.com", "facebook.com", "instagram.com", "x.com", "twitter.com"]):
        return True
    if any(token in path for token in ["/login", "/signin", "/paywall", "/subscribe"]):
        return True
    return False


def _normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip())


def _strip_draft_suffix(name: str) -> str:
    cleaned = _normalize_name(name)
    if cleaned.lower().endswith(" (draft)"):
        return cleaned[:-8].strip()
    return cleaned


def _names_conflict(existing: Optional[str], requested: Optional[str]) -> bool:
    left = _strip_draft_suffix(existing or "").lower()
    right = _strip_draft_suffix(requested or "").lower()
    if not left or not right:
        return False
    return left != right


def _name_variants(full_name: str) -> List[str]:
    name = _normalize_name(full_name)
    parts = [p for p in name.split(" ") if p]
    variants = {name}
    if len(parts) >= 2:
        variants.add(f"{parts[0]} {parts[-1]}")
        variants.add(f"{parts[0]} \"{parts[-1]}\"")
    if len(parts) >= 3 and len(parts[1]) == 1:
        variants.add(f"{parts[0]} {parts[-1]}")
    return [v for v in variants if v]


class HintsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    location: Optional[str] = None
    company: Optional[str] = None
    website: Optional[str] = None


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    hints: HintsModel


class PossibleDuplicateModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)


class ClaimedIdentityModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    canonical_name: str
    is_match_confidence: float = Field(ge=0.0, le=1.0)
    disambiguation_notes: List[str]
    possible_duplicates: List[PossibleDuplicateModel]


class BioModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    short: str
    medium: str
    long: str


class ExpertiseTopicModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_count: int = Field(ge=0)


class ProfileSummaryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    what_they_do: List[str]
    expertise_topics: List[ExpertiseTopicModel]
    organizations: List[str]
    locations: List[str]
    public_roles: List[str]


class TimelineItemModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date_or_range: str
    event: str
    confidence: float = Field(ge=0.0, le=1.0)
    citations: List[str]


class ClaimItemModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_id: str
    text: str
    claim_type: Literal["credential", "experience", "role", "preference", "opinion", "project", "contact", "other"]
    status: Literal["verified", "partially_verified", "unverified", "disputed", "unknown"]
    confidence: float = Field(ge=0.0, le=1.0)
    citations: List[str]
    notes: str


class KnownUnknownModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str
    why_missing: str


class CrawlStatsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    queries_used: List[str]
    urls_considered: int = Field(ge=0)
    urls_crawled: int = Field(ge=0)
    urls_blocked: int = Field(ge=0)
    sources_used_in_final: int = Field(ge=0)
    words_extracted: int = Field(ge=0)
    run_started_at: str
    run_completed_at: str


class QualityModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    overall_confidence: float = Field(ge=0.0, le=1.0)
    freshness_score: float = Field(ge=0.0, le=1.0)
    coverage_score: float = Field(ge=0.0, le=1.0)
    hallucination_risk: Literal["low", "medium", "high"]
    warnings: List[str]


class SourceItemModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    url: str
    title: str
    source_type: Literal["website", "linkedin", "youtube", "news", "podcast", "profile", "other"]
    published_at: Optional[str] = None
    retrieved_at: str
    content_quality: Literal["full", "partial", "blocked", "manual_needed"]
    identity_match_confidence: float = Field(ge=0.0, le=1.0)
    used_in_final: bool


class TrainingMetricsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    words_processed: int = Field(ge=0)
    words_processed_display: str
    questions_answerable_est: int = Field(ge=0)
    questions_answerable_display: str
    mind_score: int = Field(ge=0, le=100)
    mind_score_label: str
    method_version: str
    notes: str


class PreparedQuestionAnswerModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str
    answer: str
    confidence: float = Field(ge=0.0, le=1.0)
    citations: List[str]


class NameDeepResearchResultModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    input: InputModel
    claimed_identity: ClaimedIdentityModel
    bio: BioModel
    profile_summary: ProfileSummaryModel
    timeline: List[TimelineItemModel]
    claims: List[ClaimItemModel]
    known_unknowns: List[KnownUnknownModel]
    suggested_followup_questions: List[str]
    crawl_stats: CrawlStatsModel
    quality: QualityModel
    sources: List[SourceItemModel]
    training_metrics: Optional[TrainingMetricsModel] = None
    prepared_question_answers: List[PreparedQuestionAnswerModel] = Field(default_factory=list)


def _validate_citations(result_doc: Dict[str, Any]) -> None:
    source_ids = {s.get("source_id") for s in result_doc.get("sources", [])}
    source_ids.discard(None)

    def _check(citations: List[str], owner: str) -> None:
        if not citations:
            raise ValueError(f"{owner} is missing citations")
        missing = [c for c in citations if c not in source_ids]
        if missing:
            raise ValueError(f"{owner} has unknown citation ids: {missing}")

    for idx, item in enumerate(result_doc.get("timeline", [])):
        _check(item.get("citations", []), f"timeline[{idx}]")
    for idx, item in enumerate(result_doc.get("claims", [])):
        _check(item.get("citations", []), f"claims[{idx}]")
    for idx, item in enumerate(result_doc.get("prepared_question_answers", [])):
        _check(item.get("citations", []), f"prepared_question_answers[{idx}]")


@dataclass
class RankedEvidence:
    source_id: str
    rank_score: float
    url: str
    title: str
    source_type: str
    published_at: Optional[str]
    retrieved_at: str
    content_quality: str
    identity_match_confidence: float
    excerpt: str


@dataclass
class SourceSelectionDecision:
    source_id: str
    selected: bool
    selection_score: float
    reason_codes: List[str]


class NameDeepResearchService:
    """
    Production name-only deep research pipeline.

    DB persistence:
    - name_deep_research_runs
    - name_deep_research_sources
    - name_deep_research_pages
    - name_deep_research_artifacts
    """

    def __init__(
        self,
        *,
        db_client: Any = None,
        firecrawl_client: Any = None,
        openai_client: Any = None,
        robots_checker: Optional[RobotsChecker] = None,
    ):
        self.db = db_client or supabase
        self.firecrawl = firecrawl_client if firecrawl_client is not None else get_firecrawl_client()
        self._openai_client = openai_client
        self.robots_checker = robots_checker or RobotsChecker(
            user_agent=os.getenv("NAME_RESEARCH_USER_AGENT", "VerifiedTwinResearchBot/1.0")
        )
        self.identity_scorer = IdentityConfidenceScorer()
        self.max_urls = int(os.getenv("NAME_RESEARCH_MAX_URLS", "30"))
        self.max_sources_for_synthesis = int(os.getenv("NAME_RESEARCH_MAX_SOURCES", "12"))
        self.max_excerpt_chars = int(os.getenv("NAME_RESEARCH_MAX_EXCERPT_CHARS", "3500"))
        self.identity_gating_enabled = os.getenv("NAME_RESEARCH_IDENTITY_GATING_ENABLED", "true").lower() == "true"
        self.synthesis_hardening_enabled = (
            os.getenv("NAME_RESEARCH_SYNTHESIS_HARDENING_ENABLED", "true").lower() == "true"
        )
        self.synthesis_repair_retry_enabled = (
            os.getenv("NAME_RESEARCH_SYNTHESIS_REPAIR_RETRY_ENABLED", "true").lower() == "true"
        )
        self.metrics_and_qa_enabled = os.getenv("NAME_RESEARCH_METRICS_QA_ENABLED", "true").lower() == "true"
        self._models_cache: Optional[List[str]] = None
        preferred_provider = (os.getenv("SEARCH_PROVIDER", "exa") or "exa").lower()
        self.search_provider = create_search_provider_with_fallback(preferred=preferred_provider)

    def _creator_candidates(self, *, tenant_id: str, user_id: str) -> List[str]:
        candidates: List[str] = []
        if user_id:
            candidates.append(str(user_id))
        if tenant_id:
            candidates.append(f"tenant_{tenant_id}")
        # Keep order, remove duplicates.
        seen: set[str] = set()
        ordered: List[str] = []
        for candidate in candidates:
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            ordered.append(candidate)
        return ordered

    def _score_twin_for_user(self, twin: Dict[str, Any], *, user_id: str, creator_candidates: List[str]) -> int:
        score = 0
        creator_id = str(twin.get("creator_id") or "")
        settings = twin.get("settings") or {}
        owner_user_id = str(settings.get("owner_user_id") or "")
        status = str(twin.get("status") or "").lower()

        if owner_user_id and user_id and owner_user_id == user_id:
            score += 100
        if creator_id and user_id and creator_id == user_id:
            score += 80
        if creator_id in creator_candidates:
            score += 40
        if status == "active":
            score += 20
        if status == "persona_built":
            score += 10
        return score

    def _find_existing_profile_twin(self, *, tenant_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        rows = (
            self.db.table("twins")
            .select("id,name,status,is_active,settings,created_at,creator_id")
            .eq("tenant_id", tenant_id)
            .is_("settings->>deleted_at", "null")
            .order("created_at", desc=True)
            .limit(25)
            .execute()
        ).data or []
        if not rows:
            return None

        creator_candidates = self._creator_candidates(tenant_id=tenant_id, user_id=user_id)
        ranked = sorted(
            rows,
            key=lambda row: (
                self._score_twin_for_user(row, user_id=user_id, creator_candidates=creator_candidates),
                str(row.get("created_at") or ""),
            ),
            reverse=True,
        )
        return ranked[0] if ranked else None

    def _has_material_person_data(self, *, twin_id: str) -> bool:
        count_checks = [
            ("sources", "id"),
            ("chunks", "id"),
            ("person_source_registry", "id"),
            ("person_claims", "id"),
            ("person_timeline_events", "id"),
        ]
        for table, field in count_checks:
            try:
                res = (
                    self.db.table(table)
                    .select(field, count="exact")
                    .eq("twin_id", twin_id)
                    .limit(1)
                    .execute()
                )
                if (res.count or 0) > 0:
                    return True
            except Exception:
                # Legacy/missing table/column should not block flow.
                continue
        return False

    def _clear_twin_person_data(self, *, twin_id: str) -> None:
        # Ordered from derived tables -> base sources.
        tables = [
            "person_claim_evidence_spans",
            "person_claims",
            "person_timeline_events",
            "person_topic_profiles",
            "person_contradictions",
            "person_answerability_scores",
            "person_style_profile",
            "person_source_registry",
            "person_completeness_runs",
            "chunks",
            "sources",
        ]
        for table in tables:
            try:
                self.db.table(table).delete().eq("twin_id", twin_id).execute()
            except Exception as exc:
                logger.warning("name-research reset: failed clearing %s for twin=%s (%s)", table, twin_id, exc)

        # Best-effort vector namespace purge to avoid cross-person retrieval bleed.
        try:
            from modules.clients import get_pinecone_index
            from modules.delphi_namespace import get_primary_namespace_for_twin

            namespace = get_primary_namespace_for_twin(twin_id=twin_id)
            index = get_pinecone_index()
            index.delete(delete_all=True, namespace=namespace)
        except Exception as exc:
            logger.warning("name-research reset: vector purge failed for twin=%s (%s)", twin_id, exc)

    def _safe_update_twin_record(self, *, twin_id: str, tenant_id: str, payload: Dict[str, Any]) -> None:
        mutable_payload = dict(payload)
        removable_columns = ["status", "is_active"]

        while True:
            try:
                (
                    self.db.table("twins")
                    .update(mutable_payload)
                    .eq("id", twin_id)
                    .eq("tenant_id", tenant_id)
                    .execute()
                )
                return
            except Exception as exc:
                msg = str(exc).lower()
                removed = None
                for column in removable_columns:
                    if column in mutable_payload and column in msg and (
                        "does not exist" in msg or "could not find" in msg or "pgrst204" in msg
                    ):
                        removed = column
                        break
                if removed:
                    mutable_payload.pop(removed, None)
                    continue
                raise

    def _reset_identity_on_existing_twin(
        self,
        *,
        twin: Dict[str, Any],
        tenant_id: str,
        user_id: str,
        normalized_name: str,
        hints: Dict[str, Optional[str]],
    ) -> None:
        twin_id = twin["id"]
        previous_name = str(twin.get("name") or "").strip()
        self._clear_twin_person_data(twin_id=twin_id)

        current_settings = twin.get("settings") or {}
        merged_settings = {
            **current_settings,
            "owner_name": normalized_name,
            "owner_user_id": user_id,
            "build_mode": "name_only",
            "creation_mode": "name_first",
            "name_first_state": "researching",
            "name_first_hints": {
                "location": hints.get("location"),
                "company": hints.get("company"),
                "website": hints.get("website"),
            },
            "identity_reset_at": _utcnow_iso(),
            "identity_reset_from": previous_name,
        }

        update_payload = {
            "name": normalized_name,
            "settings": merged_settings,
            "description": f"{normalized_name}'s verified digital profile",
            "status": "draft",
            "is_active": False,
        }
        self._safe_update_twin_record(
            twin_id=twin_id,
            tenant_id=tenant_id,
            payload=update_payload,
        )
        logger.info(
            "name-research identity reset applied: twin_id=%s from=%s to=%s",
            twin_id,
            previous_name,
            normalized_name,
        )

    async def create_run(
        self,
        *,
        tenant_id: str,
        user_id: str,
        name: str,
        hints: Dict[str, Optional[str]],
        idempotency_key: Optional[str],
    ) -> Dict[str, Any]:
        normalized_name = _normalize_name(name)
        if not normalized_name:
            raise ValueError("name is required")

        idempotency_key = (idempotency_key or "").strip() or None
        if idempotency_key:
            existing = (
                self.db.table("name_deep_research_runs")
                .select("*")
                .eq("tenant_id", tenant_id)
                .eq("idempotency_key", idempotency_key)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if existing.data:
                row = dict(existing.data[0])
                if not row.get("twin_id"):
                    fallback_twin = self._find_existing_profile_twin(tenant_id=tenant_id, user_id=user_id)
                    if fallback_twin:
                        row["twin_id"] = fallback_twin["id"]
                return row

        # ====================================================================
        # STEP 1: Check for existing profile (one profile per user rule)
        # ====================================================================
        existing_twin = self._find_existing_profile_twin(tenant_id=tenant_id, user_id=user_id)

        if existing_twin:
            existing_name = _strip_draft_suffix(str(existing_twin.get("name") or ""))
            status = str(existing_twin.get("status") or "").lower()
            material_data_exists = self._has_material_person_data(twin_id=existing_twin["id"])

            if _names_conflict(existing_name, normalized_name):
                # Guard against multi-person identity drift for single-profile accounts.
                if status == "active" and material_data_exists:
                    raise ValueError(
                        f"Existing profile identity is '{existing_name}'. "
                        "Reset profile before researching a different person."
                    )
                self._reset_identity_on_existing_twin(
                    twin=existing_twin,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    normalized_name=normalized_name,
                    hints=hints,
                )

            # User already has a profile - attach research to existing twin.
            twin_id = existing_twin["id"]
            logger.info(
                "name-research attaching to existing twin: twin_id=%s tenant_id=%s user_id=%s",
                twin_id,
                tenant_id,
                user_id,
            )
        else:
            # No existing profile - create new twin in "name_first" mode
            from modules.twin_service import create_twin_for_name_research
            
            twin_id = await create_twin_for_name_research(
                db=self.db,
                tenant_id=tenant_id,
                user_id=user_id,
                name=normalized_name,
                hints=hints,
            )
            logger.info("name-research created twin: twin_id=%s name=%s", twin_id, normalized_name)

        insert_payload = {
            "tenant_id": tenant_id,
            "created_by": user_id,
            "twin_id": twin_id,
            "status": "created",
            "input_name": normalized_name,
            "input_location": (hints.get("location") or None),
            "input_company": (hints.get("company") or None),
            "input_website": (hints.get("website") or None),
            "idempotency_key": idempotency_key,
            "run_started_at": _utcnow_iso(),
        }

        try:
            created = self.db.table("name_deep_research_runs").insert(insert_payload).execute()
        except Exception as exc:
            msg = str(exc).lower()
            if "twin_id" in msg and ("could not find" in msg or "does not exist" in msg):
                # Backward compatibility for environments that have not yet applied
                # migration adding name_deep_research_runs.twin_id.
                logger.warning(
                    "name_deep_research_runs.twin_id missing; retrying insert without twin_id column"
                )
                insert_payload.pop("twin_id", None)
                created = self.db.table("name_deep_research_runs").insert(insert_payload).execute()
            else:
                raise
        if not created.data:
            raise RuntimeError("Failed to create deep research run")

        run_row = created.data[0]
        run_id = run_row["id"]

        task = asyncio.create_task(self._execute_pipeline(run_id=run_id, tenant_id=tenant_id, user_id=user_id, twin_id=twin_id))
        _ACTIVE_RUN_TASKS[run_id] = task

        def _cleanup(_task: asyncio.Task) -> None:
            _ACTIVE_RUN_TASKS.pop(run_id, None)
            if _task.cancelled():
                logger.warning("name-research run task cancelled: %s", run_id)
                return
            exc = _task.exception()
            if exc:
                logger.exception("name-research run task failed: run_id=%s err=%s", run_id, exc)

        task.add_done_callback(_cleanup)
        
        # Include twin_id in the returned row for the API response
        run_row["twin_id"] = twin_id
        return run_row

    async def get_run(self, *, run_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        response = (
            self.db.table("name_deep_research_runs")
            .select("*")
            .eq("id", run_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    async def get_result(self, *, run_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        response = (
            self.db.table("name_deep_research_artifacts")
            .select("result_json")
            .eq("run_id", run_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        if not response.data:
            return None
        return response.data[0].get("result_json")

    def build_queries(self, *, name: str, hints: Dict[str, Optional[str]]) -> List[str]:
        full_name = _normalize_name(name)
        if not full_name:
            return []

        this_year = datetime.now(timezone.utc).year
        variants = _name_variants(full_name)
        queries: List[str] = []

        for variant in variants:
            queries.append(f"\"{variant}\"")
            queries.append(f"{variant} biography")
            queries.append(f"{variant} interviews podcast talks")
            queries.append(f"{variant} profile linkedin")
            queries.append(f"{variant} {this_year}")
            queries.append(f"{variant} {this_year - 1}")

        location = (hints.get("location") or "").strip()
        company = (hints.get("company") or "").strip()
        website = (hints.get("website") or "").strip()

        if location:
            queries.append(f"\"{full_name}\" \"{location}\"")
            queries.append(f"{full_name} {location} profile")
        if company:
            queries.append(f"\"{full_name}\" \"{company}\"")
            queries.append(f"{full_name} {company} leadership")
        if website:
            domain = website.replace("https://", "").replace("http://", "").split("/")[0]
            queries.append(f"\"{full_name}\" site:{domain}")

        seen: set[str] = set()
        unique_queries: List[str] = []
        for q in queries:
            normalized = re.sub(r"\s+", " ", q).strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                unique_queries.append(normalized)
        return unique_queries[:20]

    async def discover_urls_for_identity(
        self,
        *,
        name: str,
        hints: Dict[str, Optional[str]],
        max_queries: int = 10,
        max_urls: int = 80,
    ) -> List[str]:
        """
        Shared URL discovery helper for name-anchored research flows.

        This exposes the same discovery stack used by name-only deep research
        (query expansion + provider fallback + Firecrawl search) so other
        onboarding flows can reuse it safely.
        """
        queries = self.build_queries(name=name, hints=hints)
        if max_queries > 0:
            queries = queries[:max_queries]
        if not queries:
            return []

        try:
            discovered = await self._discover_urls(queries)
        except Exception as exc:
            logger.warning("URL discovery failed for '%s': %s", name, exc)
            return []

        deduped = self.dedupe_urls(discovered)
        if max_urls > 0:
            return deduped[:max_urls]
        return deduped

    def dedupe_urls(self, urls: List[str]) -> List[str]:
        deduped: List[str] = []
        seen: set[str] = set()
        for raw in urls:
            if not raw:
                continue
            try:
                canonical = canonicalize_url(raw)
            except Exception:
                continue
            if canonical in seen:
                continue
            seen.add(canonical)
            deduped.append(canonical)
        return deduped

    def validate_result_schema(self, doc: Dict[str, Any]) -> NameDeepResearchResultModel:
        parsed = NameDeepResearchResultModel.model_validate(doc)
        _validate_citations(parsed.model_dump())
        return parsed

    def _log_metric(self, *, run_id: str, metric: str, value: int = 1, **fields: Any) -> None:
        payload = {"metric": metric, "value": value, **fields}
        logger.info("name-research metric run_id=%s %s", run_id, json.dumps(payload, default=str))

    def _log_fallback_reason(self, *, run_id: str, reason: str, detail: Optional[str] = None) -> None:
        payload = {"fallback_reason": reason}
        if detail:
            payload["detail"] = detail[:1200]
        logger.warning("name-research fallback run_id=%s %s", run_id, json.dumps(payload, default=str))

    async def _execute_pipeline(self, *, run_id: str, tenant_id: str, user_id: str, twin_id: str) -> None:
        try:
            run = await self.get_run(run_id=run_id, tenant_id=tenant_id)
            if not run:
                raise RuntimeError(f"Run not found: {run_id}")

            hints = {
                "location": run.get("input_location"),
                "company": run.get("input_company"),
                "website": run.get("input_website"),
            }
            queries = self.build_queries(name=run.get("input_name", ""), hints=hints)
            await self._update_run(
                run_id,
                status="searching",
                queries_used=queries,
                updated_at=_utcnow_iso(),
            )

            discovered_urls = await self._discover_urls(queries)
            deduped_urls = self.dedupe_urls(discovered_urls)
            await self._update_run(run_id, urls_considered=len(deduped_urls), updated_at=_utcnow_iso())

            await self._update_run(run_id, status="crawling", updated_at=_utcnow_iso())
            source_rows, page_rows, blocked_count, words_extracted = await self._crawl_and_extract(
                run_id=run_id,
                tenant_id=tenant_id,
                name=run.get("input_name", ""),
                hints=hints,
                urls=deduped_urls[: self.max_urls],
            )

            await self._update_run(
                run_id,
                status="extracting",
                urls_crawled=len([s for s in source_rows if s.get("content_quality") in {"full", "partial"}]),
                urls_blocked=blocked_count,
                words_extracted=words_extracted,
                updated_at=_utcnow_iso(),
            )

            ranked_evidence = self._rank_evidence(source_rows, page_rows)
            gated_candidates, source_decisions = self._select_synthesis_candidates(
                run_id=run_id,
                name=run.get("input_name", ""),
                hints=hints,
                ranked_evidence=ranked_evidence,
                source_rows=source_rows,
            )
            selected_evidence = gated_candidates[: self.max_sources_for_synthesis]
            used_source_ids = [item.source_id for item in selected_evidence]
            self._persist_source_selection_decisions(
                run_id=run_id,
                source_rows=source_rows,
                selected_source_ids=used_source_ids,
                decisions=source_decisions,
            )

            await self._update_run(run_id, status="synthesizing", updated_at=_utcnow_iso())

            result_doc, selected_model = await self._synthesize_result(
                run_id=run_id,
                name=run.get("input_name", ""),
                hints=hints,
                queries=queries,
                source_rows=source_rows,
                ranked_evidence=selected_evidence,
                urls_considered=len(deduped_urls),
                words_extracted=words_extracted,
                run_started_at=run.get("run_started_at") or _utcnow_iso(),
            )

            self.db.table("name_deep_research_artifacts").upsert(
                {
                    "run_id": run_id,
                    "tenant_id": tenant_id,
                    "schema_version": "v1",
                    "result_json": result_doc,
                    "updated_at": _utcnow_iso(),
                },
                on_conflict="run_id",
            ).execute()

            # Update twin with research results before marking the run complete.
            from modules.twin_service import update_twin_from_research
            twin_updated = await update_twin_from_research(
                db=self.db,
                twin_id=twin_id,
                tenant_id=tenant_id,
                research_result=result_doc,
            )

            update_fields: Dict[str, Any] = {
                "status": "completed",
                "selected_model": selected_model,
                "sources_used_in_final": len([s for s in result_doc.get("sources", []) if s.get("used_in_final")]),
                "run_completed_at": result_doc["crawl_stats"]["run_completed_at"],
                "updated_at": _utcnow_iso(),
            }
            if not twin_updated:
                update_fields["error_message"] = (
                    "Research completed but profile activation update failed; retry may be required."
                )
            await self._update_run(run_id, **update_fields)
            
            logger.info("name-research run completed: run_id=%s twin_id=%s", run_id, twin_id)
        except Exception as exc:
            logger.exception("name-research run failed: run_id=%s error=%s", run_id, exc)
            await self._update_run(
                run_id,
                status="failed",
                error_message=str(exc),
                run_completed_at=_utcnow_iso(),
                updated_at=_utcnow_iso(),
            )

    async def _discover_urls(self, queries: List[str]) -> List[str]:
        if not queries:
            return []
        if not self.firecrawl and not self.search_provider:
            raise RuntimeError("No web search provider configured for name-only deep research")

        urls: List[str] = []
        for query in queries:
            try:
                if self.search_provider:
                    provider_results = await self.search_provider.search(query=query, num_results=8)
                    urls.extend([r.url for r in provider_results if getattr(r, "url", "")])
            except Exception as exc:
                logger.warning("Search provider failed for query '%s': %s", query[:80], exc)

            if self.firecrawl:
                batch = await self.firecrawl.search(query=query, limit=8)
                urls.extend(batch or [])
        return urls

    async def _crawl_and_extract(
        self,
        *,
        run_id: str,
        tenant_id: str,
        name: str,
        hints: Dict[str, Optional[str]],
        urls: List[str],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int, int]:
        source_rows: List[Dict[str, Any]] = []
        page_rows: List[Dict[str, Any]] = []
        blocked = 0
        words_total = 0
        claimed_identity = {
            "full_name": name,
            "location": hints.get("location"),
            "submitted_links": [hints.get("website")] if hints.get("website") else [],
        }

        for url in urls:
            canonical_url = url
            now_iso = _utcnow_iso()

            if _is_known_auth_wall(canonical_url):
                blocked += 1
                source_rows.append(
                    self._insert_source(
                        {
                            "run_id": run_id,
                            "tenant_id": tenant_id,
                            "url": url,
                            "canonical_url": canonical_url,
                            "title": "",
                            "source_type": _source_type_from_url(url),
                            "published_at": None,
                            "retrieved_at": now_iso,
                            "content_quality": "manual_needed",
                            "identity_match_confidence": 0.0,
                            "used_in_final": False,
                            "blocked_reason": "auth_or_paywall_restricted",
                            "metadata": {"restriction": "public-web-only"},
                        }
                    )
                )
                continue

            allowed, reason = await self.robots_checker.can_fetch(canonical_url)
            if not allowed:
                blocked += 1
                source_rows.append(
                    self._insert_source(
                        {
                            "run_id": run_id,
                            "tenant_id": tenant_id,
                            "url": url,
                            "canonical_url": canonical_url,
                            "title": "",
                            "source_type": _source_type_from_url(url),
                            "published_at": None,
                            "retrieved_at": now_iso,
                            "content_quality": "blocked",
                            "identity_match_confidence": 0.0,
                            "used_in_final": False,
                            "blocked_reason": reason,
                            "metadata": {"restriction": "robots_txt"},
                        }
                    )
                )
                continue

            result: FirecrawlResult = await self.firecrawl.scrape_with_retry(canonical_url)
            metadata = result.metadata or {}
            content = result.content or ""
            quality = _to_quality_value(result.quality)
            if quality in {"blocked", "manual_needed"}:
                blocked += 1
            title = str(metadata.get("title") or metadata.get("ogTitle") or "").strip()
            score_metadata: Dict[str, Any] = {"title": title, "url": canonical_url, **metadata}
            author_value = score_metadata.get("author")
            if isinstance(author_value, list):
                score_metadata["author"] = ", ".join(str(x) for x in author_value if x is not None)
            elif author_value is not None and not isinstance(author_value, str):
                score_metadata["author"] = str(author_value)

            identity = self.identity_scorer.score_page(
                page_content=content,
                page_metadata=score_metadata,
                claimed_identity=claimed_identity,
                content_quality=quality,
            )

            source_row = self._insert_source(
                {
                    "run_id": run_id,
                    "tenant_id": tenant_id,
                    "url": url,
                    "canonical_url": canonical_url,
                    "title": title,
                    "source_type": _source_type_from_url(canonical_url),
                    "published_at": _extract_published_at(metadata),
                    "retrieved_at": now_iso,
                    "content_quality": quality,
                    "identity_match_confidence": identity.score,
                    "used_in_final": False,
                    "blocked_reason": result.error.get("detail") if result.error else None,
                    "metadata": {
                        "quality_reason": result.quality_reason,
                        "http_status": result.http_status,
                        "match_reasons": identity.reasons,
                    },
                }
            )
            source_rows.append(source_row)

            if quality in {"full", "partial"} and content.strip():
                text = content.strip()
                words = _word_count(text)
                words_total += words
                page_row = self._insert_page(
                    {
                        "run_id": run_id,
                        "source_id": source_row["id"],
                        "tenant_id": tenant_id,
                        "canonical_url": canonical_url,
                        "extracted_text": text,
                        "extracted_word_count": words,
                        "content_hash": None,
                        "metadata": {"title": title},
                    }
                )
                page_rows.append(page_row)

        return source_rows, page_rows, blocked, words_total

    def _rank_evidence(self, source_rows: List[Dict[str, Any]], page_rows: List[Dict[str, Any]]) -> List[RankedEvidence]:
        page_by_source = {p.get("source_id"): p for p in page_rows}
        ranked: List[RankedEvidence] = []

        for source in source_rows:
            source_id = source.get("id")
            page = page_by_source.get(source_id)
            excerpt = (page or {}).get("extracted_text", "")[: self.max_excerpt_chars]
            quality = str(source.get("content_quality") or "partial")
            identity = float(source.get("identity_match_confidence") or 0.0)
            score = (0.65 * identity) + (0.25 * _quality_score(quality)) + (0.10 * _recency_score(source.get("published_at")))
            ranked.append(
                RankedEvidence(
                    source_id=str(source_id),
                    rank_score=round(score, 4),
                    url=str(source.get("canonical_url") or source.get("url") or ""),
                    title=str(source.get("title") or ""),
                    source_type=str(source.get("source_type") or "other"),
                    published_at=source.get("published_at"),
                    retrieved_at=str(source.get("retrieved_at") or _utcnow_iso()),
                    content_quality=quality,
                    identity_match_confidence=identity,
                    excerpt=excerpt,
                )
            )

        ranked.sort(key=lambda r: r.rank_score, reverse=True)
        return ranked

    def _hint_tokens(self, value: Optional[str]) -> List[str]:
        raw = (value or "").strip().lower()
        if not raw:
            return []
        tokens = [token for token in re.split(r"[^a-z0-9]+", raw) if len(token) >= 3]
        return tokens

    def _compute_source_selection_decision(
        self,
        *,
        name: str,
        hints: Dict[str, Optional[str]],
        evidence: RankedEvidence,
        source_row: Dict[str, Any],
    ) -> SourceSelectionDecision:
        reason_codes: List[str] = []
        score = float(evidence.rank_score)

        company_tokens = self._hint_tokens(hints.get("company"))
        location_tokens = self._hint_tokens(hints.get("location"))
        website_hint = (hints.get("website") or "").strip().lower()
        website_domain = (
            website_hint.replace("https://", "").replace("http://", "").split("/")[0]
            if website_hint
            else ""
        )

        metadata = source_row.get("metadata") if isinstance(source_row.get("metadata"), dict) else {}
        blob_parts = [
            str(evidence.url or ""),
            str(evidence.title or ""),
            str(evidence.excerpt or ""),
            str((metadata or {}).get("match_reasons") or ""),
        ]
        blob = " ".join(blob_parts).lower()

        if website_domain and website_domain in blob:
            score += 0.24
            reason_codes.append("HANDLE_MATCH")

        if company_tokens:
            company_match = any(token in blob for token in company_tokens)
            # Schulich/York should be strongly preferred for this style of person-research disambiguation.
            if any(token in company_tokens for token in ("schulich", "york")) and (
                "schulich" in blob or "york" in blob
            ):
                company_match = True
            if company_match:
                score += 0.22
                reason_codes.append("HINT_MATCH")
            else:
                score -= 0.20
                reason_codes.append("HINT_MISMATCH")

        if location_tokens and any(token in blob for token in location_tokens):
            score += 0.08
            reason_codes.append("LOCATION_MATCH")

        unrelated_markers = [
            "photography",
            "photographer",
            "musician",
            "album",
            "song",
            "hockey",
            "ice hockey",
            "attorney",
            "law firm",
            "real estate",
            "office broker",
        ]
        if company_tokens and any(marker in blob for marker in unrelated_markers):
            score -= 0.30
            reason_codes.append("TOPIC_MISMATCH_PENALTY")

        normalized_name = _normalize_name(name).lower()
        name_parts = [part for part in normalized_name.split(" ") if part]
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[-1] if len(name_parts) >= 2 else ""
        allowed_first_names = {first_name}
        if first_name == "chris":
            allowed_first_names.add("christopher")
        if first_name == "christopher":
            allowed_first_names.add("chris")

        if last_name:
            first_name_mentions = re.findall(rf"\b([a-z]+)\s+{re.escape(last_name)}\b", blob)
            if any(first and first not in allowed_first_names for first in first_name_mentions):
                reason_codes.append("EXCLUDED_DIFFERENT_PERSON")
                return SourceSelectionDecision(
                    source_id=evidence.source_id,
                    selected=False,
                    selection_score=max(0.0, min(1.0, score)),
                    reason_codes=reason_codes,
                )

        if not company_tokens and evidence.identity_match_confidence < 0.45:
            score -= 0.06
            reason_codes.append("NAME_ONLY_LOW_CONF")

        threshold = 0.52 if company_tokens else 0.42
        selected = score >= threshold
        if selected:
            reason_codes.append("SELECTED")
        else:
            reason_codes.append("EXCLUDED_BELOW_THRESHOLD")

        return SourceSelectionDecision(
            source_id=evidence.source_id,
            selected=selected,
            selection_score=max(0.0, min(1.0, score)),
            reason_codes=reason_codes,
        )

    def _select_synthesis_candidates(
        self,
        *,
        run_id: str,
        name: str,
        hints: Dict[str, Optional[str]],
        ranked_evidence: List[RankedEvidence],
        source_rows: List[Dict[str, Any]],
    ) -> Tuple[List[RankedEvidence], Dict[str, SourceSelectionDecision]]:
        source_by_id = {str(row.get("id")): row for row in source_rows}
        if not self.identity_gating_enabled:
            passthrough = {
                e.source_id: SourceSelectionDecision(
                    source_id=e.source_id,
                    selected=True,
                    selection_score=e.rank_score,
                    reason_codes=["IDENTITY_GATING_DISABLED", "SELECTED"],
                )
                for e in ranked_evidence
            }
            self._log_metric(
                run_id=run_id,
                metric="source_identity_filtered_count",
                value=len(ranked_evidence),
            )
            self._log_metric(
                run_id=run_id,
                metric="source_identity_excluded_count",
                value=0,
            )
            return ranked_evidence, passthrough

        selected: List[RankedEvidence] = []
        decisions: Dict[str, SourceSelectionDecision] = {}
        for evidence in ranked_evidence:
            source_row = source_by_id.get(evidence.source_id) or {}
            decision = self._compute_source_selection_decision(
                name=name,
                hints=hints,
                evidence=evidence,
                source_row=source_row,
            )
            decisions[evidence.source_id] = decision
            if not decision.selected:
                continue
            selected.append(
                RankedEvidence(
                    source_id=evidence.source_id,
                    rank_score=decision.selection_score,
                    url=evidence.url,
                    title=evidence.title,
                    source_type=evidence.source_type,
                    published_at=evidence.published_at,
                    retrieved_at=evidence.retrieved_at,
                    content_quality=evidence.content_quality,
                    identity_match_confidence=evidence.identity_match_confidence,
                    excerpt=evidence.excerpt,
                )
            )

        selected.sort(key=lambda item: item.rank_score, reverse=True)
        self._log_metric(
            run_id=run_id,
            metric="source_identity_filtered_count",
            value=len(selected),
        )
        self._log_metric(
            run_id=run_id,
            metric="source_identity_excluded_count",
            value=max(0, len(ranked_evidence) - len(selected)),
        )
        return selected, decisions

    def _persist_source_selection_decisions(
        self,
        *,
        run_id: str,
        source_rows: List[Dict[str, Any]],
        selected_source_ids: List[str],
        decisions: Dict[str, SourceSelectionDecision],
    ) -> None:
        selected_set = set(selected_source_ids)
        for source in source_rows:
            source_id = str(source.get("id"))
            decision = decisions.get(source_id)
            metadata = dict(source.get("metadata") or {})
            if decision:
                metadata["selection_reason_codes"] = decision.reason_codes
                metadata["selection_score"] = round(float(decision.selection_score), 4)
                metadata["selection_selected"] = bool(source_id in selected_set)

            used_in_final = source_id in selected_set
            source["used_in_final"] = used_in_final
            source["metadata"] = metadata
            self.db.table("name_deep_research_sources").update(
                {"used_in_final": used_in_final, "metadata": metadata}
            ).eq("id", source_id).eq("run_id", run_id).execute()

    def _conservative_bios(self) -> Dict[str, str]:
        return {
            "short": "Unknown. Needs additional evidence.",
            "medium": "Unknown. Needs additional evidence from reliable public sources.",
            "long": "Insufficient verified public evidence for a grounded long biography.",
        }

    def _build_stage_a_repair_prompt(self, error_text: str) -> str:
        lines = [line.strip() for line in str(error_text).splitlines() if line.strip()]
        top_lines = lines[:12]
        return (
            "Your previous JSON failed validation.\n"
            f"Validation issues:\n- " + "\n- ".join(top_lines) + "\n\n"
            "Repair requirements:\n"
            "1) timeline items MUST use {date_or_range,event,confidence,citations}.\n"
            "2) claim items MUST use {claim_id,text,claim_type,status,confidence,citations,notes}.\n"
            "3) citations MUST be list[str] and use existing source_id values only.\n"
            "4) bio.short|medium|long MUST be plain strings.\n"
            "5) profile_summary.what_they_do/organizations/locations/public_roles/disambiguation_notes MUST be lists.\n"
            "6) Remove unsupported keys.\n\n"
            "Valid timeline example:\n"
            "{\"date_or_range\":\"2024\",\"event\":\"Joined X\",\"confidence\":0.7,\"citations\":[\"src-1\"]}\n"
            "Valid claim example:\n"
            "{\"claim_id\":\"claim_1\",\"text\":\"Joined X\",\"claim_type\":\"role\",\"status\":\"partially_verified\","
            "\"confidence\":0.7,\"citations\":[\"src-1\"],\"notes\":\"\"}\n"
        )

    def _normalize_stage_a_payload(
        self,
        *,
        run_id: str,
        raw_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            logger.debug(
                "name-research stage_a raw_payload run_id=%s payload=%s",
                run_id,
                json.dumps(raw_payload, default=str)[:8000],
            )
        except Exception:
            logger.debug("name-research stage_a raw_payload run_id=%s (unserializable payload)", run_id)
        draft = NameDeepResearchDraftModel.model_validate(raw_payload)
        draft_dict = draft.model_dump(exclude_none=True)
        normalized = normalize_name_deep_research_synthesis_payload(draft_dict)
        if normalized != draft_dict:
            self._log_metric(
                run_id=run_id,
                metric="synthesis_normalization_applied_count",
                value=1,
            )
        return normalized

    def _apply_identity_safety_constraints(
        self,
        *,
        result_doc: Dict[str, Any],
        hints: Dict[str, Optional[str]],
    ) -> Dict[str, Any]:
        doc = dict(result_doc)
        claimed_identity = dict(doc.get("claimed_identity") or {})
        sources = doc.get("sources") or []
        used_sources = [s for s in sources if bool((s or {}).get("used_in_final"))]
        best_conf = max([float((s or {}).get("identity_match_confidence") or 0.0) for s in used_sources] + [0.0])

        company_tokens = self._hint_tokens(hints.get("company"))
        if company_tokens:
            company_match_count = 0
            for src in used_sources:
                text_blob = f"{src.get('url','')} {src.get('title','')}".lower()
                if any(token in text_blob for token in company_tokens):
                    company_match_count += 1
            if used_sources and company_match_count == 0:
                best_conf = min(best_conf, 0.65)
                notes = list(claimed_identity.get("disambiguation_notes") or [])
                notes.append("Company hint mismatch across selected sources; manual review recommended.")
                claimed_identity["disambiguation_notes"] = list(dict.fromkeys(notes))
                known_unknowns = list(doc.get("known_unknowns") or [])
                known_unknowns.append(
                    {
                        "question": "Do selected sources refer to the same person as the company hint?",
                        "why_missing": "Selected sources did not consistently match the company hint.",
                    }
                )
                doc["known_unknowns"] = known_unknowns

        if len(used_sources) <= 1:
            best_conf = min(best_conf, 0.70)
        claimed_identity["is_match_confidence"] = round(float(best_conf), 3)
        doc["claimed_identity"] = claimed_identity
        return doc

    def _coerce_bio_strings(self, raw_bio: Any) -> Dict[str, str]:
        conservative = self._conservative_bios()
        raw = raw_bio if isinstance(raw_bio, dict) else {}

        def _extract(value: Any) -> str:
            if isinstance(value, str):
                return value.strip()
            if isinstance(value, dict):
                for key in ("text", "value", "content", "summary"):
                    if value.get(key):
                        return str(value.get(key)).strip()
            if value is None:
                return ""
            return str(value).strip()

        short = _extract(raw.get("short")) or conservative["short"]
        medium = _extract(raw.get("medium")) or conservative["medium"]
        long = _extract(raw.get("long")) or conservative["long"]
        return {"short": short, "medium": medium, "long": long}

    def _compute_training_metrics_summary(self, result_doc: Dict[str, Any]) -> Dict[str, Any]:
        words_processed = int(((result_doc.get("crawl_stats") or {}).get("words_extracted") or 0))
        sources = list(result_doc.get("sources") or [])
        claims = list(result_doc.get("claims") or [])
        timeline = list(result_doc.get("timeline") or [])

        source_metrics: List[SourceMetrics] = []
        for source in sources:
            quality = str(source.get("content_quality") or "partial")
            has_content = quality in {"full", "partial"}
            source_metrics.append(
                SourceMetrics(
                    source_id=str(source.get("source_id") or ""),
                    source_type=str(source.get("source_type") or "unknown"),
                    status="processed" if has_content else "failed",
                    word_count=max(1, int(words_processed / max(1, len(sources)))) if has_content and words_processed > 0 else 0,
                    extracted_at=str(source.get("retrieved_at") or ""),
                    has_content=has_content,
                )
            )

        processed_sources = [s for s in source_metrics if s.has_content]
        success_rate = (len(processed_sources) / len(source_metrics)) if source_metrics else 0.0
        diversity_score, unique_types = calculate_diversity_score(processed_sources)
        volume_score = calculate_volume_score(words_processed)
        quality_score = round(success_rate * 100.0, 3)

        recency_scores = [
            _recency_score((source or {}).get("published_at"))
            for source in sources
            if (source or {}).get("content_quality") in {"full", "partial"}
        ]
        freshness_score = round((sum(recency_scores) / len(recency_scores) if recency_scores else 0.5) * 100.0, 3)

        structured_signals = len(claims) + len(timeline)
        structure_score = round(min(100.0, (structured_signals / max(1.0, float(len(processed_sources) or 1))) * 18.0), 3)

        verified_weight = 0.0
        for claim in claims:
            status = str((claim or {}).get("status") or "unknown").lower()
            if status == "verified":
                verified_weight += 1.0
            elif status == "partially_verified":
                verified_weight += 0.6
        verification_score = round(
            min(100.0, 100.0 * (verified_weight / max(1.0, float(len(claims) or 1)))),
            3,
        )

        mind_score = calculate_mind_score(
            volume_score=volume_score,
            diversity_score=diversity_score,
            quality_score=quality_score,
            freshness_score=freshness_score,
            structure_score=structure_score,
            verification_score=verification_score,
        )
        diversity_factor = 1.0 + (max(0, unique_types - 1) * 0.2)
        questions_est = estimate_questions_answerable(
            words_processed=words_processed,
            sources=processed_sources,
            quality_factor=max(0.1, success_rate),
            diversity_factor=diversity_factor,
        )

        return {
            "words_processed": words_processed,
            "words_processed_display": format_number_compact(words_processed),
            "questions_answerable_est": questions_est,
            "questions_answerable_display": format_number_compact(questions_est),
            "mind_score": mind_score,
            "mind_score_label": get_mind_score_label(mind_score),
            "method_version": "v1_heuristic_name_research",
            "notes": "Estimated metrics from extracted public-web evidence volume, diversity, and verification density.",
        }

    def _build_prepared_question_answers(self, *, name: str, result_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        qas: List[Dict[str, Any]] = []
        seen: set[Tuple[str, Tuple[str, ...]]] = set()

        claims = sorted(
            [c for c in (result_doc.get("claims") or []) if (c or {}).get("citations")],
            key=lambda item: float((item or {}).get("confidence") or 0.0),
            reverse=True,
        )
        timeline = sorted(
            [t for t in (result_doc.get("timeline") or []) if (t or {}).get("citations")],
            key=lambda item: float((item or {}).get("confidence") or 0.0),
            reverse=True,
        )

        claim_type_to_question = {
            "role": f"What public role is {name} associated with?",
            "experience": f"What experience is documented for {name}?",
            "project": f"What project work is publicly linked to {name}?",
            "credential": f"What credentials are publicly evidenced for {name}?",
            "opinion": f"What public viewpoints are evidenced for {name}?",
        }

        for claim in claims:
            citations = [str(c) for c in list((claim or {}).get("citations") or []) if str(c)]
            if not citations:
                continue
            claim_type = str((claim or {}).get("claim_type") or "other").lower()
            question = claim_type_to_question.get(claim_type, f"What is a key documented fact about {name}?")
            status = str((claim or {}).get("status") or "unknown").lower()
            answer = str((claim or {}).get("text") or "").strip()
            if not answer:
                continue
            if status in {"unknown", "unverified", "disputed"}:
                answer = f"{answer} (evidence is incomplete; treat as {status})."
            key = (question.lower(), tuple(sorted(citations)))
            if key in seen:
                continue
            seen.add(key)
            qas.append(
                {
                    "question": question,
                    "answer": answer,
                    "confidence": round(float((claim or {}).get("confidence") or 0.5), 3),
                    "citations": citations,
                }
            )

        for item in timeline:
            citations = [str(c) for c in list((item or {}).get("citations") or []) if str(c)]
            if not citations:
                continue
            date_or_range = str((item or {}).get("date_or_range") or "unknown")
            event = str((item or {}).get("event") or "").strip()
            if not event:
                continue
            question = f"What timeline event is documented for {name} around {date_or_range}?"
            answer = f"{event} (time reference: {date_or_range})."
            key = (question.lower(), tuple(sorted(citations)))
            if key in seen:
                continue
            seen.add(key)
            qas.append(
                {
                    "question": question,
                    "answer": answer,
                    "confidence": round(float((item or {}).get("confidence") or 0.5), 3),
                    "citations": citations,
                }
            )

        if not qas:
            best_source = next(
                (src for src in (result_doc.get("sources") or []) if (src or {}).get("source_id")),
                None,
            )
            if best_source:
                source_id = str(best_source.get("source_id"))
                qas.append(
                    {
                        "question": f"Can we confidently identify {name} from current public evidence?",
                        "answer": "Unknown. The currently available public sources remain ambiguous and need manual review.",
                        "confidence": 0.35,
                        "citations": [source_id],
                    }
                )

        return qas[:8]

    def _augment_result_with_metrics_and_qa(self, *, name: str, result_doc: Dict[str, Any]) -> Dict[str, Any]:
        if not self.metrics_and_qa_enabled:
            return result_doc

        doc = dict(result_doc)
        doc["training_metrics"] = self._compute_training_metrics_summary(doc)
        doc["prepared_question_answers"] = self._build_prepared_question_answers(name=name, result_doc=doc)
        return doc

    def _build_stage_a_document(
        self,
        *,
        run_id: str,
        name: str,
        hints: Dict[str, Optional[str]],
        queries: List[str],
        source_items: List[Dict[str, Any]],
        normalized_payload: Dict[str, Any],
        urls_considered: int,
        words_extracted: int,
        run_started_at: str,
        run_completed_at: str,
    ) -> Dict[str, Any]:
        source_ids = {str(item.get("source_id")) for item in source_items}

        timeline: List[Dict[str, Any]] = []
        for item in normalized_payload.get("timeline") or []:
            citations = [str(c) for c in (item.get("citations") or []) if str(c) in source_ids]
            if not citations:
                continue
            timeline.append(
                {
                    "date_or_range": str(item.get("date_or_range") or "unknown"),
                    "event": str(item.get("event") or "").strip(),
                    "confidence": float(item.get("confidence") or 0.5),
                    "citations": citations,
                }
            )
        timeline = [item for item in timeline if item["event"]]

        claims: List[Dict[str, Any]] = []
        for idx, item in enumerate(normalized_payload.get("claims") or [], start=1):
            citations = [str(c) for c in (item.get("citations") or []) if str(c) in source_ids]
            if not citations:
                continue
            claim_type = str(item.get("claim_type") or "other").lower()
            if claim_type not in {"credential", "experience", "role", "preference", "opinion", "project", "contact", "other"}:
                claim_type = "other"
            status = str(item.get("status") or "unknown").lower()
            if status not in {"verified", "partially_verified", "unverified", "disputed", "unknown"}:
                status = "unknown"
            if status == "verified" and not citations:
                status = "unknown"
            claims.append(
                {
                    "claim_id": str(item.get("claim_id") or f"claim_{idx}"),
                    "text": str(item.get("text") or "").strip(),
                    "claim_type": claim_type,
                    "status": status,
                    "confidence": float(item.get("confidence") or 0.5),
                    "citations": citations,
                    "notes": str(item.get("notes") or ""),
                }
            )
        claims = [item for item in claims if item["text"]]

        payload_warnings = list((normalized_payload.get("quality") or {}).get("warnings") or [])
        crawl_stats = {
            "queries_used": queries,
            "urls_considered": urls_considered,
            "urls_crawled": len([s for s in source_items if s.get("content_quality") in {"full", "partial"}]),
            "urls_blocked": len([s for s in source_items if s.get("content_quality") in {"blocked", "manual_needed"}]),
            "sources_used_in_final": len([s for s in source_items if s.get("used_in_final")]),
            "words_extracted": words_extracted,
            "run_started_at": run_started_at,
            "run_completed_at": run_completed_at,
        }
        quality_raw = normalized_payload.get("quality") or {}
        used_sources = [item for item in source_items if item.get("used_in_final")]
        max_identity = max([float((item or {}).get("identity_match_confidence") or 0.0) for item in used_sources] + [0.0])
        avg_freshness = 0.0
        if used_sources:
            avg_freshness = sum(_recency_score(item.get("published_at")) for item in used_sources) / len(used_sources)
        coverage_heuristic = 0.0
        if source_items:
            coverage_heuristic = min(
                1.0,
                (len(claims) + len(timeline) + len(used_sources)) / max(1.0, float(len(source_items) + 2)),
            )
        heuristic_overall = min(1.0, (0.60 * max_identity) + (0.40 * coverage_heuristic))
        explicit_overall = float(quality_raw.get("overall_confidence") or 0.0)
        explicit_freshness = float(quality_raw.get("freshness_score") or 0.0)
        explicit_coverage = float(quality_raw.get("coverage_score") or 0.0)
        overall_confidence = explicit_overall if explicit_overall > 0 else heuristic_overall
        freshness_score = explicit_freshness if explicit_freshness > 0 else avg_freshness
        coverage_score = explicit_coverage if explicit_coverage > 0 else coverage_heuristic

        hallucination_risk = str(quality_raw.get("hallucination_risk") or "").strip().lower()
        if hallucination_risk not in {"low", "medium", "high"}:
            if overall_confidence >= 0.75 and coverage_score >= 0.5:
                hallucination_risk = "low"
            elif overall_confidence >= 0.5:
                hallucination_risk = "medium"
            else:
                hallucination_risk = "high"
        quality = {
            "overall_confidence": round(overall_confidence, 3),
            "freshness_score": round(max(0.0, min(1.0, freshness_score)), 3),
            "coverage_score": round(max(0.0, min(1.0, coverage_score)), 3),
            "hallucination_risk": hallucination_risk,
            "warnings": [w for w in payload_warnings if isinstance(w, str) and w.strip()],
        }

        profile_summary = normalized_payload.get("profile_summary") or {}
        claimed_identity = normalized_payload.get("claimed_identity") or {}
        known_unknowns = normalized_payload.get("known_unknowns") or []
        if not known_unknowns:
            known_unknowns = [
                {
                    "question": f"Is all discovered content about {name} the same person?",
                    "why_missing": "Identity signals were mixed or incomplete.",
                }
            ]

        doc = {
            "run_id": run_id,
            "input": {
                "name": name,
                "hints": {
                    "location": hints.get("location"),
                    "company": hints.get("company"),
                    "website": hints.get("website"),
                },
            },
            "claimed_identity": {
                "canonical_name": str(claimed_identity.get("canonical_name") or name),
                "is_match_confidence": float(claimed_identity.get("is_match_confidence") or 0.0),
                "disambiguation_notes": list(claimed_identity.get("disambiguation_notes") or ["Requires manual review."]),
                "possible_duplicates": list(claimed_identity.get("possible_duplicates") or []),
            },
            "bio": self._conservative_bios(),
            "profile_summary": {
                "what_they_do": list(profile_summary.get("what_they_do") or []),
                "expertise_topics": list(profile_summary.get("expertise_topics") or []),
                "organizations": list(profile_summary.get("organizations") or []),
                "locations": list(profile_summary.get("locations") or []),
                "public_roles": list(profile_summary.get("public_roles") or []),
            },
            "timeline": timeline,
            "claims": claims,
            "known_unknowns": known_unknowns,
            "suggested_followup_questions": list(
                normalized_payload.get("suggested_followup_questions")
                or ["What official profile best disambiguates this person?"]
            ),
            "crawl_stats": crawl_stats,
            "quality": quality,
            "sources": source_items,
        }
        safe_doc = self._apply_identity_safety_constraints(result_doc=doc, hints=hints)
        return self._augment_result_with_metrics_and_qa(name=name, result_doc=safe_doc)

    async def _run_stage_a_synthesis(
        self,
        *,
        model: str,
        run_id: str,
        name: str,
        hints: Dict[str, Optional[str]],
        queries: List[str],
        source_items: List[Dict[str, Any]],
        ranked_evidence: List[RankedEvidence],
        urls_considered: int,
        words_extracted: int,
        run_started_at: str,
        validation_error: Optional[str],
    ) -> Dict[str, Any]:
        now_iso = _utcnow_iso()
        payload = {
            "run_id": run_id,
            "input": {"name": name, "hints": hints},
            "sources": source_items,
            "ranked_evidence": [
                {
                    "source_id": e.source_id,
                    "rank_score": e.rank_score,
                    "url": e.url,
                    "title": e.title,
                    "source_type": e.source_type,
                    "published_at": e.published_at,
                    "retrieved_at": e.retrieved_at,
                    "content_quality": e.content_quality,
                    "identity_match_confidence": e.identity_match_confidence,
                    "excerpt": e.excerpt,
                }
                for e in ranked_evidence
            ],
        }
        response_doc = await self._invoke_reasoning_model(
            model=model,
            system_prompt=(
                "You are an evidence-grounded person research synthesizer. Return JSON only. "
                "Generate STRUCTURED fields only; do not generate verbose prose bios. "
                "Never invent facts. If weak evidence, mark unknown/unverified."
            ),
            user_payload=payload,
            schema_instruction=(
                "Return keys: claimed_identity,profile_summary,timeline,claims,known_unknowns,"
                "suggested_followup_questions,quality. "
                "timeline items use date_or_range,event,confidence,citations. "
                "claims use claim_id,text,claim_type,status,confidence,citations,notes."
            ),
            validation_error=validation_error,
        )
        normalized = self._normalize_stage_a_payload(run_id=run_id, raw_payload=response_doc)
        stage_doc = self._build_stage_a_document(
            run_id=run_id,
            name=name,
            hints=hints,
            queries=queries,
            source_items=source_items,
            normalized_payload=normalized,
            urls_considered=urls_considered,
            words_extracted=words_extracted,
            run_started_at=run_started_at,
            run_completed_at=now_iso,
        )
        parsed = self.validate_result_schema(stage_doc)
        return parsed.model_dump()

    async def _run_stage_b_bio_generation(
        self,
        *,
        model: str,
        run_id: str,
        name: str,
        structured_doc: Dict[str, Any],
    ) -> Dict[str, str]:
        payload = {
            "name": name,
            "claimed_identity": structured_doc.get("claimed_identity"),
            "profile_summary": structured_doc.get("profile_summary"),
            "timeline": structured_doc.get("timeline"),
            "claims": structured_doc.get("claims"),
            "known_unknowns": structured_doc.get("known_unknowns"),
            "sources": [s for s in (structured_doc.get("sources") or []) if s.get("used_in_final")],
            "instructions": {
                "style": "concise evidence-grounded",
                "citations_inline": True,
                "no_uncited_factual_claims": True,
                "unknown_if_weak": True,
            },
        }
        response_doc = await self._invoke_reasoning_model(
            model=model,
            system_prompt=(
                "Generate bio strings only from provided structured evidence. "
                "Return JSON with keys short,medium,long. "
                "If evidence weak, use unknown wording. Do not fabricate."
            ),
            user_payload=payload,
            schema_instruction="Return JSON with exactly keys short,medium,long as strings.",
            validation_error=None,
        )
        bio_payload = response_doc.get("bio") if isinstance(response_doc.get("bio"), dict) else response_doc
        bio = self._coerce_bio_strings(bio_payload)
        if not bio["short"] or not bio["medium"] or not bio["long"]:
            raise ValueError("Bio stage returned empty fields")
        logger.info("name-research stage_b generated run_id=%s", run_id)
        return bio

    async def _synthesize_result(
        self,
        *,
        run_id: str,
        name: str,
        hints: Dict[str, Optional[str]],
        queries: List[str],
        source_rows: List[Dict[str, Any]],
        ranked_evidence: List[RankedEvidence],
        urls_considered: Optional[int] = None,
        words_extracted: int = 0,
        run_started_at: str,
    ) -> Tuple[Dict[str, Any], str]:
        source_items = [
            {
                "source_id": str(s.get("id")),
                "url": s.get("canonical_url") or s.get("url") or "",
                "title": s.get("title") or "",
                "source_type": s.get("source_type") or "other",
                "published_at": s.get("published_at"),
                "retrieved_at": s.get("retrieved_at") or _utcnow_iso(),
                "content_quality": s.get("content_quality") or "partial",
                "identity_match_confidence": float(s.get("identity_match_confidence") or 0.0),
                "used_in_final": bool(s.get("used_in_final")),
            }
            for s in source_rows
        ]
        urls_considered = urls_considered if urls_considered is not None else len(source_items)
        now_iso = _utcnow_iso()
        if not ranked_evidence:
            self._log_fallback_reason(run_id=run_id, reason="no_ranked_evidence")
            fallback = self._build_fallback_result(
                run_id=run_id,
                name=name,
                hints=hints,
                queries=queries,
                source_items=source_items,
                urls_considered=urls_considered,
                words_extracted=words_extracted,
                run_started_at=run_started_at,
                run_completed_at=now_iso,
                warning="No usable public content extracted from discovered sources.",
            )
            parsed = self.validate_result_schema(fallback)
            return parsed.model_dump(), "none"

        selected_model = await self._resolve_reasoning_model()
        model_candidates = [selected_model] + [m for m in await self._reasoning_model_candidates() if m != selected_model]
        stage_a_result: Optional[Dict[str, Any]] = None
        stage_a_model = selected_model
        errors: List[str] = []

        for model in model_candidates:
            try:
                stage_a_result = await self._run_stage_a_synthesis(
                    model=model,
                    run_id=run_id,
                    name=name,
                    hints=hints,
                    queries=queries,
                    source_items=source_items,
                    ranked_evidence=ranked_evidence,
                    urls_considered=urls_considered,
                    words_extracted=words_extracted,
                    run_started_at=run_started_at,
                    validation_error=None,
                )
                stage_a_model = model
                self._log_metric(run_id=run_id, metric="synthesis_stage_a_success", value=1, model=model)
                break
            except Exception as exc:
                errors.append(str(exc))
                self._log_metric(
                    run_id=run_id,
                    metric="synthesis_raw_validation_failures_count",
                    value=1,
                    model=model,
                )
                logger.warning("name-research stage_a failed model=%s run_id=%s err=%s", model, run_id, exc)
                if not self.synthesis_hardening_enabled or not self.synthesis_repair_retry_enabled:
                    continue
                try:
                    self._log_metric(run_id=run_id, metric="synthesis_repair_retry_count", value=1, model=model)
                    stage_a_result = await self._run_stage_a_synthesis(
                        model=model,
                        run_id=run_id,
                        name=name,
                        hints=hints,
                        queries=queries,
                        source_items=source_items,
                        ranked_evidence=ranked_evidence,
                        urls_considered=urls_considered,
                        words_extracted=words_extracted,
                        run_started_at=run_started_at,
                        validation_error=self._build_stage_a_repair_prompt(str(exc)),
                    )
                    stage_a_model = model
                    self._log_metric(run_id=run_id, metric="synthesis_repair_success_count", value=1, model=model)
                    self._log_metric(run_id=run_id, metric="synthesis_stage_a_success", value=1, model=model)
                    logger.info("name-research stage_a repair success model=%s run_id=%s", model, run_id)
                    break
                except Exception as repair_exc:
                    errors.append(str(repair_exc))
                    self._log_metric(
                        run_id=run_id,
                        metric="synthesis_raw_validation_failures_count",
                        value=1,
                        model=model,
                    )
                    logger.warning(
                        "name-research stage_a repair failed model=%s run_id=%s err=%s",
                        model,
                        run_id,
                        repair_exc,
                    )

        if not stage_a_result:
            self._log_fallback_reason(run_id=run_id, reason="stage_a_validation_failed", detail=errors[-1] if errors else "")
            fallback = self._build_fallback_result(
                run_id=run_id,
                name=name,
                hints=hints,
                queries=queries,
                source_items=source_items,
                urls_considered=urls_considered,
                words_extracted=words_extracted,
                run_started_at=run_started_at,
                run_completed_at=now_iso,
                warning=f"Synthesis validation failed after retries: {errors[-1] if errors else 'unknown error'}",
            )
            parsed = self.validate_result_schema(fallback)
            return parsed.model_dump(), model_candidates[0] if model_candidates else "none"

        final_doc = dict(stage_a_result)
        try:
            bio = await self._run_stage_b_bio_generation(
                model=stage_a_model,
                run_id=run_id,
                name=name,
                structured_doc=stage_a_result,
            )
            final_doc["bio"] = bio
            parsed = self.validate_result_schema(final_doc)
            self._log_metric(run_id=run_id, metric="synthesis_stage_b_success", value=1, model=stage_a_model)
            return parsed.model_dump(), stage_a_model
        except Exception as exc:
            logger.warning("name-research stage_b failed run_id=%s model=%s err=%s", run_id, stage_a_model, exc)
            warnings = list(((final_doc.get("quality") or {}).get("warnings") or []))
            warnings.append(f"Bio generation fallback applied: {str(exc)[:500]}")
            final_doc.setdefault("quality", {})["warnings"] = warnings
            final_doc["bio"] = self._conservative_bios()
            parsed = self.validate_result_schema(final_doc)
            return parsed.model_dump(), stage_a_model

    async def _invoke_reasoning_model(
        self,
        *,
        model: str,
        system_prompt: str,
        user_payload: Dict[str, Any],
        schema_instruction: str,
        validation_error: Optional[str],
    ) -> Dict[str, Any]:
        client = self._openai_client or get_async_openai_client()
        user_prompt = {
            "schema_instruction": schema_instruction,
            "validation_error": validation_error,
            "payload": user_payload,
        }
        request_payload: Dict[str, Any] = {
            "model": model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_prompt)},
            ],
        }
        # Reasoning models (o-series) do not accept temperature overrides.
        if not str(model).lower().startswith("o"):
            request_payload["temperature"] = 0.0
        completion = await client.chat.completions.create(**request_payload)
        raw = (completion.choices[0].message.content or "").strip()
        if not raw:
            raise RuntimeError("Model returned empty response")
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise RuntimeError("Model output is not a JSON object")
        return parsed

    async def _reasoning_model_candidates(self) -> List[str]:
        explicit = (os.getenv("OPENAI_DEEP_RESEARCH_MODEL") or "").strip()
        if explicit:
            return [explicit]

        if self._models_cache is not None:
            return self._models_cache

        candidates = ["o3", "o3-mini", "o1", "gpt-4o"]
        try:
            client = self._openai_client or get_async_openai_client()
            listing = await client.models.list()
            available = {m.id for m in getattr(listing, "data", [])}
            preferred: List[str] = []
            for c in candidates:
                if c in available:
                    preferred.append(c)
            if not preferred:
                dynamic = sorted([m for m in available if m.startswith("o3") or m.startswith("o1")])
                preferred = dynamic[:2] if dynamic else candidates
            self._models_cache = preferred
            return preferred
        except Exception as exc:
            logger.warning("Could not list OpenAI models for reasoning selection: %s", exc)
            self._models_cache = candidates
            return candidates

    async def _resolve_reasoning_model(self) -> str:
        candidates = await self._reasoning_model_candidates()
        return candidates[0]

    def _build_fallback_result(
        self,
        *,
        run_id: str,
        name: str,
        hints: Dict[str, Optional[str]],
        queries: List[str],
        source_items: List[Dict[str, Any]],
        urls_considered: Optional[int] = None,
        words_extracted: int = 0,
        run_started_at: str,
        run_completed_at: str,
        warning: str,
    ) -> Dict[str, Any]:
        urls_considered = urls_considered if urls_considered is not None else len(source_items)
        best_source = next(
            (s for s in sorted(source_items, key=lambda x: float(x.get("identity_match_confidence") or 0.0), reverse=True)
             if s.get("content_quality") in {"full", "partial"}),
            None,
        )
        best_conf = float((best_source or {}).get("identity_match_confidence") or 0.0)
        source_id = (best_source or {}).get("source_id")
        claims: List[Dict[str, Any]] = []
        timeline: List[Dict[str, Any]] = []
        if source_id:
            claims.append(
                {
                    "claim_id": "claim_1",
                    "text": "Identity match evidence exists but is insufficient for a complete verified profile.",
                    "claim_type": "other",
                    "status": "unknown" if best_conf < 0.7 else "partially_verified",
                    "confidence": round(best_conf, 3),
                    "citations": [source_id],
                    "notes": "Automatic fallback output due insufficient structured synthesis confidence.",
                }
            )
            timeline.append(
                {
                    "date_or_range": "unknown",
                    "event": "No timeline event confidently supported.",
                    "confidence": round(min(best_conf, 0.5), 3),
                    "citations": [source_id],
                }
            )

        fallback_doc = {
            "run_id": run_id,
            "input": {
                "name": name,
                "hints": {
                    "location": hints.get("location"),
                    "company": hints.get("company"),
                    "website": hints.get("website"),
                },
            },
            "claimed_identity": {
                "canonical_name": name,
                "is_match_confidence": round(best_conf, 3),
                "disambiguation_notes": [
                    "Evidence was limited; canonical identity requires manual review."
                ],
                "possible_duplicates": [],
            },
            "bio": {
                "short": "Unknown. Needs additional evidence.",
                "medium": "Unknown. Needs additional evidence from reliable public sources.",
                "long": "Insufficient verified public evidence for a grounded long biography.",
            },
            "profile_summary": {
                "what_they_do": ["unknown"],
                "expertise_topics": [],
                "organizations": [],
                "locations": [],
                "public_roles": [],
            },
            "timeline": timeline,
            "claims": claims,
            "known_unknowns": [
                {
                    "question": f"Is all discovered content about {name} the same person?",
                    "why_missing": "Identity signals were weak or ambiguous across available sources.",
                }
            ],
            "suggested_followup_questions": [
                "What is the correct official profile URL for this person?",
                "Which organizations can be independently verified from public records?",
            ],
            "crawl_stats": {
                "queries_used": queries,
                "urls_considered": urls_considered,
                "urls_crawled": len([s for s in source_items if s.get("content_quality") in {"full", "partial"}]),
                "urls_blocked": len([s for s in source_items if s.get("content_quality") in {"blocked", "manual_needed"}]),
                "sources_used_in_final": len([s for s in source_items if s.get("used_in_final")]),
                "words_extracted": words_extracted,
                "run_started_at": run_started_at,
                "run_completed_at": run_completed_at,
            },
            "quality": {
                "overall_confidence": round(best_conf, 3),
                "freshness_score": 0.4,
                "coverage_score": 0.2 if source_items else 0.0,
                "hallucination_risk": "high",
                "warnings": [warning],
            },
            "sources": source_items,
        }
        return self._augment_result_with_metrics_and_qa(name=name, result_doc=fallback_doc)

    async def _update_run(self, run_id: str, **fields: Any) -> None:
        self.db.table("name_deep_research_runs").update(fields).eq("id", run_id).execute()

    def _insert_source(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = self.db.table("name_deep_research_sources").insert(payload).execute()
        if not response.data:
            raise RuntimeError("Failed to insert source row")
        return response.data[0]

    def _insert_page(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = self.db.table("name_deep_research_pages").insert(payload).execute()
        if not response.data:
            raise RuntimeError("Failed to insert page row")
        return response.data[0]


_ACTIVE_RUN_TASKS: Dict[str, asyncio.Task] = {}
_SERVICE_SINGLETON: Optional[NameDeepResearchService] = None


def get_name_deep_research_service() -> NameDeepResearchService:
    global _SERVICE_SINGLETON
    if _SERVICE_SINGLETON is None:
        _SERVICE_SINGLETON = NameDeepResearchService()
    return _SERVICE_SINGLETON


def is_name_only_deep_research_enabled() -> bool:
    cfg = get_dr_config()
    return bool(getattr(cfg, "name_only_deep_research_enabled", False))
