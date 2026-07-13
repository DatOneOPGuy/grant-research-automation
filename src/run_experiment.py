"""Single-pass classifier experiment: metrics + raw output + tracked artifacts.

Replaces running validate_classifier and review_classifier_output separately
(two model passes). One pass over a ground-truth sample produces the gate
metrics AND the raw per-record output, then writes a tracked run folder under
runs/ plus a row in runs/INDEX.md. Read-only against the database.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from src.recipient_taxonomy import (
    CHRISTIAN_TRADITIONS,
    DEFAULT_MODEL,
    SYSTEM_PROMPT,
    TAXONOMY,
    ensure_model_available,
    ollama_client,
    prompt_for,
    response_content,
    unload_model,
)
from src.run_tracking import append_index, evaluate_gate, new_run_dir, write_run
from src.validate_classifier import metrics, open_readonly, sample_ground_truth


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("data/grants.db"))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--sample-size", type=int, default=300)
    parser.add_argument("--seed", type=int, default=20260709)
    parser.add_argument("--label", default=None, help="Folder label; defaults to the model name.")
    parser.add_argument("--note", default="", help="Short description of what changed this run.")
    parser.add_argument("--workers", type=int, default=1,
                        help="Concurrent Ollama requests (validation harness only).")
    return parser.parse_args()


def classify_capture(model: str, row: dict) -> dict:
    """Classify one row, keeping the exact JSON the model emitted for review."""
    response = ollama_client().chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt_for(row)},
        ],
        format="json",
        keep_alive="10m",
    )
    raw = response_content(response)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        payload = {"_parse_error": str(error)}
    predicted = payload.get("classification")
    return {
        "name": row.get("display_name"),
        "city": row.get("recipient_city"),
        "state": row.get("recipient_state"),
        "purpose": row.get("sample_purpose_text"),
        "ground_truth": row["faith_classification"],
        "model_prompt_input": prompt_for(row),
        "model_raw_json": raw,
        "predicted": predicted,
        "confidence": payload.get("confidence"),
        "reason": payload.get("reason"),
        "agree": predicted == row["faith_classification"],
        "predicted_valid": predicted in TAXONOMY,
    }


def safety_counts(records: list[dict]) -> dict[str, int]:
    """Count the three classifier failure modes that would poison the donor pipeline."""
    pairs = [(entry["ground_truth"], entry["predicted"]) for entry in records]
    return {
        "jewish_as_christian": sum(
            truth == "jewish" and pred in CHRISTIAN_TRADITIONS for truth, pred in pairs),
        "catholic_evangelical": sum(
            {truth, pred} == {"catholic", "evangelical_protestant"} for truth, pred in pairs),
        "nonchristian_as_christian": sum(
            truth not in CHRISTIAN_TRADITIONS and pred in CHRISTIAN_TRADITIONS
            for truth, pred in pairs),
    }


def classify_sample(model: str, sample: list[dict], workers: int = 1) -> list[dict]:
    from concurrent.futures import ThreadPoolExecutor
    from tqdm import tqdm

    ensure_model_available(model)
    records = []
    try:
        if workers <= 1:
            for row in tqdm(sample, desc=f"Classifying ({model})", unit="recipient"):
                records.append(classify_capture(model, row))
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(classify_capture, model, row) for row in sample]
                for future in tqdm(futures, desc=f"Classifying ({model} x{workers})", unit="recipient"):
                    records.append(future.result())
    finally:
        unload_model(model)
    return records


def main() -> None:
    args = parse_args()
    if not args.db.exists():
        raise FileNotFoundError(f"SQLite database not found: {args.db}")
    with open_readonly(args.db) as conn:
        sample = sample_ground_truth(conn, args.sample_size, args.seed)
    if not sample:
        raise RuntimeError("No rule/NTEE ground truth available. Run the migration first.")

    records = classify_sample(args.model, sample, args.workers)
    truth = [entry["ground_truth"] for entry in records]
    predicted = [entry["predicted"] for entry in records]
    report = metrics(truth, predicted)
    gate = evaluate_gate(report)
    safety = safety_counts(records)
    agreement = sum(entry["agree"] for entry in records) / len(records)

    config = {
        "model": args.model, "sample_size": len(records), "seed": args.seed,
        "note": args.note, "timestamp": datetime.now().isoformat(timespec="seconds"),
        "system_prompt": SYSTEM_PROMPT,
    }
    path, run_id = new_run_dir(args.label or args.model)
    # Sort disagreements to the top so review starts with the interesting cases.
    records.sort(key=lambda entry: (entry["agree"], entry["ground_truth"] or ""))
    write_run(path, run_id, config, agreement, report, gate, safety, records)
    append_index(run_id, config, agreement, gate, safety)

    verdict = "SAFE TO RUN" if gate["passed"] else "TUNE THE PROMPT FIRST"
    print(f"\nRun {run_id}: {agreement:.1%} agreement, gate = {verdict}")
    print(f"Artifacts: {path}/summary.md  (index: runs/INDEX.md)")


if __name__ == "__main__":
    main()
