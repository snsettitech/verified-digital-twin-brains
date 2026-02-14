from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_URL = "http://127.0.0.1:3000"
BACKEND_URL = "http://127.0.0.1:8000"
PROMPTS = ["hi", "who are you?", "do you know antler"]


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"'))


def parse_sse_payload(raw_text: str) -> Dict[str, Any]:
    lines = [line.strip() for line in (raw_text or "").splitlines() if line.strip()]
    events: List[Dict[str, Any]] = []
    content_parts: List[str] = []
    metadata: Optional[Dict[str, Any]] = None
    clarify: Optional[Dict[str, Any]] = None
    for line in lines:
        try:
            event = json.loads(line)
        except Exception:
            continue
        events.append(event)
        if event.get("type") == "metadata":
            metadata = event
        elif event.get("type") == "content":
            token = event.get("content") or event.get("token") or ""
            content_parts.append(str(token))
        elif event.get("type") == "clarify":
            clarify = event
    return {
        "events": events,
        "content": "".join(content_parts).strip(),
        "metadata": metadata,
        "clarify": clarify,
    }


def ensure_twin() -> Dict[str, Any]:
    service_key = os.environ["SUPABASE_SERVICE_KEY"]
    supabase_url = os.environ["SUPABASE_URL"]
    headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}"}
    query = f"{supabase_url}/rest/v1/twins?select=id,name,settings,created_at&order=created_at.desc&limit=50"
    res = requests.get(query, headers=headers, timeout=20)
    res.raise_for_status()
    rows = res.json()
    for row in rows:
        settings = row.get("settings") if isinstance(row.get("settings"), dict) else {}
        widget_settings = settings.get("widget_settings") if isinstance(settings, dict) else {}
        token_value = (widget_settings or {}).get("share_token")
        if token_value:
            return row
    raise RuntimeError("No twin with share token found in Supabase `twins.settings.widget_settings.share_token`")


def get_share_from_twin_row(twin_row: Dict[str, Any]) -> Dict[str, Any]:
    settings = twin_row.get("settings") if isinstance(twin_row.get("settings"), dict) else {}
    widget_settings = settings.get("widget_settings") if isinstance(settings, dict) else {}
    share_token = (widget_settings or {}).get("share_token")
    public_enabled = bool((widget_settings or {}).get("public_share_enabled"))
    if not share_token:
        raise RuntimeError("Selected twin has no share_token")
    return {
        "share_token": share_token,
        "public_share_enabled": public_enabled,
    }


def run_public_api_prompt(twin_id: str, share_token: str, prompt: str) -> Dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(
            f"{BACKEND_URL}/public/chat/{twin_id}/{share_token}",
            headers=headers,
            json={"message": prompt, "conversation_history": []},
            timeout=25,
        )
        status = response.status_code
        payload = response.json() if response.text else {}
    except requests.RequestException:
        status = 408
        payload = {}

    assistant = payload.get("response") or payload.get("message") or ""
    return {
        "prompt": prompt,
        "endpoint": f"/public/chat/{twin_id}/{share_token}",
        "status": status,
        "assistant": assistant,
        "confidence_score": payload.get("confidence_score"),
        "citations_count": len(payload.get("citations") or []),
        "clarify": {
            "clarification_id": payload.get("clarification_id"),
            "question": payload.get("question"),
        }
        if payload.get("status") == "queued"
        else None,
    }


def run_public_ui_prompt(page, twin_id: str, prompt: str) -> Dict[str, Any]:
    page.fill('textarea[aria-label="Chat message input"]', prompt)
    with page.expect_response(
        lambda res: res.request.method == "POST"
        and (f"/public/chat/{twin_id}/" in res.url or res.url.endswith(f"/chat/{twin_id}")),
        timeout=25000,
    ) as resp_info:
        page.press('textarea[aria-label="Chat message input"]', "Enter")

    response = resp_info.value
    raw = response.text()
    try:
        payload = json.loads(raw) if raw else {}
    except Exception:
        payload = {}

    assistant = payload.get("response") or payload.get("message") or ""
    endpoint_url = response.url
    return {
        "prompt": prompt,
        "status": response.status,
        "endpoint": endpoint_url,
        "endpoint_type": "public_chat" if "/public/chat/" in endpoint_url else "legacy_chat",
        "assistant": assistant,
        "confidence_score": payload.get("confidence_score"),
        "citations_count": len(payload.get("citations") or []),
        "queued": payload.get("status") == "queued",
    }


