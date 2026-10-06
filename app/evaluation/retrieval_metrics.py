"""
Retrieval quality metrics.

Metrics implemented:
  - Recall@K: fraction of relevant items found in top-K results
  - MRR (Mean Reciprocal Rank): average of 1/rank for first relevant result
  - Hit Rate@K: 1 if any relevant item in top-K, else 0 (averaged across queries)
  - Precision@K: fraction of top-K that are relevant

All functions take a list of retrieved chunk dicts and a set of relevant
identifiers (section names or accession numbers, depending on what's known
for the eval example).
"""

from typing import Callable


def recall_at_k(retrieved: list[dict], relevant: set[str], k: int, key_fn: Callable) -> float:
    """Fraction of relevant items found in the top-k retrieved results."""
    if not relevant:
        return 0.0
    top_k = retrieved[:k]
    found = sum(1 for r in top_k if key_fn(r) in relevant)
    return found / len(relevant)


def precision_at_k(retrieved: list[dict], relevant: set[str], k: int, key_fn: Callable) -> float:
    """Fraction of top-k retrieved results that are relevant."""
    top_k = retrieved[:k]
    if not top_k:
        return 0.0
    found = sum(1 for r in top_k if key_fn(r) in relevant)
    return found / len(top_k)


def reciprocal_rank(retrieved: list[dict], relevant: set[str], key_fn: Callable) -> float:
    """1/rank of the first relevant result, or 0 if none found."""
    for rank, r in enumerate(retrieved, start=1):
        if key_fn(r) in relevant:
            return 1.0 / rank
    return 0.0


def hit_rate_at_k(retrieved: list[dict], relevant: set[str], k: int, key_fn: Callable) -> float:
    """1.0 if at least one relevant item is in top-k, else 0.0."""
    top_k = retrieved[:k]
    for r in top_k:
        if key_fn(r) in relevant:
            return 1.0
    return 0.0


def section_key(chunk: dict) -> str:
    """Extract the section name from a chunk dict."""
    return (chunk.get("section") or "").strip()


def accession_key(chunk: dict) -> str:
    """Extract the accession number from a chunk dict."""
    return chunk.get("accession_number", "")
