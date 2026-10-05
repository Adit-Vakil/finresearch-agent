"""Tests for the SEC filing parser and cleaner."""

from pathlib import Path

import pytest

from app.ingestion.cleaner import clean_text
from app.ingestion.parser import ParsedFiling, parse_filing

SAMPLE_HTML = Path(__file__).parent.parent / "data" / "sample" / "sample_10k_fragment.html"


@pytest.fixture
def sample_html() -> str:
    return SAMPLE_HTML.read_text()


@pytest.fixture
def parsed(sample_html: str) -> ParsedFiling:
    return parse_filing(sample_html, filing_type="10-K")


# ------------------------------------------------------------------
# Parser tests
# ------------------------------------------------------------------

def test_parse_extracts_text(parsed: ParsedFiling) -> None:
    assert len(parsed.full_text) > 100
    assert "SampleCorp" in parsed.full_text


def test_parse_detects_sections(parsed: ParsedFiling) -> None:
    assert len(parsed.sections) >= 2, "Expected at least 2 sections from sample filing"


def test_section_names_are_known(parsed: ParsedFiling) -> None:
    known = {"Business", "Risk Factors", "Properties", "MD&A", "Financial Statements"}
    detected = {s.name for s in parsed.sections}
    assert detected & known, f"No known section names found; got: {detected}"


def test_section_text_is_nonempty(parsed: ParsedFiling) -> None:
    for section in parsed.sections:
        assert len(section.text) > 50, f"Section '{section.name}' text is too short"


def test_risk_factors_section_content(parsed: ParsedFiling) -> None:
    rf = next((s for s in parsed.sections if s.name == "Risk Factors"), None)
    assert rf is not None, "Risk Factors section not detected"
    assert "supply chain" in rf.text.lower() or "competition" in rf.text.lower()


def test_plain_text_parsing() -> None:
    plain = "ITEM 1. BUSINESS\nWe make widgets.\n\nITEM 1A. RISK FACTORS\nMarkets fluctuate."
    result = parse_filing(plain, filing_type="10-K")
    assert len(result.full_text) > 0
    # Plain text with all-caps items should still be detected
    # (lower-cased internally before matching)
    section_names = {s.name for s in result.sections}
    assert "Business" in section_names or "Risk Factors" in section_names


def test_html_tags_removed(parsed: ParsedFiling) -> None:
    assert "<html" not in parsed.full_text
    assert "<h2>" not in parsed.full_text
    assert "<p>" not in parsed.full_text


def test_financial_numbers_preserved(parsed: ParsedFiling) -> None:
    # Key numbers from the sample filing should survive
    assert "400" in parsed.full_text or "400.2" in parsed.full_text


# ------------------------------------------------------------------
# Cleaner tests
# ------------------------------------------------------------------

def test_clean_removes_separator_lines() -> None:
    text = "Intro\n-----\nContent"
    result = clean_text(text)
    assert "-----" not in result
    assert "Content" in result


def test_clean_removes_standalone_page_numbers() -> None:
    text = "Para one.\n\n42\n\nPara two."
    result = clean_text(text)
    lines = [l.strip() for l in result.split("\n")]
    assert "42" not in lines


def test_clean_collapses_blank_lines() -> None:
    text = "A\n\n\n\n\nB"
    result = clean_text(text)
    assert "\n\n\n" not in result


def test_clean_preserves_financial_content() -> None:
    text = "Revenue was $12.3 billion, up 3%.\nGross margin: 46.2%."
    result = clean_text(text)
    assert "12.3 billion" in result
    assert "46.2%" in result


def test_clean_handles_empty_string() -> None:
    assert clean_text("") == ""


def test_clean_normalizes_whitespace() -> None:
    text = "Word1    Word2\tWord3"
    result = clean_text(text)
    assert "    " not in result
    assert "Word1" in result and "Word2" in result
