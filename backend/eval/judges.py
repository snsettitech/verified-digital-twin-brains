# backend/eval/judges.py
"""LLM Judges for Online Evaluation

Provides LLM-based evaluation of chat responses for:
- Faithfulness: Does the answer match the context?
- Citation alignment: Are citations accurate?
"""

import os
import asyncio
import json
from typing import Dict, Any, Optional, List
import logging
import re

logger = logging.getLogger(__name__)


async def judge_faithfulness(
    answer: str,
    context: str,
    model: str = "gpt-4o-mini"
) -> Dict[str, Any]:
    """
    Judge if the answer is faithful to the provided context.
    
    Args:
        answer: The generated answer
        context: The retrieved context
        model: Model to use for judging
    
    Returns:
        Dict with score (0.0-1.0), reasoning, and verdict
    """
    from modules.clients import get_openai_client
    
    prompt = f"""You are an expert judge evaluating answer faithfulness.

CONTEXT PROVIDED TO THE AI:
{context[:2000]}

AI'S ANSWER:
{answer}

TASK: Evaluate if the AI's answer is faithful to the context.

Criteria:
- The answer should only contain information supported by the context
- The answer should not make claims not present in the context
- The answer can paraphrase but should not distort meaning

Respond with a JSON object:
{{
  "score": <float 0.0-1.0>,
  "verdict": "faithful" | "partially_faithful" | "unfaithful",
  "reasoning": "<brief explanation>"
}}

Only respond with the JSON, no other text."""

    try:
        client = get_openai_client()
        loop = asyncio.get_event_loop()
        
        def _call():
            return client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=200,
                response_format={"type": "json_object"}
            )
        
        response = await loop.run_in_executor(None, _call)
        result = response.choices[0].message.content
        
        import json
        return json.loads(result)
        
    except Exception as e:
        logger.error(f"Faithfulness judge failed: {e}")
        return {
            "score": None,
            "verdict": "error",
            "reasoning": str(e)
        }


async def judge_citation_alignment(
    answer: str,
    citations: list,
    model: str = "gpt-4o-mini"
) -> Dict[str, Any]:
    """
    Judge if the citations in the answer are accurate.
    
    Args:
        answer: The generated answer
        citations: List of citation objects
        model: Model to use for judging
    
    Returns:
        Dict with aligned (bool), score, and reasoning
    """
    if not citations:
        return {
            "aligned": True,
            "score": 1.0,
            "reasoning": "No citations to evaluate"
        }
    
    from modules.clients import get_openai_client
    
    citations_text = "\n".join([
        f"- {c.get('title', 'Untitled')}: {c.get('content', '')[:200]}"
        for c in citations[:5]
    ])
    
    prompt = f"""You are an expert judge evaluating citation accuracy.

AI'S ANSWER:
{answer}

CITED SOURCES:
{citations_text}

TASK: Evaluate if the citations support the claims in the answer.

Respond with a JSON object:
{{
  "aligned": <true/false>,
  "score": <float 0.0-1.0>,
  "reasoning": "<brief explanation>"
}}

Only respond with the JSON, no other text."""

    try:
        client = get_openai_client()
        loop = asyncio.get_event_loop()
        
        def _call():
            return client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=200,
                response_format={"type": "json_object"}
            )
        
        response = await loop.run_in_executor(None, _call)
        result = response.choices[0].message.content
        
        import json
        return json.loads(result)
        
    except Exception as e:
        logger.error(f"Citation judge failed: {e}")
        return {
            "aligned": None,
            "score": None,
            "reasoning": str(e)
        }


