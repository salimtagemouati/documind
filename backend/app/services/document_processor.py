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
from zipfile import BadZipFile, ZipFile

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
    if reader.is_encrypted:
        raise ValueError("Encrypted PDFs are not supported. Upload an unlocked copy.")
    if len(reader.pages) > 500:
        raise ValueError("PDF exceeds the 500-page processing limit.")
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text.strip())
    full_text = "\f".join(pages)
    return full_text, len(reader.pages)


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text from DOCX preserving paragraph structure."""
    try:
        with ZipFile(io.BytesIO(file_bytes)) as archive:
            if sum(item.file_size for item in archive.infolist()) > 50 * 1024 * 1024:
                raise ValueError("DOCX expanded content exceeds 50 MB.")
    except BadZipFile as exc:
        raise ValueError("Invalid DOCX file.") from exc
    doc = DocxDocument(io.BytesIO(file_bytes))
    paragraphs = []
    for block in doc.iter_inner_content():
        if hasattr(block, "rows"):
            paragraphs.extend(" | ".join(cell.text for cell in row.cells) for row in block.rows)
        elif block.text.strip():
            paragraphs.append(block.text.strip())
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

    if not text.strip():
        raise ValueError("No readable text found. Scanned PDFs require OCR before upload.")
    if len(text) > 2_000_000:
        raise ValueError("Extracted text exceeds the 2 million character limit.")
    return text, pages


# ─── Chunking ────────────────────────────────────────────────────────────────
def count_tokens(text: str) -> int:
    return len(_tokenizer.encode(text, disallowed_special=()))


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
    chunk_size = settings.CHUNK_SIZE if chunk_size is None else chunk_size
    chunk_overlap = settings.CHUNK_OVERLAP if chunk_overlap is None else chunk_overlap
    if chunk_size <= 0 or not 0 <= chunk_overlap < chunk_size:
        raise ValueError("Require chunk_size > 0 and 0 <= chunk_overlap < chunk_size")
    chunks = []
    page_offset = 0
    # PDF extraction preserves physical page boundaries, including blank pages.
    pages = text.split("\f")
    for page_index, page in enumerate(pages):
        start = 0
        while start < len(page):
            while start < len(page) and page[start].isspace():
                start += 1
            if start == len(page):
                break
            low, high = start + 1, min(len(page), start + chunk_size * 8)
            end = start
            while low <= high:
                mid = (low + high) // 2
                if count_tokens(page[start:mid]) <= chunk_size:
                    end, low = mid, mid + 1
                else:
                    high = mid - 1
            if end == start:
                raise ValueError("Chunk size cannot encode a single character")
            if end < len(page):
                boundaries = list(re.finditer(r"[.!?]\s+|\n\n|\s+", page[start:end]))
                if boundaries and boundaries[-1].end() >= (end - start) // 2:
                    end = start + boundaries[-1].end()
            content = page[start:end]
            chunks.append({
                "content": content, "chunk_index": len(chunks),
                "token_count": count_tokens(content),
                "char_start": page_offset + start, "char_end": page_offset + end,
                "page_number": page_index + 1 if len(pages) > 1 else None,
            })
            if len(chunks) > settings.MAX_CHUNKS_PER_DOC:
                raise ValueError("Document exceeds the chunk limit; split it into smaller files.")
            if end == len(page):
                break
            next_start = end
            if chunk_overlap:
                low, high = start + 1, end
                while low <= high:
                    mid = (low + high) // 2
                    if count_tokens(page[mid:end]) <= chunk_overlap:
                        next_start, high = mid, mid - 1
                    else:
                        low = mid + 1
            start = max(start + 1, next_start)
        page_offset += len(page) + 1
    return chunks


def validate_file(filename: str, file_size_bytes: int, file_type: str) -> None:
    """Raise ValueError if file doesn't meet constraints."""
    ext = Path(filename).suffix.lstrip(".").lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise ValueError(
            f"File type '{ext}' not supported. Allowed: {settings.ALLOWED_EXTENSIONS}"
        )
    if file_size_bytes <= 0:
        raise ValueError("The uploaded file is empty.")
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if file_size_bytes > max_bytes:
        raise ValueError(
            f"File too large ({file_size_bytes / 1024 / 1024:.1f} MB). "
            f"Maximum: {settings.MAX_FILE_SIZE_MB} MB"
        )
