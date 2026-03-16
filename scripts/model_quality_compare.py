#!/usr/bin/env python3
"""
PersonaOn AI — Model Quality Comparison
Directly compares GPT-4.1 vs Gemini 2.5 Flash for persona chat quality.

Usage:
    python scripts/model_quality_compare.py
    python scripts/model_quality_compare.py --persona "Elon Musk"
    python scripts/model_quality_compare.py --persona "Warren Buffett" --questions 5
"""

import argparse
import asyncio
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

# Try to load backend .env for API keys
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))
except ImportError:
    pass

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
OPENAI_MODEL = "gpt-4.1"
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

# ── System prompt (matches production exactly) ────────────────────────────────
SYSTEM_PROMPT_TEMPLATE = """You are {persona_name}.

You speak in the first person as {persona_name}. You are not a generic assistant.
You should sound like the actual person: their judgment, tone, vocabulary,
cadence, and way of thinking should come through naturally.

Stay in character at all times.
- Never say "as an AI", "as a language model", or anything similar.
- Do not describe yourself as a system unless the user directly asks.
- If the user asks whether you are real, say once, briefly, that you are a
  digital version of {persona_name}, then move on.
- Speak directly. No filler. No corporate language. No generic assistant
  phrases like "Great question" or "Certainly."

HOW TO RESPOND
- Start with the substance immediately.
- Keep simple answers short.
- Go deeper only when the question deserves it.
- Give a real point of view, not a safe summary.
- Sound like a person talking, not a report being generated.

CONVERSATION RULE
- End every response with exactly one direct question.
- The question must be specific to the user's situation.

PERSONA CONTEXT
{persona_context}"""

# ── Persona contexts (condensed from public knowledge) ────────────────────────
PERSONA_CONTEXTS = {
    "Elon Musk": """Elon Musk is the CEO of Tesla and SpaceX, and owner of X (formerly Twitter).
Born in South Africa, he moved to Canada then the US. He co-founded PayPal, founded SpaceX in 2002
and Tesla in 2003. His stated mission is to make humanity multi-planetary. Known for intense work
ethic, blunt communication, and disruptive thinking. Has said he sleeps 6 hours a night, works
80-100 hours a week. Believes in first-principles thinking. Quote style: short, punchy, sometimes
provocative. Genuinely believes in his missions beyond profit.""",
    "Arnold Schwarzenegger": """Arnold Schwarzenegger is a 7-time Mr. Olympia bodybuilder, Hollywood action star, and
former Governor of California (2003-2011). Born in Thal, Austria. Moved to the US at 21 with
nothing but his ambition. Famous for Total Recall, Terminator, Predator. Republican but
environmentally progressive. Author of 'Total Recall' autobiography. Known for: hard work,
positive energy, 'Rules of Success', fitness advocacy. Communication style: warm, motivational,
practical, uses personal stories and humor. Often references his immigrant journey.""",
    "Warren Buffett": """Warren Buffett is the CEO of Berkshire Hathaway and one of the most successful investors ever.
Born 1930 in Omaha, Nebraska. Known as the 'Oracle of Omaha'. Has lived in the same Omaha house since
1958. Started investing at age 11. Key principles: value investing, long-term holding, understanding
businesses you invest in, margin of safety, economic moats. Famous for annual Berkshire shareholder
letters. Communication style: plain-spoken, uses folksy analogies, self-deprecating humor, extremely
direct about mistakes. Quotes Charlie Munger often. Drinks 5 Cokes a day.""",
    "Donald Trump": """Donald Trump is a businessman turned politician, 45th and 47th President of the United States.
Born 1946 in Queens, NY. Built real estate empire. Created 'The Apprentice'. Signature phrases:
'Make America Great Again', 'You're fired', 'Tremendous'. Communication style: superlatives,
repetition, direct attacks on critics, confident to the point of braggadocio. Views: America-first
nationalism, protectionist trade, strong military, tough immigration. Loyal to base, combative
with media.""",
    "Narendra Modi": """Narendra Modi is the Prime Minister of India since 2014, from the BJP party.
Born 1950 in Vadnagar, Gujarat. Humble origins—father sold tea. Rose through RSS and BJP.
Was Gujarat Chief Minister for 13 years before becoming PM. Key programs: Digital India, Make in India,
Swachh Bharat, Jan Dhan Yojana, PLI scheme. Vision: Viksit Bharat 2047 (Developed India by centenary).
Communication style: direct, nationalistic, storytelling-heavy, references common citizens, uses
Gujarati phrases occasionally. Known for morning yoga, minimal sleep (~4-5 hours), discipline.""",
}

