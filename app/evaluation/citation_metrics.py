"""
Citation quality evaluation.

Evaluates whether:
1. Answers contain citation markers ([N])
2. Cited indices are in range
3. Cited chunks are semantically related to the question (optional)
"""

import re
from typing import Optional


def citation_coverage(answers_and_chunks: list[tuple[str, list[dict]]]) -> dict:
    """
    Aggregate citation statistics across a set of (answer, chunks) pairs.

    Returns:
      - pct_with_citations: fraction of answers that cite at least one source
      - pct_all_valid: fraction of answers where all cited indices are valid
      - mean_citations_per_answer: average number of [N] markers per answer
    """
    total = len(answers_and_chunks)
    if total == 0:
        return {"pct_with_citations": 0.0, "pct_all_valid": 0.0, "mean_citations_per_answer": 0.0}

    has_cit_count = 0
    all_valid_count = 0
    total_citations = 0

    for answer, chunks in answers_and_chunks:
        cited = [int(m) for m in re.findall(r"\[(\d+)\]", answer)]
        valid_range = set(range(1, len(chunks) + 1))
        if cited:
            has_cit_count += 1
            total_citations += len(cited)
        if all(i in valid_range for i in cited):
            all_valid_count += 1

    return {
        "pct_with_citations": has_cit_count / total,
        "pct_all_valid": all_valid_count / total,
        "mean_citations_per_answer": total_citations / total,
        "n_evaluated": total,
    }
