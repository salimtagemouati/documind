import pytest
from uuid import uuid4
from app.services.rag_service import build_document_index, retrieve_similar_chunks, delete_document_index

@pytest.mark.asyncio
async def test_build_and_delete_index(tmp_path, monkeypatch):
    import app.services.rag_service as rag
    monkeypatch.setattr(rag, "FAISS_INDEX_DIR", tmp_path)
    
    doc_id = uuid4()
    chunks = [
        {"content": "This is a test chunk", "chunk_index": 0, "token_count": 5, "page_number": 1},
        {"content": "Another test chunk right here", "chunk_index": 1, "token_count": 6, "page_number": 1}
    ]
    
    await build_document_index(doc_id, chunks)
    
    idx_file = tmp_path / f"{doc_id}.faiss"
    meta_file = tmp_path / f"{doc_id}.meta"
    assert idx_file.exists()
    assert meta_file.exists()
    
    delete_document_index(doc_id)
    assert not idx_file.exists()
    assert not meta_file.exists()


@pytest.mark.asyncio
async def test_retrieve_similar_chunks(tmp_path, monkeypatch):
    import app.services.rag_service as rag
    monkeypatch.setattr(rag, "FAISS_INDEX_DIR", tmp_path)
    
    doc_id = uuid4()
    chunks = [
        {"content": "Test content alpha", "chunk_index": 0, "token_count": 5, "page_number": 1},
        {"content": "Test content beta", "chunk_index": 1, "token_count": 5, "page_number": 1}
    ]
    await build_document_index(doc_id, chunks)
    
    results = await retrieve_similar_chunks(doc_id, "Find alpha", top_k=2, threshold=0.0)
    
    assert len(results) > 0
    assert "content" in results[0]
    assert "similarity_score" in results[0]


@pytest.mark.asyncio
async def test_retrieve_missing_index(tmp_path, monkeypatch):
    import app.services.rag_service as rag
    monkeypatch.setattr(rag, "FAISS_INDEX_DIR", tmp_path)
    
    doc_id = uuid4()
    with pytest.raises(ValueError, match="No FAISS index found"):
        await retrieve_similar_chunks(doc_id, "Query")
