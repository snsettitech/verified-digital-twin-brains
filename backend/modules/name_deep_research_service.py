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
from modules.observability import supabase
from modules.robots_checker import RobotsChecker
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
        self._models_cache: Optional[List[str]] = None

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
                return existing.data[0]

        created = (
            self.db.table("name_deep_research_runs")
            .insert(
                {
                    "tenant_id": tenant_id,
                    "created_by": user_id,
                    "status": "created",
                    "input_name": normalized_name,
                    "input_location": (hints.get("location") or None),
                    "input_company": (hints.get("company") or None),
                    "input_website": (hints.get("website") or None),
                    "idempotency_key": idempotency_key,
                    "run_started_at": _utcnow_iso(),
                }
            )
            .execute()
        )
        if not created.data:
            raise RuntimeError("Failed to create deep research run")

        run_row = created.data[0]
        run_id = run_row["id"]

        task = asyncio.create_task(self._execute_pipeline(run_id=run_id, tenant_id=tenant_id, user_id=user_id))
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

    async def _execute_pipeline(self, *, run_id: str, tenant_id: str, user_id: str) -> None:
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
            used_source_ids = [e.source_id for e in ranked_evidence[: self.max_sources_for_synthesis]]
            for source_id in used_source_ids:
                self.db.table("name_deep_research_sources").update(
                    {"used_in_final": True}
                ).eq("id", source_id).eq("run_id", run_id).execute()

            await self._update_run(run_id, status="synthesizing", updated_at=_utcnow_iso())

            result_doc, selected_model = await self._synthesize_result(
                run_id=run_id,
                name=run.get("input_name", ""),
                hints=hints,
                queries=queries,
                source_rows=source_rows,
                ranked_evidence=ranked_evidence[: self.max_sources_for_synthesis],
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

            await self._update_run(
                run_id,
                status="completed",
                selected_model=selected_model,
                sources_used_in_final=len([s for s in result_doc.get("sources", []) if s.get("used_in_final")]),
                run_completed_at=result_doc["crawl_stats"]["run_completed_at"],
                updated_at=_utcnow_iso(),
            )
            logger.info("name-research run completed: run_id=%s", run_id)
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
        if not self.firecrawl:
            raise RuntimeError("Firecrawl is not configured for name-only deep research")

        urls: List[str] = []
        for query in queries:
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

            identity = self.identity_scorer.score_page(
                page_content=content,
                page_metadata={"title": title, "url": canonical_url, **metadata},
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

    async def _synthesize_result(
        self,
        *,
        run_id: str,
        name: str,
        hints: Dict[str, Optional[str]],
        queries: List[str],
        source_rows: List[Dict[str, Any]],
        ranked_evidence: List[RankedEvidence],
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
        now_iso = _utcnow_iso()
        if not ranked_evidence:
            fallback = self._build_fallback_result(
                run_id=run_id,
                name=name,
                hints=hints,
                queries=queries,
                source_items=source_items,
                run_started_at=run_started_at,
                run_completed_at=now_iso,
                warning="No usable public content extracted from discovered sources.",
            )
            parsed = self.validate_result_schema(fallback)
            return parsed.model_dump(), "none"

        selected_model = await self._resolve_reasoning_model()
        prompt_payload = {
            "run_id": run_id,
            "input": {
                "name": name,
                "hints": {
                    "location": hints.get("location"),
                    "company": hints.get("company"),
                    "website": hints.get("website"),
                },
            },
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
            "requirements": {
                "public_web_only": True,
                "no_uncited_facts": True,
                "unknown_if_weak_evidence": True,
                "statuses": [
                    "verified",
                    "partially_verified",
                    "unverified",
                    "disputed",
                    "unknown",
                ],
            },
        }

        system_prompt = (
            "You are an evidence-grounded research synthesizer. "
            "Output only one JSON object. Never guess. "
            "Every timeline and claim item must include citations source_id[] that exist in sources. "
            "If evidence is weak or ambiguous, use unknown/unverified/needs_review wording."
        )

        schema_instruction = (
            "Return JSON with EXACT keys: run_id,input,claimed_identity,bio,profile_summary,timeline,claims,"
            "known_unknowns,suggested_followup_questions,crawl_stats,quality,sources. "
            "Do not include additional top-level keys."
        )

        model_candidates = [selected_model] + [m for m in await self._reasoning_model_candidates() if m != selected_model]
        errors: List[str] = []
        for model in model_candidates:
            for attempt in range(3):
                try:
                    response_doc = await self._invoke_reasoning_model(
                        model=model,
                        system_prompt=system_prompt,
                        user_payload=prompt_payload,
                        schema_instruction=schema_instruction,
                        validation_error=None if attempt == 0 else errors[-1],
                    )
                    response_doc["run_id"] = run_id
                    response_doc["input"] = {
                        "name": name,
                        "hints": {
                            "location": hints.get("location"),
                            "company": hints.get("company"),
                            "website": hints.get("website"),
                        },
                    }
                    response_doc["sources"] = source_items

                    crawl_stats = dict(response_doc.get("crawl_stats") or {})
                    crawl_stats["queries_used"] = queries
                    crawl_stats["urls_considered"] = len(source_items)
                    crawl_stats["urls_crawled"] = len(
                        [s for s in source_items if s.get("content_quality") in {"full", "partial"}]
                    )
                    crawl_stats["urls_blocked"] = len(
                        [s for s in source_items if s.get("content_quality") in {"blocked", "manual_needed"}]
                    )
                    crawl_stats["sources_used_in_final"] = len([s for s in source_items if s.get("used_in_final")])
                    crawl_stats["words_extracted"] = sum(
                        _word_count(e.excerpt) for e in ranked_evidence
                    )
                    crawl_stats["run_started_at"] = run_started_at
                    crawl_stats["run_completed_at"] = now_iso
                    response_doc["crawl_stats"] = crawl_stats

                    parsed = self.validate_result_schema(response_doc)
                    return parsed.model_dump(), model
                except Exception as exc:
                    errors.append(str(exc))
                    logger.warning(
                        "name-research synth attempt failed model=%s attempt=%s run_id=%s err=%s",
                        model,
                        attempt + 1,
                        run_id,
                        exc,
                    )

        fallback = self._build_fallback_result(
            run_id=run_id,
            name=name,
            hints=hints,
            queries=queries,
            source_items=source_items,
            run_started_at=run_started_at,
            run_completed_at=now_iso,
            warning=f"Synthesis validation failed after retries: {errors[-1] if errors else 'unknown error'}",
        )
        parsed = self.validate_result_schema(fallback)
        return parsed.model_dump(), model_candidates[0] if model_candidates else "none"

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
        run_started_at: str,
        run_completed_at: str,
        warning: str,
    ) -> Dict[str, Any]:
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

        return {
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
                "urls_considered": len(source_items),
                "urls_crawled": len([s for s in source_items if s.get("content_quality") in {"full", "partial"}]),
                "urls_blocked": len([s for s in source_items if s.get("content_quality") in {"blocked", "manual_needed"}]),
                "sources_used_in_final": len([s for s in source_items if s.get("used_in_final")]),
                "words_extracted": 0,
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
