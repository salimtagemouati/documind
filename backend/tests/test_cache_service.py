import pytest
from copy import deepcopy

class MockRedis:
    def __init__(self):
        self._data = {}
    
    async def get(self, key):
        if key in self._data:
            return self._data[key]
        return None
        
    async def setex(self, key, ttl, value):
        self._data[key] = value

    async def delete(self, *keys):
        for key in keys:
            self._data.pop(key, None)
            
    async def keys(self, pattern):
        import re
        regex = pattern.replace('*', '.*').replace('?', '.')
        try:
            return [k for k in self._data.keys() if re.match(regex, k)]
        except Exception:
            return []

@pytest.fixture
def mock_redis(monkeypatch):
    import app.services.cache_service as cache
    mr = MockRedis()
    monkeypatch.setattr(cache, "_redis", mr)
    monkeypatch.setattr(cache, "_use_redis", True)
    return mr

@pytest.mark.asyncio
async def test_set_and_get_cache(mock_redis):
    from uuid import uuid4
    from app.services.cache_service import set_cached_answer, get_cached_answer
    
    doc_id = str(uuid4())
    query = "What is X?"
    response_data = {
        "question": query, "answer": "Y", "sources": [], "model_used": "gpt", "tokens_used": 10, "latency_ms": 100, "from_cache": False
    }
    
    await set_cached_answer(doc_id, query, response_data)
    cached = await get_cached_answer(doc_id, query)
    
    assert cached is not None
    assert cached["answer"] == "Y"
    
@pytest.mark.asyncio
async def test_invalidate_cache(mock_redis):
    from uuid import uuid4
    from app.services.cache_service import invalidate_document_cache, set_cached_answer, get_cached_answer
    
    doc_id = str(uuid4())
    query = "What is X?"
    response_data = {
        "question": query, "answer": "Y", "sources": [], "model_used": "gpt", "tokens_used": 10, "latency_ms": 100, "from_cache": False
    }
    
    await set_cached_answer(doc_id, query, response_data)
    await invalidate_document_cache(doc_id)
    
    cached = await get_cached_answer(doc_id, query)
    assert cached is None
