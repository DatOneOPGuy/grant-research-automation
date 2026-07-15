"""Recipient explorer queries for legacy and provenance-first databases."""

from __future__ import annotations

import json
import sqlite3

from db import is_v2_pipeline, rows_to_dicts

LABELS = {
    "evangelical_protestant": "Evangelical / Protestant",
    "catholic": "Catholic",
    "orthodox_christian": "Orthodox Christian",
    "christian_unspecified": "Christian (unspecified)",
    "christian_science": "Christian Science",
    "mormon_lds": "Mormon / LDS",
    "jewish": "Jewish",
    "muslim": "Muslim",
    "other_religion": "Other religion",
    "nonchristian_unspecified": "Non-Christian (unspecified)",
    "secular": "Secular",
}


def current_identity_run(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT identity_run_id FROM pipeline.current_foundation_enrichment LIMIT 1"
    ).fetchone()
    if not row:
        raise RuntimeError("The v2 pipeline has no published enrichment release.")
    return row[0]


def list_recipients(
    conn: sqlite3.Connection,
    *,
    q: str | None,
    tag: str | None,
    source: str | None,
    min_max_grant: int | None,
    page: int,
    page_size: int,
) -> dict:
    if is_v2_pipeline(conn):
        return list_v2(conn, q, tag, source, min_max_grant, page, page_size)
    return list_legacy(conn, q, tag, source, min_max_grant, page, page_size)


def v2_base_sql() -> str:
    return """
    SELECT e.entity_id AS name_norm,e.canonical_name AS display_name,
           e.identity_status,COALESCE(c.classification,'unknown') classification,
           COALESCE(ev.evidence_method,'unclassified') source,
           COALESCE(c.confidence,0) confidence,
           COALESCE(SUM(m.paid_dollars),0) total_received,
           COALESCE(MAX(m.max_paid_grant),0) max_grant
    FROM pipeline.recipient_entities e
    LEFT JOIN pipeline.recipient_entity_mentions em
      ON em.run_id=e.run_id AND em.entity_id=e.entity_id
    LEFT JOIN pipeline.recipient_mentions m
      ON m.run_id=em.run_id AND m.mention_id=em.mention_id
    LEFT JOIN pipeline.current_classifications c
      ON c.identity_run_id=e.run_id AND c.entity_id=e.entity_id
    LEFT JOIN pipeline.classification_evidence ev ON ev.evidence_id=c.evidence_id
    WHERE e.run_id=?
    GROUP BY e.entity_id,e.canonical_name,e.identity_status,c.classification,
             ev.evidence_method,c.confidence
    """


def list_v2(conn, q, tag, source, min_max_grant, page, page_size) -> dict:
    clauses, args = ["1=1"], []
    if q:
        clauses.append("display_name LIKE ?")
        args.append(f"%{q}%")
    if tag:
        clauses.append("classification=?")
        args.append(tag)
    if source:
        clauses.append("source=?")
        args.append(source)
    if min_max_grant is not None:
        clauses.append("max_grant>=?")
        args.append(min_max_grant)
    base = v2_base_sql()
    run_id = current_identity_run(conn)
    where = " AND ".join(clauses)
    total = conn.execute(
        f"SELECT COUNT(*) FROM ({base}) WHERE {where}", [run_id, *args]
    ).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM ({base}) WHERE {where} ORDER BY total_received DESC LIMIT ? OFFSET ?",
        [run_id, *args, page_size, (page - 1) * page_size],
    ).fetchall()
    output = rows_to_dicts(rows)
    for row in output:
        label = LABELS.get(row["classification"])
        row["tags"] = [{"name": label, "confidence": row["confidence"]}] if label else []
    return {"total": total, "page": page, "rows": output}


