"""Build release-scoped foundation metrics from canonical positive paid grants."""

from __future__ import annotations

import argparse
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from src.enrichment_schema import ENRICHMENT_POLICY_VERSION, ENRICHMENT_SCHEMA
from src.enrichment_values import enrichment_row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("data/grants_v2.db"))
    parser.add_argument("--identity-run", required=True)
    parser.add_argument("--classification-release", required=True)
    parser.add_argument("--tax-year-start", type=int, default=2023)
    parser.add_argument("--tax-year-end", type=int)
    return parser.parse_args()


def available_tax_year_end(conn: sqlite3.Connection, start: int) -> int:
    value = conn.execute(
        "SELECT MAX(tax_year) FROM canonical_filings WHERE tax_year>=?", (start,)
    ).fetchone()[0]
    if value is None:
        raise RuntimeError(f"No canonical filings exist at or after tax year {start}.")
    return int(value)


def validate_inputs(
    conn: sqlite3.Connection, identity_run_id: str, classification_release_id: str
) -> None:
    identity = conn.execute(
        "SELECT 1 FROM identity_runs WHERE run_id=?", (identity_run_id,)
    ).fetchone()
    release = conn.execute(
        "SELECT identity_run_id,status FROM classification_releases WHERE release_id=?",
        (classification_release_id,),
    ).fetchone()
    if not identity:
        raise ValueError(f"Unknown identity run: {identity_run_id}")
    if not release or release[1] != "published":
        raise ValueError("Classification release is missing or unpublished.")
    if release[0] != identity_run_id:
        raise ValueError("Classification release belongs to a different identity run.")


def create_release(
    conn: sqlite3.Connection,
    identity_run_id: str,
    classification_release_id: str,
    year_start: int,
    year_end: int,
) -> str:
    release_id = f"enrich-{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
    conn.execute(
        "INSERT INTO enrichment_releases VALUES (?,?,?,?,?,?,?, ?,NULL)",
        (
            release_id,
            identity_run_id,
            classification_release_id,
            ENRICHMENT_POLICY_VERSION,
            year_start,
            year_end,
            "building",
            datetime.now(UTC).isoformat(),
        ),
    )
    return release_id


def classified_grants_sql() -> str:
    return """
    SELECT g.grant_id,g.ein,g.tax_year,g.signed_amount,
           e.entity_id,e.canonical_name,e.bmf_ein,e.identity_status,
           r.classification,r.is_christian,r.confidence,
           ce.evidence_method
    FROM paid_grants g
    LEFT JOIN grant_recipient_links l
      ON l.run_id=:identity_run AND l.grant_id=g.grant_id
    LEFT JOIN recipient_entity_mentions m
      ON m.run_id=:identity_run AND m.mention_id=l.mention_id
    LEFT JOIN recipient_entities e
      ON e.run_id=:identity_run AND e.entity_id=m.entity_id
    LEFT JOIN classification_resolutions r
      ON r.release_id=:classification_release AND r.entity_id=e.entity_id
    LEFT JOIN classification_evidence ce ON ce.evidence_id=r.evidence_id
    WHERE g.tax_year BETWEEN :year_start AND :year_end
    """


def create_classified_grants_temp(conn: sqlite3.Connection, params: dict[str, str | int]) -> None:
    conn.execute("DROP TABLE IF EXISTS temp.classified_paid_grants")
    conn.execute(f"CREATE TEMP TABLE classified_paid_grants AS {classified_grants_sql()}", params)
    conn.execute("CREATE INDEX temp.idx_cpg_ein ON classified_paid_grants(ein)")
    conn.execute("CREATE INDEX temp.idx_cpg_entity ON classified_paid_grants(entity_id)")


