"""Bounded local-LLM batching, transactions, retries, and last-commit journal."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Number of concurrent local-LLM requests per 500-row batch. 1 preserves the
# original strictly-sequential behavior; higher values parallelize inference
# against Ollama's own request concurrency (OLLAMA_NUM_PARALLEL on the server).
CONCURRENCY = max(1, int(os.environ.get("CLASSIFY_CONCURRENCY", "1")))

from src.recipient_context import hydrate_records
from src.recipient_taxonomy import (
    classify_row,
    ensure_model_available,
    tags_for,
    unload_model,
)


class BatchInterrupted(KeyboardInterrupt):
    """Carries fully inferred rows so Ctrl-C can commit the active partial batch."""

    def __init__(self, successes: list[tuple], failures: list[tuple], context: list[tuple[str, str, str, str]]):
        self.successes = successes
        self.failures = failures
        self.context = context


def write_last_commit(path: Path, recipient_ids: list[str]) -> None:
    """Atomically journal only the just-committed batch to keep memory bounded."""
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.",
        suffix=".tmp", delete=False,
    ) as file:
        temporary = Path(file.name)
        json.dump({item: timestamp for item in recipient_ids}, file, separators=(",", ":"))
        file.flush()
        os.fsync(file.fileno())
    os.replace(temporary, path)


def success_update(row: dict[str, Any], result: tuple[str, float, str, float]) -> tuple:
    """Build one non-overwriting update for a valid LLM response."""
    tradition, confidence, reason, _latency = result
    return (
        tradition, confidence, reason, "llm", 0, tags_for(tradition, confidence),
        "llm", row["name_norm"],
    )


def failure_update(row: dict[str, Any], error: Exception, limit: int) -> tuple:
    """Increment retries, making persistently malformed records terminal."""
    attempts = int(row.get("classification_attempts") or 0) + 1
    terminal = attempts >= limit
    return (
        "llm_failed" if terminal else "pending",
        "llm_failed" if terminal else None,
        f"{type(error).__name__}: local LLM response failed validation",
        attempts,
        "llm_failed" if terminal else "pending",
        row["name_norm"],
    )


def is_record_error(error: Exception) -> bool:
    """Only malformed model responses consume an individual retry."""
    return isinstance(error, (KeyError, TypeError, ValueError, json.JSONDecodeError))


def commit_batch(
    conn: sqlite3.Connection,
    successes: list[tuple],
    failures: list[tuple],
    context_updates: list[tuple[str, str, str, str]],
    checkpoint_path: Path,
) -> tuple[int, int]:
    """Commit one batch, then write the bounded journal only after commit."""
    if not successes and not failures and not context_updates:
        return 0, 0
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN TRANSACTION;")
        cursor.executemany(
            """UPDATE recipients SET recipient_city=COALESCE(NULLIF(recipient_city, ''), ?),
               recipient_state=COALESCE(NULLIF(recipient_state, ''), ?),
               sample_purpose_text=COALESCE(NULLIF(sample_purpose_text, ''), ?)
               WHERE name_norm=?""",
            context_updates,
        )
        cursor.executemany(
            """UPDATE recipients SET faith_classification=?, confidence_score=?,
               classification_reason=?, classification_method=?, classification_attempts=?,
               tags=?, source=? WHERE name_norm=? AND source='pending'
               AND (classification_method IS NULL OR classification_method NOT IN ('rule', 'ntee'))""",
            successes,
        )
        cursor.executemany(
            """UPDATE recipients SET faith_classification=?, classification_method=?,
               confidence_score=NULL, classification_reason=?, classification_attempts=?,
               tags='[]', source=?
               WHERE name_norm=? AND source='pending'
               AND (classification_method IS NULL OR classification_method NOT IN ('rule', 'ntee'))""",
            failures,
        )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        cursor.close()
    ids = [update[-1] for update in successes] + [update[-1] for update in failures]
    if ids:
        write_last_commit(checkpoint_path, ids)
    return len(successes), sum(update[1] == "llm_failed" for update in failures)


def record_result(row, result_or_error, max_attempts, successes, failures, latencies) -> None:
    """Route one finished inference into the success or retry-failure buckets."""
    if isinstance(result_or_error, BaseException):
        if not is_record_error(result_or_error):
            raise result_or_error
        failures.append(failure_update(row, result_or_error, max_attempts))
    else:
        successes.append(success_update(row, result_or_error))
        latencies.append(result_or_error[3])


def classify_sequential(records, context, model, max_attempts, successes, failures, latencies):
    """Original one-at-a-time path; a bare Ctrl-C commits the partial batch."""
    for row in records:
        try:
            record_result(row, classify_row(model, row), max_attempts, successes, failures, latencies)
        except KeyboardInterrupt:
            raise BatchInterrupted(successes, failures, context) from None
        except Exception as error:
            record_result(row, error, max_attempts, successes, failures, latencies)


def classify_parallel(records, context, model, max_attempts, successes, failures, latencies):
    """Fan a 500-row batch across CONCURRENCY workers; Ctrl-C commits what finished."""
    pool = ThreadPoolExecutor(max_workers=CONCURRENCY)
    futures = {pool.submit(classify_row, model, row): row for row in records}
    consumed = set()
    try:
        for future in as_completed(futures):
            consumed.add(future)
            row = futures[future]
            try:
                record_result(row, future.result(), max_attempts, successes, failures, latencies)
            except Exception as error:
                record_result(row, error, max_attempts, successes, failures, latencies)
        pool.shutdown(wait=True)
    except KeyboardInterrupt:
        # Cancel queued work so Ctrl-C stops within seconds, not a full batch;
        # harvest results that finished but were not yet consumed above.
        pool.shutdown(wait=True, cancel_futures=True)
        for future, row in futures.items():
            if future in consumed or future.cancelled() or not future.done():
                continue
            try:
                record_result(row, future.result(), max_attempts, successes, failures, latencies)
            except Exception as error:
                record_result(row, error, max_attempts, successes, failures, latencies)
        raise BatchInterrupted(successes, failures, context) from None


def classify_dataframe(conn, dataframe, model: str, max_attempts: int) -> tuple[list[tuple], list[tuple], list[tuple[str, str, str, str]], list[float]]:
    """Hydrate a strict 500-row chunk and return pending writes without committing."""
    records, context = hydrate_records(conn, dataframe.to_dict("records"))
    successes: list[tuple] = []
    failures: list[tuple] = []
    latencies: list[float] = []
    runner = classify_parallel if CONCURRENCY > 1 else classify_sequential
    runner(records, context, model, max_attempts, successes, failures, latencies)
    return successes, failures, context, latencies


def run_batches(conn, query: str, model: str, max_attempts: int, checkpoint_path: Path) -> None:
    """Run strict pandas chunks with safe interrupt commits and model unloading."""
    import pandas as pd
    from tqdm import tqdm

    ensure_model_available(model)
    active: tuple[list[tuple], list[tuple], list[tuple[str, str, str, str]]] = ([], [], [])
    warm_latencies: list[float] = []
    try:
        chunks = pd.read_sql_query(query, conn, chunksize=500)
        with tqdm(desc="LLM recipient classifications", unit="recipient") as bar:
            for dataframe in chunks:
                successes, failures, context, latencies = classify_dataframe(conn, dataframe, model, max_attempts)
                active = successes, failures, context
                applied, terminal = commit_batch(conn, *active, checkpoint_path)
                active = [], [], []
                bar.update(len(dataframe))
                bar.set_postfix(applied=applied, deferred=len(failures) - terminal, terminal=terminal)
                warm_latencies.extend(latencies)
                if len(warm_latencies) == 2:
                    print(f"Ollama warm check: first={warm_latencies[0]:.2f}s, "
                          f"next={warm_latencies[1]:.2f}s (keep_alive=10m).")
    except BatchInterrupted as interrupted:
        active = interrupted.successes, interrupted.failures, interrupted.context
        applied, terminal = commit_batch(conn, *active, checkpoint_path)
        print(f"Interrupted safely: committed {applied} results and {terminal} terminal failures.")
    except KeyboardInterrupt:
        applied, terminal = commit_batch(conn, *active, checkpoint_path)
        print(f"Interrupted safely: committed {applied} results and {terminal} terminal failures.")
    finally:
        unload_model(model)
