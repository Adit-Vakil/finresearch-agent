"""
Filing text cleaner.

Normalizes whitespace and removes structural noise without destroying
financial numbers, tables, or meaningful formatting.
"""

import re


def clean_text(text: str) -> str:
    """
    Clean extracted filing text.

    Operations applied:
    - Normalize line endings
    - Collapse runs of 3+ blank lines to 2
    - Remove lines that are pure separators or standalone page numbers
    - Collapse intra-line whitespace runs to a single space
    - Strip leading/trailing whitespace
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)

    cleaned_lines: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if _is_separator(stripped) or _is_page_number(stripped):
            continue
        cleaned_lines.append(re.sub(r"[ \t]{2,}", " ", line))

    return "\n".join(cleaned_lines).strip()


def _is_separator(line: str) -> bool:
    return bool(line) and bool(re.fullmatch(r"[-=_*~]{5,}", line))


def _is_page_number(line: str) -> bool:
    # Standalone 1-4 digit numbers (page numbers)
    return bool(re.fullmatch(r"\d{1,4}", line))
