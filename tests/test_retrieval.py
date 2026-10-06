"""
Tests for retrieval components that do not require a live database.

Live DB integration tests belong in a separate test suite gated by a
FINRESEARCH_INTEGRATION_TESTS env var.  These unit tests mock the DB
layer and verify correctness of fusion logic, citation building, and
citation validation.
"""

import pytest

from app.rag.citations import build_citations, validate_citations
from app.retrieval.hybrid_search import _reciprocal_rank_fusion


# ------------------------------------------------------------------
# RRF fusion
# ------------------------------------------------------------------

def _make_chunk(chunk_id: int, text: str = "text", score: float = 0.9) -> dict:
    return {
        "chunk_id": chunk_id,
        "text": text,
        "section": None,
        "chunk_index": 0,
        "score": score,
        "filing_type": "10-K",
        "filing_date": "2024-01-01",
        "source_url": "https://example.com",
        "accession_number": "0001234567-24-000001",
        "ticker": "TEST",
        "company": "Test Corp",
    }


def test_rrf_combines_two_lists():
    list1 = [_make_chunk(1), _make_chunk(2), _make_chunk(3)]
    list2 = [_make_chunk(2), _make_chunk(3), _make_chunk(4)]
    fused = _reciprocal_rank_fusion([list1, list2])
    ids = [d["chunk_id"] for d in fused]
    # chunk 2 and 3 appear in both lists — should rank higher than 1 or 4
    assert ids.index(2) < ids.index(1) or ids.index(3) < ids.index(1)
    # All 4 unique chunks should appear
    assert set(ids) == {1, 2, 3, 4}


def test_rrf_single_list_preserves_order():
    chunks = [_make_chunk(i) for i in [10, 20, 30]]
    fused = _reciprocal_rank_fusion([chunks])
    ids = [d["chunk_id"] for d in fused]
    assert ids == [10, 20, 30]


def test_rrf_empty_lists():
    result = _reciprocal_rank_fusion([[], []])
    assert result == []


def test_rrf_scores_are_positive():
    chunks = [_make_chunk(i) for i in range(5)]
    fused = _reciprocal_rank_fusion([chunks, chunks[::-1]])
    for doc in fused:
        assert doc["score"] > 0


def test_rrf_top_ranked_in_both_gets_highest_score():
    # chunk_id=99 is rank-1 in both lists — should win overall
    list1 = [_make_chunk(99), _make_chunk(1), _make_chunk(2)]
    list2 = [_make_chunk(99), _make_chunk(3), _make_chunk(4)]
    fused = _reciprocal_rank_fusion([list1, list2])
    assert fused[0]["chunk_id"] == 99


# ------------------------------------------------------------------
# Citation construction
# ------------------------------------------------------------------

def test_build_citations_maps_fields():
    chunks = [_make_chunk(42)]
    citations = build_citations(chunks)
    assert len(citations) == 1
    c = citations[0]
    assert c["chunk_id"] == 42
    assert c["ticker"] == "TEST"
    assert c["filing_type"] == "10-K"


def test_build_citations_empty_input():
    assert build_citations([]) == []


def test_build_citations_preserves_all_chunks():
    chunks = [_make_chunk(i) for i in range(5)]
    citations = build_citations(chunks)
    assert len(citations) == 5


# ------------------------------------------------------------------
# Citation validation
# ------------------------------------------------------------------

def test_validate_detects_citations():
    chunks = [_make_chunk(i) for i in range(3)]
    result = validate_citations("The answer is supported by [1] and [2].", chunks)
    assert result["has_citations"] is True
    assert 1 in result["cited_indices"]
    assert 2 in result["cited_indices"]


def test_validate_no_citations():
    chunks = [_make_chunk(1)]
    result = validate_citations("No citations here.", chunks)
    assert result["has_citations"] is False


def test_validate_out_of_range_detected():
    chunks = [_make_chunk(1)]  # only 1 chunk
    result = validate_citations("See [1] and [5].", chunks)
    assert 5 in result["out_of_range"]
    assert result["all_valid"] is False


def test_validate_all_valid_when_in_range():
    chunks = [_make_chunk(i) for i in range(4)]
    result = validate_citations("Points [1], [2], [3], [4] support this.", chunks)
    assert result["all_valid"] is True
    assert result["out_of_range"] == []


# ------------------------------------------------------------------
# API-level search and ask stubs (no DB)
# ------------------------------------------------------------------

from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_search_returns_empty_without_db():
    with patch("app.retrieval.hybrid_search.retrieve", return_value=([], "hybrid")):
        resp = client.post("/search", json={"query": "supply chain"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["results"] == []
    assert data["retrieval_mode"] == "hybrid"


def test_ask_returns_no_results_message_without_db():
    with patch(
        "app.rag.workflow.answer_question",
        return_value={
            "answer": "No relevant filings found.",
            "sources": [],
            "retrieval_mode": "hybrid",
            "citation_validation": {"has_citations": False},
        },
    ):
        resp = client.post("/ask", json={"question": "What are the risks?"})
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "sources" in data


def test_search_with_ticker_filter_passes_through():
    with patch("app.retrieval.hybrid_search.retrieve", return_value=([], "hybrid")) as mock:
        client.post("/search", json={"query": "revenue", "ticker": "AAPL", "filing_type": "10-K"})
    mock.assert_called_once()
    call_kwargs = mock.call_args.kwargs
    assert call_kwargs["ticker"] == "AAPL"
    assert call_kwargs["filing_type"] == "10-K"
