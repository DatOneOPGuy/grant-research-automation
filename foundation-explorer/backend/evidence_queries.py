"""Christian-evidence queries across legacy and provenance-first releases."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from db import data_window, is_v2_pipeline, rows_to_dicts

TRADITIONS = {
    "evangelical_protestant": "Evangelical/Protestant",
    "catholic": "Catholic",
    "orthodox_christian": "Orthodox",
    "christian_unspecified": "Christian (unspecified)",
}


def christian_evidence(conn: sqlite3.Connection, ein: str) -> dict:
    """Return visible evidence using the same release that produced the verdict."""
    year_start, year_end = data_window(conn)
    if is_v2_pipeline(conn):
        recipients = v2_evidence(conn, ein)
    else:
        recipients = legacy_evidence(conn, ein, year_start, year_end)
    return {
        "count": len(recipients),
        "recipients": recipients,
        "tax_year_start": year_start,
        "tax_year_end": year_end,
    }


def v2_evidence(conn: sqlite3.Connection, ein: str) -> list[dict]:
    rows = conn.execute(
        "SELECT recipient_name AS name,total_paid_dollars AS total,"
        "most_recent_tax_year AS most_recent_year,classification "
        "FROM pipeline.current_christian_evidence WHERE ein IN (?,?) "
        "ORDER BY total_paid_dollars DESC",
        (ein, ein.lstrip("0")),
    ).fetchall()
    output = rows_to_dicts(rows)
    for row in output:
        row["tradition"] = TRADITIONS.get(row.pop("classification"), "")
    return output


def legacy_evidence(
    conn: sqlite3.Connection, ein: str, year_start: int, year_end: int
) -> list[dict]:
    normalize, tradition, faith_tags, confidence_min = legacy_helpers()
    grants = conn.execute(
        "SELECT grantee_name,amount,tax_year FROM pipeline.grants "
        "WHERE ein IN (?,?) AND grantee_name != '' AND tax_year BETWEEN ? AND ?",
        (ein, ein.lstrip("0"), year_start, year_end),
    ).fetchall()
    aggregates: dict[str, dict] = {}
    for name, amount, year in grants:
        key = normalize(name)
        if key not in aggregates:
            aggregates[key] = legacy_recipient(
                conn, key, name, tradition, faith_tags, confidence_min
            )
        if aggregates[key]["is_christian"]:
            aggregates[key]["total"] += amount or 0
            aggregates[key]["most_recent_year"] = max(aggregates[key]["most_recent_year"], year)
    rows = [
        clean_legacy(row) for row in aggregates.values() if row["is_christian"] and row["total"] > 0
    ]
    return sorted(rows, key=lambda row: -row["total"])


def legacy_helpers():
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from src.classifier import tradition
    from src.faith_config import CONFIDENCE_MIN, FAITH_TAGS
    from src.matcher import normalize

    return normalize, tradition, set(FAITH_TAGS), CONFIDENCE_MIN


def legacy_recipient(conn, key, name, tradition, faith_tags, confidence_min):
    tag = conn.execute("SELECT tags FROM pipeline.recipients WHERE name_norm=?", (key,)).fetchone()
    labels = (
        {item["name"] for item in json.loads(tag[0]) if item.get("confidence", 0) >= confidence_min}
        if tag
        else set()
    )
    return {
        "is_christian": bool(labels & faith_tags),
        "name": name,
        "total": 0,
        "most_recent_year": 0,
        "tradition": tradition(name),
    }


def clean_legacy(row: dict) -> dict:
    return {key: value for key, value in row.items() if key != "is_christian"}
