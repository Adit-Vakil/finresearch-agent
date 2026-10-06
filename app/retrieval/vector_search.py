"""
Vector (semantic) retrieval using pgvector cosine similarity.

All similarity computation runs in PostgreSQL via pgvector — no vectors
are loaded into Python memory for comparison.
"""

import logging
from typing import Optional

from sqlalchemy import text

from app.db.connection import get_session
from app.retrieval.embeddings import embed_query

logger = logging.getLogger(__name__)


def vector_search(
    query: str,
    top_k: int = 10,
    ticker: Optional[str] = None,
    filing_type: Optional[str] = None,
) -> list[dict]:
    """
    Retrieve the top-k chunks most semantically similar to query.

    Filters by ticker and/or filing_type when provided.
    Returns a list of result dicts with chunk text, score, and metadata.
    """
    query_vec = embed_query(query)
    vec_literal = f"[{','.join(str(x) for x in query_vec)}]"

    filters, params = _build_filters(ticker, filing_type)
    params["top_k"] = top_k
    params["vec"] = vec_literal

    sql = text(
        f"""
        SELECT
            dc.id          AS chunk_id,
            dc.text,
            dc.section,
            dc.chunk_index,
            dc.metadata    AS metadata,
            1 - (dc.embedding <=> CAST(:vec AS vector)) AS score,
            f.filing_type,
            f.filing_date,
            f.source_url,
            f.accession_number,
            c.ticker,
            c.company_name AS company
        FROM document_chunks dc
        JOIN filings f ON dc.filing_id = f.id
        JOIN companies c ON f.company_id = c.id
        WHERE dc.embedding IS NOT NULL
          {filters}
        ORDER BY dc.embedding <=> CAST(:vec AS vector)
        LIMIT :top_k
        """
    )

    with get_session() as session:
        rows = session.execute(sql, params).mappings().all()

    return [_row_to_dict(row) for row in rows]


# ------------------------------------------------------------------
# Shared helpers (also used by hybrid_search)
# ------------------------------------------------------------------

def _build_filters(
    ticker: Optional[str],
    filing_type: Optional[str],
) -> tuple[str, dict]:
    clauses: list[str] = []
    params: dict = {}
    if ticker:
        clauses.append("AND c.ticker = :ticker")
        params["ticker"] = ticker.upper()
    if filing_type:
        clauses.append("AND f.filing_type = :filing_type")
        params["filing_type"] = filing_type
    return "\n          ".join(clauses), params


def _row_to_dict(row) -> dict:
    return {
        "chunk_id": row["chunk_id"],
        "text": row["text"],
        "section": row["section"],
        "chunk_index": row["chunk_index"],
        "score": float(row["score"]),
        "filing_type": row["filing_type"],
        "filing_date": str(row["filing_date"]) if row["filing_date"] else "",
        "source_url": row["source_url"] or "",
        "accession_number": row["accession_number"],
        "ticker": row["ticker"],
        "company": row["company"] or "",
    }
