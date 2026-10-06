"""
Optional cross-encoder reranker.

When RERANK_ENABLED=true, retrieves a larger candidate set and reranks
using a cross-encoder model.  Falls back gracefully to the original order
if the model cannot be loaded or an error occurs.

The reranker is intentionally optional so the system works fully without it.
"""

import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_reranker = None
_RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def _get_reranker():
    global _reranker
    if _reranker is None:
        from sentence_transformers import CrossEncoder

        logger.info("Loading reranker model: %s", _RERANK_MODEL)
        _reranker = CrossEncoder(_RERANK_MODEL)
    return _reranker


def rerank(query: str, candidates: list[dict], top_k: int = 10) -> list[dict]:
    """
    Rerank candidates using a cross-encoder.  Returns at most top_k results.

    If reranking is disabled or fails, returns the first top_k candidates
    from the original list unchanged.
    """
    if not settings.RERANK_ENABLED or not candidates:
        return candidates[:top_k]

    try:
        model = _get_reranker()
        pairs = [(query, doc["text"]) for doc in candidates]
        scores = model.predict(pairs)

        scored = sorted(
            zip(scores, candidates),
            key=lambda x: x[0],
            reverse=True,
        )
        result = []
        for score, doc in scored[:top_k]:
            doc = dict(doc)
            doc["rerank_score"] = float(score)
            result.append(doc)
        return result

    except Exception:
        logger.exception("Reranking failed; returning original order")
        return candidates[:top_k]
