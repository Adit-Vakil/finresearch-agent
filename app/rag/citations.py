"""
Citation construction.

Citations are built from database-retrieved chunk metadata, not from
LLM-generated text.  This prevents hallucinated source URLs or filing dates.
"""

import re
from typing import Optional


def build_citations(chunks: list[dict]) -> list[dict]:
    """
    Convert retrieved chunks into structured citation objects.

    Each citation maps directly to a chunk that was actually retrieved and
    used as context.  Nothing here is inferred from the model output.
    """
    citations = []
    for chunk in chunks:
        citations.append(
            {
                "chunk_id": chunk["chunk_id"],
                "company": chunk.get("company", ""),
                "ticker": chunk.get("ticker", ""),
                "filing_type": chunk.get("filing_type", ""),
                "filing_date": chunk.get("filing_date", ""),
                "section": chunk.get("section"),
                "source_url": chunk.get("source_url", ""),
                "accession_number": chunk.get("accession_number", ""),
            }
        )
    return citations


def validate_citations(answer: str, chunks: list[dict]) -> dict:
    """
    Basic citation validation.

    Checks:
    1. Whether the answer contains any [N] citation markers.
    2. Whether all cited indices refer to valid chunks.

    Returns a validation report dict.
    """
    cited_indices = [int(m) for m in re.findall(r"\[(\d+)\]", answer)]
    valid_range = set(range(1, len(chunks) + 1))

    out_of_range = [i for i in cited_indices if i not in valid_range]
    has_citations = len(cited_indices) > 0

    return {
        "has_citations": has_citations,
        "cited_indices": cited_indices,
        "out_of_range": out_of_range,
        "all_valid": len(out_of_range) == 0,
        "num_chunks_provided": len(chunks),
    }
