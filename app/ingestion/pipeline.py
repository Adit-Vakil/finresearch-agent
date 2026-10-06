"""
Ingestion pipeline.

Orchestrates: SEC fetch → parse → clean → chunk → store.
Idempotent: a filing already in the database is skipped, not duplicated.
"""

import logging

from app.core.config import settings
from app.db.connection import get_session
from app.db.models import Company, DocumentChunk, Filing
from app.ingestion.chunker import chunk_filing
from app.ingestion.cleaner import clean_text
from app.ingestion.parser import parse_filing
from app.ingestion.sec_client import SECClient
from app.retrieval.embeddings import embed_texts

logger = logging.getLogger(__name__)

_RAW_TEXT_CAP = 500_000  # characters; avoid bloating the DB with full HTML


def ingest_company(
    ticker: str,
    filing_type: str = "10-K",
    limit: int = 3,
) -> dict:
    """
    Run the full ingestion pipeline for a ticker.

    Returns a summary dict with counts of processed/skipped filings and
    chunks created.  Raises on unrecoverable errors after logging them.
    """
    client = SECClient()
    logger.info("Starting ingestion: ticker=%s type=%s limit=%d", ticker, filing_type, limit)

    filings_meta = client.get_filings(ticker, filing_type, limit=limit)
    if not filings_meta:
        logger.warning("No %s filings found for %s", filing_type, ticker)
        return {"ticker": ticker, "filings_processed": 0, "chunks_created": 0, "skipped": 0}

    summary = {"ticker": ticker, "filings_processed": 0, "chunks_created": 0, "skipped": 0}

    with get_session() as session:
        company = _upsert_company(session, ticker.upper(), filings_meta[0])

        for meta in filings_meta:
            existing = (
                session.query(Filing)
                .filter_by(accession_number=meta["accession_number"])
                .first()
            )
            if existing:
                logger.info("Skipping %s — already ingested", meta["accession_number"])
                summary["skipped"] += 1
                continue

            try:
                n_chunks = _process_one_filing(session, company, meta, client)
                summary["filings_processed"] += 1
                summary["chunks_created"] += n_chunks
            except Exception:
                logger.exception("Failed to process filing %s", meta["accession_number"])
                session.rollback()
                raise

    logger.info("Ingestion complete: %s", summary)
    return summary


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _upsert_company(session, ticker: str, meta: dict) -> Company:
    company = session.query(Company).filter_by(ticker=ticker).first()
    if not company:
        company = Company(
            ticker=ticker,
            company_name=meta.get("company_name", ""),
            cik=meta.get("cik", ""),
        )
        session.add(company)
        session.flush()
    return company


def _process_one_filing(session, company: Company, meta: dict, client: SECClient) -> int:
    logger.info("Fetching %s", meta["source_url"])
    raw_text = client.fetch_filing_text(meta["source_url"])

    parsed = parse_filing(raw_text, filing_type=meta["filing_type"])

    cleaned_full = clean_text(parsed.full_text)
    for section in parsed.sections:
        section.text = clean_text(section.text)

    filing = Filing(
        company_id=company.id,
        accession_number=meta["accession_number"],
        filing_type=meta["filing_type"],
        filing_date=meta["filing_date"],
        source_url=meta["source_url"],
        raw_text=cleaned_full[:_RAW_TEXT_CAP],
    )
    session.add(filing)
    session.flush()

    filing_metadata = {
        "ticker": company.ticker,
        "company": company.company_name,
        "filing_type": meta["filing_type"],
        "filing_date": meta["filing_date"],
        "accession_number": meta["accession_number"],
        "source_url": meta["source_url"],
        "cik": company.cik,
    }

    chunks = chunk_filing(
        parsed,
        filing_metadata,
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
    )

    # Batch-embed all chunks before writing to DB
    chunk_texts = [c.text for c in chunks]
    embeddings = embed_texts(chunk_texts)

    for chunk, embedding in zip(chunks, embeddings):
        session.add(
            DocumentChunk(
                filing_id=filing.id,
                chunk_index=chunk.chunk_index,
                section=chunk.section,
                text=chunk.text,
                token_count=chunk.token_count,
                embedding=embedding,
                metadata_=chunk.metadata,
            )
        )

    session.commit()
    logger.info(
        "Stored filing %s with %d chunks",
        meta["accession_number"],
        len(chunks),
    )
    return len(chunks)
