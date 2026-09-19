"""
Unit tests for LLM rate limiter, concurrency controller, and retry mechanism.
"""
from unittest.mock import AsyncMock, patch
import litellm
import pytest

from app.services.llm_limiter import call_with_limits, extract_retry_delay, is_retryable_llm_error


@pytest.mark.asyncio
async def test_call_with_limits_retries_429_then_succeeds():
    """Simulate 2 rate-limit errors (429) followed by success -> exactly 3 attempts."""
    call_count = 0

    async def flaky_llm_call():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise litellm.RateLimitError(
                message="Resource has been exhausted (e.g. check quota) 429",
                model="gemini/gemini-3.6-flash",
                llm_provider="gemini",
            )
        return {"result": "success", "attempts": call_count}

    # Patch tenacity wait time to 0 to keep unit tests instantaneous
    with patch("app.services.llm_limiter.wait_random_exponential.__call__", return_value=0.01):
        result = await call_with_limits(flaky_llm_call)

    assert call_count == 3
    assert result["result"] == "success"
    assert result["attempts"] == 3


def test_is_retryable_llm_error():
    assert is_retryable_llm_error(litellm.RateLimitError("rate limit", model="m", llm_provider="p")) is True
    assert is_retryable_llm_error(litellm.ServiceUnavailableError("unavailable", model="m", llm_provider="p")) is True
    assert is_retryable_llm_error(litellm.Timeout("timeout", model="m", llm_provider="p")) is True
    assert is_retryable_llm_error(RuntimeError("HTTP 429 RESOURCE_EXHAUSTED")) is True
    assert is_retryable_llm_error(ValueError("Invalid argument")) is False


def test_extract_retry_delay():
    assert extract_retry_delay(RuntimeError("Quota exceeded. Please retry in 46.14s.")) == 46.14
    assert extract_retry_delay(RuntimeError('{"retryDelay": "30s"}')) == 30.0
    assert extract_retry_delay(ValueError("generic error")) is None