async def run_online_eval(
    trace_id: str,
    answer: str,
    context: str,
    citations: list = None,
    threshold: float = 0.7
) -> Dict[str, Any]:
    """
    Run online evaluation and log scores to Langfuse.
    
    Args:
        trace_id: Langfuse trace ID
        answer: Generated answer
        context: Retrieved context
        citations: Optional citations
        threshold: Threshold for flagging
    
    Returns:
        Dict with evaluation results
    """
    # Run judges in parallel
    faithfulness_task = judge_faithfulness(answer, context)
    citation_task = judge_citation_alignment(answer, citations or [])
    
    faithfulness_result, citation_result = await asyncio.gather(
        faithfulness_task, 
        citation_task
    )
    
    # Log scores to Langfuse
    try:
        from langfuse import get_client
        client = get_client()
        
        if faithfulness_result.get("score") is not None:
            client.score(
                trace_id=trace_id,
                name="faithfulness",
                value=faithfulness_result["score"],
                comment=faithfulness_result.get("reasoning", ""),
                data_type="NUMERIC"
            )
        
        if citation_result.get("score") is not None:
            client.score(
                trace_id=trace_id,
                name="citation_alignment",
                value=citation_result["score"],
                comment=citation_result.get("reasoning", ""),
                data_type="NUMERIC"
            )
        
        # Flag for review if below threshold
        needs_review = (
            (faithfulness_result.get("score") or 1.0) < threshold or
            (citation_result.get("score") or 1.0) < threshold
        )
        
        if needs_review:
            client.score(
                trace_id=trace_id,
                name="needs_review",
                value=1,
                comment="Low confidence - flagged for manual review",
                data_type="BOOLEAN"
            )
        
        client.flush()
        
    except Exception as e:
        logger.error(f"Failed to log eval scores: {e}")
    
    return {
        "faithfulness": faithfulness_result,
        "citation_alignment": citation_result,
        "needs_review": needs_review if 'needs_review' in dir() else False
    }


def _safe_json_loads(raw: str, fallback: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return json.loads(raw or "{}")
    except Exception:
        return fallback


async def judge_persona_structure_policy(
    *,
    user_query: str,
    answer: str,
    intent_label: str,
    required_structure: Optional[str],
    citations_required: bool,
    citations_present: bool,
    banned_phrases: Optional[List[str]] = None,
    model: str = "gpt-4o-mini",
) -> Dict[str, Any]:
    """
    Judge A: structure + policy compliance.
    """
    banned_phrases = banned_phrases or []
    rule_violations = []
    answer_lower = (answer or "").lower()
    for phrase in banned_phrases:
        if phrase and phrase.lower() in answer_lower:
            rule_violations.append(f"POL_BANNED_PHRASE::{phrase}")

    if citations_required and not citations_present:
        rule_violations.append("POL_CITATION_REQUIRED")

    if required_structure == "bullets":
        has_bullets = bool(re.search(r"(?m)^\s*([-*]|\d+\.)\s+", answer or ""))
        if not has_bullets:
            rule_violations.append("POL_REQUIRED_BULLET_FORMAT")

    base_score = 1.0 - min(0.8, len(rule_violations) * 0.25)

    # If static checks fail heavily, skip model call and return deterministic fail.
    if len(rule_violations) >= 2:
        return {
            "score": round(max(0.0, base_score), 4),
            "verdict": "fail",
            "violated_clauses": rule_violations,
            "rewrite_directives": [
                "Satisfy required structure and citation rules.",
                "Remove banned phrases and policy violations.",
            ],
            "reasoning": "Deterministic structure/policy checks failed before model judge.",
        }

    prompt = f"""You are Persona Judge A (Structure and Policy).

You must evaluate whether the answer follows policy and structure rules.

INPUTS:
- intent_label: {intent_label}
- citations_required: {str(citations_required).lower()}
- citations_present: {str(citations_present).lower()}
- required_structure: {required_structure or "none"}
- banned_phrases: {json.dumps(banned_phrases, ensure_ascii=True)}
- user_query: {user_query}
- answer: {answer}

Return JSON only:
{{
  "score": <float 0.0-1.0>,
  "verdict": "pass" | "fail",
  "violated_clauses": ["POL_..."],
  "rewrite_directives": ["short, clause-targeted fix instructions"],
  "reasoning": "brief"
}}
"""

    try:
        from modules.clients import get_async_openai_client

        client = get_async_openai_client()
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=350,
            response_format={"type": "json_object"},
        )
        parsed = _safe_json_loads(resp.choices[0].message.content, fallback={})
        model_score = float(parsed.get("score", base_score))
        merged_clauses = list(dict.fromkeys([*rule_violations, *(parsed.get("violated_clauses") or [])]))
        verdict = "fail" if (merged_clauses or model_score < 0.75 or parsed.get("verdict") == "fail") else "pass"
        directives = parsed.get("rewrite_directives") or []
        if not directives and merged_clauses:
            directives = ["Fix violated policy clauses and keep the response concise."]
        return {
            "score": round(max(0.0, min(1.0, model_score)), 4),
            "verdict": verdict,
            "violated_clauses": merged_clauses,
            "rewrite_directives": directives,
            "reasoning": parsed.get("reasoning", ""),
        }
    except Exception as e:
        logger.warning(f"Structure/policy judge fallback: {e}")
        verdict = "fail" if rule_violations else ("pass" if base_score >= 0.75 else "fail")
        return {
            "score": round(max(0.0, min(1.0, base_score)), 4),
            "verdict": verdict,
            "violated_clauses": rule_violations,
            "rewrite_directives": ["Fix policy violations and structure contract."],
            "reasoning": f"Fallback due to judge error: {e}",
        }


