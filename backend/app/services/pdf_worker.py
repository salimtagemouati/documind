"""Bounded PDF extraction subprocess for the Linux service."""
import io
import json
import sys

from pypdf import PdfReader


def parse(file_bytes: bytes):
    reader = PdfReader(io.BytesIO(file_bytes))
    if reader.is_encrypted:
        raise ValueError("Encrypted PDFs are not supported. Upload an unlocked copy.")
    if len(reader.pages) > 500:
        raise ValueError("PDF exceeds the 500-page processing limit.")
    pages = []
    characters = 0
    for page in reader.pages:
        text = page.extract_text() or ""
        characters += len(text) + 1
        if characters > 2_000_001:
            raise ValueError("Extracted text exceeds the 2 million character limit.")
        pages.append(text.strip())
    full_text = "\f".join(pages)
    return full_text, len(reader.pages)


if __name__ == "__main__":
    import resource

    resource.setrlimit(resource.RLIMIT_CPU, (15, 16))
    if sys.platform.startswith("linux"):
        memory = 512 * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    try:
        text, pages = parse(sys.stdin.buffer.read())
        print(json.dumps({"text": text, "pages": pages}, ensure_ascii=False))
    except ValueError as exc:
        # Limit messages crossing the worker boundary.
        print(json.dumps({"error": str(exc)[:200]}))
