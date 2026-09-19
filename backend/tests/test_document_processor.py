"""
Tests for document processing service.
Run: pytest tests/ -v
"""
import pytest
from app.services.document_processor import chunk_text, count_tokens, extract_text_from_txt


def test_chunk_text_basic():
    text = "This is sentence one. This is sentence two. This is sentence three. " * 20
    chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)
    assert len(chunks) > 1
    for chunk in chunks:
        assert "content" in chunk
        assert "chunk_index" in chunk
        assert chunk["token_count"] > 0


def test_chunk_overlap_creates_continuity():
    """Consecutive chunks should share some content (overlap)."""
    text = ". ".join([f"Sentence number {i} with some content" for i in range(50)])
    chunks = chunk_text(text, chunk_size=80, chunk_overlap=30)
    if len(chunks) >= 2:
        # The end of chunk 0 and start of chunk 1 should share words
        end_of_first = chunks[0]["content"][-100:]
        start_of_second = chunks[1]["content"][:100]
        shared = set(end_of_first.split()) & set(start_of_second.split())
        assert len(shared) > 0, "Expected overlapping tokens between consecutive chunks"


def test_chunk_respects_max():
    """Should not exceed MAX_CHUNKS_PER_DOC."""
    # ~2000 tokens of text
    long_text = "The quick brown fox jumps over the lazy dog. " * 200
    chunks = chunk_text(long_text, chunk_size=50, chunk_overlap=10)
    from app.core.config import get_settings
    assert len(chunks) <= get_settings().MAX_CHUNKS_PER_DOC


def test_count_tokens():
    text = "Hello, world!"
    count = count_tokens(text)
    assert count > 0
    assert count < 10  # Should be around 4 tokens


def test_extract_txt_utf8():
    content = "Hello, this is a UTF-8 document with special chars: é à ü"
    result = extract_text_from_txt(content.encode("utf-8"))
    assert "UTF-8" in result
    assert "é" in result


def test_extract_txt_latin1_fallback():
    content = "Caf\xe9"  # 'Café' in latin-1
    result = extract_text_from_txt(content.encode("latin-1"))
    assert "Caf" in result


def test_empty_text_returns_no_chunks():
    chunks = chunk_text("")
    assert chunks == []


def test_single_short_sentence():
    chunks = chunk_text("Hello world.", chunk_size=100, chunk_overlap=20)
    assert len(chunks) == 1
    assert "Hello world" in chunks[0]["content"]