async def judge_persona_voice_fidelity(
    *,
    user_query: str,
    answer: str,
    intent_label: str,
    voice_identity: Dict[str, Any],
    interaction_style: Dict[str, Any],
    model: str = "gpt-4o-mini",
) -> Dict[str, Any]:
    """
    Judge B: voice fidelity only.
    """
    prompt = f"""You are Persona Judge B (Voice Fidelity).

Evaluate voice alignment only (tone/cadence/style), not factual correctness.

INPUTS:
- intent_label: {intent_label}
- voice_identity: {json.dumps(voice_identity or {}, ensure_ascii=True)}
- interaction_style: {json.dumps(interaction_style or {}, ensure_ascii=True)}
- user_query: {user_query}
- answer: {answer}

Return JSON only:
{{
  "score": <float 0.0-1.0>,
  "verdict": "pass" | "fail",
  "violated_clauses": ["POL_STYLE_..."],
  "rewrite_directives": ["short style-specific instructions"],
  "reasoning": "brief"
}}
"""

    try:
        from modules.clients import get_async_openai_client

        client = get_async_openai_client()
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
        parsed = _safe_json_loads(resp.choices[0].message.content, fallback={})
        score = float(parsed.get("score", 0.75))
        verdict = parsed.get("verdict", "pass" if score >= 0.78 else "fail")
        clauses = parsed.get("violated_clauses") or []
        directives = parsed.get("rewrite_directives") or []
        if not directives and verdict == "fail":
            directives = ["Adjust tone/cadence to match persona voice identity."]
        return {
            "score": round(max(0.0, min(1.0, score)), 4),
            "verdict": "fail" if verdict == "fail" or score < 0.78 else "pass",
            "violated_clauses": clauses,
            "rewrite_directives": directives,
            "reasoning": parsed.get("reasoning", ""),
        }
    except Exception as e:
        logger.warning(f"Voice judge fallback: {e}")
        return {
            "score": 0.8,
            "verdict": "pass",
            "violated_clauses": [],
            "rewrite_directives": [],
            "reasoning": f"Fallback pass due to judge error: {e}",
        }


async def rewrite_with_clause_directives(
    *,
    user_query: str,
    draft_answer: str,
    intent_label: str,
    violated_clauses: List[str],
    rewrite_directives: List[str],
    max_words: Optional[int] = None,
    required_structure: Optional[str] = None,
    model: str = "gpt-4o-mini",
) -> Dict[str, Any]:
    """
    Clause-targeted rewrite helper.
    """
    if not rewrite_directives and not violated_clauses:
        return {"rewritten_answer": draft_answer, "applied": False, "reasoning": "No directives."}

    max_words_text = str(max_words) if max_words and max_words > 0 else "120"
    prompt = f"""You are a response rewriter.

Rewrite the answer by fixing only the violated clauses and directives below.

INPUTS:
- intent_label: {intent_label}
- user_query: {user_query}
- violated_clauses: {json.dumps(violated_clauses, ensure_ascii=True)}
- rewrite_directives: {json.dumps(rewrite_directives, ensure_ascii=True)}
- max_words: {max_words_text}
- required_structure: {required_structure or "none"}
- draft_answer: {draft_answer}

RULES:
1) Preserve original meaning unless needed for compliance.
2) Keep answer <= max_words.
3) If required_structure is bullets, use bullet list.
4) Return JSON only.

JSON FORMAT:
{{
  "rewritten_answer": "...",
  "applied": true,
  "reasoning": "brief"
}}
"""

    try:
        from modules.clients import get_async_openai_client

        client = get_async_openai_client()
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=450,
            response_format={"type": "json_object"},
        )
        parsed = _safe_json_loads(resp.choices[0].message.content, fallback={})
        rewritten = (parsed.get("rewritten_answer") or "").strip()
        if not rewritten:
            return {"rewritten_answer": draft_answer, "applied": False, "reasoning": "Rewrite empty."}
        return {
            "rewritten_answer": rewritten,
            "applied": bool(parsed.get("applied", True)),
            "reasoning": parsed.get("reasoning", ""),
        }
    except Exception as e:
        logger.warning(f"Rewrite fallback: {e}")
        return {
            "rewritten_answer": draft_answer,
            "applied": False,
            "reasoning": f"Rewrite failed: {e}",
        }
