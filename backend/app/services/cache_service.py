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


def _make_cache_key(prefix: str, document_id: str, *parts: str) -> str:
    """
    Stable, collision-resistant cache key.

    Format: documind:{prefix}:{document_id}:{digest}

    The raw document_id is embedded in the key so that pattern-based
    invalidation (`documind:*:{document_id}*`) actually finds the keys.
    The trailing digest preserves uniqueness across questions /
    analysis types within a single document.
    """
    raw = "|".join(str(p) for p in parts)
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"documind:{prefix}:{document_id}:{digest}"


def _normalize_question(q: str) -> str:
    """Normalize a question for cache key stability."""
    return re.sub(r"\s+", " ", q.lower().strip()).rstrip("?").strip()


async def get_cached_answer(document_id: str, question: str) -> Optional[dict]:
    key = _make_cache_key("qa", document_id, _normalize_question(question))
    r = await get_redis()
    if r:
        val = await r.get(key)
        if val:
            logger.debug("cache_hit", key=key)
            return json.loads(val)
    else:
        val = _memory_cache.get(key)
        if val:
            return val
    return None


async def set_cached_answer(document_id: str, question: str, data: dict) -> None:
    key = _make_cache_key("qa", document_id, _normalize_question(question))
    r = await get_redis()
    if r:
        await r.setex(key, settings.CACHE_TTL_SECONDS, json.dumps(data))
    else:
        _memory_cache[key] = data
    logger.debug("cache_set", key=key, ttl=settings.CACHE_TTL_SECONDS)


async def get_cached_analysis(document_id: str, analysis_type: str) -> Optional[dict]:
    """Cache document analysis results (summary, entities, sentiment)."""
    key = _make_cache_key(analysis_type, document_id, analysis_type)
    r = await get_redis()
    if r:
        val = await r.get(key)
        return json.loads(val) if val else None
    return _memory_cache.get(key)


async def set_cached_analysis(document_id: str, analysis_type: str, data: dict) -> None:
    key = _make_cache_key(analysis_type, document_id, analysis_type)
    r = await get_redis()
    if r:
        await r.setex(key, settings.CACHE_TTL_SECONDS, json.dumps(data))
    else:
        _memory_cache[key] = data


async def invalidate_document_cache(document_id: str) -> None:
    """Delete all cache entries related to a document."""
    r = await get_redis()
    if r:
        try:
            # Matches documind:{any-prefix}:{document_id}:{any-digest}
            pattern = f"documind:*:{document_id}:*"
            keys = await r.keys(pattern)
            if keys:
                await r.delete(*keys)
                logger.info("cache_invalidated", document_id=document_id, keys=len(keys))
        except Exception as e:
            logger.warning(
                "cache_invalidation_failed_redis_unavailable",
                document_id=document_id,
                error=str(e),
            )
    else:
        to_delete = [k for k in _memory_cache if f":{document_id}:" in k]
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
