"""
Document Processing Progress Service — Redis Pub/Sub for real-time updates.

Architecture:
- Each processing document gets a Redis pub/sub channel: documind:progress:{document_id}
- The processing pipeline publishes JSON progress events to this channel
- WebSocket handlers subscribe to the channel and forward events to clients
- Graceful fallback: if Redis is unavailable, falls back to in-memory asyncio events

Events follow this schema:
{
    "stage": "extracting" | "chunking" | "embedding" | "analyzing" | "complete" | "error",
    "progress": 0-100 (integer),
    "message": "Human-readable status message"
}
"""
import asyncio
import json
from typing import Any, AsyncGenerator, Dict, Optional
from uuid import UUID

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

# ─── Redis pub/sub ────────────────────────────────────────────────────────────
_redis_pubsub = None
_use_redis = bool(settings.REDIS_URL)

# In-memory fallback: document_id → asyncio.Queue
_memory_channels: Dict[str, list] = {}  # document_id → list of asyncio.Queue


def _channel_name(document_id: str) -> str:
    return f"documind:progress:{document_id}"


async def _get_redis():
    """Get a dedicated Redis connection for pub/sub (separate from cache)."""
    if not _use_redis:
        return None
    try:
        import redis.asyncio as aioredis
        return aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    except Exception as e:
        logger.warning("redis_pubsub_unavailable", error=str(e))
        return None


async def publish_progress(
    document_id: str,
    stage: str,
    progress: int,
    message: str,
) -> None:
    """
    Publish a progress event for a document.
    Called from the processing pipeline at each stage.
    """
    event = json.dumps({
        "stage": stage,
        "progress": progress,
        "message": message,
        "document_id": document_id,
    })

    channel = _channel_name(document_id)

    # Try Redis first
    if _use_redis:
        try:
            r = await _get_redis()
            if r:
                await r.publish(channel, event)
                await r.close()
                return
        except Exception as e:
            logger.warning("redis_publish_failed", error=str(e))

    # Fallback: in-memory async queues
    if document_id in _memory_channels:
        for queue in _memory_channels[document_id]:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass


async def subscribe_progress(document_id: str) -> AsyncGenerator[str, None]:
    """
    Subscribe to progress events for a document.
    Yields JSON strings as they arrive.
    Used by the WebSocket handler.
    """
    channel = _channel_name(document_id)

    # Try Redis pub/sub
    if _use_redis:
        try:
            r = await _get_redis()
            if r:
                pubsub = r.pubsub()
                await pubsub.subscribe(channel)
                try:
                    async for message in pubsub.listen():
                        if message["type"] == "message":
                            yield message["data"]
                            # Check if this was a terminal event
                            try:
                                data = json.loads(message["data"])
                                if data.get("stage") in ("complete", "error"):
                                    break
                            except (json.JSONDecodeError, KeyError):
                                pass
                finally:
                    await pubsub.unsubscribe(channel)
                    await pubsub.close()
                    await r.close()
                return
        except Exception as e:
            logger.warning("redis_subscribe_failed", error=str(e))

    # Fallback: in-memory async queue
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    if document_id not in _memory_channels:
        _memory_channels[document_id] = []
    _memory_channels[document_id].append(queue)

    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=120.0)
                yield event
                # Check if terminal
                try:
                    data = json.loads(event)
                    if data.get("stage") in ("complete", "error"):
                        break
                except (json.JSONDecodeError, KeyError):
                    pass
            except asyncio.TimeoutError:
                # Send a keepalive ping after 2 min of silence
                yield json.dumps({"stage": "waiting", "progress": 0, "message": "Waiting..."})
    finally:
        if document_id in _memory_channels:
            _memory_channels[document_id].remove(queue)
            if not _memory_channels[document_id]:
                del _memory_channels[document_id]
