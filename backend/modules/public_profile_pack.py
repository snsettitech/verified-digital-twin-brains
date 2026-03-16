from __future__ import annotations

import json
from datetime import datetime
import html as html_lib
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote, urljoin, urlparse
from urllib.request import Request, urlopen

from modules.observability import supabase

PUBLIC_PROFILE_META_VERSION = "1.0"
OWNER_LOCKED_IMAGE_SOURCE_TYPES = {"owner_uploaded", "oauth"}


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _clean_unique_strings(values: Iterable[Any], *, limit: int = 6) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        text = _clean_text(value)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _first_sentence(text: Any) -> str:
    normalized = _clean_text(text)
    if not normalized:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", normalized, maxsplit=1)
    return parts[0].strip()


def _coerce_score_percent(value: Any) -> float:
    try:
        score = float(value or 0)
    except Exception:
        return 0.0
    if score <= 1.0:
        score *= 100.0
    return max(0.0, min(score, 100.0))


def _coerce_year(value: Any) -> Optional[int]:
    if value in (None, "", 0):
        return None
    if isinstance(value, int):
        return value if 1800 <= value <= 2100 else None
    if isinstance(value, datetime):
        return value.year
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        year_match = re.search(r"\b(18|19|20)\d{2}\b", text)
        if year_match:
            return int(year_match.group(0))
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).year
        except Exception:
            return None
    return None


