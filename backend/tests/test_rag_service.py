from uuid import uuid4
import pytest
from sqlalchemy import select

from app.models.models import Document, DocumentChunk, DocumentStatus, User
from app.services.rag_service import build_document_index, delete_document_index, retrieve_similar_chunks


@pytest.mark.asyncio
async def test_build_and_retrieve_pgvector(db_session):
    # Setup test user and document
    user = User(
        email="vector_test@example.com",
        hashed_password="hash",
        full_name="Vector User",
    )
    db_session.add(user)
    await db_session.flush()

    doc_id = uuid4()
    doc = Document(
        id=doc_id,
        user_id=user.id,
        filename="test.pdf",
        original_filename="test.pdf",
        file_type="pdf",
        file_size_bytes=100,
        storage_path="path/test.pdf",
        status=DocumentStatus.ready,
    )
    db_session.add(doc)
    await db_session.commit()

    chunks = [
        {"content": "This is alpha content about distributed systems.", "chunk_index": 0, "token_count": 8, "page_number": 1},
        {"content": "This is beta content about database consensus.", "chunk_index": 1, "token_count": 7, "page_number": 1},
    ]

    # Build pgvector index in database
    await build_document_index(db_session, doc_id, chunks)

    # Verify chunks exist in DB
    result = await db_session.execute(select(DocumentChunk).where(DocumentChunk.document_id == doc_id))
    db_chunks = result.scalars().all()
    assert len(db_chunks) == 2
    assert db_chunks[0].embedding is not None

    # Retrieve chunks
    retrieved = await retrieve_similar_chunks(
        db=db_session,
        document_id=doc_id,
        query="Tell me about distributed systems",
        top_k=2,
        threshold=0.0,
        enable_hybrid=False,
    )

    assert len(retrieved) > 0
    assert "content" in retrieved[0]
    assert "similarity_score" in retrieved[0]

    # Test delete_document_index does not raise error
    delete_document_index(doc_id)


@pytest.mark.asyncio
async def test_retrieve_empty_document(db_session):
    non_existent = uuid4()
    results = await retrieve_similar_chunks(
        db=db_session,
        document_id=non_existent,
        query="Hello",
        top_k=2,
    )
    assert results == []


@pytest.mark.asyncio
async def test_multi_document_retrieval(db_session):
    user = User(
        email="multi_doc@example.com",
        hashed_password="hash",
        full_name="Multi Doc User",
    )
    db_session.add(user)
    await db_session.flush()

    doc1_id = uuid4()
    doc2_id = uuid4()

    doc1 = Document(
        id=doc1_id,
        user_id=user.id,
        filename="doc1.pdf",
        original_filename="Contract A.pdf",
        file_type="pdf",
        file_size_bytes=100,
        storage_path="path/doc1.pdf",
        status=DocumentStatus.ready,
    )
    doc2 = Document(
        id=doc2_id,
        user_id=user.id,
        filename="doc2.pdf",
        original_filename="Contract B.pdf",
        file_type="pdf",
        file_size_bytes=100,
        storage_path="path/doc2.pdf",
        status=DocumentStatus.ready,
    )
    db_session.add_all([doc1, doc2])
    await db_session.commit()

    await build_document_index(db_session, doc1_id, [{"content": "Contract A liability cap $100k", "chunk_index": 0, "token_count": 6}])
    await build_document_index(db_session, doc2_id, [{"content": "Contract B liability cap $200k", "chunk_index": 0, "token_count": 6}])

    retrieved = await retrieve_similar_chunks(
        db=db_session,
        document_id=[doc1_id, doc2_id],
        query="What is the liability cap?",
        top_k=4,
        threshold=0.0,
        enable_hybrid=False,
    )

    assert len(retrieved) == 2
    doc_names = {r["document_name"] for r in retrieved}
    assert "Contract A.pdf" in doc_names
    assert "Contract B.pdf" in doc_names


@pytest.mark.asyncio
async def test_embedding_dimensions_and_unit_norm():
    import numpy as np
    from app.core.config import get_settings
    from app.services.rag_service import embed_query, embed_texts

    settings = get_settings()

    # Query embedding
    q_vec = await embed_query("Test retrieval query")
    assert len(q_vec) == settings.EMBEDDING_DIM
    assert np.isclose(np.linalg.norm(q_vec), 1.0, atol=1e-4)

    # Batch texts embedding
    texts = ["First passage to embed", "Second passage to embed"]
    batch_arr = await embed_texts(texts)
    assert batch_arr.shape == (2, settings.EMBEDDING_DIM)
    for vec in batch_arr:
        assert len(vec) == settings.EMBEDDING_DIM
        assert np.isclose(np.linalg.norm(vec), 1.0, atol=1e-4)