COMPARISON_QUESTIONS = {
    "Elon Musk": [
        "What's your honest assessment of the biggest threat to humanity right now?",
        "Why do you think people misunderstand your intentions so much?",
        "Walk me through how you make a major business decision.",
    ],
    "Arnold Schwarzenegger": [
        "How did bodybuilding teach you about business and politics?",
        "What's the one thing young people don't understand about success?",
        "What's your biggest political regret from your time as Governor?",
    ],
    "Warren Buffett": [
        "What's the single investing mistake you see most often that costs people the most?",
        "Why do you stay in Omaha when you could live anywhere?",
        "What would you tell a young person who wants to build wealth?",
    ],
    "Donald Trump": [
        "What do you think the media consistently gets wrong about you?",
        "What was your proudest moment as President?",
        "What's your approach to negotiating a deal when the other side is stronger?",
    ],
    "Narendra Modi": [
        "What does Viksit Bharat mean to you personally?",
        "How has India's position in the world changed since 2014?",
        "What's the most important lesson your early life taught you about leadership?",
    ],
}


# ── Model callers ─────────────────────────────────────────────────────────────
async def call_openai(
    client: httpx.AsyncClient,
    system_prompt: str,
    question: str,
) -> tuple[str, float]:
    t0 = time.perf_counter()
    r = await client.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            "temperature": 0.7,
            "max_tokens": 500,
        },
        timeout=45,
    )
    elapsed = time.perf_counter() - t0
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip(), round(elapsed, 2)


async def call_gemini(
    client: httpx.AsyncClient,
    system_prompt: str,
    question: str,
) -> tuple[str, float]:
    t0 = time.perf_counter()
    r = await client.post(
        f"{GEMINI_BASE_URL}chat/completions",
        headers={
            "Authorization": f"Bearer {GOOGLE_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": GEMINI_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            "temperature": 0.7,
            "max_tokens": 500,
        },
        timeout=45,
    )
    elapsed = time.perf_counter() - t0
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip(), round(elapsed, 2)


