from typing import List

from src.config import CHUNK_OVERLAP_CHARS, CHUNK_SIZE_CHARS


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE_CHARS,
                overlap: int = CHUNK_OVERLAP_CHARS) -> List[str]:
    """
    Simple sliding-window character chunker. Good enough for short internal
    documents; swap in a token-aware / semantic chunker for production use
    with longer or more heterogeneous documents.
    """
    text = text.strip()
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = end - overlap
    return chunks
