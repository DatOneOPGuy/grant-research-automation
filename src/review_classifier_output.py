"""Read-only: dump raw local-LLM output next to ground truth for manual review.

Unlike validate_classifier (which keeps only labels for metrics), this persists
the exact JSON the model returned, the input it saw, and whether it agreed with
the rule/NTEE ground truth -- so a human can see *why* it abstains or misfires.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from src.recipient_taxonomy import (
    DEFAULT_MODEL,
    SYSTEM_PROMPT,
    TAXONOMY,
    ensure_model_available,
    ollama_client,
    prompt_for,
    response_content,
    unload_model,
)
from src.validate_classifier import open_readonly, sample_ground_truth


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("data/grants.db"))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260709)
    parser.add_argument("--out", type=Path, default=Path("logs/validation_review.json"))
    parser.add_argument("--only-disagreements", action="store_true",
                        help="Write only rows where the model disagreed with ground truth.")
    return parser.parse_args()


def raw_classify(model: str, row: dict) -> tuple[str, dict]:
    """Return (raw_json_string, parsed_payload_or_error) exactly as the model emitted it."""
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
    return raw, payload


def build_entry(model: str, row: dict) -> dict:
    truth = row["faith_classification"]
    raw, payload = raw_classify(model, row)
    predicted = payload.get("classification")
    return {
        "name": row.get("display_name"),
        "city": row.get("recipient_city"),
        "state": row.get("recipient_state"),
        "purpose": row.get("sample_purpose_text"),
        "ground_truth": truth,
        "model_prompt_input": prompt_for(row),
        "model_raw_json": raw,
        "predicted": predicted,
        "confidence": payload.get("confidence"),
        "reason": payload.get("reason"),
        "agree": predicted == truth,
        "predicted_valid": predicted in TAXONOMY,
    }


def main() -> None:
    args = parse_args()
    if not args.db.exists():
        raise FileNotFoundError(f"SQLite database not found: {args.db}")
    with open_readonly(args.db) as conn:
        sample = sample_ground_truth(conn, args.sample_size, args.seed)
    if not sample:
        raise RuntimeError("No rule/NTEE ground truth available to review.")
    from tqdm import tqdm

    ensure_model_available(args.model)
    entries = []
    try:
        for row in tqdm(sample, desc="Reviewing model output", unit="recipient"):
            entries.append(build_entry(args.model, row))
    finally:
        unload_model(args.model)

    if args.only_disagreements:
        entries = [entry for entry in entries if not entry["agree"]]
    # Disagreements first so the interesting cases are at the top of the file.
    entries.sort(key=lambda entry: (entry["agree"], entry["ground_truth"] or ""))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")

    disagreements = sum(not entry["agree"] for entry in entries)
    print(f"\nWrote {len(entries)} records to {args.out}")
    print(f"Disagreements with ground truth: {disagreements}")
    print("\nSample disagreements (truth -> predicted): reason")
    for entry in entries:
        if not entry["agree"]:
            print(f"  [{entry['ground_truth']} -> {entry['predicted']}] "
                  f"{entry['name']}: {entry['reason']}")
            if sum(not item["agree"] for item in entries[:entries.index(entry) + 1]) >= 15:
                break


if __name__ == "__main__":
    main()
