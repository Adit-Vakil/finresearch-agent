from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query

from app.api.schemas import (
    AskRequest,
    AskResponse,
    Citation,
    HealthResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from app.core.config import settings
from app.db.connection import check_db_health, get_session
from app.db.models import Company, Filing

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    db_ok = check_db_health()
    return HealthResponse(
        status="healthy" if db_ok else "degraded",
        db_connected=db_ok,
        version="0.1.0",
    )


@router.get("/companies")
def list_companies() -> list[dict]:
    with get_session() as session:
        companies = session.query(Company).order_by(Company.ticker).all()
        return [
            {"id": c.id, "ticker": c.ticker, "company_name": c.company_name, "cik": c.cik}
            for c in companies
        ]


@router.get("/filings/{ticker}")
def list_filings(ticker: str) -> list[dict]:
    with get_session() as session:
        company = session.query(Company).filter_by(ticker=ticker.upper()).first()
        if not company:
            raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' not found")
        filings = (
            session.query(Filing)
            .filter_by(company_id=company.id)
            .order_by(Filing.filing_date.desc())
            .all()
        )
        return [
            {
                "id": f.id,
                "filing_type": f.filing_type,
                "filing_date": f.filing_date,
                "accession_number": f.accession_number,
                "source_url": f.source_url,
            }
            for f in filings
        ]


@router.post("/search", response_model=SearchResponse)
def search(
    request: SearchRequest,
    mode: Literal["vector", "keyword", "hybrid"] = Query(default="hybrid"),
) -> SearchResponse:
    from app.retrieval.hybrid_search import retrieve

    results, mode_used = retrieve(
        query=request.query,
        top_k=request.top_k,
        ticker=request.ticker,
        filing_type=request.filing_type,
        mode=mode,
    )

    search_results = [
        SearchResult(
            chunk_id=r["chunk_id"],
            text=r["text"],
            score=r["score"],
            ticker=r["ticker"],
            company=r["company"],
            filing_type=r["filing_type"],
            filing_date=r["filing_date"],
            section=r.get("section"),
            source_url=r["source_url"],
        )
        for r in results
    ]
    return SearchResponse(query=request.query, results=search_results, retrieval_mode=mode_used)


@router.post("/ask", response_model=AskResponse)
def ask(
    request: AskRequest,
    mode: Literal["vector", "keyword", "hybrid"] = Query(default="hybrid"),
) -> AskResponse:
    from app.rag.workflow import answer_question

    result = answer_question(
        question=request.question,
        ticker=request.ticker,
        filing_type=request.filing_type,
        retrieval_mode=mode,
    )

    citations = [
        Citation(
            chunk_id=s["chunk_id"],
            company=s["company"],
            ticker=s["ticker"],
            filing_type=s["filing_type"],
            filing_date=s["filing_date"],
            section=s.get("section"),
            source_url=s["source_url"],
        )
        for s in result["sources"]
    ]

    model_name = "anthropic/claude-sonnet-4-6" if settings.ANTHROPIC_API_KEY else (
        "openai/gpt-4o-mini" if settings.OPENAI_API_KEY else "stub"
    )

    return AskResponse(
        answer=result["answer"],
        sources=citations,
        model=model_name,
    )