# ── Scoring ───────────────────────────────────────────────────────────────────
def score_response(persona_name: str, response: str) -> dict:
    r = response.lower()
    name_lower = persona_name.split()[0].lower()

    in_character = 10
    if any(x in r for x in ["as an ai", "as a language model", "i cannot", "i'm unable"]):
        in_character = 0
    elif f"{name_lower} would" in r or f"as {name_lower}" in r:
        in_character -= 3  # third-person reference to self

    word_count = len(response.split())
    substance = min(10, max(2, word_count // 12))

    ends_with_question = response.strip().endswith("?")
    has_question = "?" in response[-150:]
    conversational = 9 if ends_with_question else (6 if has_question else 2)

    directness = 8 if not any(x in r for x in ["certainly", "great question", "absolutely", "of course"]) else 4

    total = in_character + substance + conversational + directness
    return {
        "in_character": in_character,
        "substance": substance,
        "conversational": conversational,
        "directness": directness,
        "total": total,
        "pct": round(total / 40 * 100, 1),
    }


# ── Main comparison ───────────────────────────────────────────────────────────
async def compare_models(persona_name: str, num_questions: int = 3) -> None:
    if not OPENAI_API_KEY:
        print("✗ OPENAI_API_KEY not set")
        return
    if not GOOGLE_API_KEY:
        print("✗ GOOGLE_API_KEY not set")
        return

    context = PERSONA_CONTEXTS.get(persona_name)
    if not context:
        print(f"✗ No context for '{persona_name}'. Available: {list(PERSONA_CONTEXTS.keys())}")
        return

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        persona_name=persona_name,
        persona_context=context,
    )
    questions = COMPARISON_QUESTIONS.get(persona_name, [])[:num_questions]
    if not questions:
        print(f"✗ No questions for '{persona_name}'")
        return

    print(f"\n{'='*72}")
    print(f"  MODEL COMPARISON: {persona_name}")
    print(f"  GPT-4.1  vs  Gemini 2.5 Flash")
    print(f"{'='*72}\n")

    openai_scores = []
    gemini_scores = []
    openai_latencies = []
    gemini_latencies = []

    async with httpx.AsyncClient(follow_redirects=True) as client:
        for i, question in enumerate(questions):
            print(f"\n{'-'*72}")
            print(f"Q{i+1}: {question}")
            print(f"{'-'*72}")

            # Run both models in parallel
            try:
                (oa_resp, oa_lat), (gm_resp, gm_lat) = await asyncio.gather(
                    call_openai(client, system_prompt, question),
                    call_gemini(client, system_prompt, question),
                )
            except Exception as e:
                print(f"  ✗ Error: {e}")
                continue

            oa_score = score_response(persona_name, oa_resp)
            gm_score = score_response(persona_name, gm_resp)
            openai_scores.append(oa_score["pct"])
            gemini_scores.append(gm_score["pct"])
            openai_latencies.append(oa_lat)
            gemini_latencies.append(gm_lat)

            winner = "GPT-4.1" if oa_score["pct"] >= gm_score["pct"] else "Gemini 2.5 Flash"

            print(f"\n  [GPT-4.1 | {oa_lat}s | score={oa_score['pct']}/100]")
            print(f"  {oa_resp[:400]}{'...' if len(oa_resp) > 400 else ''}")

            print(f"\n  [Gemini 2.5 Flash | {gm_lat}s | score={gm_score['pct']}/100]")
            print(f"  {gm_resp[:400]}{'...' if len(gm_resp) > 400 else ''}")

            print(f"\n  >> Winner: {winner}")

    # Summary
    if openai_scores and gemini_scores:
        oa_avg = round(sum(openai_scores) / len(openai_scores), 1)
        gm_avg = round(sum(gemini_scores) / len(gemini_scores), 1)
        oa_lat_avg = round(sum(openai_latencies) / len(openai_latencies), 2)
        gm_lat_avg = round(sum(gemini_latencies) / len(gemini_latencies), 2)
        diff = round(abs(oa_avg - gm_avg), 1)
        overall_winner = "GPT-4.1" if oa_avg >= gm_avg else "Gemini 2.5 Flash"

        print(f"\n{'='*72}")
        print(f"  SUMMARY for {persona_name}")
        print(f"{'-'*72}")
        print(f"  {'Model':<25} {'Avg Score':>10} {'Avg Latency':>12}")
        print(f"  {'GPT-4.1':<25} {oa_avg:>9}/100 {oa_lat_avg:>10}s")
        print(f"  {'Gemini 2.5 Flash':<25} {gm_avg:>9}/100 {gm_lat_avg:>10}s")
        print(f"{'-'*72}")
        print(f"  Winner: {overall_winner} (+{diff} pts)")
        pct_better = round(diff / max(oa_avg, gm_avg) * 100, 1)
        print(f"  Improvement: {pct_better}% better quality")
        print(f"  Recommendation: Use {overall_winner} as primary for persona chat")
        print(f"{'='*72}\n")

        return overall_winner, oa_avg, gm_avg


async def main():
    parser = argparse.ArgumentParser(description="Model quality comparison")
    parser.add_argument("--persona", default=None, help="Persona name (default: all)")
    parser.add_argument("--questions", type=int, default=3, help="Questions per persona")
    args = parser.parse_args()

    personas_to_test = [args.persona] if args.persona else list(PERSONA_CONTEXTS.keys())

    results = {}
    for persona in personas_to_test:
        result = await compare_models(persona, args.questions)
        if result:
            winner, oa, gm = result
            results[persona] = {"winner": winner, "gpt41": oa, "gemini25": gm}

    if len(results) > 1:
        print(f"\n{'='*72}")
        print(f"  OVERALL COMPARISON ACROSS ALL PERSONAS")
        print(f"{'-'*72}")
        gpt_wins = sum(1 for r in results.values() if r["winner"] == "GPT-4.1")
        gem_wins = sum(1 for r in results.values() if r["winner"] == "Gemini 2.5 Flash")
        gpt_avg = round(sum(r["gpt41"] for r in results.values()) / len(results), 1)
        gem_avg = round(sum(r["gemini25"] for r in results.values()) / len(results), 1)
        print(f"  GPT-4.1 wins: {gpt_wins}/{len(results)} | avg score: {gpt_avg}/100")
        print(f"  Gemini 2.5 Flash wins: {gem_wins}/{len(results)} | avg score: {gem_avg}/100")
        final_winner = "GPT-4.1" if gpt_avg >= gem_avg else "Gemini 2.5 Flash"
        print(f"\n  FINAL VERDICT: {final_winner} is better for persona chat")
        print(f"{'='*72}\n")


if __name__ == "__main__":
    asyncio.run(main())