@pytest.mark.asyncio
async def test_rerank_chunks_fallback_on_invalid_json():
    """Verify that when LLM produces invalid JSON, rerank_chunks falls back to composite scoring without raising."""
    from unittest.mock import MagicMock, patch
    from app.services.rerank_service import rerank_chunks

    candidates = [
        {"content": "Irrelevant text about gardening", "chunk_index": 0, "similarity_score": 0.8},
        {"content": "Direct answer about liability dollar caps $500,000", "chunk_index": 1, "similarity_score": 0.75},
    ]

    # Mock litellm returning broken non-JSON text
    mock_choice = MagicMock()
    mock_choice.message.content = "I am an AI and here is my freeform analysis without JSON."
    mock_resp = MagicMock(choices=[mock_choice])

    with patch("litellm.acompletion", return_value=mock_resp):
        reranked = await rerank_chunks(query="What is the liability cap?", chunks=candidates, top_k=2)

    assert len(reranked) == 2
    # Composite fallback gives higher score to text with exact keyword overlap ("liability", "cap")
    assert "liability dollar caps" in reranked[0]["content"]
    assert "rerank_score" in reranked[0]


@pytest.mark.asyncio
async def test_rerank_chunks_with_fences_and_commentary():
    """Verify robust extraction when JSON array is wrapped in markdown code blocks or commentary."""
    from unittest.mock import MagicMock, patch
    from app.services.rerank_service import rerank_chunks

    candidates = [
        {"content": "Candidate 0", "chunk_index": 0, "similarity_score": 0.5},
        {"content": "Candidate 1", "chunk_index": 1, "similarity_score": 0.5},
    ]

    mock_choice = MagicMock()
    mock_choice.message.content = "Here are your scores:\n```json\n[{\"id\": 0, \"score\": 2.0}, {\"id\": 1, \"score\": 9.5}]\n```\nHope that helps!"
    mock_resp = MagicMock(choices=[mock_choice])

    with patch("litellm.acompletion", return_value=mock_resp):
        reranked = await rerank_chunks(query="test query", chunks=candidates, top_k=2)

    assert len(reranked) == 2
    assert reranked[0]["chunk_index"] == 1
    assert reranked[0]["rerank_score"] > reranked[1]["rerank_score"]


@pytest.mark.asyncio
async def test_retrieve_user_isolation(db_session):
    """Verify that retrieve_similar_chunks strictly respects document_id filtering preventing cross-tenant leakage."""
    user1 = User(email="tenant1@example.com", hashed_password="h", full_name="User 1")
    user2 = User(email="tenant2@example.com", hashed_password="h", full_name="User 2")
    db_session.add_all([user1, user2])
    await db_session.flush()

    doc1_id = uuid4()
    doc2_id = uuid4()

    doc1 = Document(
        id=doc1_id, user_id=user1.id, filename="tenant1.txt", original_filename="tenant1.txt",
        file_type="txt", file_size_bytes=50, storage_path="p1", status=DocumentStatus.ready,
    )
    doc2 = Document(
        id=doc2_id, user_id=user2.id, filename="tenant2.txt", original_filename="tenant2.txt",
        file_type="txt", file_size_bytes=50, storage_path="p2", status=DocumentStatus.ready,
    )
    db_session.add_all([doc1, doc2])
    await db_session.commit()

    await build_document_index(db_session, doc1_id, [{"content": "Secret credentials for tenant 1", "chunk_index": 0, "token_count": 5}])
    await build_document_index(db_session, doc2_id, [{"content": "Secret credentials for tenant 2", "chunk_index": 0, "token_count": 5}])

    # Querying tenant1's document should never return tenant2's chunks
    retrieved = await retrieve_similar_chunks(
        db=db_session,
        document_id=doc1_id,
        query="Secret credentials",
        top_k=5,
        threshold=0.0,
        enable_hybrid=False,
    )
    assert len(retrieved) == 1
    assert retrieved[0]["document_id"] == doc1_id
    assert "tenant 1" in retrieved[0]["content"]


