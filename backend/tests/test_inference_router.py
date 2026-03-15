from unittest.mock import patch

import pytest

from modules import clients, inference_router


def test_get_async_gemini_client_uses_google_openai_compat_base_url(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "google-test-key")
    monkeypatch.setenv(
        "GEMINI_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta/openai/",
    )
    clients._async_gemini_client = None

    with patch("modules.clients.AsyncOpenAI") as mock_async_openai:
        mock_async_openai.return_value = object()
        client = clients.get_async_gemini_client()

    assert client is mock_async_openai.return_value
    mock_async_openai.assert_called_once_with(
        api_key="google-test-key",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )
    clients._async_gemini_client = None


def test_candidate_providers_prefers_gemini_for_text_when_default(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "google-test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setattr(inference_router, "DEFAULT_PROVIDER", "gemini")
    monkeypatch.setattr(inference_router, "ROUTING_MODE", "auto")
    monkeypatch.setattr(inference_router, "FALLBACK_ENABLED", True)

    candidates = inference_router._candidate_providers("realizer", json_mode=False)

    assert candidates[0] == "gemini"
    assert "openai" in candidates


@pytest.mark.asyncio
async def test_invoke_text_gemini_falls_back_to_openai(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "google-test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(inference_router, "DEFAULT_PROVIDER", "gemini")
    monkeypatch.setattr(inference_router, "ROUTING_MODE", "auto")
    monkeypatch.setattr(inference_router, "FALLBACK_ENABLED", True)

    async def fake_call_provider(provider, messages, *, json_mode, temperature, max_tokens):
        if provider == "gemini":
            raise RuntimeError("gemini unavailable")
        return ("Recovered via OpenAI", "gpt-4o")

    monkeypatch.setattr(inference_router, "_call_provider", fake_call_provider)

    content, meta = await inference_router.invoke_text(
        [{"role": "system", "content": "test"}],
        task="realizer",
    )

    assert content == "Recovered via OpenAI"
    assert meta["provider"] == "openai"
    assert meta["fallback_used"] is True
    assert meta["attempts"][0]["provider"] == "gemini"
    assert meta["attempts"][0]["status"] == "error"


@pytest.mark.asyncio
async def test_invoke_json_excludes_gemini_even_when_default(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "google-test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setattr(inference_router, "DEFAULT_PROVIDER", "gemini")
    monkeypatch.setattr(inference_router, "ROUTING_MODE", "auto")
    monkeypatch.setattr(inference_router, "FALLBACK_ENABLED", True)

    seen_providers = []

    async def fake_call_provider(provider, messages, *, json_mode, temperature, max_tokens):
        seen_providers.append(provider)
        return ('{"ok": true}', "gpt-4o-mini")

    monkeypatch.setattr(inference_router, "_call_provider", fake_call_provider)

    payload, meta = await inference_router.invoke_json(
        [{"role": "system", "content": "Return JSON"}],
        task="planner",
    )

    assert payload == {"ok": True}
    assert meta["provider"] == "openai"
    assert "gemini" not in seen_providers
