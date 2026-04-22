"""
Document Processing Service
Handles: file validation, text extraction (PDF/DOCX/TXT), smart chunking.

Chunking strategy:
- Respect sentence/paragraph boundaries (not raw token splits)
- Overlap between chunks preserves context for RAG retrieval
- Token counting via tiktoken (same tokenizer as OpenAI embeddings)
"""
import io
import re
from pathlib import Path
from typing import List, Tuple

import tiktoken
from docx import Document as DocxDocument
from pypdf import PdfReader

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

# Use the embedding model's tokenizer for accurate counts
_tokenizer = tiktoken.get_encoding("cl100k_base")


# ─── Text extraction ──────────────────────────────────────────────────────────
def extract_text_from_pdf(file_bytes: bytes) -> Tuple[str, int]:
    """Extract full text from PDF. Returns (text, page_count)."""
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text.strip())
    full_text = "\n\n".join(p for p in pages if p)
    return full_text, len(reader.pages)


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text from DOCX preserving paragraph structure."""
    doc = DocxDocument(io.BytesIO(file_bytes))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)


def extract_text_from_txt(file_bytes: bytes) -> str:
    """Decode plain text with charset detection fallback."""
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        import chardet
        encoding = chardet.detect(file_bytes)["encoding"] or "latin-1"
        return file_bytes.decode(encoding, errors="replace")


def extract_text(file_bytes: bytes, file_type: str) -> Tuple[str, int]:
    """
    Route to the right extractor. Returns (text, page_count).
    page_count is meaningful only for PDFs.
    """
    file_type = file_type.lower().lstrip(".")

    if file_type == "pdf":
        text, pages = extract_text_from_pdf(file_bytes)
    elif file_type == "docx":
        text = extract_text_from_docx(file_bytes)
        pages = None
    elif file_type in ("txt", "md"):
        text = extract_text_from_txt(file_bytes)
        pages = None
    else:
        raise ValueError(f"Unsupported file type: {file_type}")

    # Clean whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)  # Collapse excessive blank lines
    text = re.sub(r"[ \t]{2,}", " ", text)  # Collapse inline whitespace

    return text.strip(), pages


# ─── Chunking ────────────────────────────────────────────────────────────────
def count_tokens(text: str) -> int:
    return len(_tokenizer.encode(text))


def _split_into_sentences(text: str) -> List[str]:
    """Naive but effective sentence splitter that handles common edge cases."""
    # Split on sentence-ending punctuation followed by space+capital or newline
    pattern = r'(?<=[.!?])\s+(?=[A-Z\u00C0-\u017E\d])'
    sentences = re.split(pattern, text)
    # Also split on double newlines (paragraph breaks)
    result = []
    for sent in sentences:
        parts = sent.split("\n\n")
        result.extend(p.strip() for p in parts if p.strip())
    return result


def chunk_text(
    text: str,
    chunk_size: int = None,
    chunk_overlap: int = None,
) -> List[dict]:
    """
    Split text into overlapping chunks respecting sentence boundaries.

    Returns list of dicts:
    {
        "content": str,
        "chunk_index": int,
        "token_count": int,
        "char_start": int,
        "char_end": int,
    }

    Algorithm:
    1. Split document into sentences
    2. Greedily build chunks by adding sentences until chunk_size is reached
    3. Start next chunk from the overlap boundary (last N tokens of previous chunk)
    """
    chunk_size = chunk_size or settings.CHUNK_SIZE
    chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP
    max_chunks = settings.MAX_CHUNKS_PER_DOC

    sentences = _split_into_sentences(text)
    if not sentences:
        return []

    chunks = []
    current_sentences: List[str] = []
    current_tokens = 0
    char_pos = 0

    for sentence in sentences:
        s_tokens = count_tokens(sentence)

        # If single sentence exceeds chunk size, split it hard
        if s_tokens > chunk_size:
            # Flush current chunk
            if current_sentences:
                content = " ".join(current_sentences)
                chunks.append({
                    "content": content,
                    "chunk_index": len(chunks),
                    "token_count": current_tokens,
                    "char_start": char_pos - len(content),
                    "char_end": char_pos,
                })
                current_sentences, current_tokens = [], 0

            # Hard-split the long sentence by words
            words = sentence.split()
            word_chunk: List[str] = []
            w_tokens = 0
            for word in words:
                wt = count_tokens(word)
                if w_tokens + wt > chunk_size and word_chunk:
                    content = " ".join(word_chunk)
                    chunks.append({
                        "content": content,
                        "chunk_index": len(chunks),
                        "token_count": w_tokens,
                        "char_start": 0,
                        "char_end": 0,
                    })
                    word_chunk, w_tokens = [], 0
                word_chunk.append(word)
                w_tokens += wt
            if word_chunk:
                current_sentences = [" ".join(word_chunk)]
                current_tokens = w_tokens
            continue

        # If adding this sentence exceeds chunk size, flush and start new chunk
        if current_tokens + s_tokens > chunk_size and current_sentences:
            content = " ".join(current_sentences)
            chunks.append({
                "content": content,
                "chunk_index": len(chunks),
                "token_count": current_tokens,
                "char_start": 0,
                "char_end": 0,
            })

            # Build overlap: keep sentences from the end of the previous chunk
            overlap_sentences: List[str] = []
            overlap_tokens = 0
            for prev_s in reversed(current_sentences):
                pt = count_tokens(prev_s)
                if overlap_tokens + pt > chunk_overlap:
                    break
                overlap_sentences.insert(0, prev_s)
                overlap_tokens += pt

            current_sentences = overlap_sentences + [sentence]
            current_tokens = overlap_tokens + s_tokens
        else:
            current_sentences.append(sentence)
            current_tokens += s_tokens

        if len(chunks) >= max_chunks:
            logger.warning(
                "chunk_limit_reached",
                max_chunks=max_chunks,
                document_truncated=True,
            )
            break

    # Flush the last partial chunk
    if current_sentences and len(chunks) < max_chunks:
        content = " ".join(current_sentences)
        chunks.append({
            "content": content,
            "chunk_index": len(chunks),
            "token_count": current_tokens,
            "char_start": 0,
            "char_end": 0,
        })

    logger.info(
        "document_chunked",
        total_chunks=len(chunks),
        total_tokens=sum(c["token_count"] for c in chunks),
    )
    return chunks


def validate_file(filename: str, file_size_bytes: int, file_type: str) -> None:
    """Raise ValueError if file doesn't meet constraints."""
    ext = Path(filename).suffix.lstrip(".").lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise ValueError(
            f"File type '{ext}' not supported. Allowed: {settings.ALLOWED_EXTENSIONS}"
        )
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if file_size_bytes > max_bytes:
        raise ValueError(
            f"File too large ({file_size_bytes / 1024 / 1024:.1f} MB). "
            f"Maximum: {settings.MAX_FILE_SIZE_MB} MB"
        )
