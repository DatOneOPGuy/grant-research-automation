"""Efficiently hydrate recipient classification context from raw grant rows."""

from __future__ import annotations

import sqlite3
from typing import Any


def hydrate_records(
    conn: sqlite3.Connection, records: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[tuple[str, str, str, str]]]:
    """Fill missing city/state/purpose from the largest matching raw grant.

    The caller processes at most 500 records, so this uses at most 500 bound
    parameters and stays below SQLite's default parameter limit.
    """
    names = sorted({str(row["display_name"] or "") for row in records})
    names = [name for name in names if name]
    if not names:
        return records, []
    values = ", ".join("(?)" for _ in names)
    query = f"""
        WITH candidates(name) AS (VALUES {values}), ranked AS (
            SELECT g.grantee_name, g.city, g.state, g.purpose,
                   ROW_NUMBER() OVER (
                       PARTITION BY g.grantee_name
                       ORDER BY ABS(COALESCE(g.amount, 0)) DESC, g.tax_year DESC
                   ) AS row_number
            FROM grants AS g
            JOIN candidates AS c ON c.name = g.grantee_name
        )
        SELECT grantee_name, city, state, purpose FROM ranked WHERE row_number = 1
    """
    context = {
        name: (city or "", state or "", purpose or "")
        for name, city, state, purpose in conn.execute(query, names)
    }
    updates: list[tuple[str, str, str, str]] = []
    for row in records:
        city, state, purpose = context.get(str(row["display_name"] or ""), ("", "", ""))
        row["recipient_city"] = row.get("recipient_city") or city
        row["recipient_state"] = row.get("recipient_state") or state
        row["sample_purpose_text"] = row.get("sample_purpose_text") or purpose
        if city or state or purpose:
            updates.append((city, state, purpose, row["name_norm"]))
    return records, updates
