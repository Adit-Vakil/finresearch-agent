#!/usr/bin/env python3
"""
Ingest a small representative set of companies for demo / testing purposes.

This populates the database with a few filings so the application has data
to search over without requiring a full corpus ingest.

Usage:
    python scripts/ingest_sample.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.logging import configure_logging
from app.ingestion.pipeline import ingest_company

SAMPLE_COMPANIES = [
    ("AAPL", "10-K", 2),
    ("MSFT", "10-K", 2),
    ("NVDA", "10-K", 1),
]


def main() -> None:
    configure_logging()

    total_chunks = 0
    for ticker, filing_type, limit in SAMPLE_COMPANIES:
        print(f"\nIngesting {ticker} ({filing_type}, limit={limit})...")
        try:
            result = ingest_company(ticker=ticker, filing_type=filing_type, limit=limit)
            total_chunks += result["chunks_created"]
            print(
                f"  filings={result['filings_processed']} "
                f"chunks={result['chunks_created']} "
                f"skipped={result['skipped']}"
            )
        except Exception as exc:
            print(f"  ERROR: {exc}")

    print(f"\nSample ingest complete. Total chunks created: {total_chunks}")


if __name__ == "__main__":
    main()
