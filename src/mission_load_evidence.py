"""Load mission-text classifications into the ledger as immutable llm evidence.

Reads the fan-out result files, validates coverage, and appends one evidence
row per confident classification (method='llm', priority 50, floor 0.7 — it
fills gaps in unclassified entities and can never override deterministic
evidence). Confidence is recorded as-is; below-floor rows are written but do
not resolve. 'unknown' predictions are skipped. Then builds a fresh
classification release. Verifies coverage before writing; refuses if too many
batches are missing.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

from src.classification_store import (
    CLASSIFICATIONS,
    Evidence,
    append_evidence,
    build_release,
    create_classification_schema,
    create_run,
)
from src.mission_prompt import PROMPT_VERSION

DB = Path("data/grants_v2.db")
RESULTS = Path("scratch/mission/full/results")
BATCHES = Path("scratch/mission/full")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def load_results() -> tuple[dict[str, tuple[str, int, str]], list[str]]:
    expected = len(list(BATCHES.glob("batch_*.json")))
    preds: dict[str, tuple[str, int, str]] = {}
    missing: list[str] = []
    for i in range(expected):
        b = f"{i:04d}"
        path = RESULTS / f"batch_{b}.json"
        if not path.exists():
            missing.append(b)
            continue
        try:
            rows = json.loads(path.read_text())
        except json.JSONDecodeError:
            missing.append(b)
            continue
        for row in rows:
            try:
                conf = int(row.get("confidence", 0))
            except (TypeError, ValueError):
                conf = 0
            preds[row["id"]] = (row.get("tradition", "unknown"), conf,
                                (row.get("reason") or "")[:400])
    return preds, missing


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-missing", type=int, default=3,
                    help="refuse to load if more than this many batches missing")
    args = ap.parse_args()
    preds, missing = load_results()
    log(f"predictions: {len(preds):,} | missing/bad batches: {len(missing)} "
        f"{missing[:10]}")
    if len(missing) > args.max_missing:
        log(f"too many missing batches (> {args.max_missing}); re-run the "
            "fan-out to fill them before loading. Aborting.")
        sys.exit(2)

    conn = sqlite3.connect(f"file:{DB.resolve()}?mode=rw", uri=True, timeout=60)
    create_classification_schema(conn)
    identity_run = conn.execute(
        "SELECT run_id FROM identity_runs ORDER BY created_at_utc DESC LIMIT 1"
    ).fetchone()[0]
    run_id = create_run(conn, identity_run, "llm",
                        engine_name="fable-5-mission-text",
                        prompt_hash=PROMPT_VERSION,
                        config={"floor": 0.70, "source": "recipient-990-mission"})
    log(f"identity {identity_run} | classification run {run_id}")

    written = skipped_unknown = bad_label = below_floor = 0
    started = time.monotonic()
    for entity_id, (tradition, conf, reason) in preds.items():
        if tradition == "unknown":
            skipped_unknown += 1
            continue
        if tradition not in CLASSIFICATIONS:
            bad_label += 1
            continue
        if conf < 70:
            below_floor += 1  # still written; will not resolve (floor 0.7)
        append_evidence(conn, run_id, identity_run, Evidence(
            entity_id, tradition, min(max(conf, 0), 100) / 100.0, "llm",
            reason=reason, source_rule_id="mission-text-v1",
            source_record={"prompt": PROMPT_VERSION, "confidence": conf},
        ))
        written += 1
        if written % 5000 == 0:
            conn.commit()
            log(f"  wrote {written:,} evidence rows "
                f"({written / (time.monotonic() - started):,.0f}/s)")
    conn.commit()
    log(f"evidence written: {written:,} | skipped unknown: {skipped_unknown:,} "
        f"| bad label: {bad_label:,} | below-floor (recorded, non-resolving): "
        f"{below_floor:,}")

    log("building classification release…")
    release = build_release(conn, identity_run)
    issues = conn.execute(
        "SELECT COUNT(*) FROM classification_resolution_issues WHERE release_id=?",
        (release,)).fetchone()[0]
    resolved = conn.execute(
        "SELECT COUNT(*) FROM classification_resolutions WHERE release_id=?",
        (release,)).fetchone()[0]
    conn.close()
    log(f"release {release}: {resolved:,} entities resolved, {issues:,} issues")
    print(release)


if __name__ == "__main__":
    main()
