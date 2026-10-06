"""
RAG workflow.

Ties together retrieval → reranking → context assembly → generation → citation.

The flow:
  1. Hybrid retrieval (vector + keyword via RRF)
  2. Optional reranking
  3. Build prompt with numbered evidence excerpts
  4. Call LLM
  5. Attach structured citations from retrieved metadata (not LLM output)
  6. Return answer + citations
"""

import logging
from typing import Optional

from app.core.config import settings
from app.rag.citations import build_citations, validate_citations
from app.rag.generator import generate
from app.rag.prompts import SYSTEM_PROMPT, build_user_message
from app.retrieval.hybrid_search import RetrievalMode, retrieve
from app.retrieval.reranker import rerank

logger = logging.getLogger(__name__)


def answer_question(
    question: str,
    ticker: Optional[str] = None,
    filing_type: Optional[str] = None,
    top_k: int = 6,
    retrieval_mode: RetrievalMode = "hybrid",
) -> dict:
    """
    Full RAG pipeline: retrieve evidence, generate answer, attach citations.

    Returns a dict with:
      - answer: str
      - sources: list of citation dicts
      - retrieval_mode: str
      - citation_validation: dict
    """
    # 1. Retrieve candidates (larger pool for reranker)
    candidate_k = top_k * 4 if settings.RERANK_ENABLED else top_k
    candidates, mode_used = retrieve(
        query=question,
        top_k=candidate_k,
        ticker=ticker,
        filing_type=filing_type,
        mode=retrieval_mode,
    )
    logger.info(
        "Retrieved %d candidates via %s for question: %.80s",
        len(candidates),
        mode_used,
        question,
    )

    if not candidates:
        return {
            "answer": "No relevant filings found in the database for your query. "
                      "Please ingest some filings first using the ingestion pipeline.",
            "sources": [],
            "retrieval_mode": mode_used,
            "citation_validation": {"has_citations": False},
        }

    # 2. Optional reranking
    context_chunks = rerank(question, candidates, top_k=top_k)

    # 3. Build prompt
    user_msg = build_user_message(question, context_chunks)

    # 4. Generate
    answer = generate(SYSTEM_PROMPT, user_msg)

    # 5. Citations from metadata (ground truth, not LLM output)
    citations = build_citations(context_chunks)

    # 6. Validate
    validation = validate_citations(answer, context_chunks)
    if validation["out_of_range"]:
        logger.warning(
            "Answer cited out-of-range indices: %s", validation["out_of_range"]
        )

    return {
        "answer": answer,
        "sources": citations,
        "retrieval_mode": mode_used,
        "citation_validation": validation,
    }
