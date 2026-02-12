"""
Hybrid inference router for Phase 4.

Routes generation requests across OpenAI, Cerebras, and Anthropic with:
- task-aware provider preference
- automatic fallback
- per-request telemetry (provider/model/latency/attempts)
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from modules.clients import get_async_openai_client
from modules.inference_cerebras import CerebrasClient

logger = logging.getLogger(__name__)

# Backward-compatible control flag.
DEFAULT_PROVIDER = os.getenv("INFERENCE_PROVIDER", "openai").lower()
ROUTING_MODE = os.getenv("INFERENCE_ROUTING_MODE", "auto").lower()
FALLBACK_ENABLED = os.getenv("INFERENCE_FALLBACK_ENABLED", "true").lower() == "true"

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_JSON_MODEL = os.getenv("OPENAI_JSON_MODEL", "gpt-4o-mini")
CEREBRAS_MODEL = os.getenv("CEREBRAS_MODEL", "llama-3.3-70b")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-7-sonnet-latest")

# Small timeout to avoid long tail latency when a provider is degraded.
PROVIDER_TIMEOUT_SECONDS = float(os.getenv("INFERENCE_PROVIDER_TIMEOUT_SECONDS", "25"))


def _provider_available(provider: str) -> bool:
    if provider == "openai":
        return bool(os.getenv("OPENAI_API_KEY"))
    if provider == "cerebras":
        return bool(os.getenv("CEREBRAS_API_KEY"))
    if provider == "anthropic":
        return bool(os.getenv("ANTHROPIC_API_KEY"))
    return False


def _candidate_providers(task: str, preferred_provider: Optional[str] = None) -> List[str]:
    task = (task or "general").lower()
    preferred = (preferred_provider or "").lower()

    # Optional hard pin for rollout safety.
    if ROUTING_MODE in {"single", "forced"}:
        chain = [preferred or DEFAULT_PROVIDER]
        if FALLBACK_ENABLED:
            chain += ["openai", "cerebras", "anthropic"]
    else:
        if preferred:
            chain = [preferred]
        elif task in {"realizer", "fast"}:
            chain = ["cerebras", "openai", "anthropic"]
        elif task in {"deep_reasoning"}:
            chain = ["anthropic", "openai", "cerebras"]
        else:
            # JSON-heavy planner/router/verifier and default general tasks.
            chain = ["openai", "anthropic", "cerebras"]
        if FALLBACK_ENABLED:
            chain += ["openai", "cerebras", "anthropic"]

    out: List[str] = []
    for p in chain:
        if p in {"openai", "cerebras", "anthropic"} and p not in out and _provider_available(p):
            out.append(p)
    return out


def _strip_json_markdown(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_json_object(text: str) -> Dict[str, Any]:
    cleaned = _strip_json_markdown(text)
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    # Fallback: extract first JSON object candidate from free-form text.
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in model output")

    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("Model JSON output is not an object")
    return parsed


async def _call_openai(
    messages: List[Dict[str, str]],
    *,
    json_mode: bool,
    temperature: float,
    max_tokens: int,
) -> Tuple[str, str]:
    client = get_async_openai_client()
    model = OPENAI_JSON_MODEL if json_mode else OPENAI_MODEL
    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "timeout": PROVIDER_TIMEOUT_SECONDS,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = await client.chat.completions.create(**kwargs)
    return (resp.choices[0].message.content or "").strip(), model


async def _call_cerebras(
    messages: List[Dict[str, str]],
    *,
    temperature: float,
    max_tokens: int,
) -> Tuple[str, str]:
    client = CerebrasClient()
    resp = await client.generate_async(
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return (resp.choices[0].message.content or "").strip(), client.model


async def _call_anthropic(
    messages: List[Dict[str, str]],
    *,
    temperature: float,
    max_tokens: int,
) -> Tuple[str, str]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")

    system_parts: List[str] = []
    anthropic_messages: List[Dict[str, str]] = []

    for m in messages:
        role = (m.get("role") or "user").lower()
        content = m.get("content") or ""
        if role == "system":
            system_parts.append(content)
        elif role in {"assistant", "user"}:
            anthropic_messages.append({"role": role, "content": content})
        else:
            anthropic_messages.append({"role": "user", "content": content})

    if not anthropic_messages:
        anthropic_messages = [{"role": "user", "content": "Continue."}]

    payload: Dict[str, Any] = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": anthropic_messages,
    }
    if system_parts:
        payload["system"] = "\n\n".join(system_parts)

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    async with httpx.AsyncClient(timeout=PROVIDER_TIMEOUT_SECONDS) as client:
        resp = await client.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    text_chunks = [
        block.get("text", "")
        for block in (data.get("content") or [])
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    return "".join(text_chunks).strip(), ANTHROPIC_MODEL


async def _call_provider(
    provider: str,
    messages: List[Dict[str, str]],
    *,
    json_mode: bool,
    temperature: float,
    max_tokens: int,
) -> Tuple[str, str]:
    if provider == "openai":
        return await _call_openai(
            messages,
            json_mode=json_mode,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    if provider == "cerebras":
        return await _call_cerebras(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    if provider == "anthropic":
        return await _call_anthropic(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    raise ValueError(f"Unsupported provider: {provider}")


async def invoke_text(
    messages: List[Dict[str, str]],
    *,
    task: str = "general",
    temperature: float = 0.0,
    max_tokens: int = 1024,
    preferred_provider: Optional[str] = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Invoke text generation with hybrid routing + fallback.
    """
    attempts: List[Dict[str, Any]] = []
    candidates = _candidate_providers(task, preferred_provider=preferred_provider)
    if not candidates:
        raise RuntimeError("No configured inference providers available")

    for provider in candidates:
        start = time.perf_counter()
        try:
            content, model = await _call_provider(
                provider,
                messages,
                json_mode=False,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            meta = {
                "provider": provider,
                "model": model,
                "task": task,
                "latency_ms": latency_ms,
                "fallback_used": len(attempts) > 0,
                "attempts": attempts + [{"provider": provider, "status": "ok", "latency_ms": latency_ms}],
            }
            return content, meta
        except Exception as e:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            attempts.append(
                {
                    "provider": provider,
                    "status": "error",
                    "latency_ms": latency_ms,
                    "error": str(e),
                }
            )
            logger.warning("[InferenceRouter] provider=%s failed task=%s: %s", provider, task, e)

    raise RuntimeError(f"All providers failed for task '{task}': {attempts}")


async def invoke_json(
    messages: List[Dict[str, str]],
    *,
    task: str = "structured",
    temperature: float = 0.0,
    max_tokens: int = 1024,
    preferred_provider: Optional[str] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Invoke structured generation with hybrid routing + fallback.
    """
    attempts: List[Dict[str, Any]] = []
    candidates = _candidate_providers(task, preferred_provider=preferred_provider)
    if not candidates:
        raise RuntimeError("No configured inference providers available")

    for provider in candidates:
        start = time.perf_counter()
        try:
            raw, model = await _call_provider(
                provider,
                messages,
                json_mode=(provider == "openai"),
                temperature=temperature,
                max_tokens=max_tokens,
            )
            parsed = _parse_json_object(raw)
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            meta = {
                "provider": provider,
                "model": model,
                "task": task,
                "latency_ms": latency_ms,
                "fallback_used": len(attempts) > 0,
                "attempts": attempts + [{"provider": provider, "status": "ok", "latency_ms": latency_ms}],
            }
            return parsed, meta
        except Exception as e:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            attempts.append(
                {
                    "provider": provider,
                    "status": "error",
                    "latency_ms": latency_ms,
                    "error": str(e),
                }
            )
            logger.warning("[InferenceRouter] provider=%s failed json task=%s: %s", provider, task, e)

    raise RuntimeError(f"All providers failed for JSON task '{task}': {attempts}")