def _social_key_from_url(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return "website"
    if "wikipedia.org" in host:
        return "wikipedia"
    if "linkedin.com" in host:
        return "linkedin"
    if "github.com" in host:
        return "github"
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "instagram.com" in host:
        return "instagram"
    if "x.com" in host or "twitter.com" in host:
        return "twitter"
    return "website"


def normalize_social_links(value: Any) -> Dict[str, str]:
    if isinstance(value, dict):
        return {
            _clean_text(key).lower(): _clean_text(url)
            for key, url in value.items()
            if _clean_text(url)
        }

    links: Dict[str, str] = {}
    for raw in _safe_list(value):
        url = _clean_text(raw)
        if not url:
            continue
        key = _social_key_from_url(url)
        links.setdefault(key, url)
    return links


def _is_populated(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_is_populated(v) for v in value.values())
    if isinstance(value, list):
        return any(_is_populated(v) for v in value)
    return bool(_clean_text(value))


def _iso_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _coerce_ratio(value: Any) -> float:
    try:
        score = float(value or 0.0)
    except Exception:
        return 0.0
    if score > 1.0:
        score /= 100.0
    return max(0.0, min(score, 1.0))


def _calculate_completeness_score(public_profile: Dict[str, Any]) -> float:
    weighted_checks = [
        (_clean_text(public_profile.get("display_name")), 12),
        (_clean_text(public_profile.get("occupation")) or _clean_text(public_profile.get("role")), 10),
        (_clean_text(public_profile.get("headline")), 10),
        (_clean_text(public_profile.get("bio")), 12),
        (_clean_text(public_profile.get("short_description")), 10),
        (public_profile.get("areas_of_expertise"), 10),
        (public_profile.get("key_achievements"), 8),
        (public_profile.get("contributions"), 8),
        (public_profile.get("education"), 8),
        (public_profile.get("work_experience"), 8),
        (public_profile.get("social_links"), 7),
        (_clean_text(public_profile.get("image_url")) or _clean_text(public_profile.get("avatar_url")), 7),
    ]
    total = float(sum(weight for _value, weight in weighted_checks))
    if total <= 0:
        return 0.0
    earned = sum(weight for value, weight in weighted_checks if _is_populated(value))
    return round((earned / total) * 100.0, 1)


def _request_url(url: str, *, accept: str, timeout: float = 4.0):
    return Request(
        url,
        headers={
            "User-Agent": "VerifiedDigitalTwinBrain/1.0",
            "Accept": accept,
        },
    )


def _fetch_remote_text(url: str, *, timeout: float = 4.0, max_bytes: int = 160000) -> str:
    normalized_url = _clean_text(url)
    if not normalized_url.startswith(("http://", "https://")):
        return ""
    try:
        request = _request_url(normalized_url, accept="text/html,application/xhtml+xml")
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(max_bytes)
            return raw.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _fetch_remote_json(url: str, *, timeout: float = 4.0) -> Dict[str, Any]:
    normalized_url = _clean_text(url)
    if not normalized_url.startswith(("http://", "https://")):
        return {}
    try:
        request = _request_url(normalized_url, accept="application/json")
        with urlopen(request, timeout=timeout) as response:
            payload = response.read(250000).decode("utf-8", errors="ignore")
        data = json.loads(payload)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _clean_host(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower().strip()
    except Exception:
        return ""
    return host[4:] if host.startswith("www.") else host


def _looks_like_image_url(url: Any) -> bool:
    normalized = _clean_text(url).lower()
    if not normalized:
        return False
    image_markers = (
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".avif",
        ".gif",
        "upload.wikimedia.org",
        "media.licdn.com/dms/image",
        "/photo/",
        "/images/",
        "/headshot",
        "/portrait",
    )
    return any(marker in normalized for marker in image_markers)


def _looks_like_logo_url(url: Any) -> bool:
    normalized = _clean_text(url).lower()
    if not normalized:
        return False
    return any(token in normalized for token in ("logo", "favicon", "icon", "apple-touch"))


def _host_matches(expected_hosts: List[str], url: str) -> bool:
    host = _clean_host(url)
    if not host:
        return False
    for expected in expected_hosts:
        if not expected:
            continue
        if host == expected or host.endswith("." + expected) or expected.endswith("." + host):
            return True
    return False


def _official_host_candidates(result: Dict[str, Any]) -> List[str]:
    input_data = _safe_dict(result.get("input"))
    hints = _safe_dict(input_data.get("hints"))
    hosts = []
    for raw_url in (
        hints.get("website"),
        hints.get("official_website"),
        hints.get("organization_website"),
    ):
        host = _clean_host(_clean_text(raw_url))
        if host and host not in hosts:
            hosts.append(host)
    return hosts


def _is_official_source(url: str, source: Dict[str, Any], official_hosts: List[str]) -> bool:
    host = _clean_host(url)
    if not host:
        return False
    if _host_matches(official_hosts, url):
        return True
    source_type = _clean_text(source.get("source_type")).lower()
    return source_type in {"profile", "website"} and (
        host.endswith(".gov")
        or host.endswith(".gov.in")
        or host.endswith(".edu")
        or host.endswith(".edu.in")
        or host.endswith(".org")
    )


def _extract_meta_image(html_text: str, page_url: str) -> str:
    if not html_text:
        return ""
    patterns = (
        r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image(?::secure_url)?["\']',
        r'<meta[^>]+name=["\']twitter:image(?::src)?["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image(?::src)?["\']',
    )
    for pattern in patterns:
        match = re.search(pattern, html_text, re.IGNORECASE)
        if not match:
            continue
        candidate = html_lib.unescape(_clean_text(match.group(1)))
        if not candidate:
            continue
        candidate = urljoin(page_url, candidate)
        if _looks_like_image_url(candidate) and not _looks_like_logo_url(candidate):
            return candidate
    return ""


def _wikipedia_summary_api_url(page_url: str) -> str:
    parsed = urlparse(page_url)
    if "wikipedia.org" not in parsed.netloc.lower():
        return ""
    if "/wiki/" not in parsed.path:
        return ""
    page_title = parsed.path.split("/wiki/", 1)[1].strip("/")
    if not page_title:
        return ""
    return f"{parsed.scheme or 'https'}://{parsed.netloc}/api/rest_v1/page/summary/{quote(page_title)}"


def _fetch_wikipedia_thumbnail(page_url: str) -> str:
    api_url = _wikipedia_summary_api_url(page_url)
    if not api_url:
        return ""
    summary = _fetch_remote_json(api_url)
    thumbnail = _safe_dict(summary.get("thumbnail"))
    source = _clean_text(thumbnail.get("source"))
    return source if _looks_like_image_url(source) and not _looks_like_logo_url(source) else ""


def _build_image_candidate(
    *,
    url: str,
    source_type: str,
    source_url: str,
    confidence: Any,
) -> Optional[Dict[str, Any]]:
    image_url = _clean_text(url)
    if not _looks_like_image_url(image_url) or _looks_like_logo_url(image_url):
        return None
    return {
        "url": image_url,
        "source_type": _clean_text(source_type).lower() or "generic_public",
        "source_url": _clean_text(source_url),
        "confidence": round(_coerce_ratio(confidence), 3),
    }


def _candidate_priority(candidate: Dict[str, Any]) -> float:
    priority_map = {
        "owner_uploaded": 1.0,
        "oauth": 0.98,
        "official_profile": 0.9,
        "wikipedia": 0.82,
        "direct_public_image": 0.72,
        "generic_public": 0.64,
        "linkedin_public": 0.55,
        "existing": 0.45,
    }
    source_type = _clean_text(candidate.get("source_type")).lower()
    confidence = _coerce_ratio(candidate.get("confidence"))
    return priority_map.get(source_type, 0.4) + confidence


def _resolve_profile_image(
    result: Dict[str, Any],
    existing_public_profile: Dict[str, Any],
    existing_meta: Dict[str, Any],
) -> Dict[str, Any]:
    existing_image_url = (
        _clean_text(existing_public_profile.get("image_url"))
        or _clean_text(existing_public_profile.get("avatar_url"))
    )
    existing_source_type = _clean_text(existing_meta.get("image_source_type")).lower()
    existing_confidence = _coerce_ratio(existing_meta.get("image_confidence") or 0.9)
    if existing_image_url and existing_source_type in OWNER_LOCKED_IMAGE_SOURCE_TYPES:
        return {
            "status": "resolved",
            "image_url": existing_image_url,
            "image_source_type": existing_source_type,
            "image_source_url": _clean_text(existing_meta.get("image_source_url")) or existing_image_url,
            "image_confidence": round(existing_confidence, 3),
        }

    candidates: Dict[str, Dict[str, Any]] = {}

    def add_candidate(candidate: Optional[Dict[str, Any]]) -> None:
        if not candidate:
            return
        key = str(candidate.get("url") or "").lower()
        if not key:
            return
        current = candidates.get(key)
        if current is None or _candidate_priority(candidate) > _candidate_priority(current):
            candidates[key] = candidate

    if existing_image_url:
        add_candidate(
            _build_image_candidate(
                url=existing_image_url,
                source_type=existing_source_type or "existing",
                source_url=_clean_text(existing_meta.get("image_source_url")) or existing_image_url,
                confidence=existing_confidence or 0.6,
            )
        )

    input_data = _safe_dict(result.get("input"))
    hints = _safe_dict(input_data.get("hints"))
    for hint_key in ("image_url", "avatar_url", "profile_image_url", "photo_url", "headshot_url"):
        hint_image = _clean_text(hints.get(hint_key))
        if not hint_image:
            continue
        add_candidate(
            _build_image_candidate(
                url=hint_image,
                source_type="direct_public_image",
                source_url=hint_image,
                confidence=0.9,
            )
        )

    official_hosts = _official_host_candidates(result)
    sorted_sources = sorted(
        _safe_list(result.get("sources")),
        key=lambda row: (
            not bool(_safe_dict(row).get("used_in_final")),
            -float(_safe_dict(row).get("identity_match_confidence") or 0.0),
        ),
    )

    for raw_source in sorted_sources:
        source = _safe_dict(raw_source)
        source_url = _clean_text(source.get("url"))
        if not source_url:
            continue
        source_type = _clean_text(source.get("source_type")).lower()
        confidence = float(source.get("identity_match_confidence") or 0.0)

        if _looks_like_image_url(source_url):
            resolved_type = "direct_public_image"
            if _is_official_source(source_url, source, official_hosts):
                resolved_type = "official_profile"
            elif "linkedin.com" in _clean_host(source_url):
                resolved_type = "linkedin_public"
            add_candidate(
                _build_image_candidate(
                    url=source_url,
                    source_type=resolved_type,
                    source_url=source_url,
                    confidence=max(confidence, 0.75),
                )
            )
            continue

        if "linkedin.com" in _clean_host(source_url):
            continue

        if "wikipedia.org" in _clean_host(source_url):
            thumbnail = _fetch_wikipedia_thumbnail(source_url)
            add_candidate(
                _build_image_candidate(
                    url=thumbnail,
                    source_type="wikipedia",
                    source_url=source_url,
                    confidence=max(confidence, 0.8),
                )
            )
            continue

        if source_type not in {"website", "profile"}:
            continue

        if not source.get("used_in_final") and confidence < 0.65:
            continue

        html_text = _fetch_remote_text(source_url)
        image_url = _extract_meta_image(html_text, source_url)
        if not image_url:
            continue
        resolved_type = "official_profile" if _is_official_source(source_url, source, official_hosts) else "generic_public"
        minimum_confidence = 0.55 if resolved_type == "official_profile" else 0.7
        if confidence < minimum_confidence and not source.get("used_in_final"):
            continue
        add_candidate(
            _build_image_candidate(
                url=image_url,
                source_type=resolved_type,
                source_url=source_url,
                confidence=max(confidence, minimum_confidence),
            )
        )

    if not candidates:
        return {
            "status": "resolved" if existing_image_url else "missing",
            "image_url": existing_image_url,
            "image_source_type": existing_source_type,
            "image_source_url": _clean_text(existing_meta.get("image_source_url")),
            "image_confidence": round(existing_confidence, 3) if existing_image_url else 0.0,
        }

    best = max(candidates.values(), key=_candidate_priority)
    return {
        "status": "resolved",
        "image_url": _clean_text(best.get("url")),
        "image_source_type": _clean_text(best.get("source_type")).lower(),
        "image_source_url": _clean_text(best.get("source_url")),
        "image_confidence": round(_coerce_ratio(best.get("confidence")), 3),
    }


def _build_public_profile_meta(
    *,
    source_flow: str,
    materialized_at: str,
    public_profile: Dict[str, Any],
    image_resolution: Dict[str, Any],
    existing_meta: Dict[str, Any],
) -> Dict[str, Any]:
    image_status = _clean_text(image_resolution.get("status")).lower() or "missing"
    return {
        **existing_meta,
        "version": _clean_text(existing_meta.get("version")) or PUBLIC_PROFILE_META_VERSION,
        "source_flow": _clean_text(source_flow) or _clean_text(existing_meta.get("source_flow")) or "generated",
        "materialized_at": _clean_text(materialized_at) or _clean_text(existing_meta.get("materialized_at")) or _iso_now(),
        "completeness_score": _calculate_completeness_score(public_profile),
        "image_status": image_status if image_status in {"missing", "pending", "resolved", "rejected"} else "missing",
        "image_source_type": _clean_text(image_resolution.get("image_source_type"))
        or _clean_text(existing_meta.get("image_source_type")),
        "image_source_url": _clean_text(image_resolution.get("image_source_url"))
        or _clean_text(existing_meta.get("image_source_url")),
        "image_confidence": round(
            _coerce_ratio(image_resolution.get("image_confidence") or existing_meta.get("image_confidence")),
            3,
        ),
    }


def _fetch_existing_source_candidates(twin_id: str, *, limit: int = 24) -> List[Dict[str, Any]]:
    if not _clean_text(twin_id):
        return []
    select_variants = (
        "id, citation_url, filename, source_type",
        "id, citation_url, filename",
    )
    for select_clause in select_variants:
        try:
            response = (
                supabase.table("sources")
                .select(select_clause)
                .eq("twin_id", twin_id)
                .limit(limit)
                .execute()
            )
            rows = response.data or []
            if isinstance(rows, list):
                return [_safe_dict(row) for row in rows]
        except Exception:
            continue
    return []


def normalize_public_profile(twin: Dict[str, Any]) -> Dict[str, Any]:
    settings = _safe_dict(twin.get("settings"))
    public_profile = _safe_dict(settings.get("public_profile"))
    public_profile_meta = _safe_dict(settings.get("public_profile_meta"))

    display_name = (
        _clean_text(public_profile.get("display_name"))
        or _clean_text(twin.get("name"))
        or "Persona"
    )
    organization = _clean_text(public_profile.get("organization")) or _clean_text(settings.get("organization"))
    role = _clean_text(public_profile.get("role")) or _clean_text(settings.get("role"))
    headline = (
        _clean_text(public_profile.get("headline"))
        or _clean_text(settings.get("headline"))
        or _clean_text(settings.get("tagline"))
    )
    bio = (
        _clean_text(public_profile.get("bio"))
        or _clean_text(settings.get("public_intro"))
        or _clean_text(twin.get("description"))
        or _clean_text(settings.get("description"))
        or headline
    )
    avatar_url = _clean_text(public_profile.get("avatar_url"))
    pinned_questions = _clean_unique_strings(public_profile.get("pinned_questions") or [], limit=4)

    return {
        "display_name": display_name,
        "organization": organization,
        "role": role,
        "occupation": _clean_text(public_profile.get("occupation")) or _clean_text(settings.get("occupation")),
        "headline": headline,
        "bio": bio,
        "short_description": _clean_text(public_profile.get("short_description")),
        "avatar_url": avatar_url,
        "image_url": _clean_text(public_profile.get("image_url")) or avatar_url,
        "mind_label": _clean_text(public_profile.get("mind_label")),
        "handle": _clean_text(settings.get("handle")),
        "pinned_questions": pinned_questions,
        "social_links": normalize_social_links(public_profile.get("social_links")),
        "featured_content": _safe_list(public_profile.get("featured_content")),
        "personality_traits": _clean_unique_strings(public_profile.get("personality_traits") or [], limit=6),
        "key_achievements": _clean_unique_strings(public_profile.get("key_achievements") or [], limit=6),
        "areas_of_expertise": _clean_unique_strings(public_profile.get("areas_of_expertise") or [], limit=6),
        "contributions": _clean_unique_strings(public_profile.get("contributions") or [], limit=6),
        "speaking_style": _clean_text(public_profile.get("speaking_style")),
        "verified_profile": bool(public_profile.get("verified_profile")),
        "birth_year": _coerce_year(public_profile.get("birth_year")),
        "death_year": _coerce_year(public_profile.get("death_year")),
        "nationality": _clean_text(public_profile.get("nationality")),
        "education": _dedupe_object_rows(
            _safe_list(public_profile.get("education")),
            ("institution", "degree", "field"),
        ),
        "work_experience": _dedupe_object_rows(
            _safe_list(public_profile.get("work_experience")),
            ("company", "role", "description"),
        ),
        "public_profile_meta": public_profile_meta,
        "settings": settings,
        "public_profile": public_profile,
    }


def _build_occupation(profile: Dict[str, Any], expertise: Optional[List[str]] = None) -> str:
    explicit_occupation = _clean_text(profile.get("occupation"))
    if explicit_occupation:
        return explicit_occupation
    role = _clean_text(profile.get("role"))
    organization = _clean_text(profile.get("organization"))
    headline = _clean_text(profile.get("headline"))
    if role and organization:
        return f"{role} at {organization}"
    if role:
        return role
    if headline:
        return headline
    if expertise:
        return ", ".join(expertise[:3])
    return "Public persona"


def _fetch_answerability_score(twin_id: str) -> float:
    try:
        result = (
            supabase.table("person_answerability_scores")
            .select("answerability_score")
            .eq("twin_id", twin_id)
            .eq("scope_type", "global")
            .eq("scope_key", "global")
            .single()
            .execute()
        )
        if result.data:
            return _coerce_score_percent(result.data.get("answerability_score"))
    except Exception:
        pass
    return 0.0


def _fetch_verified_claim_count(twin_id: str) -> int:
    try:
        result = (
            supabase.table("person_claims")
            .select("id", count="exact")
            .eq("twin_id", twin_id)
            .eq("verification_status", "verified")
            .eq("public_visibility", "public")
            .eq("is_active", True)
            .execute()
        )
        return int(result.count or 0)
    except Exception:
        return 0


def _fetch_public_topics(twin_id: str, *, limit: int = 6) -> List[Dict[str, Any]]:
    topic_select_variants = [
        ("topic_slug, topic_name, answerability_score", "topic_slug", "topic_name"),
        ("topic_slug, name, answerability_score", "topic_slug", "name"),
        ("slug, name, answerability_score", "slug", "name"),
    ]

    for select_clause, slug_key, name_key in topic_select_variants:
        try:
            result = (
                supabase.table("person_topic_profiles")
                .select(select_clause)
                .eq("twin_id", twin_id)
                .order("answerability_score", desc=True)
                .limit(limit * 2)
                .execute()
            )
            topics: List[Dict[str, Any]] = []
            for row in result.data or []:
                score = _coerce_score_percent(row.get("answerability_score"))
                if score < 45:
                    continue
                slug = _clean_text(row.get(slug_key) or row.get("topic_slug") or row.get("slug")).lower()
                name = _clean_text(row.get(name_key) or row.get("topic_name") or row.get("name") or slug)
                if not slug and not name:
                    continue
                topics.append(
                    {
                        "slug": slug or name.lower().replace(" ", "-"),
                        "name": name,
                        "answerability_score": score,
                    }
                )
            if topics:
                deduped = []
                seen = set()
                for topic in topics:
                    key = str(topic.get("slug") or topic.get("name")).lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    deduped.append(topic)
                    if len(deduped) >= limit:
                        break
                return deduped
        except Exception:
            continue
    return []


def _fetch_public_claims(twin_id: str) -> List[Dict[str, Any]]:
    try:
        result = (
            supabase.table("person_claims")
            .select(
                "id, claim_text, claim_type, claim_time_start, claim_time_end, verification_status, "
                "public_visibility, extraction_confidence, metadata_json, is_active"
            )
            .eq("twin_id", twin_id)
            .eq("is_active", True)
            .neq("verification_status", "rejected")
            .neq("public_visibility", "private")
            .order("verification_status", desc=True)
            .order("extraction_confidence", desc=True)
            .limit(100)
            .execute()
        )
        return result.data or []
    except Exception:
        return []


def _fetch_timeline_events(twin_id: str) -> List[Dict[str, Any]]:
    try:
        result = (
            supabase.table("person_timeline_events")
            .select(
                "event_type, title, description, start_date, end_date, organization, role_title, "
                "confidence, is_active"
            )
            .eq("twin_id", twin_id)
            .eq("is_active", True)
            .order("start_date", desc=True)
            .limit(24)
            .execute()
        )
        return result.data or []
    except Exception:
        return []


def _fetch_style_profile(twin_id: str) -> Dict[str, Any]:
    try:
        result = (
            supabase.table("person_style_profile")
            .select("tone_descriptors, sentence_length_profile, common_phrases")
            .eq("twin_id", twin_id)
            .eq("is_active_version", True)
            .order("version", desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            return _safe_dict(result.data[0])
    except Exception:
        pass
    return {}


def _claim_meta(row: Dict[str, Any]) -> Dict[str, Any]:
    return _safe_dict(row.get("metadata_json"))


def _identity_stat_from_claims(claims: List[Dict[str, Any]]) -> Tuple[Optional[int], Optional[int], str]:
    birth_year: Optional[int] = None
    death_year: Optional[int] = None
    nationality = ""

    for claim in claims:
        if claim.get("claim_type") not in {"identity", "bio_fact"}:
            continue
        meta = _claim_meta(claim)
        if birth_year is None:
            birth_year = _coerce_year(meta.get("birth_year")) or _coerce_year(claim.get("claim_time_start"))
        if death_year is None:
            death_year = _coerce_year(meta.get("death_year")) or _coerce_year(claim.get("claim_time_end"))
        if not nationality:
            nationality = _clean_text(meta.get("nationality"))
            if not nationality:
                text = _clean_text(claim.get("claim_text"))
                match = re.search(r"\b([A-Z][a-z]+)\s+(?:national|citizen|American|Canadian|Indian|British)\b", text)
                if match:
                    nationality = match.group(1)

    return birth_year, death_year, nationality


def _build_work_entries(
    claims: List[Dict[str, Any]],
    timeline_events: List[Dict[str, Any]],
    seeded: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = list(seeded or [])

    for event in timeline_events:
        event_type = _clean_text(event.get("event_type")).lower()
        if event_type and not event_type.startswith("job") and event_type not in {"founded_company", "board_role", "investment"}:
            continue
        company = _clean_text(event.get("organization"))
        role = _clean_text(event.get("role_title")) or _clean_text(event.get("title"))
        description = _clean_text(event.get("description"))
        if not company and not role:
            continue
        entries.append(
            {
                "company": company,
                "role": role,
                "description": description,
                "start_year": _coerce_year(event.get("start_date")),
                "end_year": _coerce_year(event.get("end_date")),
            }
        )

    for claim in claims:
        if claim.get("claim_type") != "work_experience":
            continue
        meta = _claim_meta(claim)
        claim_text = _clean_text(claim.get("claim_text"))
        role = _clean_text(meta.get("role") or meta.get("role_title"))
        company = _clean_text(meta.get("company") or meta.get("organization"))
        if not role or not company:
            match = re.search(r"(?:a|an)\s+([^,.]+?)\s+(?:at|with)\s+([^,.]+)", claim_text, re.IGNORECASE)
            if match:
                role = role or _clean_text(match.group(1))
                company = company or _clean_text(match.group(2))
        if not role and not company:
            continue
        entries.append(
            {
                "company": company,
                "role": role,
                "description": claim_text,
                "start_year": _coerce_year(meta.get("start_year")) or _coerce_year(claim.get("claim_time_start")),
                "end_year": _coerce_year(meta.get("end_year")) or _coerce_year(claim.get("claim_time_end")),
            }
        )

    return _dedupe_object_rows(entries, ("company", "role"))


def _build_education_entries(
    claims: List[Dict[str, Any]],
    timeline_events: List[Dict[str, Any]],
    seeded: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = list(seeded or [])

    for event in timeline_events:
        event_type = _clean_text(event.get("event_type")).lower()
        if not event_type.startswith("education"):
            continue
        institution = _clean_text(event.get("organization"))
        degree = _clean_text(event.get("title"))
        if not institution and not degree:
            continue
        entries.append(
            {
                "institution": institution,
                "degree": degree,
                "field": "",
                "start_year": _coerce_year(event.get("start_date")),
                "end_year": _coerce_year(event.get("end_date")),
            }
        )

    for claim in claims:
        if claim.get("claim_type") != "education":
            continue
        meta = _claim_meta(claim)
        institution = _clean_text(meta.get("institution") or meta.get("school"))
        degree = _clean_text(meta.get("degree"))
        field = _clean_text(meta.get("field") or meta.get("major") or meta.get("subject"))
        if not institution:
            claim_text = _clean_text(claim.get("claim_text"))
            match = re.search(r"(?:from|at)\s+([^,.]+)", claim_text, re.IGNORECASE)
            if match:
                institution = _clean_text(match.group(1))
        if not institution and not degree and not field:
            continue
        entries.append(
            {
                "institution": institution,
                "degree": degree,
                "field": field,
                "start_year": _coerce_year(meta.get("start_year")) or _coerce_year(claim.get("claim_time_start")),
                "end_year": _coerce_year(meta.get("end_year")) or _coerce_year(claim.get("claim_time_end")),
            }
        )

    return _dedupe_object_rows(entries, ("institution", "degree", "field"))


def _dedupe_object_rows(rows: List[Dict[str, Any]], keys: Tuple[str, ...]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for row in rows:
        normalized = {
            key: _clean_text(row.get(key)) if isinstance(row.get(key), str) else row.get(key)
            for key in row.keys()
        }
        dedupe_key = tuple(str(normalized.get(key) or "").lower() for key in keys)
        if not any(dedupe_key):
            continue
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        deduped.append(normalized)
    return deduped[:6]


def _extract_research_expertise(profile_summary: Dict[str, Any]) -> List[str]:
    values: List[str] = []
    for item in _safe_list(profile_summary.get("expertise_topics")):
        if isinstance(item, dict):
            values.append(item.get("topic"))
        else:
            values.append(item)
    return _clean_unique_strings(values, limit=6)


def _build_headline_from_research(
    role: str,
    organization: str,
    what_they_do: List[str],
    bio_text: str,
) -> str:
    if what_they_do:
        return _first_sentence(what_they_do[0]) or _clean_text(what_they_do[0])
    if role and organization:
        return f"{role} at {organization}"
    if role:
        return role
    return _first_sentence(bio_text)


def _extract_research_years(text: Any) -> Tuple[Optional[int], Optional[int]]:
    normalized = _clean_text(text)
    years = re.findall(r"\b(?:18|19|20)\d{2}\b", normalized)
    if not years:
        return None, None
    start_year = int(years[0])
    end_year = int(years[1]) if len(years) > 1 else None
    return start_year, end_year


def _extract_social_links_from_research(
    result: Dict[str, Any],
    *,
    existing_links: Any = None,
) -> Dict[str, str]:
    links = normalize_social_links(existing_links)

    input_data = _safe_dict(result.get("input"))
    hints = _safe_dict(input_data.get("hints"))
    website_hint = _clean_text(hints.get("website"))
    if website_hint:
        links.setdefault(_social_key_from_url(website_hint), website_hint)

    sources = sorted(
        _safe_list(result.get("sources")),
        key=lambda row: (
            not bool(_safe_dict(row).get("used_in_final")),
            -float(_safe_dict(row).get("identity_match_confidence") or 0.0),
        ),
    )
    for raw_source in sources:
        source = _safe_dict(raw_source)
        url = _clean_text(source.get("url"))
        if not url:
            continue
        source_type = _clean_text(source.get("source_type")).lower()
        key = _social_key_from_url(url)
        if key == "website" and source_type not in {"website", "profile"}:
            continue
        links.setdefault(key, url)
        if len(links) >= 6:
            break
    return links


def _parse_education_entry_from_text(text: Any) -> Optional[Dict[str, Any]]:
    normalized = _clean_text(text)
    if not normalized:
        return None

    degree_match = re.search(
        r"\b(BA|B\.A\.|BS|B\.S\.|BSc|Bachelor(?: of [^,.]+)?|MA|M\.A\.|MS|M\.S\.|MSc|MBA|Master(?: of [^,.]+)?|PhD|Ph\.D\.|Doctorate|JD)\b[^,.]*",
        normalized,
        re.IGNORECASE,
    )
    institution_match = re.search(
        r"(?:from|at)\s+([^,.]*(?:University|College|School|Institute|Academy)[^,.]*)",
        normalized,
        re.IGNORECASE,
    )
    field_match = re.search(r"\bin\s+([^,.]{3,80})", normalized, re.IGNORECASE)

    institution = _clean_text(institution_match.group(1)) if institution_match else ""
    degree = _clean_text(degree_match.group(0)) if degree_match else ""
    field = _clean_text(field_match.group(1)) if field_match else ""
    if degree:
        degree = re.split(r"\s+from\s+", degree, maxsplit=1, flags=re.IGNORECASE)[0]
        degree = re.sub(r"\s+in\s+(?:18|19|20)\d{2}\b.*$", "", degree, flags=re.IGNORECASE)
    if field:
        field = re.split(r"\s+from\s+|\s+at\s+", field, maxsplit=1, flags=re.IGNORECASE)[0]
    if institution:
        institution = re.sub(r"\s+in\s+(?:18|19|20)\d{2}\b.*$", "", institution, flags=re.IGNORECASE)
    start_year, end_year = _extract_research_years(normalized)

    if not institution and not degree and not field:
        return None

    return {
        "institution": institution,
        "degree": degree,
        "field": field,
        "start_year": start_year,
        "end_year": end_year,
    }


def _parse_work_entry_from_text(text: Any) -> Optional[Dict[str, Any]]:
    normalized = _clean_text(text)
    if not normalized:
        return None

    role = ""
    company = ""
    for pattern in (
        r"(?:served as|worked as|joined as|appointed as|elected as|became)\s+([^,.]+?)\s+(?:at|with|for|of)\s+([^,.]+)",
        r"(?:a|an)\s+([^,.]+?)\s+(?:at|with)\s+([^,.]+)",
        r"([^,.]+?)\s+(?:at|with|for|of)\s+([^,.]+)",
    ):
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            role = _clean_text(match.group(1))
            company = _clean_text(match.group(2))
            break
    if company:
        company = re.sub(r"\s+(?:from|since)\s+(?:18|19|20)\d{2}\b.*$", "", company, flags=re.IGNORECASE)

    start_year, end_year = _extract_research_years(normalized)
    if not role and not company and len(normalized) < 18:
        return None

    return {
        "company": company,
        "role": role,
        "description": normalized,
        "start_year": start_year,
        "end_year": end_year,
    }


def _looks_like_work_event(text: Any) -> bool:
    normalized = _clean_text(text).lower()
    if not normalized:
        return False
    if _parse_education_entry_from_text(normalized):
        return False
    return any(
        token in normalized
        for token in (
            " at ",
            " with ",
            " for ",
            " served as ",
            " worked as ",
            " joined ",
            " appointed ",
            " elected ",
            " became ",
            " minister",
            " ceo",
            " founder",
            " director",
            " president",
            " engineer",
        )
    )


def _build_research_education(result: Dict[str, Any], existing_rows: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = list(existing_rows or [])
    for claim in _safe_list(result.get("claims")):
        claim_dict = _safe_dict(claim)
        if _clean_text(claim_dict.get("claim_type")).lower() != "credential":
            continue
        parsed = _parse_education_entry_from_text(claim_dict.get("text"))
        if parsed:
            entries.append(parsed)

    for item in _safe_list(result.get("timeline")):
        parsed = _parse_education_entry_from_text(_safe_dict(item).get("event"))
        if parsed:
            if parsed.get("start_year") is None:
                parsed["start_year"] = _coerce_year(_safe_dict(item).get("date_or_range"))
            if parsed.get("end_year") is None:
                parsed["end_year"] = _coerce_year(_safe_dict(item).get("date_or_range"))
            entries.append(parsed)

    return _dedupe_object_rows(entries, ("institution", "degree", "field"))


def _build_research_work_history(result: Dict[str, Any], existing_rows: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = list(existing_rows or [])
    for claim in _safe_list(result.get("claims")):
        claim_dict = _safe_dict(claim)
        claim_type = _clean_text(claim_dict.get("claim_type")).lower()
        if claim_type not in {"experience", "role", "project"}:
            continue
        parsed = _parse_work_entry_from_text(claim_dict.get("text"))
        if parsed:
            entries.append(parsed)

    for item in _safe_list(result.get("timeline")):
        event_text = _safe_dict(item).get("event")
        if not _looks_like_work_event(event_text):
            continue
        parsed = _parse_work_entry_from_text(event_text)
        if parsed:
            if parsed.get("start_year") is None:
                parsed["start_year"] = _coerce_year(_safe_dict(item).get("date_or_range"))
            if parsed.get("end_year") is None:
                parsed["end_year"] = _coerce_year(_safe_dict(item).get("date_or_range"))
            entries.append(parsed)

    return _dedupe_object_rows(entries, ("company", "role", "description"))


def _build_research_key_achievements(
    result: Dict[str, Any],
    existing_values: Optional[List[str]] = None,
) -> List[str]:
    seeded = list(existing_values or [])
    claims = [
        _first_sentence(_safe_dict(claim).get("text"))
        for claim in _safe_list(result.get("claims"))
        if _clean_text(_safe_dict(claim).get("claim_type")).lower() in {"credential", "role"}
        and _clean_text(_safe_dict(claim).get("status")).lower() not in {"disputed", "unverified"}
    ]
    return _clean_unique_strings([*seeded, *claims], limit=6)


def _build_research_contributions(
    result: Dict[str, Any],
    existing_values: Optional[List[str]] = None,
) -> List[str]:
    seeded = list(existing_values or [])
    claims = [
        _first_sentence(_safe_dict(claim).get("text"))
        for claim in _safe_list(result.get("claims"))
        if _clean_text(_safe_dict(claim).get("claim_type")).lower() in {"project", "experience", "opinion"}
        and _clean_text(_safe_dict(claim).get("status")).lower() not in {"disputed"}
    ]
    timeline = [_first_sentence(_safe_dict(item).get("event")) for item in _safe_list(result.get("timeline"))]
    return _clean_unique_strings([*seeded, *claims, *timeline], limit=6)


def _infer_birth_death_nationality(
    result: Dict[str, Any],
    existing_profile: Dict[str, Any],
) -> Tuple[Optional[int], Optional[int], str]:
    birth_year = _coerce_year(existing_profile.get("birth_year"))
    death_year = _coerce_year(existing_profile.get("death_year"))
    nationality = _clean_text(existing_profile.get("nationality"))

    texts = [
        _safe_dict(result.get("bio")).get("short"),
        _safe_dict(result.get("bio")).get("medium"),
        *[_safe_dict(claim).get("text") for claim in _safe_list(result.get("claims"))],
    ]
    for raw_text in texts:
        text = _clean_text(raw_text)
        if not text:
            continue
        if birth_year is None:
            born_match = re.search(r"\bborn\b[^0-9]{0,24}((?:18|19|20)\d{2})", text, re.IGNORECASE)
            if born_match:
                birth_year = int(born_match.group(1))
        if death_year is None:
            died_match = re.search(r"\bdied\b[^0-9]{0,24}((?:18|19|20)\d{2})", text, re.IGNORECASE)
            if died_match:
                death_year = int(died_match.group(1))
        if not nationality:
            nationality_match = re.search(
                r"\b(?:an?|the)\s+([A-Z][a-z]+)\s+(?:politician|businessman|businesswoman|leader|entrepreneur|executive|actor|author|economist|scientist|citizen|national)\b",
                text,
            )
            if nationality_match:
                nationality = nationality_match.group(1)
    return birth_year, death_year, nationality


def build_research_profile_projection(
    twin: Dict[str, Any],
    result: Dict[str, Any],
    *,
    source_flow: str = "generated",
) -> Dict[str, Any]:
    settings = _safe_dict(twin.get("settings"))
    existing_public_profile = _safe_dict(settings.get("public_profile"))
    existing_identity_pack = _safe_dict(settings.get("persona_identity_pack"))
    existing_meta = _safe_dict(settings.get("public_profile_meta"))
    claimed_identity = _safe_dict(result.get("claimed_identity"))
    profile_summary = _safe_dict(result.get("profile_summary"))
    bio = _safe_dict(result.get("bio"))

    display_name = (
        _clean_text(claimed_identity.get("canonical_name"))
        or _clean_text(existing_public_profile.get("display_name"))
        or _clean_text(twin.get("name"))
        or "Persona"
    )
    role = (
        _clean_text(existing_public_profile.get("role"))
        or _clean_text((_safe_list(profile_summary.get("public_roles")) or [""])[0])
    )
    organization = (
        _clean_text(existing_public_profile.get("organization"))
        or _clean_text((_safe_list(profile_summary.get("organizations")) or [""])[0])
    )
    bio_text = (
        _clean_text(existing_public_profile.get("bio"))
        or _clean_text(bio.get("medium"))
        or _clean_text(bio.get("short"))
        or _clean_text(twin.get("description"))
    )
    expertise = _clean_unique_strings(
        [
            *(_safe_list(existing_public_profile.get("areas_of_expertise")) or []),
            *_extract_research_expertise(profile_summary),
        ],
        limit=6,
    )
    what_they_do = _clean_unique_strings(profile_summary.get("what_they_do") or [], limit=4)
    headline = (
        _clean_text(existing_public_profile.get("headline"))
        or _build_headline_from_research(role, organization, what_they_do, bio_text)
    )
    occupation = _build_occupation(
        {
            "occupation": existing_public_profile.get("occupation"),
            "role": role,
            "organization": organization,
            "headline": headline,
        },
        expertise,
    )
    short_description = (
        _clean_text(existing_public_profile.get("short_description"))
        or _first_sentence(_clean_text(bio.get("short")))
        or _first_sentence(bio_text)
        or bio_text
    )
    pinned_questions = _clean_unique_strings(
        [
            *(_safe_list(existing_public_profile.get("pinned_questions")) or []),
            *(_safe_list(result.get("suggested_followup_questions")) or []),
            *[
                _safe_dict(item).get("question")
                for item in _safe_list(result.get("prepared_question_answers"))
            ],
        ],
        limit=4,
    )
    social_links = _extract_social_links_from_research(
        result,
        existing_links=existing_public_profile.get("social_links") or existing_identity_pack.get("social_links"),
    )
    education = _build_research_education(result, _safe_list(existing_public_profile.get("education")))
    work_experience = _build_research_work_history(result, _safe_list(existing_public_profile.get("work_experience")))
    key_achievements = _build_research_key_achievements(
        result,
        _safe_list(existing_public_profile.get("key_achievements")),
    )
    contributions = _build_research_contributions(
        result,
        _safe_list(existing_public_profile.get("contributions")),
    )
    birth_year, death_year, nationality = _infer_birth_death_nationality(result, existing_public_profile)
    materialized_at = (
        _clean_text(_safe_dict(result.get("crawl_stats")).get("run_completed_at"))
        or _clean_text(existing_meta.get("materialized_at"))
        or _iso_now()
    )
    image_resolution = _resolve_profile_image(result, existing_public_profile, existing_meta)

    public_profile = {
        **existing_public_profile,
        "display_name": display_name,
        "role": role,
        "organization": organization,
        "occupation": occupation,
        "headline": headline,
        "bio": bio_text,
        "short_description": short_description,
        "avatar_url": (
            _clean_text(existing_public_profile.get("avatar_url"))
            or _clean_text(image_resolution.get("image_url"))
        ),
        "image_url": (
            _clean_text(image_resolution.get("image_url"))
            or _clean_text(existing_public_profile.get("image_url"))
            or _clean_text(existing_public_profile.get("avatar_url"))
        ),
        "pinned_questions": pinned_questions,
        "social_links": social_links,
        "areas_of_expertise": expertise,
        "key_achievements": key_achievements,
        "contributions": contributions,
        "personality_traits": _clean_unique_strings(existing_public_profile.get("personality_traits") or [], limit=6),
        "speaking_style": _clean_text(existing_public_profile.get("speaking_style")),
        "education": education,
        "work_experience": work_experience,
        "birth_year": birth_year,
        "death_year": death_year,
        "nationality": nationality,
        "verified_profile": bool(existing_public_profile.get("verified_profile")),
    }
    public_profile_meta = _build_public_profile_meta(
        source_flow=source_flow,
        materialized_at=materialized_at,
        public_profile=public_profile,
        image_resolution=image_resolution,
        existing_meta=existing_meta,
    )

    identity_pack = {
        **existing_identity_pack,
        "display_name": display_name,
        "preferred_name": display_name,
        "role": role,
        "current_role": role,
        "organization": organization,
        "current_company": organization,
        "headline": headline,
        "summary": short_description or bio_text,
        "biography": bio_text,
        "expertise_areas": expertise,
        "social_links": social_links,
        "preferred_contact_channel": (
            _clean_text(existing_identity_pack.get("preferred_contact_channel"))
            or next(iter(social_links.keys()), "")
        ),
    }

    return {
        "public_profile": public_profile,
        "persona_identity_pack": identity_pack,
        "public_profile_meta": public_profile_meta,
        "tagline": headline,
        "public_intro": short_description or bio_text,
        "description": short_description or bio_text,
        "specialization": expertise[0] if expertise else role,
    }


def merge_materialized_profile_settings(
    current_settings: Dict[str, Any],
    projection: Dict[str, Any],
) -> Dict[str, Any]:
    merged_settings = {**_safe_dict(current_settings)}
    if projection.get("public_profile"):
        merged_settings["public_profile"] = projection["public_profile"]
    if projection.get("persona_identity_pack"):
        merged_settings["persona_identity_pack"] = projection["persona_identity_pack"]
    if projection.get("public_profile_meta"):
        merged_settings["public_profile_meta"] = projection["public_profile_meta"]
    if projection.get("tagline"):
        merged_settings["tagline"] = projection["tagline"]
    if projection.get("public_intro"):
        merged_settings["public_intro"] = projection["public_intro"]
    return merged_settings


def build_existing_profile_projection(
    twin: Dict[str, Any],
    *,
    source_flow: str = "backfill",
) -> Dict[str, Any]:
    normalized = normalize_public_profile(twin)
    settings = _safe_dict(normalized.get("settings"))
    existing_public_profile = _safe_dict(settings.get("public_profile"))
    existing_identity_pack = _safe_dict(settings.get("persona_identity_pack"))
    existing_meta = _safe_dict(settings.get("public_profile_meta"))
    source_rows = _fetch_existing_source_candidates(str(twin.get("id") or ""))
    source_urls = [
        _clean_text(row.get("citation_url"))
        for row in source_rows
        if _clean_text(row.get("citation_url"))
    ]

    display_name = normalized["display_name"]
    role = normalized["role"]
    organization = normalized["organization"]
    expertise = _clean_unique_strings(
        [
            *normalized.get("areas_of_expertise", []),
            *_safe_list(existing_identity_pack.get("expertise_areas")),
            _clean_text(settings.get("specialization")),
            _clean_text(settings.get("headline")),
        ],
        limit=6,
    )
    fallback_social_links = normalize_social_links(source_urls)
    social_links = normalized["social_links"] or fallback_social_links
    image_resolution = _resolve_profile_image(
        {
            "input": {
                "hints": {
                    "website": social_links.get("website") or social_links.get("wikipedia") or "",
                }
            },
            "sources": [
                {
                    "source_id": row.get("id"),
                    "url": _clean_text(row.get("citation_url")),
                    "title": _clean_text(row.get("filename")),
                    "source_type": (
                        _clean_text(row.get("source_type"))
                        or ("profile" if "wikipedia.org" in _clean_host(row.get("citation_url")) else "website")
                    ),
                    "used_in_final": True,
                    "identity_match_confidence": 0.82,
                }
                for row in source_rows
                if _clean_text(row.get("citation_url"))
            ],
        },
        existing_public_profile,
        existing_meta,
    )
    image_url = _clean_text(
        image_resolution.get("image_url")
        or normalized.get("image_url")
        or normalized.get("avatar_url")
    )

    public_profile = {
        **existing_public_profile,
        "display_name": display_name,
        "role": role,
        "organization": organization,
        "occupation": _build_occupation(
            {
                "occupation": existing_public_profile.get("occupation") or settings.get("occupation"),
                "role": role,
                "organization": organization,
                "headline": normalized["headline"] or settings.get("headline"),
            },
            expertise,
        ),
        "headline": normalized["headline"],
        "bio": normalized["bio"],
        "short_description": normalized["short_description"] or _first_sentence(normalized["bio"]) or normalized["bio"],
        "avatar_url": _clean_text(normalized.get("avatar_url")) or image_url,
        "image_url": image_url,
        "pinned_questions": normalized["pinned_questions"],
        "social_links": social_links,
        "areas_of_expertise": expertise,
        "key_achievements": normalized["key_achievements"],
        "contributions": normalized["contributions"],
        "personality_traits": normalized["personality_traits"],
        "speaking_style": normalized["speaking_style"],
        "education": normalized["education"],
        "work_experience": normalized["work_experience"],
        "birth_year": normalized["birth_year"],
        "death_year": normalized["death_year"],
        "nationality": normalized["nationality"],
        "verified_profile": bool(normalized.get("verified_profile")),
    }
    public_profile_meta = _build_public_profile_meta(
        source_flow=source_flow,
        materialized_at=_clean_text(existing_meta.get("materialized_at")) or _iso_now(),
        public_profile=public_profile,
        image_resolution=image_resolution,
        existing_meta=existing_meta,
    )
    identity_pack = {
        **existing_identity_pack,
        "display_name": display_name,
        "preferred_name": _clean_text(existing_identity_pack.get("preferred_name")) or display_name,
        "role": role or _clean_text(existing_identity_pack.get("role")),
        "current_role": role or _clean_text(existing_identity_pack.get("current_role")),
        "organization": organization or _clean_text(existing_identity_pack.get("organization")),
        "current_company": organization or _clean_text(existing_identity_pack.get("current_company")),
        "headline": normalized["headline"] or _clean_text(existing_identity_pack.get("headline")),
        "summary": normalized["short_description"] or normalized["bio"] or _clean_text(existing_identity_pack.get("summary")),
        "biography": normalized["bio"] or _clean_text(existing_identity_pack.get("biography")),
        "expertise_areas": expertise,
        "social_links": social_links,
        "preferred_contact_channel": (
            _clean_text(existing_identity_pack.get("preferred_contact_channel"))
            or next(iter(social_links.keys()), "")
        ),
    }
    return {
        "public_profile": public_profile,
        "persona_identity_pack": identity_pack,
        "public_profile_meta": public_profile_meta,
        "tagline": normalized["headline"],
        "public_intro": normalized["short_description"] or normalized["bio"],
        "description": normalized["short_description"] or normalized["bio"],
        "specialization": expertise[0] if expertise else role,
    }


def _build_speaking_style(
    profile: Dict[str, Any],
    identity_pack: Dict[str, Any],
    style_profile: Dict[str, Any],
) -> str:
    explicit = _clean_text(profile.get("speaking_style"))
    if explicit:
        return explicit

    tone_descriptors = _clean_unique_strings(
        [
            *_safe_list(identity_pack.get("tone_tags")),
            *_safe_list(style_profile.get("tone_descriptors")),
        ],
        limit=3,
    )
    sentence_profile = _safe_dict(style_profile.get("sentence_length_profile"))
    average_length = sentence_profile.get("average_length")

    parts: List[str] = []
    if tone_descriptors:
        parts.append(", ".join(tone_descriptors))
    if isinstance(average_length, (int, float)):
        if average_length <= 10:
            parts.append("generally concise")
        elif average_length >= 24:
            parts.append("detail-oriented")
        else:
            parts.append("balanced in detail")
    if not parts:
        return ""
    return f"{parts[0].capitalize()}" + (f", {parts[1]}." if len(parts) > 1 else ".")


def _build_key_achievements(profile: Dict[str, Any], claims: List[Dict[str, Any]], timeline_events: List[Dict[str, Any]]) -> List[str]:
    seeded = _safe_list(profile.get("key_achievements"))
    claim_values = [
        claim.get("claim_text")
        for claim in claims
        if claim.get("claim_type") in {"achievement", "credential", "media_appearance"}
    ]
    timeline_values = [
        event.get("title")
        for event in timeline_events
        if _clean_text(event.get("event_type")).lower() in {"award", "publication", "founded_company", "milestone"}
    ]
    return _clean_unique_strings([*seeded, *claim_values, *timeline_values], limit=6)


def _build_contributions(profile: Dict[str, Any], claims: List[Dict[str, Any]], timeline_events: List[Dict[str, Any]]) -> List[str]:
    seeded = _safe_list(profile.get("contributions"))
    claim_values = [
        claim.get("claim_text")
        for claim in claims
        if claim.get("claim_type") in {"project", "expertise", "media_appearance"}
    ]
    timeline_values = [event.get("description") or event.get("title") for event in timeline_events[:6]]
    return _clean_unique_strings([*seeded, *claim_values, *timeline_values], limit=6)


def _build_expertise(profile: Dict[str, Any], identity_pack: Dict[str, Any], public_topics: List[Dict[str, Any]]) -> List[str]:
    seeded = _safe_list(profile.get("areas_of_expertise"))
    identity = _safe_list(identity_pack.get("expertise_areas"))
    topic_names = [topic.get("name") for topic in public_topics]
    return _clean_unique_strings([*seeded, *identity, *topic_names], limit=6)


def _build_personality_traits(profile: Dict[str, Any], identity_pack: Dict[str, Any], style_profile: Dict[str, Any]) -> List[str]:
    seeded = _safe_list(profile.get("personality_traits"))
    tone_tags = _safe_list(identity_pack.get("tone_tags"))
    style_tags = _safe_list(style_profile.get("tone_descriptors"))
    return _clean_unique_strings([*seeded, *tone_tags, *style_tags], limit=6)


def build_marketplace_persona_payload(
    twin: Dict[str, Any],
    *,
    public_topics: Optional[List[Dict[str, Any]]] = None,
    answerability_score: float = 0.0,
    verified_claims_count: int = 0,
) -> Dict[str, Any]:
    profile = normalize_public_profile(twin)
    identity_pack = _safe_dict(profile.get("settings", {}).get("persona_identity_pack"))
    profile_meta = _safe_dict(profile.get("public_profile_meta"))
    topics = public_topics or []
    expertise = _build_expertise(profile, identity_pack, topics)
    short_description = _first_sentence(profile.get("bio")) or _clean_text(profile.get("bio"))

    return {
        "twin_id": twin.get("id"),
        "display_name": profile["display_name"],
        "occupation": _build_occupation(profile, expertise),
        "headline": profile["headline"],
        "bio": profile["bio"],
        "short_description": profile["short_description"] or short_description,
        "avatar_url": profile["image_url"] or profile["avatar_url"],
        "organization": profile["organization"],
        "role": profile["role"],
        "mind_label": profile["mind_label"],
        "answerability_score": _coerce_score_percent(answerability_score),
        "verified_claims_count": int(verified_claims_count or 0),
        "public_topics": topics,
        "areas_of_expertise": expertise,
        "personality_traits": _build_personality_traits(profile, identity_pack, {}),
        "pinned_questions": profile["pinned_questions"],
        "handle": profile["handle"],
        "verified_profile": bool(profile.get("verified_profile")),
        "profile_meta": profile_meta,
        "completeness_score": profile_meta.get("completeness_score"),
    }


def build_public_profile_pack(twin: Dict[str, Any]) -> Dict[str, Any]:
    profile = normalize_public_profile(twin)
    settings = _safe_dict(profile.get("settings"))
    identity_pack = _safe_dict(settings.get("persona_identity_pack"))
    profile_meta = _safe_dict(profile.get("public_profile_meta"))
    twin_id = str(twin.get("id") or "")

    answerability_score = _fetch_answerability_score(twin_id)
    verified_claims_count = _fetch_verified_claim_count(twin_id)
    public_topics = _fetch_public_topics(twin_id)
    claims = _fetch_public_claims(twin_id)
    timeline_events = _fetch_timeline_events(twin_id)
    style_profile = _fetch_style_profile(twin_id)

    birth_year, death_year, nationality = _identity_stat_from_claims(claims)
    birth_year = birth_year or profile.get("birth_year")
    death_year = death_year or profile.get("death_year")
    nationality = nationality or profile.get("nationality")
    expertise = _build_expertise(profile, identity_pack, public_topics)

    return {
        "id": twin_id,
        "name": profile["display_name"],
        "occupation": _build_occupation(profile, expertise),
        "headline": profile["headline"],
        "bio": profile["bio"],
        "short_description": profile["short_description"] or _first_sentence(profile["bio"]) or profile["bio"],
        "avatar_url": profile["image_url"] or profile["avatar_url"],
        "image_url": profile["image_url"] or profile["avatar_url"],
        "birth_year": birth_year,
        "death_year": death_year,
        "nationality": nationality,
        "verified_profile": bool(profile.get("verified_profile")),
        "answerability_score": answerability_score,
        "verified_claims_count": verified_claims_count,
        "public_topics": public_topics,
        "areas_of_expertise": expertise,
        "personality_traits": _build_personality_traits(profile, identity_pack, style_profile),
        "key_achievements": _build_key_achievements(profile, claims, timeline_events),
        "contributions": _build_contributions(profile, claims, timeline_events),
        "speaking_style": _build_speaking_style(profile, identity_pack, style_profile),
        "social_links": profile["social_links"],
        "education": _build_education_entries(claims, timeline_events, profile.get("education")),
        "work_experience": _build_work_entries(claims, timeline_events, profile.get("work_experience")),
        "pinned_questions": profile["pinned_questions"],
        "featured_content": _safe_list(profile.get("featured_content")),
        "mind_label": profile["mind_label"],
        "profile_meta": profile_meta,
        "completeness_score": profile_meta.get("completeness_score"),
        "extra": {},
        "created_at": twin.get("created_at"),
        "updated_at": twin.get("updated_at"),
    }