def ensure_logged_in(page, target_url: str) -> None:
    page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
    if "/auth/login" not in page.url:
        return

    email = os.environ["TEST_ACCOUNT_EMAIL"]
    password = os.environ["TEST_ACCOUNT_PASSWORD"]
    page.fill('input[type="email"]', email)
    page.fill('input[type="password"]', password)
    page.click('button:has-text("Sign in")')
    page.wait_for_url(re.compile(r".*/dashboard.*"), timeout=60000)
    page.goto(target_url, wait_until="domcontentloaded", timeout=60000)


def main() -> None:
    load_env_file(REPO_ROOT / ".env")
    load_env_file(REPO_ROOT / "backend" / ".env")
    twin = ensure_twin()
    print(f"[walkthrough] twin_id={twin.get('id')}")
    twin_id = twin["id"]
    share = get_share_from_twin_row(twin)
    print("[walkthrough] share ready")
    share_token = share["share_token"]

    before = [run_public_api_prompt(twin_id, share_token, prompt) for prompt in PROMPTS]

    simulator_url = (
        f"{FRONTEND_URL}/dashboard/simulator/public?"
        f"twin_id={twin_id}&share_token={share_token}"
    )
    after: List[Dict[str, Any]] = []
    screenshot_path = REPO_ROOT / "tmp" / "public_simulator_walkthrough.png"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        ensure_logged_in(page, simulator_url)
        page.wait_for_selector('textarea[aria-label="Chat message input"]', timeout=60000)

        for prompt in PROMPTS:
            try:
                trace = run_public_ui_prompt(page, twin_id, prompt)
            except PlaywrightTimeoutError:
                trace = {
                    "prompt": prompt,
                    "status": 408,
                    "endpoint": None,
                    "endpoint_type": "none",
                    "assistant": "",
                    "confidence_score": None,
                    "citations_count": 0,
                    "queued": False,
                }
            after.append(trace)
            page.wait_for_timeout(800)

        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot_path), full_page=True)
        context.close()
        browser.close()

    executed_at = requests.get(f"{BACKEND_URL}/health", timeout=10).headers.get("date")
    output = {
        "executed_at": executed_at,
        "frontend_url": FRONTEND_URL,
        "backend_url": BACKEND_URL,
        "simulator_url": simulator_url,
        "twin_id": twin_id,
        "share_token_preview": f"{share_token[:4]}...{share_token[-4:]}",
        "prompts": PROMPTS,
        "before_public_api": before,
        "after_public_simulator_ui": after,
        "screenshot": str(screenshot_path.relative_to(REPO_ROOT)),
    }

    out_dir = REPO_ROOT / "tmp"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "public_simulator_walkthrough.json"
    md_path = out_dir / "public_simulator_walkthrough.md"
    json_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    md_lines = [
        "# Public Simulator Walkthrough",
        "",
        f"- Executed at: {output['executed_at']}",
        f"- Frontend: {FRONTEND_URL}",
        f"- Backend: {BACKEND_URL}",
        f"- Simulator URL: {simulator_url}",
        f"- Twin ID: {twin_id}",
        f"- Share token: {output['share_token_preview']}",
        f"- Screenshot: `{output['screenshot']}`",
        "",
        "## Before (Direct Public API `/public/chat/{twin}/{token}`)",
    ]
    for row in before:
        md_lines.append(
            f"- `{row['prompt']}` -> status {row['status']}, confidence={row['confidence_score']}, "
            f"citations={row['citations_count']}, endpoint=`{row['endpoint']}`"
        )
        md_lines.append(f"  - assistant: {json.dumps(row['assistant'])}")
    md_lines.append("")
    md_lines.append("## After (UI on `/dashboard/simulator/public`)")
    for row in after:
        md_lines.append(
            f"- `{row['prompt']}` -> status {row['status']}, endpoint_type={row['endpoint_type']}, "
            f"confidence={row['confidence_score']}, citations={row['citations_count']}, queued={row['queued']}"
        )
        md_lines.append(f"  - endpoint: `{row['endpoint']}`")
        md_lines.append(f"  - assistant: {json.dumps(row['assistant'])}")
    md_lines.append("")
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"WALKTHROUGH_JSON={json_path}")
    print(f"WALKTHROUGH_MD={md_path}")


if __name__ == "__main__":
    main()
