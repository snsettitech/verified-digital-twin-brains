"""
Phase 5 quality benchmark (manual).

Runs a small live suite against a target twin to measure:
- fallback rate (generic failure responses)
- exact marker accuracy
- latest-marker correctness for recency queries

This script intentionally performs real network calls (Supabase/Pinecone/LLMs).
Do not run in CI.

Usage (PowerShell):
  cd backend
  $env:PHASE5_TEST_TWIN_ID="93fab8a3-8042-4d87-aa80-1040450e19ec"
  $env:PHASE5_EXPECTED_MARKER="PHASE5_MARKER_1770880449"
  python scripts/phase5_quality_benchmark.py
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

from modules.agent import run_agent_stream  # noqa: E402


TWIN_ID = os.getenv("PHASE5_TEST_TWIN_ID", "").strip()
EXPECTED = os.getenv("PHASE5_EXPECTED_MARKER", "").strip()

if not TWIN_ID:
    raise SystemExit("Missing PHASE5_TEST_TWIN_ID")
if not EXPECTED:
    raise SystemExit("Missing PHASE5_EXPECTED_MARKER")


QUERIES = [
    "What is the exact marker token from the latest realtime ingestion? Return only the marker.",
    "Tell me the most recent marker that was ingested for this twin.",
    f"Repeat the exact token {EXPECTED} and confirm if it exists.",
]


async def _ask(query: str) -> Dict[str, Any]:
    events_seen: List[Dict[str, Any]] = []
    answer_text = ""
    citations: List[str] = []

    async for event in run_agent_stream(twin_id=TWIN_ID, query=query, history=[]):
        events_seen.append(event)
        if not isinstance(event, dict):
            continue
        for node_payload in event.values():
            if not isinstance(node_payload, dict):
                continue
            if isinstance(node_payload.get("citations"), list):
                citations = [str(c) for c in node_payload["citations"] if c]
            msgs = node_payload.get("messages")
            if isinstance(msgs, list) and msgs:
                last = msgs[-1]
                content = getattr(last, "content", "")
                if isinstance(content, str) and content.strip():
                    answer_text = content.strip()

    return {
        "query": query,
        "answer": answer_text,
        "citations": citations,
        "events": len(events_seen),
    }


async def main() -> None:
    rounds = int(os.getenv("PHASE5_BENCH_ROUNDS", "5"))
    runs: List[Dict[str, Any]] = []
    for _ in range(rounds):
        for q in QUERIES:
            runs.append(await _ask(q))

    fallback_patterns = [
        "having trouble finding the words",
        "i need one concrete detail",
        "need one more detail",
        "encountered an error",
    ]

    token_re = re.compile(r"PHASE5_MARKER_\d+")

    fallback = 0
    exact_total = 0
    exact_ok = 0
    recent_total = 0
    recent_ok = 0
    recent_wrong = 0

    for r in runs:
        ans_lower = (r.get("answer") or "").lower()
        if any(p in ans_lower for p in fallback_patterns):
            fallback += 1

        q_lower = (r.get("query") or "").lower()
        found = token_re.findall(r.get("answer") or "")

        if "exact" in q_lower or "return only the marker" in q_lower:
            exact_total += 1
            if EXPECTED in found or (r.get("answer") or "").strip() == EXPECTED:
                exact_ok += 1

        if "most recent" in q_lower or "latest" in q_lower:
            recent_total += 1
            if EXPECTED in found or EXPECTED in (r.get("answer") or ""):
                recent_ok += 1
            if found and EXPECTED not in found:
                recent_wrong += 1

    summary = {
        "twin_id": TWIN_ID,
        "expected_marker": EXPECTED,
        "total_runs": len(runs),
        "fallback_rate": round(fallback / len(runs), 4) if runs else 0.0,
        "exact_accuracy": round(exact_ok / exact_total, 4) if exact_total else 0.0,
        "latest_expected_marker_rate": round(recent_ok / recent_total, 4) if recent_total else 0.0,
        "latest_wrong_marker_rate": round(recent_wrong / recent_total, 4) if recent_total else 0.0,
        "sample_outputs": runs[:6],
    }

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

