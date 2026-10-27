from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import ai_service


@pytest.mark.asyncio
async def test_groq_route_uses_groq_key_and_reports_model(monkeypatch):
    monkeypatch.setattr(ai_service.settings, "ENABLE_GROQ_GPT_OSS", True)
    monkeypatch.setattr(ai_service.settings, "GROQ_API_KEY", "groq-test")
    monkeypatch.setattr(ai_service.settings, "OPENAI_API_KEY", "openai-test")
    completion = AsyncMock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))]))
    monkeypatch.setattr(ai_service.litellm, "acompletion", completion)
    assert await ai_service._generate_text("test") == "ok"
    assert completion.await_args.kwargs["model"] == "groq/openai/gpt-oss-120b"
    assert completion.await_args.kwargs["api_key"] == "groq-test"
    assert ai_service._last_model.get() == "groq/openai/gpt-oss-120b"


@pytest.mark.asyncio
async def test_transient_failure_falls_back_once(monkeypatch):
    monkeypatch.setattr(ai_service.settings, "ENABLE_GROQ_GPT_OSS", True)
    monkeypatch.setattr(ai_service.settings, "ENABLE_GEMINI_FALLBACK", True)
    calls = []

    async def fake_limiter(factory, max_attempts=3):
        calls.append(max_attempts)
        if len(calls) == 1:
            raise TimeoutError()
        return await factory()

    completion = AsyncMock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))]))
    monkeypatch.setattr(ai_service, "call_with_limits", fake_limiter)
    monkeypatch.setattr(ai_service.litellm, "acompletion", completion)
    logger = MagicMock()
    monkeypatch.setattr(ai_service, "logger", logger)
    assert await ai_service._generate_text("test") == "ok"
    assert calls == [3, 1]
    assert completion.await_args.kwargs["model"] == ai_service.settings.GEMINI_FALLBACK_MODEL
    assert ai_service._last_model.get() == ai_service.settings.GEMINI_FALLBACK_MODEL
    assert ai_service._last_fallback.get() is True
    assert any(call.args[0] == "rag_generation" and call.kwargs["fallback"] is True
               for call in logger.info.call_args_list)


@pytest.mark.asyncio
async def test_nontransient_failure_does_not_fallback(monkeypatch):
    monkeypatch.setattr(ai_service.settings, "ENABLE_GROQ_GPT_OSS", True)
    monkeypatch.setattr(ai_service.settings, "ENABLE_GEMINI_FALLBACK", True)
    limiter = AsyncMock(side_effect=ValueError("bad request"))
    monkeypatch.setattr(ai_service, "call_with_limits", limiter)
    with pytest.raises(ValueError):
        await ai_service._generate_text("test")
    assert limiter.await_count == 1
