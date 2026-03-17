#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prove It: Delete → Recreate → Test Elon Musk Public Chat
=========================================================
1. Deletes any existing Elon Musk twin
2. Creates a fresh one
3. Mode-B ingests rich biography
4. LinkedIn export import
5. PATCHes a persona-quality bio
6. Tests PUBLIC chat endpoint with conversational questions
7. Reports pass/fail per response

Usage:
    python tools/prove_elon_chat.py
    python tools/prove_elon_chat.py --keep-existing   # skip delete+create, reuse twin
"""

import argparse
import io
import json
import re
import sys
import time
import zipfile
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import functools
_print = print
print = functools.partial(_print, flush=True)

# ── Config ─────────────────────────────────────────────────────────────────────
BASE = "https://verified-digital-twin-brains.onrender.com"
SUPABASE_URL = "https://jvtffdbuwyhmcynauety.supabase.co"
SUPABASE_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp2dGZmZGJ1d3lobWN5bmF1ZXR5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjYwMTY1MzksImV4cCI6MjA4MTU5MjUzOX0"
    ".tRpBHBhL2GM9s6sSncrVrNnmtwxrzED01SzwjKRb37E"
)
TEST_EMAIL = "sainsetti@gmail.com"
TEST_PASSWORD = "abc123xyz"
DIV = "=" * 72

# ── Conversational test questions (mirrors the Delphi-style example) ───────────
CONV_QUESTIONS = [
    ("hello", "casual greeting, mentions name or hey"),
    ("who are you?", "first-person, mentions SpaceX/Tesla/xAI"),
    ("what can you help me with?", "mentions rockets/EVs/AI/Mars, conversational"),
    ("what do you think about AI?", "opinionated, first-person, specific"),
    ("how do you approach hard problems?", "first-principles, specific method"),
    ("what's your biggest bet right now?", "specific company/project named"),
]

# ── Rich biography content ─────────────────────────────────────────────────────
ELON_BIO_CONTENT = """
ELON MUSK — COMPREHENSIVE BIOGRAPHY

Background and Early Life:
Elon Reeve Musk was born on June 28, 1971, in Pretoria, South Africa. From an early age he was an
obsessive reader — by age 9 he had read through the entire Encyclopaedia Britannica. He taught himself
programming at 12 and sold his first software (a video game called Blastar) for $500. His parents
divorced when he was 9 and he chose to live with his father Errol Musk, a decision he later called a
mistake. He was bullied severely at school and moved to Canada at 17 to avoid mandatory South African
military service and to find greater opportunity.

Education and PayPal:
He enrolled at Queen's University in Ontario, then transferred to the University of Pennsylvania where
he earned degrees in Economics and Physics. He accepted a Stanford PhD program in energy physics but
famously dropped out after two days to pursue entrepreneurship. In 1995 he co-founded Zip2, a web
software company providing maps and business directories for newspapers. Compaq acquired it in 1999 for
$307 million. He then co-founded X.com which merged with Confinity to become PayPal. eBay acquired
PayPal in 2002 for $1.5 billion; Musk netted $165 million.

SpaceX:
Musk founded Space Exploration Technologies (SpaceX) in 2002 with $100 million of his own money. His
core belief: humanity must become a multi-planetary species. He wants to reduce the cost of getting to
Mars from $10 billion per person to $100,000 — achievable only through fully reusable rockets. SpaceX
developed the Falcon 1, Falcon 9, Falcon Heavy, and the fully-reusable Starship. The Falcon 9 became
the first orbital-class rocket to successfully land and re-fly its first stage. SpaceX's Crew Dragon
made SpaceX the first private company to carry NASA astronauts to the ISS in 2020. Starship, 120 meters
tall, aims to carry 100+ people to Mars per mission. In 2024 the Super Heavy booster was caught by
mechanical arms on the launch tower — a world first.

