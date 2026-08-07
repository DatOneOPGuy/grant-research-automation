"""Immutable recipient-classification evidence and versioned release resolution."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from src.classification_schema import SCHEMA

CHRISTIAN_LABELS = frozenset(
    {
        "evangelical_protestant",
        "catholic",
        "orthodox_christian",
        "christian_unspecified",
    }
)
CLASSIFICATIONS = frozenset(
    {
        *CHRISTIAN_LABELS,
        "christian_science",
        "mormon_lds",
        "jewish",
        "muslim",
        "other_religion",
        "nonchristian_unspecified",
        "secular",
        "unknown",
    }
)
METHOD_PRIORITY = {
    "human": 100,
    "ntee": 80,
    "church_code_name": 80,   # BMF foundation code 10 + tradition signal
    "group_exemption": 75,    # denominational group ruling inheritance
    "rule": 70,
    "llm": 50,
    "legacy_faith_classification": 30,
    "legacy_tag": 30,
}
METHOD_CONFIDENCE_FLOOR = {
    "human": 0.0,
    "ntee": 0.8,
    "church_code_name": 0.9,
    "group_exemption": 0.9,
    "rule": 0.8,
    "llm": 0.7,
    "legacy_faith_classification": 0.7,
    "legacy_tag": 0.7,
}


@dataclass(frozen=True)
class Evidence:
    entity_id: str
    classification: str
    confidence: float
    method: str
    reason: str = ""
    source_rule_id: str | None = None
    source_ntee_code: str | None = None
    source_record: dict | None = None


def create_classification_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def create_run(
    conn: sqlite3.Connection,
    identity_run_id: str,
    method: str,
    engine_name: str = "",
    engine_digest: str = "",
    prompt_hash: str = "",
    config: dict | None = None,
) -> str:
    run_id = f"classify-{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
    conn.execute(
        "INSERT INTO classification_runs VALUES (?,?,?,?,?,?,?,?)",
        (
            run_id,
            identity_run_id,
            method,
            engine_name,
            engine_digest,
            prompt_hash,
            json.dumps(config or {}, sort_keys=True),
            datetime.now(UTC).isoformat(),
        ),
    )
    conn.commit()
    return run_id


def append_evidence(
    conn: sqlite3.Connection, run_id: str, identity_run_id: str, item: Evidence
) -> str:
    if item.classification not in CLASSIFICATIONS:
        raise ValueError(f"Unsupported classification: {item.classification}")
    if item.method not in METHOD_PRIORITY:
        raise ValueError(f"Unsupported evidence method: {item.method}")
    if not 0 <= item.confidence <= 1:
        raise ValueError("Evidence confidence must be between 0 and 1.")
    evidence_id = f"evidence-{uuid.uuid4().hex}"
    run = conn.execute(
        "SELECT engine_name,engine_digest,prompt_hash FROM classification_runs WHERE run_id=?",
        (run_id,),
    ).fetchone()
    if not run:
        raise ValueError(f"Unknown classification run: {run_id}")
    conn.execute(
        "INSERT INTO classification_evidence VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            evidence_id,
            run_id,
            identity_run_id,
            item.entity_id,
            item.classification,
            int(item.classification in CHRISTIAN_LABELS),
            item.confidence,
            item.method,
            item.source_rule_id,
            item.source_ntee_code,
            run[0],
            run[1],
            run[2],
            item.reason,
            json.dumps(item.source_record or {}, sort_keys=True),
            datetime.now(UTC).isoformat(),
        ),
    )
    return evidence_id


def eligible_evidence(rows: list[sqlite3.Row]) -> list[sqlite3.Row]:
    return [
        row
        for row in rows
        if row["classification"] != "unknown"
        and row["confidence"] >= METHOD_CONFIDENCE_FLOOR[row["evidence_method"]]
    ]


GENERIC_LABELS = frozenset({"christian_unspecified", "nonchristian_unspecified"})

_RULE_VERSION = re.compile(r"-v(\d+)$")


def _rule_version(row: sqlite3.Row) -> int:
    match = _RULE_VERSION.search(row["source_rule_id"] or "")
    return int(match.group(1)) if match else 0


def newest_rule_only(rows: list[sqlite3.Row]) -> list[sqlite3.Row]:
    """Drop superseded name-rule evidence.

    The ledger is append-only, so a corrected rule cannot delete what an
    earlier version wrote. Instead each rule pass stamps its version into
    source_rule_id, and only the newest version present for an entity is
    considered. That is how a v3 pass retracts a v2 false positive: it writes
    an `unknown` row, which shadows v2 and is then filtered as ineligible,
    leaving the entity unclassified rather than wrongly Christian.
    """
    rule_rows = [row for row in rows if row["evidence_method"] == "rule"]
    if len(rule_rows) < 2:
        return rows
    newest = max(_rule_version(row) for row in rule_rows)
    superseded = {
        id(row) for row in rule_rows if _rule_version(row) != newest
    }
    return [row for row in rows if id(row) not in superseded]


def choose_evidence(rows: list[sqlite3.Row]) -> tuple[sqlite3.Row | None, str | None]:
    eligible = eligible_evidence(newest_rule_only(rows))
    if not eligible:
        return None, "no_eligible_evidence"
    priority = max(METHOD_PRIORITY[row["evidence_method"]] for row in eligible)
    top = [row for row in eligible if METHOD_PRIORITY[row["evidence_method"]] == priority]
    # A generic label (christian_unspecified) alongside a specific sibling
    # (catholic, evangelical_protestant) that agrees on is_christian is a
    # refinement, not a contradiction — prefer the specific label. Only a
    # genuine is_christian disagreement, or two different specific
    # traditions at equal priority, is an unresolved issue.
    if len({row["is_christian"] for row in top}) != 1:
        return None, "conflicting_top_priority_evidence"
    specific = [row for row in top if row["classification"] not in GENERIC_LABELS]
    pool = specific or top
    if len({row["classification"] for row in pool}) != 1:
        return None, "conflicting_top_priority_evidence"
    return max(pool, key=lambda row: (row["confidence"], row["created_at_utc"])), None


def resolve_entity(
    conn: sqlite3.Connection,
    release_id: str,
    identity_run_id: str,
    entity_id: str,
    rows: list[sqlite3.Row],
    timestamp: str,
) -> None:
    chosen, issue = choose_evidence(rows)
    if issue:
        details = [
            {
                "evidence_id": row["evidence_id"],
                "classification": row["classification"],
                "confidence": row["confidence"],
                "method": row["evidence_method"],
            }
            for row in rows
        ]
        conn.execute(
            "INSERT INTO classification_resolution_issues VALUES (?,?,?,?)",
            (release_id, entity_id, issue, json.dumps(details, sort_keys=True)),
        )
        return
    conn.execute(
        "INSERT INTO classification_resolutions VALUES (?,?,?,?,?,?,?,?,?)",
        (
            release_id,
            identity_run_id,
            entity_id,
            chosen["evidence_id"],
            chosen["classification"],
            chosen["is_christian"],
            chosen["confidence"],
            "method-priority-confidence-v1",
            timestamp,
        ),
    )


def build_release(conn: sqlite3.Connection, identity_run_id: str) -> str:
    conn.row_factory = sqlite3.Row
    release_id = f"classification-{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
    timestamp = datetime.now(UTC).isoformat()
    conn.execute(
        "INSERT INTO classification_releases VALUES (?,?,?,?,?,NULL)",
        (release_id, identity_run_id, "method-priority-confidence-v1", "building", timestamp),
    )
    rows = conn.execute(
        "SELECT * FROM classification_evidence WHERE identity_run_id=? "
        "ORDER BY entity_id,created_at_utc",
        (identity_run_id,),
    ).fetchall()
    grouped: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        grouped.setdefault(row["entity_id"], []).append(row)
    for entity_id, evidence in grouped.items():
        resolve_entity(conn, release_id, identity_run_id, entity_id, evidence, timestamp)
    conn.execute(
        "UPDATE classification_releases SET status='published',published_at_utc=? "
        "WHERE release_id=?",
        (datetime.now(UTC).isoformat(), release_id),
    )
    conn.commit()
    return release_id
