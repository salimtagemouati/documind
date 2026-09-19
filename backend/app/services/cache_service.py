"""
Cache Service — Redis-backed caching for AI responses.

Why cache AI responses?
- LLM calls are expensive ($) and slow (1-5s)
- The same question asked twice on the same document should return instantly
- Cache key: SHA-256(document_id + normalized_question)

Cache invalidation strategy:
- TTL-based: entries expire after CACHE_TTL_SECONDS (default 1h)
- Explicit: when a document is deleted, sweep related cache keys

For local development without Redis: set REDIS_URL="" to use an in-memory dict fallback.
"""
import hashlib
import json
import re
from typing import Any, Optional

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

# Try to connect to Redis; fall back to in-memory dict for dev/testing
try:
    import redis.asyncio as aioredis
    _redis: Optional[aioredis.Redis] = None
    _use_redis = bool(settings.REDIS_URL)
except ImportError:
    _use_redis = False

_memory_cache: dict = {}  # Fallback — process-local, not shared across workers


async def get_redis() -> Optional[Any]:
    global _redis
    if not _use_redis:
        return None
    if _redis is None:
        _redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return _redis


def _make_cache_key(prefix: str, *parts: str) -> str:
    """Stable, collision-resistant cache key preserving prefix and document ID for invalidation."""
    if not parts:
        return f"documind:{prefix}"
    doc_id = str(parts[0])
    raw = "|".join(str(p) for p in parts[1:]) if len(parts) > 1 else ""
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16] if raw else "all"
    return f"documind:{prefix}:{doc_id}:{digest}"


def _normalize_question(q: str) -> str:
    """Normalize a question for cache key stability."""
    return re.sub(r"\s+", " ", q.lower().strip()).rstrip("?").strip()


async def get_cached_answer(document_id: str, question: str) -> Optional[dict]:
    key = _make_cache_key("qa", document_id, _normalize_question(question))
    try:
        r = await get_redis()
        if r:
            val = await r.get(key)
            if val:
                logger.debug("cache_hit", key=key)
                return json.loads(val)
    except Exception as e:
        logger.warning("redis_cache_get_failed", error_type=type(e).__name__)
    val = _memory_cache.get(key)
    if val:
        return val
    return None


async def set_cached_answer(document_id: str, question: str, data: dict) -> None:
    key = _make_cache_key("qa", document_id, _normalize_question(question))
    try:
        r = await get_redis()
        if r:
            await r.setex(key, settings.CACHE_TTL_SECONDS, json.dumps(data))
            logger.debug("cache_set", key=key, ttl=settings.CACHE_TTL_SECONDS)
            return
    except Exception as e:
        logger.warning("redis_cache_set_failed", error_type=type(e).__name__)
    _memory_cache[key] = data


async def get_cached_analysis(document_id: str, analysis_type: str) -> Optional[dict]:
    """Cache document analysis results (summary, entities, sentiment)."""
    key = _make_cache_key(analysis_type, document_id)
    try:
        r = await get_redis()
        if r:
            val = await r.get(key)
            return json.loads(val) if val else None
    except Exception as e:
        logger.warning("redis_cache_get_failed", error_type=type(e).__name__)
    return _memory_cache.get(key)


async def set_cached_analysis(document_id: str, analysis_type: str, data: dict) -> None:
    key = _make_cache_key(analysis_type, document_id)
    try:
        r = await get_redis()
        if r:
            await r.setex(key, settings.CACHE_TTL_SECONDS, json.dumps(data))
            return
    except Exception as e:
        logger.warning("redis_cache_set_failed", error_type=type(e).__name__)
    _memory_cache[key] = data


async def invalidate_document_cache(document_id: str) -> None:
    """Delete all cache entries related to a document."""
    try:
        r = await get_redis()
        if r:
            pattern = f"documind:*:{document_id}*"
            keys = await r.keys(pattern)
            if keys:
                await r.delete(*keys)
                logger.info("cache_invalidated", document_id=document_id, keys=len(keys))
    except Exception as e:
        logger.warning("redis_cache_invalidate_failed", error_type=type(e).__name__)

    to_delete = [k for k in _memory_cache if document_id in k]
    for k in to_delete:
        del _memory_cache[k]


async def get_cache_stats() -> dict:
    """Return cache statistics for admin analytics."""
    r = await get_redis()
    if r:
        info = await r.info("stats")
        return {
            "backend": "redis",
            "hits": info.get("keyspace_hits", 0),
            "misses": info.get("keyspace_misses", 0),
            "hit_rate": round(
                info.get("keyspace_hits", 0) /
                max(info.get("keyspace_hits", 0) + info.get("keyspace_misses", 1), 1),
                3,
            ),
        }
    return {
        "backend": "in-memory",
        "keys": len(_memory_cache),
    }
