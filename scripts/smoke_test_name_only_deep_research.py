#!/usr/bin/env python3
"""
Smoke test for Name -> Deep Research JSON flow.

Usage:
  AUTH_TOKEN=<jwt> BASE_URL=https://api.example.com python scripts/smoke_test_name_only_deep_research.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict

import requests

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "").strip()
PERSON_NAME = os.getenv("SMOKE_PERSON_NAME", "Satya Nadella")
TIMEOUT_SECONDS = int(os.getenv("SMOKE_TIMEOUT_SECONDS", "600"))
POLL_SECONDS = int(os.getenv("SMOKE_POLL_SECONDS", "5"))


def _print(msg: str) -> None:
    print(msg, flush=True)


def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "Content-Type": "application/json",
    }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _validate_result_contract(result: Dict[str, Any]) -> None:
    required_top = {
        "run_id",
        "input",
        "claimed_identity",
        "bio",
        "profile_summary",
        "timeline",
        "claims",
        "known_unknowns",
        "suggested_followup_questions",
        "crawl_stats",
        "quality",
        "sources",
    }
    _require(required_top.issubset(set(result.keys())), "Missing top-level keys in result JSON")

    source_ids = {s.get("source_id") for s in result.get("sources", [])}
    for item in result.get("timeline", []):
        _require(bool(item.get("citations")), "Timeline item missing citations")
        _require(set(item.get("citations", [])).issubset(source_ids), "Timeline citation has unknown source_id")
    for item in result.get("claims", []):
        _require(bool(item.get("citations")), "Claim item missing citations")
        _require(set(item.get("citations", [])).issubset(source_ids), "Claim citation has unknown source_id")


def main() -> int:
    _print("=" * 72)
    _print("NAME-ONLY DEEP RESEARCH SMOKE TEST")
    _print("=" * 72)
    _print(f"Base URL: {BASE_URL}")
    _print(f"Person:   {PERSON_NAME}")
    _print(f"Started:  {datetime.now(timezone.utc).isoformat()}")
    _print("=" * 72)

    if not AUTH_TOKEN:
        _print("FAIL: AUTH_TOKEN is required for this smoke test.")
        return 1

    create_payload = {
        "name": PERSON_NAME,
        "hints": {
            "location": os.getenv("SMOKE_HINT_LOCATION") or None,
            "company": os.getenv("SMOKE_HINT_COMPANY") or None,
            "website": os.getenv("SMOKE_HINT_WEBSITE") or None,
        },
        "idempotency_key": f"smoke-{int(time.time())}",
    }

    _print("POST /deep-research/runs")
    create_resp = requests.post(
        f"{BASE_URL}/deep-research/runs",
        headers=_headers(),
        data=json.dumps(create_payload),
        timeout=30,
    )
    if create_resp.status_code != 200:
        _print(f"FAIL: create run returned {create_resp.status_code}: {create_resp.text[:500]}")
        return 1

    create_data = create_resp.json()
    run_id = create_data["run_id"]
    _print(f"Run created: {run_id} (status={create_data.get('status')})")

    deadline = time.time() + TIMEOUT_SECONDS
    latest_status = None
    while time.time() < deadline:
        status_resp = requests.get(
            f"{BASE_URL}/deep-research/runs/{run_id}",
            headers=_headers(),
            timeout=30,
        )
        if status_resp.status_code != 200:
            _print(f"FAIL: status returned {status_resp.status_code}: {status_resp.text[:500]}")
            return 1

        status_data = status_resp.json()
        latest_status = status_data.get("status")
        _print(f"Status: {latest_status}")

        if latest_status in {"completed", "failed"}:
            break
        time.sleep(POLL_SECONDS)

    if latest_status != "completed":
        _print(f"FAIL: run did not complete successfully (last_status={latest_status})")
        return 1

    result_resp = requests.get(
        f"{BASE_URL}/deep-research/runs/{run_id}/result.json",
        headers=_headers(),
        timeout=30,
    )
    if result_resp.status_code != 200:
        _print(f"FAIL: result endpoint returned {result_resp.status_code}: {result_resp.text[:500]}")
        return 1

    result = result_resp.json()
    try:
        _validate_result_contract(result)
    except Exception as exc:
        _print(f"FAIL: result JSON contract validation failed: {exc}")
        return 1

    _print("PASS: flow completed and result JSON contract validated.")
    _print(f"Completed: {datetime.now(timezone.utc).isoformat()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
