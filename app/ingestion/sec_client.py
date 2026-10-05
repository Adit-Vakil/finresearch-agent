"""
SEC EDGAR client.

Handles CIK lookup, filing discovery, and document fetching while
respecting SEC rate limits and applying retry logic.
"""

import logging
import time
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

logger = logging.getLogger(__name__)

_SEC_DELAY = 0.12  # ~8 req/sec; SEC asks for <= 10
_SUPPORTED_FORMS = {"10-K", "10-Q"}

EDGAR_BASE = "https://www.sec.gov"
DATA_BASE = "https://data.sec.gov"


class SECClient:
    def __init__(self) -> None:
        self._headers = {
            "User-Agent": settings.SEC_USER_AGENT,
            "Accept-Encoding": "gzip, deflate",
            "Host": "www.sec.gov",
        }
        self._data_headers = {
            **self._headers,
            "Host": "data.sec.gov",
        }
        self._ticker_map: dict[str, tuple[str, str]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_filings(
        self,
        ticker: str,
        filing_type: str,
        limit: int = 5,
    ) -> list[dict]:
        """Return up to `limit` filing-metadata dicts for the given ticker and form type."""
        if filing_type not in _SUPPORTED_FORMS:
            raise ValueError(f"Unsupported filing type: {filing_type}. Use one of {_SUPPORTED_FORMS}")

        cik, company_name = self._resolve_cik(ticker.upper())
        submissions = self._fetch_submissions(cik)

        filings: list[dict] = []
        filings.extend(
            self._extract_filing_meta(
                submissions["filings"]["recent"],
                filing_type,
                ticker.upper(),
                cik,
                company_name,
            )
        )

        # Older filings live in paginated files
        for file_entry in submissions["filings"].get("files", []):
            if len(filings) >= limit:
                break
            older = self._get(
                f"{DATA_BASE}/submissions/{file_entry['name']}",
                use_data_host=True,
            ).json()
            filings.extend(
                self._extract_filing_meta(older, filing_type, ticker.upper(), cik, company_name)
            )

        result = filings[:limit]
        logger.info("Found %d %s filings for %s", len(result), filing_type, ticker)
        return result

    def fetch_filing_text(self, source_url: str) -> str:
        """Download the raw filing document (HTML or plain text)."""
        time.sleep(_SEC_DELAY)
        try:
            resp = httpx.get(
                source_url,
                headers={**self._headers, "Host": "www.sec.gov", "Accept": "text/html,text/plain,*/*"},
                timeout=60,
                follow_redirects=True,
            )
            resp.raise_for_status()
            return resp.text
        except httpx.HTTPStatusError as exc:
            logger.error("HTTP %s fetching %s", exc.response.status_code, source_url)
            raise
        except httpx.RequestError as exc:
            logger.error("Request error fetching %s: %s", source_url, exc)
            raise

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_cik(self, ticker: str) -> tuple[str, str]:
        """Return (cik_str, company_name) for ticker, using cached mapping."""
        if not self._ticker_map:
            self._load_ticker_map()
        if ticker not in self._ticker_map:
            raise ValueError(f"Ticker '{ticker}' not found in SEC EDGAR")
        return self._ticker_map[ticker]

    def _load_ticker_map(self) -> None:
        logger.info("Loading SEC ticker→CIK mapping")
        data = self._get(f"{EDGAR_BASE}/files/company_tickers.json").json()
        # Format: {str_index: {cik_str, ticker, title}}
        self._ticker_map = {
            v["ticker"].upper(): (str(v["cik_str"]), v["title"])
            for v in data.values()
        }
        logger.info("Loaded %d tickers", len(self._ticker_map))

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=16),
        reraise=True,
    )
    def _fetch_submissions(self, cik: str) -> dict:
        cik_padded = cik.zfill(10)
        return self._get(
            f"{DATA_BASE}/submissions/CIK{cik_padded}.json",
            use_data_host=True,
        ).json()

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=16),
        reraise=True,
    )
    def _get(self, url: str, use_data_host: bool = False) -> httpx.Response:
        time.sleep(_SEC_DELAY)
        headers = self._data_headers if use_data_host else self._headers
        resp = httpx.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp

    @staticmethod
    def _extract_filing_meta(
        recent: dict,
        filing_type: str,
        ticker: str,
        cik: str,
        company_name: str,
    ) -> list[dict]:
        forms = recent.get("form", [])
        accessions = recent.get("accessionNumber", [])
        dates = recent.get("filingDate", [])
        primary_docs = recent.get("primaryDocument", [])

        results = []
        for form, accession, date, primary_doc in zip(forms, accessions, dates, primary_docs):
            if form != filing_type:
                continue
            accession_clean = accession.replace("-", "")
            source_url = (
                f"{EDGAR_BASE}/Archives/edgar/data/{cik}/"
                f"{accession_clean}/{primary_doc}"
            )
            results.append(
                {
                    "ticker": ticker,
                    "company_name": company_name,
                    "cik": cik,
                    "filing_type": form,
                    "filing_date": date,
                    "accession_number": accession,
                    "source_url": source_url,
                }
            )
        return results
