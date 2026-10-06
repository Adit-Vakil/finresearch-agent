"""
Evaluation runner.

Evaluates retrieval quality across vector, keyword, and hybrid modes
for each example in the evaluation dataset.  Results are printed as a
formatted table so they can be inspected and compared honestly.

Usage:
    python app/evaluation/run_eval.py
    python app/evaluation/run_eval.py --k 10
"""

import argparse
import statistics
from pathlib import Path
from typing import Optional

from app.core.logging import configure_logging
from app.evaluation.dataset import EvalExample, load_eval_dataset
from app.evaluation.retrieval_metrics import (
    hit_rate_at_k,
    recall_at_k,
    reciprocal_rank,
    section_key,
)
from app.retrieval.hybrid_search import retrieve

_MODES = ["vector", "keyword", "hybrid"]


def evaluate_mode(
    examples: list[EvalExample],
    mode: str,
    k: int,
) -> dict:
    """Run all eval examples under a single retrieval mode and aggregate metrics."""
    recalls, rrs, hits = [], [], []

    for ex in examples:
        if not ex.relevant_sections:
            continue

        relevant = set(ex.relevant_sections)
        try:
            results, _ = retrieve(
                query=ex.question,
                top_k=k,
                ticker=ex.ticker,
                filing_type=ex.filing_type,
                mode=mode,
            )
        except Exception as exc:
            print(f"  WARNING: retrieval failed for '{ex.question[:50]}': {exc}")
            results = []

        recalls.append(recall_at_k(results, relevant, k, section_key))
        rrs.append(reciprocal_rank(results, relevant, section_key))
        hits.append(hit_rate_at_k(results, relevant, k, section_key))

    if not recalls:
        return {"recall": 0.0, "mrr": 0.0, "hit_rate": 0.0, "n": 0}

    return {
        "recall": statistics.mean(recalls),
        "mrr": statistics.mean(rrs),
        "hit_rate": statistics.mean(hits),
        "n": len(recalls),
    }


def print_results_table(results_by_mode: dict[str, dict], k: int) -> None:
    header = f"{'Mode':<12} {'Recall@' + str(k):<14} {'MRR':<10} {'Hit Rate@' + str(k):<14} {'n':<6}"
    print()
    print("=" * 60)
    print(f"  Retrieval Evaluation Results (k={k})")
    print("=" * 60)
    print(header)
    print("-" * 60)
    for mode, metrics in results_by_mode.items():
        print(
            f"{mode:<12} "
            f"{metrics['recall']:.3f}         "
            f"{metrics['mrr']:.3f}      "
            f"{metrics['hit_rate']:.3f}          "
            f"{metrics['n']:<6}"
        )
    print("=" * 60)
    print()
    print("NOTE: Results reflect the current demo corpus.")
    print("Metrics are computed from actual retrieval, not hard-coded.")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run FinResearch retrieval evaluation")
    parser.add_argument("--k", type=int, default=10, help="Cutoff for Recall@K and Hit Rate@K")
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Path to JSON eval dataset (defaults to built-in examples)",
    )
    args = parser.parse_args()

    configure_logging()

    dataset_path = Path(args.dataset) if args.dataset else None
    examples = load_eval_dataset(dataset_path)
    print(f"\nLoaded {len(examples)} evaluation examples")

    results_by_mode: dict[str, dict] = {}
    for mode in _MODES:
        print(f"Evaluating mode: {mode}…")
        results_by_mode[mode] = evaluate_mode(examples, mode, k=args.k)

    print_results_table(results_by_mode, k=args.k)


if __name__ == "__main__":
    main()
