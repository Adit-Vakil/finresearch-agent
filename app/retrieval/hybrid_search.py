"""
Hybrid retrieval combining vector and keyword search via Reciprocal Rank Fusion.

RRF is used because vector and keyword scores live on incompatible scales.
RRF computes 1/(k + rank) for each result list and sums the scores, where k
dampens the impact of very-high-ranked results.  Empirically k=60 works well.

Retrieval mode is configurable:
  - "vector"  : semantic only
  - "keyword" : lexical only
  - "hybrid"  : RRF fusion of both lists
"""

import logging
from typing import Literal, Optional

from app.core.config import settings
from app.retrieval.keyword_search import keyword_search
from app.retrieval.vector_search import vector_search

logger = logging.getLogger(__name__)

RetrievalMode = Literal["vector", "keyword", "hybrid"]

_RRF_K = 60


def retrieve(
    query: str,
    top_k: int = 10,
    ticker: Optional[str] = None,
    filing_type: Optional[str] = None,
    mode: RetrievalMode = "hybrid",
) -> tuple[list[dict], str]:
    """
    Retrieve relevant chunks and return (results, mode_used).

    Candidate pool is `settings.VECTOR_SEARCH_LIMIT` for vector/keyword legs;
    final results are trimmed to top_k after fusion.
    """
    candidate_k = max(settings.VECTOR_SEARCH_LIMIT, top_k * 3)

    if mode == "vector":
        results = vector_search(query, top_k=candidate_k, ticker=ticker, filing_type=filing_type)
        return results[:top_k], "vector"

    if mode == "keyword":
        results = keyword_search(query, top_k=candidate_k, ticker=ticker, filing_type=filing_type)
        return results[:top_k], "keyword"

    # Hybrid: run both legs in sequence (sync), fuse with RRF
    vec_results = vector_search(query, top_k=candidate_k, ticker=ticker, filing_type=filing_type)
    kw_results = keyword_search(query, top_k=candidate_k, ticker=ticker, filing_type=filing_type)

    fused = _reciprocal_rank_fusion([vec_results, kw_results], k=_RRF_K)
    return fused[:top_k], "hybrid"


def _reciprocal_rank_fusion(result_lists: list[list[dict]], k: int = 60) -> list[dict]:
    """
    Merge multiple ranked lists using Reciprocal Rank Fusion.

    Each list contributes 1/(k+rank) to the aggregate score for each chunk_id.
    """
    scores: dict[int, float] = {}
    docs: dict[int, dict] = {}

    for ranked_list in result_lists:
        for rank, doc in enumerate(ranked_list, start=1):
            chunk_id = doc["chunk_id"]
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
            docs[chunk_id] = doc  # last write wins (same doc, same content)

    sorted_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)
    fused = []
    for cid in sorted_ids:
        doc = dict(docs[cid])
        doc["score"] = scores[cid]
        fused.append(doc)

    return fused