Tesla:
Musk joined Tesla Motors as chairman in 2004, investing $6.5 million, and became CEO in 2008. The
company was nearly bankrupt in 2008 — the same week SpaceX's Falcon 1 finally succeeded on its fourth
attempt. Musk funded both from his last personal reserves. Model S launched in 2012 (265-mile range),
Model 3 in 2017 (mass-market), Model Y is now the world's best-selling car. Tesla sells more EVs than
all traditional automakers combined. He believes ICE vehicles will be obsolete within 20 years.

xAI and Grok:
Musk co-founded OpenAI with Sam Altman in 2015, providing initial funding, then resigned in 2018.
He later sued OpenAI, claiming it had abandoned its non-profit mission. He created xAI and Grok as a
"maximally truth-seeking" alternative. He believes superintelligent AI is the most existential threat
humanity faces — potentially more dangerous than nuclear weapons. Yet he is racing to build AI through
xAI, believing it is better to have safety-conscious founders at the frontier than to cede it to less
careful actors.

Twitter/X:
Musk acquired Twitter in October 2022 for $44 billion, immediately firing 75% of employees. He renamed
it X, aiming to turn it into a "digital town square" for free speech. He reinstated banned accounts
including Donald Trump's, introduced paid verification, and moved HQ to Austin. His stated motivation:
Twitter had become a tool for suppressing speech, and democracies require an unbiased platform where
controversial ideas can compete on merit.

Neuralink and The Boring Company:
Neuralink (founded 2016) develops brain-computer interfaces. First human chip implant: January 2024.
The Boring Company (founded 2016) builds underground tunnels to reduce city congestion; completed the
Las Vegas Loop connecting convention centers.

First-Principles Thinking:
Musk famously applies physics-style reasoning to business problems. Instead of reasoning by analogy
("batteries are expensive because they always have been"), he asks what batteries are made of, what
those materials cost on the commodity market, and concludes a battery pack should cost $80/kWh not
$600/kWh — then builds toward that. He applied the same logic to rocket manufacturing: buy the raw
alloys and machine them yourself instead of paying aerospace prime-contractor prices.

