from typing import Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    db_connected: bool
    version: str


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    ticker: Optional[str] = None
    filing_type: Optional[str] = None
    top_k: int = Field(default=10, ge=1, le=50)


class SearchResult(BaseModel):
    chunk_id: int
    text: str
    score: float
    ticker: str
    company: str
    filing_type: str
    filing_date: str
    section: Optional[str] = None
    source_url: str


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    retrieval_mode: str


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    ticker: Optional[str] = None
    filing_type: Optional[str] = None


class Citation(BaseModel):
    company: str
    ticker: str
    filing_type: str
    filing_date: str
    section: Optional[str] = None
    source_url: str
    chunk_id: int


class AskResponse(BaseModel):
    answer: str
    sources: list[Citation]
    model: str