def list_legacy(conn, q, tag, source, min_max_grant, page, page_size) -> dict:
    where, args = ["1=1"], []
    for value, clause in (
        (q, "display_name LIKE ?"),
        (tag, "tags LIKE ?"),
        (source, "source = ?"),
    ):
        if value:
            where.append(clause)
            args.append(
                f'%"{value}"%'
                if clause.startswith("tags")
                else (f"%{value}%" if clause.startswith("display") else value)
            )
    if min_max_grant is not None:
        where.append("max_grant >= ?")
        args.append(min_max_grant)
    clause = " AND ".join(where)
    total = conn.execute(
        f"SELECT COUNT(*) FROM pipeline.recipients WHERE {clause}", args
    ).fetchone()[0]
    rows = conn.execute(
        "SELECT name_norm,display_name,tags,source,max_grant "
        f"FROM pipeline.recipients WHERE {clause} "
        "ORDER BY max_grant DESC LIMIT ? OFFSET ?",
        [*args, page_size, (page - 1) * page_size],
    ).fetchall()
    output = rows_to_dicts(rows)
    for row in output:
        row["tags"] = json.loads(row["tags"] or "[]")
    return {"total": total, "page": page, "rows": output}


def recipient_stats(conn: sqlite3.Connection) -> dict:
    if not is_v2_pipeline(conn):
        rows = conn.execute(
            "SELECT source,COUNT(*) FROM pipeline.recipients GROUP BY source"
        ).fetchall()
        return {"by_source": dict(rows), "pipeline_version": 1}
    run_id = current_identity_run(conn)
    rows = conn.execute(
        "SELECT COALESCE(ev.evidence_method,'unclassified'),COUNT(*) "
        "FROM pipeline.recipient_entities e "
        "LEFT JOIN pipeline.current_classifications c "
        "ON c.identity_run_id=e.run_id AND c.entity_id=e.entity_id "
        "LEFT JOIN pipeline.classification_evidence ev ON ev.evidence_id=c.evidence_id "
        "WHERE e.run_id=? GROUP BY 1",
        (run_id,),
    ).fetchall()
    return {"by_source": dict(rows), "pipeline_version": 2}


def recipient_funders(conn: sqlite3.Connection, key: str, limit: int) -> list[dict]:
    if is_v2_pipeline(conn):
        rows = funders_v2(conn, key, limit)
    else:
        rows = funders_legacy(conn, key, limit)
    output = rows_to_dicts(rows)
    attach_foundation_names(conn, output)
    return output


def funders_v2(conn, entity_id, limit):
    run_id = current_identity_run(conn)
    return conn.execute(
        "SELECT g.ein,COUNT(*) n,SUM(g.signed_amount) dollars,"
        "GROUP_CONCAT(DISTINCT g.tax_year) years "
        "FROM pipeline.recipient_entity_mentions em "
        "JOIN pipeline.grant_recipient_links l "
        "ON l.run_id=em.run_id AND l.mention_id=em.mention_id "
        "JOIN pipeline.paid_grants g ON g.grant_id=l.grant_id "
        "WHERE em.run_id=? AND em.entity_id=? GROUP BY g.ein "
        "ORDER BY dollars DESC LIMIT ?",
        (run_id, entity_id, limit),
    ).fetchall()


def funders_legacy(conn, name_norm, limit):
    display = conn.execute(
        "SELECT display_name FROM pipeline.recipients WHERE name_norm=?",
        (name_norm,),
    ).fetchone()
    if not display:
        return []
    return conn.execute(
        "SELECT ein,COUNT(*) n,SUM(amount) dollars,"
        "GROUP_CONCAT(DISTINCT tax_year) years FROM pipeline.grants "
        "WHERE grantee_name=? GROUP BY ein ORDER BY dollars DESC LIMIT ?",
        (display[0], limit),
    ).fetchall()


def attach_foundation_names(conn: sqlite3.Connection, rows: list[dict]) -> None:
    eins = {str(row["ein"]).zfill(9) for row in rows}
    if not eins:
        return
    marks = ",".join("?" * len(eins))
    names = dict(
        conn.execute(
            f"SELECT ein,foundation_name FROM universe WHERE ein IN ({marks})", list(eins)
        ).fetchall()
    )
    for row in rows:
        row["foundation_name"] = names.get(str(row["ein"]).zfill(9), "")
