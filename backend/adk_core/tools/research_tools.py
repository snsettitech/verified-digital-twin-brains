"""Research gathering tools for ADK."""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any, Dict, List, Optional

from google.adk.tools import ToolContext

from modules.firecrawl_client import FirecrawlResult, get_firecrawl_client
from modules.research_claim_web_search import SearchResult, create_search_provider_with_fallback

MAX_RESEARCH_RESULTS = max(2, min(int(os.getenv("ADK_RESEARCH_MAX_RESULTS", "3")), 8))
MAX_RESEARCH_SCRAPES = max(1, min(int(os.getenv("ADK_RESEARCH_MAX_SCRAPES", "2")), 6))
MAX_SOURCE_TEXT_CHARS = max(300, min(int(os.getenv("ADK_RESEARCH_MAX_SOURCE_TEXT_CHARS", "700")), 3000))
MAX_SNIPPET_CHARS = max(160, min(int(os.getenv("ADK_RESEARCH_MAX_SNIPPET_CHARS", "250")), 800))
MAX_QUOTE_CANDIDATES = max(3, min(int(os.getenv("ADK_RESEARCH_MAX_QUOTE_CANDIDATES", "8")), 16))


def _quote_candidates(source_id: str, text: str) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for match in re.findall(r"\"([^\"]{25,280})\"", text or ""):
        quote = re.sub(r"\s+", " ", match).strip()
        if len(quote.split()) < 5:
            continue
        results.append(
            {
                "quote": quote,
                "source_id": source_id,
                "confidence": 0.65,
                "context": quote[:180],
            }
        )
        if len(results) >= 4:
            break
    return results


def _research_queries(
    *,
    subject_name: str,
    location: str = "",
    company: str = "",
    website: str = "",
) -> List[str]:
    base = [subject_name]
    if company:
        base.append(f"{subject_name} {company}")
    if location:
        base.append(f"{subject_name} {location}")
    if website:
        domain = website.replace("https://", "").replace("http://", "").strip("/")
        base.append(f"{subject_name} site:{domain}")
    base.append(f"{subject_name} interview")
    base.append(f"{subject_name} biography")
    base.append(f"{subject_name} quote")
    deduped: List[str] = []
    seen = set()
    for query in base:
        cleaned = re.sub(r"\s+", " ", query).strip()
        if not cleaned or cleaned.lower() in seen:
            continue
        seen.add(cleaned.lower())
        deduped.append(cleaned)
    return deduped[:6]


async def gather_public_research(
    subject_name: str,
    location: str = "",
    company: str = "",
    website: str = "",
    tool_context: Optional[ToolContext] = None,
) -> Dict[str, Any]:
    """
    Gather public-source research material for a subject.

    The tool performs bounded web search, scrapes a small set of sources, and
    stores the normalized payload in session state for downstream ADK agents.
    """
    provider = create_search_provider_with_fallback()
    queries = _research_queries(
        subject_name=subject_name,
        location=location,
        company=company,
        website=website,
    )

    search_results: List[SearchResult] = []
    for query in queries:
        results = await provider.search(query, num_results=4)
        search_results.extend(results)

    deduped: List[SearchResult] = []
    seen_urls = set()
    for result in search_results:
        if not result.url or result.url in seen_urls:
            continue
        seen_urls.add(result.url)
        deduped.append(result)
        if len(deduped) >= MAX_RESEARCH_RESULTS:
            break

    firecrawl = get_firecrawl_client()
    crawl_payloads: Dict[str, FirecrawlResult] = {}
    if firecrawl and deduped:
        scrape_results = await asyncio.gather(
            *[firecrawl.scrape_with_retry(item.url) for item in deduped[:MAX_RESEARCH_SCRAPES]],
            return_exceptions=True,
        )
        for item, scrape_result in zip(deduped[:MAX_RESEARCH_SCRAPES], scrape_results):
            if isinstance(scrape_result, Exception):
                continue
            crawl_payloads[item.url] = scrape_result

    source_registry: List[Dict[str, Any]] = []
    quote_candidates: List[Dict[str, Any]] = []
    for idx, result in enumerate(deduped, start=1):
        scrape = crawl_payloads.get(result.url)
        extracted_text = ""
        quality = "search_only"
        if scrape and scrape.success:
            extracted_text = (scrape.content or "")[:MAX_SOURCE_TEXT_CHARS]
            quality = scrape.quality.value
            quote_candidates.extend(_quote_candidates(f"src-{idx}", extracted_text))
        source_registry.append(
            {
                "source_id": f"src-{idx}",
                "url": result.url,
                "title": result.title,
                "snippet": (result.snippet or "")[:MAX_SNIPPET_CHARS],
                "extracted_text": extracted_text,
                "provider": result.source or getattr(provider, "name", "unknown"),
                "quality": quality,
                "published_at": result.published_date,
            }
        )

    payload = {
        "subject_name": subject_name,
        "queries": queries,
        "source_registry": source_registry,
        "verified_quote_candidates": quote_candidates[:12],
        "gather_stats": {
            "search_provider": getattr(provider, "name", "unknown"),
            "source_count": len(source_registry),
            "scraped_count": len(crawl_payloads),
            "source_text_chars": MAX_SOURCE_TEXT_CHARS,
        },
    }
    if tool_context:
        tool_context.state["gathered_research_json"] = json.dumps(payload)
    return payload
