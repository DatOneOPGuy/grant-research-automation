"""Pipeline reconciliation metrics for the Explorer data-quality page."""

from __future__ import annotations

import sqlite3

from db import is_v2_pipeline
from recipient_queries import current_identity_run


def pipeline_quality(conn: sqlite3.Connection, year_start: int, year_end: int) -> dict:
    if is_v2_pipeline(conn):
        return v2_quality(conn, year_start, year_end)
    return legacy_quality(conn, year_start, year_end)


def v2_quality(conn: sqlite3.Connection, year_start: int, year_end: int) -> dict:
    run_id = current_identity_run(conn)
    base = conn.execute(
        "SELECT (SELECT COUNT(*) FROM pipeline.foundation_filings),"
        "(SELECT COUNT(*) FROM pipeline.grants WHERE tax_year BETWEEN ? AND ?),"
        "(SELECT COALESCE(SUM(amount),0) FROM pipeline.grants "
        " WHERE tax_year BETWEEN ? AND ?),"
        "(SELECT COUNT(*) FROM pipeline.recipient_entities WHERE run_id=?),"
        "(SELECT COUNT(*) FROM pipeline.current_classifications "
        " WHERE identity_run_id=?),"
        "(SELECT COUNT(*) FROM pipeline.recipient_mentions "
        " WHERE run_id=? AND collision_flag=1),"
        "(SELECT COUNT(*) FROM pipeline.future_approved_grants),"
        "(SELECT COALESCE(SUM(signed_amount),0) "
        " FROM pipeline.future_approved_grants WHERE amount_status='positive'),"
        "(SELECT COUNT(*) FROM pipeline.paid_adjustments)",
        (year_start, year_end, year_start, year_end, run_id, run_id, run_id),
    ).fetchone()
    pending = unclassified_over_threshold(conn, run_id, 5_000)
    return quality_dict(base, pending, pipeline_version=2)


def unclassified_over_threshold(conn: sqlite3.Connection, run_id: str, threshold: int) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM ("
        " SELECT e.entity_id,SUM(m.paid_dollars) dollars "
        " FROM pipeline.recipient_entities e "
        " JOIN pipeline.recipient_entity_mentions em "
        " ON em.run_id=e.run_id AND em.entity_id=e.entity_id "
        " JOIN pipeline.recipient_mentions m "
        " ON m.run_id=em.run_id AND m.mention_id=em.mention_id "
        " LEFT JOIN pipeline.current_classifications c "
        " ON c.identity_run_id=e.run_id AND c.entity_id=e.entity_id "
        " WHERE e.run_id=? AND c.entity_id IS NULL GROUP BY e.entity_id "
        " HAVING dollars>=?)",
        (run_id, threshold),
    ).fetchone()[0]


def legacy_quality(conn: sqlite3.Connection, year_start: int, year_end: int) -> dict:
    row = conn.execute(
        "SELECT (SELECT COUNT(*) FROM pipeline.foundations),"
        "(SELECT COUNT(*) FROM pipeline.grants WHERE tax_year BETWEEN ? AND ?),"
        "(SELECT COALESCE(SUM(amount),0) FROM pipeline.grants "
        " WHERE tax_year BETWEEN ? AND ?),"
        "(SELECT COUNT(*) FROM pipeline.recipients),"
        "(SELECT COUNT(*) FROM pipeline.recipients "
        " WHERE source IN ('rule','seed','llm')),0,0,0,0",
        (year_start, year_end, year_start, year_end),
    ).fetchone()
    pending = conn.execute(
        "SELECT COUNT(*) FROM pipeline.recipients WHERE source='pending' AND max_grant>=5000"
    ).fetchone()[0]
    return quality_dict(row, pending, pipeline_version=1)


def quality_dict(row, pending: int, pipeline_version: int) -> dict:
    return {
        "foundation_filings": row[0],
        "grants": row[1],
        "grant_dollars": row[2],
        "recipients": row[3],
        "recipients_tagged": row[4],
        "identity_collisions": row[5],
        "future_commitments": row[6],
        "future_commitment_dollars": row[7],
        "paid_adjustments": row[8],
        "recipients_unclassified_5k": pending,
        "pipeline_version": pipeline_version,
    }
