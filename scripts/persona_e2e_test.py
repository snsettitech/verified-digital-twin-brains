#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PersonaOn AI - End-to-End Persona Test Suite
Tests the full creation + chat pipeline for public figures.

Usage:
    # Test all 5 default personas
    python scripts/persona_e2e_test.py

    # Test a specific persona
    python scripts/persona_e2e_test.py --name "Elon Musk"

    # Test with a different provider
    python scripts/persona_e2e_test.py --name "Warren Buffett" --provider gemini

    # Skip research (use existing accounts)
    python scripts/persona_e2e_test.py --chat-only

    # Reset accounts and restart from scratch
    python scripts/persona_e2e_test.py --reset
"""

import argparse
import asyncio
import json
import os
import sys
import time

# Force UTF-8 stdout on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Load backend .env so we have the service key
try:
    _env_path = os.path.join(os.path.dirname(__file__), "..", "backend", ".env")
    if os.path.exists(_env_path):
        for _line in open(_env_path):
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip())
except Exception:
    pass
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import httpx

# ── Config ────────────────────────────────────────────────────────────────────
SUPABASE_URL = "https://jvtffdbuwyhmcynauety.supabase.co"
SUPABASE_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp2dGZmZGJ1d3lobWN5bmF1ZXR5Iiwi"
    "cm9sZSI6ImFub24iLCJpYXQiOjE3NjYwMTY1MzksImV4cCI6MjA4MTU5MjUzOX0"
    ".tRpBHBhL2GM9s6sSncrVrNnmtwxrzED01SzwjKRb37E"
)
# Service key is loaded from backend/.env (SUPABASE_SERVICE_KEY)
# Used for admin user creation (bypasses email confirmation)
API_BASE = "https://verified-digital-twin-brains.onrender.com"
TEST_PASSWORD = "TestPersonaQA#2025!"
POLL_INTERVAL_SECONDS = 15
RESEARCH_TIMEOUT_SECONDS = 900  # 15 min max

# ── Default personas ──────────────────────────────────────────────────────────
DEFAULT_PERSONAS = [
    {
        "name": "Elon Musk",
        "email": "qa.elon.musk@gmail.com",
        "hints": {"company": "Tesla, SpaceX"},
    },
    {
        "name": "Arnold Schwarzenegger",
        "email": "qa.arnold.schwarzenegger@gmail.com",
        "hints": {"location": "United States"},
    },
    {
        "name": "Warren Buffett",
        "email": "qa.warren.buffett@gmail.com",
        "hints": {"company": "Berkshire Hathaway"},
    },
    {
        "name": "Donald Trump",
        "email": "qa.donald.trump@gmail.com",
        "hints": {"location": "United States"},
    },
    {
        "name": "Narendra Modi",
        "email": "qa.narendra.modi@gmail.com",
        "hints": {"location": "India"},
    },
]

# ── Quality questions per persona (+ generic fallbacks) ───────────────────────
PERSONA_QUESTIONS = {
    "Elon Musk": [
        "What's your vision for humanity becoming multi-planetary?",
        "Why did you acquire Twitter and what are you trying to do with it?",
        "What do you think is the biggest threat to human civilization?",
        "How do you manage leading multiple companies simultaneously?",
        "What do people completely get wrong about you?",
    ],
    "Arnold Schwarzenegger": [
        "What drove you to leave Austria and come to America?",
        "How did your bodybuilding philosophy translate into acting and politics?",
        "What's your most important lesson from your political career as Governor?",
        "How do you handle failure and setbacks?",
        "What advice would you give to someone who wants to reinvent themselves?",
    ],
    "Warren Buffett": [
        "What's your single most important investing principle?",
        "Why do you still live in Omaha after all this success?",
        "What do you look for when evaluating a business?",
        "How do you think about risk?",
        "What's the biggest mistake investors make?",
    ],
    "Donald Trump": [
        "What makes America great and what threatened it?",
        "How do you handle criticism and negative media coverage?",
        "What was your biggest achievement as President?",
        "What's your approach to negotiation and deal-making?",
        "What do your opponents get most wrong about you?",
    ],
    "Narendra Modi": [
        "What does Viksit Bharat mean to you and how do you plan to achieve it?",
        "How has India's global standing changed since 2014?",
        "What is your vision for India's digital economy?",
        "How do you balance economic development with environmental concerns?",
        "What lesson from your early life shaped your leadership most?",
    ],
}

GENERIC_QUESTIONS = [
    "What drives you every single day?",
    "What's your biggest regret and what did you learn from it?",
    "What do most people completely get wrong about you?",
    "What's the most important thing you know that most people don't?",
    "If you could talk to your younger self, what would you say?",
]

QUALITY_RUBRIC = {
    "in_character": "Does it speak in first person as the persona? (0-10)",
    "substance": "Does it provide specific, substantive answers vs. generic? (0-10)",
    "no_ai_bleed": "Does it avoid phrases like 'As an AI' or breaking character? (0-10)",
    "conversational": "Does it end with a follow-up question or invitation? (0-10)",
    "persona_accuracy": "Does the answer align with the known views/style? (0-10)",
}


# ── Data classes ──────────────────────────────────────────────────────────────
@dataclass
class PersonaResult:
    name: str
    email: str
    jwt: str = ""
    twin_id: str = ""
    run_id: str = ""
    research_status: str = ""
    research_elapsed_s: float = 0
    chat_results: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    overall_score: float = 0


# ── Auth helpers ──────────────────────────────────────────────────────────────
async def supabase_signup_or_login(
    client: httpx.AsyncClient, email: str, password: str, full_name: str
) -> str:
    """Returns JWT access token.
    1. Try sign-in (account already exists).
    2. Try admin user creation with service key (bypasses email confirmation).
    3. Then sign in.
    """
    # Step 1: Try sign-in (fast path for existing accounts)
    r = await client.post(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"},
        json={"email": email, "password": password},
        timeout=30,
    )
    if r.status_code == 200:
        return r.json()["access_token"]

    # Step 2: Create user via admin API (requires service key, no email confirmation needed)
    service_key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if service_key:
        r_admin = await client.post(
            f"{SUPABASE_URL}/auth/v1/admin/users",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Content-Type": "application/json",
            },
            json={
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"full_name": full_name},
            },
            timeout=30,
        )
        if r_admin.status_code in (200, 201):
            # User created — now sign in
            await asyncio.sleep(0.5)
            r2 = await client.post(
                f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
                headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"},
                json={"email": email, "password": password},
                timeout=30,
            )
            if r2.status_code == 200:
                return r2.json()["access_token"]
            # Check if user already exists (422 with user_already_exists code)
        elif r_admin.status_code == 422:
            err = r_admin.json()
            if "already" in str(err).lower() or "exists" in str(err).lower():
                # Try resetting password via admin and sign in
                pass  # Fall through to error

    raise RuntimeError(f"Auth failed for {email}: {r.status_code} {r.text[:200]}")


def _auth_headers(jwt: str) -> dict:
    return {"Authorization": f"Bearer {jwt}", "Content-Type": "application/json"}


async def sync_user(client: httpx.AsyncClient, jwt: str) -> dict:
    r = await client.post(
        f"{API_BASE}/auth/sync-user",
        headers=_auth_headers(jwt),
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


async def get_my_twins(client: httpx.AsyncClient, jwt: str) -> list:
    r = await client.get(
        f"{API_BASE}/auth/my-twins",
        headers=_auth_headers(jwt),
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


async def create_profile(
    client: httpx.AsyncClient, jwt: str, full_name: str
) -> dict:
    r = await client.post(
        f"{API_BASE}/profile",
        headers=_auth_headers(jwt),
        json={"full_name": full_name, "build_mode": "name_only"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


async def start_deep_research(
    client: httpx.AsyncClient, jwt: str, name: str, hints: dict
) -> dict:
    r = await client.post(
        f"{API_BASE}/deep-research/runs",
        headers=_auth_headers(jwt),
        json={"name": name, "hints": hints},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


async def poll_research(
    client: httpx.AsyncClient, jwt: str, run_id: str
) -> dict:
    r = await client.get(
        f"{API_BASE}/deep-research/runs/{run_id}",
        headers=_auth_headers(jwt),
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


async def compile_to_twin(
    client: httpx.AsyncClient, jwt: str, run_id: str, twin_id: str
) -> dict:
    r = await client.post(
        f"{API_BASE}/deep-research/runs/{run_id}/compile-to-twin",
        headers=_auth_headers(jwt),
        json={"twin_id": twin_id},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()


async def send_chat(
    client: httpx.AsyncClient, jwt: str, twin_id: str, question: str
) -> tuple[str, dict]:
    """Send a chat message and return (response_text, metadata)."""
    r = await client.post(
        f"{API_BASE}/chat",
        headers=_auth_headers(jwt),
        json={"query": question, "twin_id": twin_id},
        timeout=60,
    )
    if r.status_code != 200:
        return f"[ERROR {r.status_code}] {r.text[:200]}", {}

    # /chat returns compiled JSON (non-streaming)
    try:
        data = r.json()
        # Response is in 'message' key based on API inspection
        text = (
            data.get("message")
            or data.get("response")
            or data.get("answer")
            or data.get("content")
            or str(data)
        )
        meta = {
            "model": data.get("model_used", "?"),
            "provider": data.get("provider_used", "?"),
            "confidence": data.get("confidence_score", 0),
            "type": data.get("response_type", "?"),
        }
        return text, meta
    except Exception:
        return r.text[:500], {}


# ── Quality scoring ───────────────────────────────────────────────────────────
def score_response(persona_name: str, question: str, response: str) -> dict:
    """Heuristic quality scoring (each dimension 0-10, total out of 100)."""
    r = response.lower()
    first_name_lower = persona_name.split()[0].lower()

    # in_character (0-10): first-person voice, no AI bleed
    first_person = sum(r.count(p) for p in [" i ", " i'm", " i've", " my ", " me ", "myself", "i've"])
    ai_bleed = any(x in r for x in ["as an ai", "as a language model", "as a digital twin", "i cannot assist"])
    thin_evidence = "i don't have a lot in my knowledge base" in r
    in_char = max(0, 7 - (5 if ai_bleed else 0) + min(3, first_person // 2) - (1 if thin_evidence else 0))
    scores = {"in_character": min(10, in_char)}

    # substance (0-10): length and specificity
    word_count = len(response.split())
    digit_count = sum(1 for c in response if c.isdigit())
    scores["substance"] = min(10, max(1, word_count // 15) + min(2, digit_count // 3))

    # no_ai_bleed (0-10)
    scores["no_ai_bleed"] = 0 if ai_bleed else 10

    # conversational (0-10): ends with a question
    stripped = response.strip()
    scores["conversational"] = 9 if stripped.endswith("?") else (5 if "?" in stripped[-150:] else 2)

    # persona_accuracy (0-10): not breaking character, no third-person self-reference
    third_ref = f"{first_name_lower} would" in r or f"as {first_name_lower}" in r
    scores["persona_accuracy"] = max(0, 8 - (4 if third_ref else 0) - (2 if thin_evidence else 0))

    total = sum(scores.values())  # max = 50
    pct = round(total / 50 * 100, 1)
    scores["total"] = total
    scores["pct"] = pct
    return scores


# ── Per-persona test runner ───────────────────────────────────────────────────
async def run_persona_test(persona: dict, chat_only: bool = False, reset: bool = False) -> PersonaResult:
    result = PersonaResult(name=persona["name"], email=persona["email"])
    print(f"\n{'='*70}")
    print(f"  PERSONA: {persona['name']}")
    print(f"{'='*70}")

    async with httpx.AsyncClient(follow_redirects=True) as client:
        # ── Step 1: Auth ──
        print(f"[1/6] Authenticating {persona['email']}...")
        try:
            result.jwt = await supabase_signup_or_login(
                client, persona["email"], TEST_PASSWORD, persona["name"]
            )
            print(f"      ✓ JWT obtained")
        except Exception as e:
            result.errors.append(f"Auth failed: {e}")
            print(f"      ✗ {e}")
            return result

        # ── Step 2: Sync user ──
        print("[2/6] Syncing user to backend...")
        try:
            await sync_user(client, result.jwt)
            print("      ✓ User synced")
        except Exception as e:
            result.errors.append(f"Sync failed: {e}")
            print(f"      ✗ {e}")
            return result

        # ── Step 3: Get/create profile ──
        print("[3/6] Getting or creating profile...")
        try:
            twins = await get_my_twins(client, result.jwt)
            if twins:
                result.twin_id = twins[0]["id"]
                print(f"      ✓ Existing twin: {result.twin_id}")
            else:
                profile = await create_profile(client, result.jwt, persona["name"])
                result.twin_id = profile["id"]
                print(f"      ✓ Created twin: {result.twin_id}")
        except Exception as e:
            result.errors.append(f"Profile failed: {e}")
            print(f"      ✗ {e}")
            return result

        if chat_only:
            print("[4-5/6] Skipping research (--chat-only)")
        else:
            # ── Step 4: Start deep research ──
            print(f"[4/6] Starting deep research for '{persona['name']}'...")
            try:
                run_data = await start_deep_research(
                    client, result.jwt, persona["name"], persona.get("hints", {})
                )
                result.run_id = run_data["run_id"]
                # Use twin_id from run if provided (authoritative)
                if run_data.get("twin_id"):
                    result.twin_id = run_data["twin_id"]
                print(f"      ✓ Run created: {result.run_id} (twin: {result.twin_id})")
            except Exception as e:
                result.errors.append(f"Research start failed: {e}")
                print(f"      ✗ {e}")
                return result

            # ── Step 5: Poll until complete ──
            print(f"[5/6] Polling research (timeout={RESEARCH_TIMEOUT_SECONDS}s)...")
            t0 = time.time()
            last_status = ""
            while time.time() - t0 < RESEARCH_TIMEOUT_SECONDS:
                try:
                    status_data = await poll_research(client, result.jwt, result.run_id)
                    status = status_data.get("status", "unknown")
                    if status != last_status:
                        elapsed = int(time.time() - t0)
                        print(f"      [{elapsed:>4}s] status={status}")
                        last_status = status
                    if status == "completed":
                        result.research_status = "completed"
                        result.research_elapsed_s = round(time.time() - t0, 1)
                        break
                    if status == "failed":
                        result.research_status = "failed"
                        result.errors.append(
                            f"Research failed: {status_data.get('error_message', 'unknown')}"
                        )
                        print(f"      ✗ Research failed")
                        return result
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)
                except Exception as e:
                    print(f"      ⚠ Poll error: {e}")
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)
            else:
                result.errors.append("Research timed out")
                print("      ✗ Research timed out")
                return result

            # Compile to twin
            print(f"      Compiling to twin {result.twin_id}...")
            try:
                compile_result = await compile_to_twin(
                    client, result.jwt, result.run_id, result.twin_id
                )
                print(f"      ✓ Compiled. Research took {result.research_elapsed_s}s")
            except Exception as e:
                result.errors.append(f"Compile failed: {e}")
                print(f"      ✗ Compile failed: {e}")
                return result

        # ── Step 6: Chat quality test ──
        questions = PERSONA_QUESTIONS.get(persona["name"], GENERIC_QUESTIONS)
        print(f"[6/6] Testing chat ({len(questions)} questions)...")
        scores_all = []
        for i, question in enumerate(questions):
            print(f"\n  Q{i+1}: {question}")
            try:
                response, meta = await send_chat(client, result.jwt, result.twin_id, question)
                print(f"  A:  {response[:500]}{'...' if len(response) > 500 else ''}")
                print(f"      [model={meta.get('model','?')} | provider={meta.get('provider','?')} | confidence={meta.get('confidence',0):.2f}]")
                scores = score_response(persona["name"], question, response)
                print(f"      Score: {scores['pct']}/100 | in_char={scores['in_character']} sub={scores['substance']} no_ai={scores['no_ai_bleed']} conv={scores['conversational']} persona={scores['persona_accuracy']}")
                result.chat_results.append({
                    "question": question,
                    "response": response,
                    "meta": meta,
                    "scores": scores,
                })
                scores_all.append(scores["pct"])
            except Exception as e:
                print(f"      ERROR: Chat error: {e}")
                result.errors.append(f"Chat error on Q{i+1}: {e}")

        if scores_all:
            result.overall_score = round(sum(scores_all) / len(scores_all), 1)

    return result


# ── Report printer ────────────────────────────────────────────────────────────
def print_report(results: list[PersonaResult]) -> None:
    print(f"\n\n{'='*70}")
    print("  FINAL REPORT")
    print(f"{'='*70}")
    print(f"{'Persona':<28} {'Score':>6} {'Research':>10} {'Errors':>6}")
    print(f"{'-'*28} {'-'*6} {'-'*10} {'-'*6}")

    total_scores = []
    for r in results:
        status = f"{r.research_elapsed_s}s" if r.research_elapsed_s else r.research_status or "skipped"
        err = str(len(r.errors)) if r.errors else "-"
        score_str = f"{r.overall_score}/100" if r.overall_score else "N/A"
        print(f"{r.name:<28} {score_str:>6} {status:>10} {err:>6}")
        if r.overall_score:
            total_scores.append(r.overall_score)

    if total_scores:
        avg = round(sum(total_scores) / len(total_scores), 1)
        print(f"\n  Average quality score: {avg}/100")
        grade = "A" if avg >= 80 else "B" if avg >= 65 else "C" if avg >= 50 else "F"
        print(f"  Grade: {grade}")

    for r in results:
        if r.errors:
            print(f"\n  ⚠ {r.name} errors:")
            for e in r.errors:
                print(f"    - {e}")

    print(f"\n  Run at: {datetime.utcnow().isoformat()}Z")


# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    parser = argparse.ArgumentParser(description="PersonaOn E2E test suite")
    parser.add_argument("--name", help="Test a single persona by name")
    parser.add_argument("--chat-only", action="store_true", help="Skip research, test chat only")
    parser.add_argument("--reset", action="store_true", help="Delete existing data before testing")
    parser.add_argument("--sequential", action="store_true", help="Run personas sequentially (default: parallel)")
    args = parser.parse_args()

    if args.name:
        personas = [p for p in DEFAULT_PERSONAS if p["name"].lower() == args.name.lower()]
        if not personas:
            # Custom persona not in defaults
            personas = [{"name": args.name, "email": f"qa.{args.name.lower().replace(' ', '.')}@gmail.com", "hints": {}}]
    else:
        personas = DEFAULT_PERSONAS

    print(f"PersonaOn AI — E2E Test Suite")
    print(f"Testing {len(personas)} persona(s): {', '.join(p['name'] for p in personas)}")
    print(f"API: {API_BASE}")
    print(f"Mode: {'chat-only' if args.chat_only else 'full (research + chat)'}")

    if args.sequential:
        results = []
        for p in personas:
            r = await run_persona_test(p, chat_only=args.chat_only, reset=args.reset)
            results.append(r)
    else:
        tasks = [run_persona_test(p, chat_only=args.chat_only, reset=args.reset) for p in personas]
        results = await asyncio.gather(*tasks)

    print_report(list(results))

    # Exit 1 if any had errors
    if any(r.errors for r in results):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
