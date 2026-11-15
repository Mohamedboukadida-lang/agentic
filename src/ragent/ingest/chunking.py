"""Two chunking strategies.

fixed      A sliding window of `size` words with `overlap` words shared between
           neighbours. Ignores document structure.
structure  Split on headings first, then pack whole paragraphs into chunks of at most
           `size` words. A paragraph longer than `size` falls back to the sliding window.
           Each chunk remembers its heading path in `section`.

Sizes are in whitespace-separated words (see text.count_tokens).
"""

from __future__ import annotations

import re

from ragent.models import Chunk, Document
from ragent.text import count_tokens

_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


def split_sections(text: str) -> list[tuple[str, str]]:
    """Return (heading_path, body) pairs. Headings inside ``` fences are ignored."""
    sections: list[tuple[str, str]] = []
    path: list[str] = []
    current = ""
    buffer: list[str] = []
    in_fence = False

    def flush() -> None:
        body = "\n".join(buffer).strip()
        if body:
            sections.append((current, body))
        buffer.clear()

    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            buffer.append(line)
            continue
        match = None if in_fence else _HEADING.match(line)
        if match is None:
            buffer.append(line)
            continue
        flush()
        level = len(match.group(1))
        del path[level - 1 :]
        while len(path) < level - 1:
            path.append("")
        path.append(match.group(2).strip())
        current = " > ".join(p for p in path if p)
    flush()
    return sections


def _window(words: list[str], size: int, overlap: int) -> list[str]:
    step = size - overlap
    pieces: list[str] = []
    for start in range(0, len(words), step):
        pieces.append(" ".join(words[start : start + size]))
        if start + size >= len(words):
            break
    return pieces


def _pack(paragraphs: list[str], size: int, overlap: int) -> list[str]:
    pieces: list[str] = []
    current: list[str] = []
    current_size = 0

    def flush() -> None:
        nonlocal current_size
        if current:
            pieces.append("\n\n".join(current))
            current.clear()
            current_size = 0

    for paragraph in paragraphs:
        n = count_tokens(paragraph)
        if n > size:
            flush()
            pieces.extend(_window(paragraph.split(), size, overlap))
            continue
        if current_size + n > size:
            flush()
        current.append(paragraph)
        current_size += n
    flush()
    return pieces


def _check(size: int, overlap: int) -> None:
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("need size > overlap >= 0")


def chunk_fixed(doc: Document, size: int, overlap: int) -> list[Chunk]:
    _check(size, overlap)
    pieces = _window(doc.text.split(), size, overlap)
    return [Chunk(doc.source, i, "", piece, count_tokens(piece)) for i, piece in enumerate(pieces)]


def chunk_structure(doc: Document, size: int, overlap: int) -> list[Chunk]:
    _check(size, overlap)
    chunks: list[Chunk] = []
    for section, body in split_sections(doc.text):
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        for piece in _pack(paragraphs, size, overlap):
            chunks.append(Chunk(doc.source, len(chunks), section, piece, count_tokens(piece)))
    return chunks


def chunk_document(doc: Document, strategy: str, size: int, overlap: int) -> list[Chunk]:
    if strategy == "fixed":
        return chunk_fixed(doc, size, overlap)
    if strategy == "structure":
        return chunk_structure(doc, size, overlap)
    raise ValueError(f"unknown chunk strategy: {strategy}")
