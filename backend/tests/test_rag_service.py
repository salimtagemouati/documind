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

