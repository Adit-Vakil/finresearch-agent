"""Tests for the document chunker."""

import pytest

from app.ingestion.chunker import Chunk, chunk_filing
from app.ingestion.parser import ParsedFiling, ParsedSection

_FILING_META = {
    "ticker": "TEST",
    "company": "Test Corp",
    "filing_type": "10-K",
    "filing_date": "2024-01-01",
    "accession_number": "0001234567-24-000001",
    "source_url": "https://example.com/filing.htm",
    "cik": "1234567",
}


def _make_parsed(full_text: str, sections: list[tuple[str, str]] | None = None) -> ParsedFiling:
    if sections:
        return ParsedFiling(
            full_text=full_text,
            sections=[ParsedSection(name=n, text=t) for n, t in sections],
        )
    return ParsedFiling(full_text=full_text)


# ------------------------------------------------------------------
# Basic chunking behavior
# ------------------------------------------------------------------

def test_short_text_yields_one_chunk() -> None:
    parsed = _make_parsed("This is a short document about finance.")
    chunks = chunk_filing(parsed, _FILING_META, chunk_size=512, chunk_overlap=64)
    assert len(chunks) == 1


def test_long_text_yields_multiple_chunks() -> None:
    # ~2000 tokens of text at ~4 chars/token
    long_text = "financial risk market analysis " * 200
    parsed = _make_parsed(long_text)
    chunks = chunk_filing(parsed, _FILING_META, chunk_size=256, chunk_overlap=32)
    assert len(chunks) > 1


def test_chunk_indices_are_sequential() -> None:
    long_text = "word " * 1000
    parsed = _make_parsed(long_text)
    chunks = chunk_filing(parsed, _FILING_META, chunk_size=100, chunk_overlap=10)
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i


def test_chunk_token_counts_match_content() -> None:
    text = "The company reported strong earnings this quarter. " * 50
    parsed = _make_parsed(text)
    chunks = chunk_filing(parsed, _FILING_META, chunk_size=128, chunk_overlap=16)
    for chunk in chunks:
        assert chunk.token_count > 0
        assert chunk.token_count <= 128


def test_overlap_is_applied() -> None:
    # With overlap, adjacent chunks should share content
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa " * 30
    parsed = _make_parsed(text)
    chunks = chunk_filing(parsed, _FILING_META, chunk_size=20, chunk_overlap=5)
    if len(chunks) >= 2:
        # Last tokens of chunk[0] should appear in beginning of chunk[1]
        c0_words = chunks[0].text.split()
        c1_words = chunks[1].text.split()
        # There must be some shared content (the overlap window)
        shared = set(c0_words[-10:]) & set(c1_words[:10])
        assert shared, "Expected overlapping tokens between adjacent chunks"


# ------------------------------------------------------------------
# Section-aware chunking
# ------------------------------------------------------------------

def test_section_chunks_carry_section_name() -> None:
    parsed = _make_parsed(
        full_text="...",
        sections=[
            ("Risk Factors", "Supply chain risk is significant. " * 20),
            ("MD&A", "Revenue increased 5% year over year. " * 20),
        ],
    )
    chunks = chunk_filing(parsed, _FILING_META, chunk_size=128, chunk_overlap=16)
    sections_seen = {c.section for c in chunks}
    assert "Risk Factors" in sections_seen
    assert "MD&A" in sections_seen


def test_section_metadata_in_chunk() -> None:
    parsed = _make_parsed(
        full_text="...",
        sections=[("Business", "We make products. " * 30)],
    )
    chunks = chunk_filing(parsed, _FILING_META)
    for chunk in chunks:
        assert chunk.metadata["section"] == "Business"
        assert chunk.metadata["ticker"] == "TEST"
        assert chunk.metadata["filing_type"] == "10-K"


def test_no_sections_falls_back_to_full_text() -> None:
    text = "General content without section headers. " * 50
    parsed = _make_parsed(text)
    assert parsed.sections == []
    chunks = chunk_filing(parsed, _FILING_META)
    assert len(chunks) >= 1
    for chunk in chunks:
        assert chunk.section is None


# ------------------------------------------------------------------
# Metadata preservation
# ------------------------------------------------------------------

def test_filing_metadata_preserved_in_chunk() -> None:
    parsed = _make_parsed("Some text about revenue.")
    chunks = chunk_filing(parsed, _FILING_META)
    assert chunks
    meta = chunks[0].metadata
    assert meta["ticker"] == "TEST"
    assert meta["company"] == "Test Corp"
    assert meta["filing_type"] == "10-K"
    assert meta["accession_number"] == "0001234567-24-000001"
    assert meta["source_url"] == "https://example.com/filing.htm"


def test_chunk_text_is_nonempty() -> None:
    parsed = _make_parsed("Revenue was strong. " * 10)
    chunks = chunk_filing(parsed, _FILING_META)
    for chunk in chunks:
        assert chunk.text.strip() != ""
