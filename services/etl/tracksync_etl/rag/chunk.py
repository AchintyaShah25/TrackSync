"""Section-aware chunking: keep each chunk inside one section, split long sections on
paragraph (or sub-article) boundaries, and overlap neighbours so a fact cut at a boundary
still appears whole in one chunk."""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_CHARS = 900
OVERLAP = 150


@dataclass(frozen=True)
class Chunk:
    section: str
    content: str


def _pieces(text: str) -> list[str]:
    """Split into paragraphs; split any over-long paragraph into sentences."""
    out = []
    for para in re.split(r"\n\s*\n|\n(?=B\d+\.\d+\.\d+\s)", text):
        para = " ".join(para.split())
        if not para:
            continue
        if len(para) <= MAX_CHARS:
            out.append(para)
            continue
        sentence = ""
        for s in re.split(r"(?<=[.;:])\s+", para):
            if sentence and len(sentence) + len(s) + 1 > MAX_CHARS:
                out.append(sentence)
                sentence = ""
            sentence = f"{sentence} {s}".strip()
            while len(sentence) > MAX_CHARS:  # no sentence breaks at all: hard cut
                out.append(sentence[:MAX_CHARS])
                sentence = sentence[MAX_CHARS:]
        if sentence:
            out.append(sentence)
    return out


def chunk_sections(sections: list[tuple[str, str]]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for section, text in sections:
        current = ""
        for piece in _pieces(text):
            if current and len(current) + len(piece) + 1 > MAX_CHARS:
                chunks.append(Chunk(section, current))
                tail = current[-OVERLAP:]
                current = tail[tail.find(" ") + 1 :] if " " in tail else ""
            current = f"{current} {piece}".strip()
        if current:
            chunks.append(Chunk(section, current))
    return chunks
