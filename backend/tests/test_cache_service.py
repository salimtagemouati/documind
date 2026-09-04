import pytest


class MockRedis:
    def __init__(self):
        self._data = {}

    async def get(self, key):
        return self._data.get(key)

    async def setex(self, key, ttl, value):
        self._data[key] = value

    async def delete(self, *keys):
        for key in keys:
            self._data.pop(key, None)

    async def keys(self, pattern):
        import re
        regex = re.escape(pattern).replace(r"\*", ".*").replace(r"\?", ".")
        return [k for k in self._data.keys() if re.fullmatch(regex, k)]


@pytest.fixture
def mock_redis(monkeypatch):
    """
    Replace the cache service's Redis client with a MockRedis instance.

    The real module exposes a single private connection at `_redis` which is
    lazily initialised by `get_redis()`. We bypass that by:
      - setting `_use_redis=True` so the code path tries Redis at all
      - pre-populating `_redis` with our mock so `get_redis()` short-circuits
    """
    import app.services.cache_service as cache

    mr = MockRedis()
    monkeypatch.setattr(cache, "_use_redis", True)
    monkeypatch.setattr(cache, "_redis", mr)
    return mr


@pytest.mark.asyncio
async def test_set_and_get_cached_answer(mock_redis):
    from app.services.cache_service import set_cached_answer, get_cached_answer

    doc_id = "11111111-2222-3333-4444-555555555555"
    question = "What is X?"
    payload = {
        "question": question,
        "answer": "Y",
        "sources": [],
        "model_used": "gemini-1.5-flash",
        "tokens_used": 10,
        "latency_ms": 100,
        "from_cache": True,
        "query_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    }

    await set_cached_answer(doc_id, question, payload)
    cached = await get_cached_answer(doc_id, question)

    assert cached is not None
    assert cached["answer"] == "Y"
    assert cached["question"] == question


@pytest.mark.asyncio
async def test_invalidate_document_cache(mock_redis):
    """Regression test: invalidation must actually find and delete keys."""
    from app.services.cache_service import (
        invalidate_document_cache,
        set_cached_answer,
        get_cached_answer,
    )

    doc_id = "11111111-2222-3333-4444-555555555555"
    question = "What is X?"
    payload = {
        "question": question,
        "answer": "Y",
        "sources": [],
        "model_used": "gemini-1.5-flash",
        "tokens_used": 10,
        "latency_ms": 100,
        "from_cache": True,
        "query_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    }

    await set_cached_answer(doc_id, question, payload)
    assert await get_cached_answer(doc_id, question) is not None

    await invalidate_document_cache(doc_id)
    assert await get_cached_answer(doc_id, question) is None
    # And the underlying store is actually empty
    assert mock_redis._data == {}


@pytest.mark.asyncio
async def test_invalidate_does_not_affect_other_documents(mock_redis):
    from app.services.cache_service import (
        invalidate_document_cache,
        set_cached_answer,
        get_cached_answer,
    )

    doc_a = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    doc_b = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    payload = {
        "question": "Q",
        "answer": "A",
        "sources": [],
        "model_used": "gemini-1.5-flash",
        "tokens_used": 1,
        "latency_ms": 1,
        "from_cache": True,
        "query_id": "00000000-0000-0000-0000-000000000000",
    }

    await set_cached_answer(doc_a, "Q", payload)
    await set_cached_answer(doc_b, "Q", payload)

    await invalidate_document_cache(doc_a)

    assert await get_cached_answer(doc_a, "Q") is None
    assert await get_cached_answer(doc_b, "Q") is not None


@pytest.mark.asyncio
async def test_invalidate_document_cache_handles_redis_connection_errors(monkeypatch):
    import app.services.cache_service as cache
    from app.services.cache_service import invalidate_document_cache

    class BrokenRedis:
        async def keys(self, pattern):
            raise RuntimeError("redis down")

    monkeypatch.setattr(cache, "_use_redis", True)
    monkeypatch.setattr(cache, "_redis", BrokenRedis())

    await invalidate_document_cache("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