def create_foundation_rollups(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TEMP TABLE foundation_metrics AS
        SELECT ein,COALESCE(SUM(signed_amount),0) total_paid,COUNT(*) grant_count,
          COALESCE(SUM(CASE WHEN is_christian=1 THEN signed_amount ELSE 0 END),0) christian,
          COALESCE(SUM(CASE WHEN is_christian=0 THEN signed_amount ELSE 0 END),0) nonchristian,
          COALESCE(SUM(CASE WHEN is_christian IS NULL
            THEN signed_amount ELSE 0 END),0) unclassified,
          COUNT(DISTINCT CASE WHEN is_christian=1 THEN entity_id END) christian_recipients,
          SUM(CASE WHEN is_christian=1 THEN 1 ELSE 0 END) christian_grants,
          MAX(CASE WHEN is_christian=1 THEN tax_year END) recent_christian_year,
          ROUND(AVG(CASE WHEN is_christian=1 THEN signed_amount END)) typical_christian_grant,
          MAX(CASE WHEN is_christian=1 THEN signed_amount END) largest_christian_grant
        FROM classified_paid_grants GROUP BY ein
        """
    )
    conn.execute("CREATE UNIQUE INDEX temp.idx_metrics_ein ON foundation_metrics(ein)")
    conn.execute(
        """
        CREATE TEMP TABLE foundation_traditions AS
        WITH totals AS (
          SELECT ein,classification,SUM(signed_amount) dollars
          FROM classified_paid_grants WHERE is_christian=1 GROUP BY ein,classification
        ), ranked AS (
          SELECT *,SUM(dollars) OVER (PARTITION BY ein) total,
            ROW_NUMBER() OVER (PARTITION BY ein ORDER BY dollars DESC,classification) rank
          FROM totals
        )
        SELECT ein,CASE WHEN dollars>total/2 THEN classification ELSE 'Mixed' END tradition
        FROM ranked WHERE rank=1
        """
    )
    conn.execute("CREATE UNIQUE INDEX temp.idx_traditions_ein ON foundation_traditions(ein)")


def insert_evidence(conn: sqlite3.Connection, release_id: str) -> None:
    conn.execute(
        """
        INSERT INTO foundation_christian_evidence_v2
        SELECT ?,ein,entity_id,MAX(canonical_name),MAX(bmf_ein),MAX(identity_status),
               MAX(classification),MAX(confidence),MAX(evidence_method),
               SUM(signed_amount),COUNT(*),MAX(tax_year)
        FROM classified_paid_grants
        WHERE is_christian=1 AND entity_id IS NOT NULL
        GROUP BY ein,entity_id
        """,
        (release_id,),
    )


def latest_foundations(conn: sqlite3.Connection, year_start: int, year_end: int):
    return conn.execute(
        """
        WITH latest AS (
          SELECT f.*, ROW_NUMBER() OVER (
            PARTITION BY ein ORDER BY tax_year DESC, source_object_id DESC
          ) AS rank
          FROM canonical_foundations f WHERE tax_year BETWEEN ? AND ?
        )
        SELECT latest.*,m.total_paid,m.grant_count,m.christian,m.nonchristian,
          m.unclassified,m.christian_recipients,m.christian_grants,
          m.recent_christian_year,m.typical_christian_grant,m.largest_christian_grant,
          t.tradition
        FROM latest
        LEFT JOIN foundation_metrics m USING(ein)
        LEFT JOIN foundation_traditions t USING(ein)
        WHERE latest.rank=1
        """,
        (year_start, year_end),
    )


def metrics_from(profile: sqlite3.Row) -> tuple:
    keys = (
        "total_paid", "grant_count", "christian", "nonchristian", "unclassified",
        "christian_recipients", "christian_grants", "recent_christian_year",
        "typical_christian_grant", "largest_christian_grant",
    )
    return tuple(profile[key] or 0 for key in keys)


def insert_foundation(
    conn: sqlite3.Connection, release_id: str, profile: sqlite3.Row, year_end: int
) -> None:
    conn.execute(
        "INSERT INTO foundation_enrichment_v2 VALUES "
        "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        enrichment_row(release_id, profile, year_end, metrics_from(profile), profile["tradition"]),
    )


def run(
    db_path: Path,
    identity_run_id: str,
    classification_release_id: str,
    year_start: int = 2023,
    year_end: int | None = None,
) -> str:
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=rw", uri=True)
    conn.row_factory = sqlite3.Row
    conn.executescript(ENRICHMENT_SCHEMA)
    validate_inputs(conn, identity_run_id, classification_release_id)
    actual_end = year_end or available_tax_year_end(conn, year_start)
    if actual_end < year_start:
        raise ValueError("Tax year end precedes tax year start.")
    release_id = create_release(
        conn, identity_run_id, classification_release_id, year_start, actual_end
    )
    params = {
        "identity_run": identity_run_id,
        "classification_release": classification_release_id,
        "year_start": year_start,
        "year_end": actual_end,
    }
    try:
        create_classified_grants_temp(conn, params)
        insert_evidence(conn, release_id)
        create_foundation_rollups(conn)
        for profile in latest_foundations(conn, year_start, actual_end):
            insert_foundation(conn, release_id, profile, actual_end)
        conn.execute(
            "UPDATE enrichment_releases SET status='published',published_at_utc=? "
            "WHERE release_id=?",
            (datetime.now(UTC).isoformat(), release_id),
        )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    conn.close()
    return release_id


def main() -> None:
    args = parse_args()
    release_id = run(
        args.db,
        args.identity_run,
        args.classification_release,
        args.tax_year_start,
        args.tax_year_end,
    )
    print(f"Published enrichment release: {release_id}")


if __name__ == "__main__":
    main()
