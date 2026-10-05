"""
SEC filing parser.

Extracts clean text from HTML/SGML filings and attempts to identify
major sections (Item 1, 1A, 7, etc.) so chunking can stay within
section boundaries.
"""

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

# 10-K section patterns in document order.
# Tuples of (regex_pattern, human_label)
_10K_SECTIONS: list[tuple[str, str]] = [
    (r"item\s+1[^a-zA-Z0-9]", "Business"),
    (r"item\s+1a[^a-zA-Z0-9]", "Risk Factors"),
    (r"item\s+1b[^a-zA-Z0-9]", "Unresolved Staff Comments"),
    (r"item\s+2[^a-zA-Z0-9]", "Properties"),
    (r"item\s+3[^a-zA-Z0-9]", "Legal Proceedings"),
    (r"item\s+7[^a-zA-Z0-9]", "MD&A"),
    (r"item\s+7a[^a-zA-Z0-9]", "Quantitative Disclosures"),
    (r"item\s+8[^a-zA-Z0-9]", "Financial Statements"),
    (r"item\s+9a[^a-zA-Z0-9]", "Controls and Procedures"),
]

_10Q_SECTIONS: list[tuple[str, str]] = [
    (r"item\s+1[^a-zA-Z0-9]", "Financial Statements"),
    (r"item\s+1a[^a-zA-Z0-9]", "Risk Factors"),
    (r"item\s+2[^a-zA-Z0-9]", "MD&A"),
    (r"item\s+3[^a-zA-Z0-9]", "Quantitative Disclosures"),
    (r"item\s+4[^a-zA-Z0-9]", "Controls and Procedures"),
]

_MIN_SECTION_CHARS = 20


@dataclass
class ParsedSection:
    name: str
    text: str


@dataclass
class ParsedFiling:
    full_text: str
    sections: list[ParsedSection] = field(default_factory=list)


def parse_filing(raw_text: str, filing_type: str = "10-K") -> ParsedFiling:
    """
    Parse a raw SEC filing document into structured text.

    Returns full_text plus a list of identified sections (may be empty
    if section detection fails or yields too-short fragments).
    """
    if _is_html(raw_text):
        text = _html_to_text(raw_text)
    else:
        text = raw_text

    patterns = _10K_SECTIONS if filing_type == "10-K" else _10Q_SECTIONS
    sections = _detect_sections(text, patterns)
    return ParsedFiling(full_text=text, sections=sections)


# ------------------------------------------------------------------
# HTML extraction
# ------------------------------------------------------------------

def _is_html(text: str) -> bool:
    return bool(re.search(r"<\s*(html|body|div|p|span|table|td|tr)\b", text, re.IGNORECASE))


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")

    # Drop non-content tags
    for tag in soup(["script", "style", "nav", "header", "footer", "noscript"]):
        tag.decompose()

    # Preserve some whitespace structure by inserting newlines around block elements
    for tag in soup.find_all(["p", "div", "br", "tr", "h1", "h2", "h3", "h4", "h5", "li"]):
        tag.insert_before("\n")
        tag.insert_after("\n")

    return soup.get_text(separator=" ", strip=False)


# ------------------------------------------------------------------
# Section detection
# ------------------------------------------------------------------

def _detect_sections(text: str, patterns: list[tuple[str, str]]) -> list[ParsedSection]:
    """
    Find section boundaries by matching Item headers, then slice the text.
    Only keeps sections with substantial content.
    """
    text_lower = text.lower()
    matches: list[tuple[int, str]] = []

    for pattern, label in patterns:
        for m in re.finditer(pattern, text_lower):
            matches.append((m.start(), label))

    if not matches:
        return []

    # Sort by position; deduplicate same-label earliest match
    matches.sort(key=lambda x: x[0])
    seen: dict[str, int] = {}
    deduped: list[tuple[int, str]] = []
    for pos, label in matches:
        if label not in seen:
            seen[label] = pos
            deduped.append((pos, label))

    sections: list[ParsedSection] = []
    for i, (start, label) in enumerate(deduped):
        end = deduped[i + 1][0] if i + 1 < len(deduped) else len(text)
        section_text = text[start:end].strip()
        if len(section_text) >= _MIN_SECTION_CHARS:
            sections.append(ParsedSection(name=label, text=section_text))

    return sections
