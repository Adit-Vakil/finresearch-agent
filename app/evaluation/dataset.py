"""
Evaluation dataset definition and loader.

Each example specifies a question, optional metadata filters, and the
chunk IDs (or accession numbers + section hints) that constitute relevant
evidence.  The dataset is intentionally small and transparent so anyone
can inspect and validate it.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import json


@dataclass
class EvalExample:
    question: str
    ticker: Optional[str]
    filing_type: Optional[str]
    relevant_accessions: list[str]
    relevant_sections: list[str]
    notes: str = ""


def load_eval_dataset(path: Optional[Path] = None) -> list[EvalExample]:
    """
    Load evaluation examples.

    If `path` points to a JSON file, load from there.
    Otherwise use the built-in minimal dataset.
    """
    if path and path.exists():
        return _load_from_file(path)
    return _builtin_dataset()


def _load_from_file(path: Path) -> list[EvalExample]:
    data = json.loads(path.read_text())
    return [EvalExample(**ex) for ex in data]


def _builtin_dataset() -> list[EvalExample]:
    return [
        EvalExample(
            question="What supply chain risks did Apple identify?",
            ticker="AAPL",
            filing_type="10-K",
            relevant_accessions=[],
            relevant_sections=["Risk Factors"],
            notes="Expect chunks from Risk Factors discussing supply chain.",
        ),
        EvalExample(
            question="How did Apple's revenue change year over year?",
            ticker="AAPL",
            filing_type="10-K",
            relevant_accessions=[],
            relevant_sections=["MD&A"],
            notes="Expect chunks from MD&A discussing net sales trends.",
        ),
        EvalExample(
            question="What did Apple say about competition in its annual report?",
            ticker="AAPL",
            filing_type="10-K",
            relevant_accessions=[],
            relevant_sections=["Business", "Risk Factors"],
            notes="Competition discussed in Business and Risk Factors sections.",
        ),
        EvalExample(
            question="What were Apple's gross margin trends?",
            ticker="AAPL",
            filing_type="10-K",
            relevant_accessions=[],
            relevant_sections=["MD&A"],
            notes="Gross margin discussed in MD&A.",
        ),
        EvalExample(
            question="What regulatory risks does Apple face?",
            ticker="AAPL",
            filing_type="10-K",
            relevant_accessions=[],
            relevant_sections=["Risk Factors"],
            notes="Regulatory/legal risks in Risk Factors.",
        ),
    ]
