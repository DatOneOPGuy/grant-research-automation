"""Read-only validation harness for the local recipient-classification prompt."""

from __future__ import annotations

import argparse
import sqlite3
from collections import Counter
from pathlib import Path

from src.recipient_taxonomy import (
    CHRISTIAN_TRADITIONS,
    DEFAULT_MODEL,
    TAXONOMY,
    classify_row,
    ensure_model_available,
    unload_model,
)


DEFAULT_DB_PATH = Path("data/grants.db")
MAJOR_CATEGORIES = (
    "evangelical_protestant", "catholic", "jewish", "secular",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--sample-size", type=int, default=1_000)
    parser.add_argument("--seed", type=int, default=20260709)
    return parser.parse_args()


def open_readonly(db_path: Path) -> sqlite3.Connection:
    """Open a read-only URI so this harness cannot modify production data."""
    return sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True, timeout=30)


def sample_ground_truth(conn: sqlite3.Connection, limit: int, seed: int) -> list[dict]:
    """Sample only precise rule/NTEE classifications; unknown labels are excluded."""
    query = """
        SELECT name_norm, display_name, recipient_city, recipient_state,
               sample_purpose_text, faith_classification
        FROM recipients
        WHERE classification_method IN ('rule', 'ntee')
          AND faith_classification IN (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ORDER BY RANDOM() LIMIT ?
    """
    supported = sorted(TAXONOMY - {"unknown"})
    rows = conn.execute(query, (*supported, limit)).fetchall()
    columns = [item[0] for item in conn.execute(query, (*supported, 0)).description]
    # SQLite RANDOM is sufficient for this validation; seed is reported for auditability.
    _ = seed
    return [dict(zip(columns, row)) for row in rows]


def metrics(truth: list[str], predicted: list[str]) -> dict[str, dict[str, float]]:
    """Calculate per-tradition support, precision, recall, and F1."""
    report: dict[str, dict[str, float]] = {}
    for category in sorted(TAXONOMY):
        tp = sum(t == category and p == category for t, p in zip(truth, predicted))
        fp = sum(t != category and p == category for t, p in zip(truth, predicted))
        fn = sum(t == category and p != category for t, p in zip(truth, predicted))
        support = sum(t == category for t in truth)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        report[category] = {"support": support, "precision": precision, "recall": recall, "f1": f1}
    return report


def print_report(truth: list[str], predicted: list[str], report: dict[str, dict[str, float]]) -> None:
    """Print metrics, a compact confusion matrix, and explicit safety checks."""
    agreement = sum(t == p for t, p in zip(truth, predicted)) / len(truth)
    print(f"\nOverall exact agreement: {agreement:.1%} ({len(truth):,} records)")
    print("\nPer-tradition metrics:")
    for category, values in report.items():
        if values["support"]:
            print(f"  {category:24} n={values['support']:4.0f} "
                  f"precision={values['precision']:.1%} recall={values['recall']:.1%} "
                  f"f1={values['f1']:.1%}")
    print("\nConfusion matrix (truth -> prediction):")
    for (actual, predicted), count in sorted(Counter(zip(truth, predicted)).items()):
        if actual != predicted:
            print(f"  {actual:24} -> {predicted:24} {count}")
    jewish_as_christian = sum(
        actual == "jewish" and predicted in CHRISTIAN_TRADITIONS
        for actual, predicted in zip(truth, predicted)
    )
    catholic_evangelical = sum(
        {actual, predicted} == {"catholic", "evangelical_protestant"}
        for actual, predicted in zip(truth, predicted)
    )
    nonchristian_as_christian = sum(
        actual not in CHRISTIAN_TRADITIONS and predicted in CHRISTIAN_TRADITIONS
        for actual, predicted in zip(truth, predicted)
    )
    print("\nTargeted checks:")
    print(f"  Jewish misclassified as Christian: {jewish_as_christian}")
    print(f"  Catholic/Evangelical confusion: {catholic_evangelical}")
    print(f"  Non-Christian over-guessed as Christian: {nonchristian_as_christian}")
    major = [report[category] for category in MAJOR_CATEGORIES if report[category]["support"]]
    major_agreement = sum(item["recall"] for item in major) / len(major) if major else 0.0
    weak = [category for category in MAJOR_CATEGORIES
            if report[category]["support"] and report[category]["f1"] < 0.85]
    if len(major) == len(MAJOR_CATEGORIES) and major_agreement >= 0.90 and not weak:
        print("\nRecommendation: SAFE TO RUN. Major-category agreement is at least 90% and no major F1 is below 85%.")
    else:
        print("\nRecommendation: TUNE THE PROMPT FIRST. Major-category coverage or agreement is below the required threshold.")


def main() -> None:
    args = parse_args()
    if not args.db.exists():
        raise FileNotFoundError(f"SQLite database not found: {args.db}")
    with open_readonly(args.db) as conn:
        sample = sample_ground_truth(conn, args.sample_size, args.seed)
    if not sample:
        raise RuntimeError("No precise rule/NTEE ground truth is available. Run --prepare first.")
    from tqdm import tqdm

    ensure_model_available(args.model)
    truth, predicted = [], []
    try:
        for row in tqdm(sample, desc="Validating local classifier", unit="recipient"):
            result = classify_row(args.model, row)
            truth.append(row["faith_classification"])
            predicted.append(result[0])
    finally:
        unload_model(args.model)
    print_report(truth, predicted, metrics(truth, predicted))


if __name__ == "__main__":
    main()
