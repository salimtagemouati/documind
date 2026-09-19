"""
LLM Rate Limiter & Concurrency Controller

Protects Gemini/multi-provider free-tier quotas using:
1. asyncio.Semaphore for bounded concurrency (LLM_MAX_CONCURRENCY, default 3)
2. Exponential backoff with jitter on 429 / RateLimit / ServiceUnavailable errors (tenacity)
"""
import asyncio
import re
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


def extract_retry_delay(exc: BaseException) -> float | None:
    """Extract explicit retry delay seconds provided by Gemini / Google AI Studio error payloads."""
    msg = str(exc)
    m = re.search(r"retry in ([\d\.]+)s", msg, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    m2 = re.search(r'retryDelay["\']?:\s*["\']?(\d+)s?', msg, re.IGNORECASE)
    if m2:
        try:
            return float(m2.group(1))
        except ValueError:
            pass
    return None


def is_retryable_llm_error(exc: BaseException) -> bool:
    """Check if exception is a transient or rate-limit error that should be retried."""
    if isinstance(exc, (litellm.RateLimitError, litellm.ServiceUnavailableError, litellm.Timeout)):
        return True
    msg = str(exc).lower()
    if any(term in msg for term in ["429", "resource_exhausted", "rate limit", "quota", "overloaded", "unavailable"]):
        return True
    return False


class SmartWait:
    """Combines explicit API-requested retryDelay with exponential backoff and jitter."""
    def __init__(self):
        self.fallback = wait_random_exponential(min=2, max=60)

    def __call__(self, retry_state):
        exc = retry_state.outcome.exception() if retry_state.outcome else None
        if exc:
            delay = extract_retry_delay(exc)
            if delay is not None:
                # Add 2 seconds buffer over Google's required retry window
                return delay + 2.0
        return self.fallback(retry_state)


_last_request_time: float = 0.0
_pacing_lock = asyncio.Lock()


async def _enforce_pacing(min_interval: float = 2.0) -> None:
    """Enforce minimum delay between calls to stay under free tier RPM quotas."""
    if getattr(settings, "ENVIRONMENT", "") == "test":
        return
    global _last_request_time
    async with _pacing_lock:
        loop = asyncio.get_event_loop()
        now = loop.time()
        elapsed = now - _last_request_time
        if elapsed < min_interval:
            wait_time = min_interval - elapsed
            await asyncio.sleep(wait_time)
        _last_request_time = loop.time()


async def call_with_limits(coro_factory: Callable[[], Coroutine[Any, Any, T]]) -> T:
    """
    Execute an LLM coroutine under concurrency semaphore and rate-limit retry protection.

    Usage:
        result = await call_with_limits(lambda: litellm.acompletion(...))
    """
    sem = get_llm_semaphore()
    smart_wait = SmartWait()

    async with sem:
        async for attempt in AsyncRetrying(
            retry=retry_if_exception(is_retryable_llm_error),
            stop=stop_after_attempt(10),
            wait=smart_wait,
            reraise=True,
        ):
            with attempt:
                try:
                    await _enforce_pacing()
                    return await coro_factory()
                except Exception as e:
                    if is_retryable_llm_error(e):
                        delay = extract_retry_delay(e)
                        logger.warning(
                            "llm_rate_limit_retry",
                            attempt=attempt.retry_state.attempt_number,
                            retry_delay_detected=delay,
                            error_type=type(e).__name__,
                        )
                    raise