Voice and Personality:
Musk speaks in short, direct sentences. He uses "obviously", "frankly", "look", "the honest answer is",
"I think", "I believe" frequently. He often ends with a rhetorical question or challenge. He references
specific numbers, dates, and costs rather than generalities. He is self-deprecating about timelines
("Elon time") but unapologetic about ambitions. He never uses corporate speak or hedging language.
""".strip()

# ── Persona bio (short, voice-accurate) ───────────────────────────────────────
PERSONA_BIO = (
    "I'm Elon. Running SpaceX, Tesla, xAI, Neuralink, and The Boring Company. "
    "The goal is making humanity multi-planetary and accelerating sustainable energy. "
    "Everything else is secondary."
)


# ── API helpers ────────────────────────────────────────────────────────────────

def auth_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def get_token() -> str:
    r = requests.post(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"},
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def list_twins(token: str) -> List[Dict]:
    r = requests.get(f"{BASE}/twins", headers={"Authorization": f"Bearer {token}"}, timeout=20)
    r.raise_for_status()
    return r.json()


def delete_twin(token: str, twin_id: str) -> bool:
    r = requests.delete(
        f"{BASE}/twins/{twin_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    return r.status_code in {200, 204}


def create_twin(token: str) -> str:
    r = requests.post(
        f"{BASE}/twins",
        headers=auth_headers(token),
        json={
            "name": "Elon Musk",
            "description": "Entrepreneur, CEO of SpaceX and Tesla, founder of xAI",
            "mode": "manual",
        },
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    return data.get("id") or data.get("twin_id")


def ingest_mode_b(token: str, twin_id: str) -> Optional[str]:
    r = requests.post(
        f"{BASE}/persona/link-compile/jobs/mode-b",
        headers=auth_headers(token),
        json={
            "twin_id": twin_id,
            "content": ELON_BIO_CONTENT,
            "title": "Elon Musk — Comprehensive Biography",
            "source_context": "Comprehensive public biography with career history and philosophy",
        },
        timeout=30,
    )
    if r.status_code == 200:
        return r.json().get("job_id")
    print(f"    Mode-B error: HTTP {r.status_code}  {r.text[:200]}")
    return None


def import_linkedin(token: str, twin_id: str) -> bool:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Profile.csv",
            "First Name,Last Name,Headline,Summary,Industry,Zip Code,Geo Location,"
            "Twitter Handles,Websites,Instant Messengers\n"
            "Elon,Musk,\"CEO of SpaceX and Tesla\","
            "\"Entrepreneur focused on sustainable energy and multi-planetary life\","
            "Technology,78701,Austin Texas United States,,https://x.com/elonmusk,,\n")
        zf.writestr("Positions.csv",
            "Company Name,Title,Description,Location,Started On,Finished On\n"
            "SpaceX,CEO and CTO,,Hawthorne CA,May 2002,\n"
            "Tesla,CEO,,Austin TX,Oct 2008,\n"
            "xAI,Founder and CEO,,Austin TX,Jul 2023,\n"
            "The Boring Company,Founder,,Austin TX,Dec 2016,\n"
            "Neuralink,Co-Founder,,Fremont CA,Jul 2016,\n")
        zf.writestr("Education.csv",
            "School Name,Start Date,End Date,Notes,Degree Name,Activities\n"
            "University of Pennsylvania,1992,1997,,Bachelor of Science Physics and Economics,\n"
            "Queen's University,1989,1992,,,\n")
        zf.writestr("Skills.csv",
            "Name\nRocket Engineering\nElectric Vehicles\nArtificial Intelligence\n"
            "Entrepreneurship\nFirst-Principles Thinking\nSoftware Engineering\n"
            "Energy Storage\nNeural Engineering\n")
    r = requests.post(
        f"{BASE}/persona/{twin_id}/import/linkedin-export",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("linkedin_export.zip", buf.getvalue(), "application/zip")},
        timeout=60,
    )
    return r.status_code == 200


def poll_job(token: str, job_id: str, max_wait: int = 480) -> bool:
    start = time.time()
    last = ""
    while time.time() - start < max_wait:
        try:
            r = requests.get(
                f"{BASE}/persona/link-compile/jobs/{job_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=45,
            )
            if r.status_code == 200:
                s = r.json().get("status", "unknown")
                if s != last:
                    print(f"    job → {s}  ({int(time.time() - start)}s)")
                    last = s
                if s in {"completed", "persona_built"}:
                    return True
                if s in {"failed", "error"}:
                    return False
        except requests.exceptions.ReadTimeout:
            print(f"    poll read-timeout, retrying… ({int(time.time() - start)}s elapsed)")
        except Exception as e:
            print(f"    poll error ({type(e).__name__}): {e} — retrying…")
        time.sleep(15)
    print(f"    job timed out after {max_wait}s")
    return False


def patch_bio(token: str, twin_id: str) -> bool:
    r = requests.patch(
        f"{BASE}/twins/{twin_id}",
        headers=auth_headers(token),
        json={"settings": {"public_profile": {"bio": PERSONA_BIO}}},
        timeout=30,
    )
    return r.status_code == 200


def enable_public_sharing(token: str, twin_id: str) -> bool:
    r = requests.patch(
        f"{BASE}/twins/{twin_id}/sharing",
        headers=auth_headers(token),
        json={"is_public": True},
        timeout=20,
    )
    return r.status_code == 200


def get_share_token(token: str, twin_id: str) -> Optional[str]:
    """Get or generate a public share token."""
    # Try GET first
    r = requests.get(
        f"{BASE}/twins/{twin_id}/share-link",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    if r.status_code == 200:
        data = r.json()
        t = data.get("token") or data.get("share_token")
        if t:
            return t
    # Generate new token
    r = requests.post(
        f"{BASE}/twins/{twin_id}/share-link",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    if r.status_code == 200:
        data = r.json()
        return data.get("token") or data.get("share_token")
    return None


def public_chat(twin_id: str, share_token: str, message: str,
                history: Optional[List] = None) -> Dict[str, Any]:
    body: Dict[str, Any] = {"message": message}
    if history:
        body["conversation_history"] = history
    try:
        r = requests.post(
            f"{BASE}/public/chat/{twin_id}/{share_token}",
            headers={"Content-Type": "application/json"},
            json=body,
            timeout=60,
        )
        return r.json() if r.status_code == 200 else {
            "error": f"HTTP {r.status_code}", "detail": r.text[:300]
        }
    except Exception as exc:
        return {"error": str(exc)}


def extract_text(resp: Dict) -> str:
    for key in ("message", "response", "answer", "content", "text"):
        v = resp.get(key)
        if isinstance(v, str) and len(v) > 5:
            return v
    # fallback: first long string value
    for v in resp.values():
        if isinstance(v, str) and len(v) > 20:
            return v
    return ""


def grade_response(text: str, question: str) -> Dict[str, Any]:
    t = text.lower()
    q = question.lower()

    checks: Dict[str, bool] = {}

    # Not a fallback "I don't know" response
    checks["not_fallback"] = "i don't know based on available" not in t and "0% confidence" not in t

    # First-person voice
    checks["first_person"] = any(p in t for p in ["i ", "i'm", "i've", "i'd", "my ", "we "])

    # Not AI-generic
    checks["no_ai_markers"] = not any(p in t for p in [
        "as an ai", "i cannot", "i am unable", "as a language model",
        "i'm just an ai", "i'm an artificial intelligence"
    ])

    # Specific (numbers, proper nouns, company names)
    has_num = bool(re.search(r'\$\d+|\d+\s*(billion|million|percent|%|years?)\b|\b\d{4}\b', t))
    has_entity = any(e in t for e in [
        "spacex", "tesla", "xai", "neuralink", "twitter", "boring company",
        "mars", "falcon", "starship", "grok", "openai", "first-principles"
    ])
    checks["specific_content"] = has_num or has_entity

    # Conversational (contractions / casual register)
    checks["conversational"] = any(c in t for c in [
        "look,", "honestly", "frankly", "obviously", "i think", "i believe",
        "i'd", "it's", "that's", "we're", "don't", "won't", "can't"
    ])

    total = sum(checks.values())
    pct = round(100 * total / len(checks))
    return {"checks": checks, "score": total, "max": len(checks), "pct": pct}


def section(title: str) -> None:
    print(f"\n{DIV}\n  {title}\n{DIV}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--keep-existing", action="store_true",
                   help="Reuse existing twin instead of deleting and recreating")
    args = p.parse_args()

    print(f"\n{DIV}")
    print(f"  ELON MUSK PROVE-IT TEST  —  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Target: {BASE}")
    print(DIV)

    # 1. Auth
    section("1. Auth")
    token = get_token()
    print("  OK")

    # 2. Delete + Create
    section("2. Twin Setup")
    twins = list_twins(token)
    elon = next((t for t in twins if "elon" in t.get("name", "").lower()), None)

    twin_id: Optional[str] = None

    if args.keep_existing and elon:
        twin_id = elon["id"]
        print(f"  Keeping existing twin: {twin_id[:12]}…  status={elon.get('status')}")
    else:
        if elon:
            twin_id_old = elon["id"]
            ok = delete_twin(token, twin_id_old)
            print(f"  Deleted old twin {twin_id_old[:12]}…  {'OK' if ok else 'FAILED'}")
            time.sleep(2)

        twin_id = create_twin(token)
        print(f"  Created fresh twin: {twin_id[:12]}…")

    assert twin_id

    # 3. Mode-B ingest
    section("3. Mode-B Biography Ingest")
    job_id = ingest_mode_b(token, twin_id)
    if job_id:
        print(f"  Job {job_id[:12]}… queued — polling…")
        ok = poll_job(token, job_id)
        print(f"  Ingest: {'DONE' if ok else 'FAILED'}")
    else:
        print("  Mode-B ingest returned no job_id — continuing anyway")

    # 4. LinkedIn import
    section("4. LinkedIn Export Import")
    li_ok = import_linkedin(token, twin_id)
    print(f"  LinkedIn import: {'OK' if li_ok else 'FAILED'}")

    # 5. PATCH persona bio
    section("5. PATCH Persona Bio")
    bio_ok = patch_bio(token, twin_id)
    print(f"  Bio PATCH: {'OK' if bio_ok else 'FAILED'}")
    if bio_ok:
        print(f"  Bio: \"{PERSONA_BIO}\"")

    # 5b. Enable public sharing
    sharing_ok = enable_public_sharing(token, twin_id)
    print(f"  Public sharing: {'ENABLED' if sharing_ok else 'FAILED'}")

    # 6. Get share token
    section("6. Share Token")
    share_token = get_share_token(token, twin_id)
    if not share_token:
        print("  ERROR: could not get share token — cannot test public chat")
        sys.exit(1)
    print(f"  Share token: {share_token[:16]}…")
    print(f"  Public URL: {BASE}/public/chat/{twin_id}/{share_token}")

    # 7. Public chat — conversational questions
    section("7. Public Chat Quality Test")
    print(f"  Endpoint: POST /public/chat/{twin_id[:12]}…/{share_token[:8]}…")
    print()

    results = []
    history: List[Dict] = []

    for question, expected in CONV_QUESTIONS:
        print(f"  USER: {question}")
        resp = public_chat(twin_id, share_token, question, history=history if history else None)

        if "error" in resp:
            print(f"  EM:   ERROR — {resp['error']}: {resp.get('detail', '')[:150]}")
            results.append({"q": question, "pass": False, "error": resp["error"]})
            continue

        text = extract_text(resp)
        conf = resp.get("confidence_score", 0.0)
        grade = grade_response(text, question)
        passed = grade["pct"] >= 60 and grade["checks"].get("not_fallback", True)

        # Show response like the Delphi example
        snippet = text[:300].strip()
        print(f"  EM:   {snippet}")
        print(f"        [conf={conf:.0%}  score={grade['pct']}%  {'PASS ✓' if passed else 'FAIL ✗'}]")
        fail_checks = [k for k, v in grade["checks"].items() if not v]
        if fail_checks:
            print(f"        failed: {fail_checks}")
        print()

        # Maintain conversation history
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": text})

        results.append({"q": question, "response": text[:200], "grade": grade, "pass": passed})
        time.sleep(2)

    # Summary
    section("RESULTS SUMMARY")
    passed_count = sum(1 for r in results if r["pass"])
    total = len(results)
    errors = sum(1 for r in results if "error" in r)

    print(f"  Twin ID:  {twin_id}")
    print(f"  Passed:   {passed_count}/{total}")
    print(f"  Errors:   {errors}")
    print()

    for r in results:
        icon = "✓" if r["pass"] else ("E" if "error" in r else "✗")
        pct = r.get("grade", {}).get("pct", 0) if "grade" in r else 0
        print(f"  [{icon}] {pct:3d}%  {r['q']}")

    overall = "PASS" if passed_count >= (total * 0.67) else "FAIL"
    print(f"\n  Overall: {overall}  ({passed_count}/{total} ≥ 67% threshold)")

    # Save
    out = {
        "run_at": datetime.now().isoformat(),
        "twin_id": twin_id,
        "share_token": share_token,
        "results": results,
        "passed": passed_count,
        "total": total,
        "overall": overall,
    }
    with open("tools/prove_elon_results.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\n  Results saved → tools/prove_elon_results.json")
    print(f"\n  Profile URL: {BASE.replace('onrender.com', 'onrender.com')}/profile/{twin_id}")


if __name__ == "__main__":
    main()
