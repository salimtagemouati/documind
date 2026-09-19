"""
LLM Rate Limiter & Concurrency Controller

Protects Gemini/multi-provider free-tier quotas using:
1. asyncio.Semaphore for bounded concurrency (LLM_MAX_CONCURRENCY, default 3)
2. Exponential backoff with jitter on 429 / RateLimit / ServiceUnavailable errors (tenacity)
"""
import asyncio
from typing import Any, Callable, Coroutine, TypeVar

import litellm
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
)

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

T = TypeVar("T")

_semaphore: asyncio.Semaphore | None = None


def get_llm_semaphore() -> asyncio.Semaphore:
    """Lazily instantiate Semaphore to bind to the active event loop."""
    global _semaphore
    if _semaphore is None:
        concurrency = getattr(settings, "LLM_MAX_CONCURRENCY", 3)
        _semaphore = asyncio.Semaphore(concurrency)
    return _semaphore


def is_retryable_llm_error(exc: BaseException) -> bool:
    """Check if exception is a transient or rate-limit error that should be retried."""
    if isinstance(exc, (litellm.RateLimitError, litellm.ServiceUnavailableError, litellm.Timeout)):
        return True
    msg = str(exc).lower()
    if any(term in msg for term in ["429", "resource_exhausted", "rate limit", "quota", "overloaded", "unavailable"]):
        return True
    return False


async def call_with_limits(coro_factory: Callable[[], Coroutine[Any, Any, T]]) -> T:
    """
    Execute an LLM coroutine under concurrency semaphore and rate-limit retry protection.

    Usage:
        result = await call_with_limits(lambda: litellm.acompletion(...))
    """
    sem = get_llm_semaphore()
    async with sem:
        async for attempt in AsyncRetrying(
            retry=retry_if_exception(is_retryable_llm_error),
            stop=stop_after_attempt(6),
            wait=wait_random_exponential(min=2, max=60),
            reraise=True,
        ):
            with attempt:
                try:
                    return await coro_factory()
                except Exception as e:
                    if is_retryable_llm_error(e):
                        logger.warning("llm_rate_limit_retry", attempt=attempt.retry_state.attempt_number, error=str(e)[:120])
                    raise
