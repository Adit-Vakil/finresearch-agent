#!/usr/bin/env python3
"""
Ingest SEC filings for a single company into the database.

Usage:
    python scripts/ingest_company.py --ticker AAPL --filing-type 10-K --limit 3
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is on the path when running directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.logging import configure_logging
from app.ingestion.pipeline import ingest_company


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest SEC filings for a company into FinResearch"
    )
    parser.add_argument("--ticker", required=True, help="Stock ticker symbol (e.g. AAPL)")
    parser.add_argument(
        "--filing-type",
        default="10-K",
        choices=["10-K", "10-Q"],
        help="SEC form type (default: 10-K)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="Maximum number of filings to ingest (default: 3)",
    )
    args = parser.parse_args()

    configure_logging()

    result = ingest_company(
        ticker=args.ticker,
        filing_type=args.filing_type,
        limit=args.limit,
    )

    print(
        f"\nDone — ticker={result['ticker']} "
        f"filings_processed={result['filings_processed']} "
        f"chunks_created={result['chunks_created']} "
        f"skipped={result['skipped']}"
    )


if __name__ == "__main__":
    main()
