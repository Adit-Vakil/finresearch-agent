"""
Document chunker.

Splits filing text into token-bounded chunks with overlap.  When sections
are available from the parser, chunks stay within section boundaries so
retrieval results are easier to attribute.
"""

from dataclasses import dataclass, field
from typing import Optional

import tiktoken

from app.ingestion.parser import ParsedFiling

_ENCODING = "cl100k_base"


@dataclass
class Chunk:
    text: str
    chunk_index: int
    section: Optional[str]
    token_count: int
    metadata: dict = field(default_factory=dict)


def chunk_filing(
    parsed: ParsedFiling,
    filing_metadata: dict,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> list[Chunk]:
    """
    Chunk a parsed filing into token-bounded segments.

    If sections were detected, each section is chunked independently so
    chunks never straddle section boundaries.  Falls back to chunking the
    full text when no sections are available.
    """
    enc = tiktoken.get_encoding(_ENCODING)
    chunks: list[Chunk] = []
    idx = 0

    if parsed.sections:
        for section in parsed.sections:
            section_chunks = _split_text(
                section.text,
                section.name,
                enc,
                chunk_size,
                chunk_overlap,
                filing_metadata,
                start_index=idx,
            )
            idx += len(section_chunks)
            chunks.extend(section_chunks)
    else:
        chunks = _split_text(
            parsed.full_text,
            None,
            enc,
            chunk_size,
            chunk_overlap,
            filing_metadata,
            start_index=0,
        )

    return chunks


def _split_text(
    text: str,
    section: Optional[str],
    enc: tiktoken.Encoding,
    chunk_size: int,
    chunk_overlap: int,
    filing_metadata: dict,
    start_index: int,
) -> list[Chunk]:
    tokens = enc.encode(text)
    chunks: list[Chunk] = []
    idx = start_index
    pos = 0

    while pos < len(tokens):
        end = min(pos + chunk_size, len(tokens))
        chunk_tokens = tokens[pos:end]
        chunk_text = enc.decode(chunk_tokens)

        chunks.append(
            Chunk(
                text=chunk_text,
                chunk_index=idx,
                section=section,
                token_count=len(chunk_tokens),
                metadata={
                    **filing_metadata,
                    "section": section,
                    "chunk_index": idx,
                },
            )
        )
        idx += 1

        if end == len(tokens):
            break
        pos = end - chunk_overlap

    return chunks
