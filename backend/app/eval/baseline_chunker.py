"""Frozen pre-audit chunker for reproducible local comparison; not production code."""
import re
from typing import List

from app.services.document_processor import count_tokens, logger, settings


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
