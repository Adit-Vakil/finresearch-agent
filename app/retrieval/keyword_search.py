"""
Keyword (lexical) retrieval using PostgreSQL full-text search.

Uses tsvector/tsquery via the pg `to_tsvector` and `plainto_tsquery`
functions so no additional extensions are required.  The text search
dictionary is 'english' for stemming and stopword removal.
"""

import logging
from typing import Optional

from sqlalchemy import text

from app.db.connection import get_session

logger = logging.getLogger(__name__)


def keyword_search(
    query: str,
    top_k: int = 20,
    ticker: Optional[str] = None,
    filing_type: Optional[str] = None,
) -> list[dict]:
    """
    Full-text search over document_chunks.text using PostgreSQL tsvector.

    Returns results ordered by ts_rank descending.
    """
    filters, params = _build_filters(ticker, filing_type)
    params["top_k"] = top_k
    params["query"] = query

    sql = text(
        f"""
        SELECT
            dc.id          AS chunk_id,
            dc.text,
            dc.section,
            dc.chunk_index,
            dc.metadata    AS metadata,
            ts_rank(
                to_tsvector('english', dc.text),
                plainto_tsquery('english', :query)
            ) AS score,
            f.filing_type,
            f.filing_date,
            f.source_url,
            f.accession_number,
            c.ticker,
            c.company_name AS company
        FROM document_chunks dc
        JOIN filings f ON dc.filing_id = f.id
        JOIN companies c ON f.company_id = c.id
        WHERE to_tsvector('english', dc.text) @@ plainto_tsquery('english', :query)
          {filters}
        ORDER BY score DESC
        LIMIT :top_k
        """
    )

    with get_session() as session:
        rows = session.execute(sql, params).mappings().all()

    return [_row_to_dict(row) for row in rows]


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
