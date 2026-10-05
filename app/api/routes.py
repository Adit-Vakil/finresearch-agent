from fastapi import APIRouter, HTTPException

from app.api.schemas import (
    AskRequest,
    AskResponse,
    Citation,
    HealthResponse,
    SearchRequest,
    SearchResponse,
)
from app.core.config import settings
from app.db.connection import check_db_health

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
    return []


@router.get("/filings/{ticker}")
def list_filings(ticker: str) -> list[dict]:
    return []


@router.post("/search", response_model=SearchResponse)
def search(request: SearchRequest) -> SearchResponse:
    return SearchResponse(
        query=request.query,
        results=[],
        retrieval_mode="not_yet_available",
    )


@router.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    return AskResponse(
        answer="The system has not been populated with filings yet. Run the ingestion pipeline first.",
        sources=[],
        model="none",
    )
