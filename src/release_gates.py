"""Fail-closed integrity gates for a Foundation Explorer v2 release."""

from __future__ import annotations

import argparse
import csv
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

from src.bmf_registry import REQUIRED_FILES


@dataclass(frozen=True)
class Gate:
    name: str
    passed: bool
    observed: int | str
    requirement: str

    def as_dict(self) -> dict:
        return asdict(self)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("data/grants_v2.db"))
    parser.add_argument("--bmf-db", type=Path, default=Path("data/bmf_registry.db"))
    parser.add_argument("--enrichment-release", required=True)
    parser.add_argument("--export", type=Path, default=Path("foundation_database_v2.csv"))
    return parser.parse_args()


def gate(name: str, observed: int, requirement: str = "must equal zero") -> Gate:
    return Gate(name, observed == 0, observed, requirement)


def release_row(conn: sqlite3.Connection, release_id: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM enrichment_releases WHERE release_id=? AND status='published'",
        (release_id,),
    ).fetchone()
    if not row:
        raise ValueError("Enrichment release is missing or unpublished.")
    return row


def source_gates(conn: sqlite3.Connection) -> list[Gate]:
    non_pf = conn.execute(
        "SELECT COUNT(*) FROM canonical_filings c JOIN filings f USING(object_id) "
        "WHERE f.return_type!='990PF' OR f.parse_status!='parsed'"
    ).fetchone()[0]
    invalid_paid = conn.execute(
        "SELECT COUNT(*) FROM paid_grants WHERE schedule_type!='paid' "
        "OR amount_status!='positive' OR signed_amount<=0"
    ).fetchone()[0]
    duplicate_canonical = conn.execute(
        "SELECT COUNT(*) FROM (SELECT ein,tax_year,COUNT(*) n FROM canonical_filings "
        "GROUP BY ein,tax_year HAVING n!=1)"
    ).fetchone()[0]
    return [
        gate("canonical_form_990pf_only", non_pf),
        gate("paid_view_positive_paid_only", invalid_paid),
        gate("one_canonical_filing_per_ein_year", duplicate_canonical),
    ]


def reconciliation_mismatches(conn: sqlite3.Connection, release: sqlite3.Row) -> int:
    return conn.execute(
        """
        WITH expected AS (
          SELECT ein,SUM(signed_amount) dollars,COUNT(*) grants
          FROM paid_grants WHERE tax_year BETWEEN ? AND ? GROUP BY ein
        ), mismatches AS (
          SELECT x.ein FROM expected x LEFT JOIN foundation_enrichment_v2 e
            ON e.release_id=? AND e.ein=x.ein
          WHERE e.ein IS NULL OR e.total_paid_grant_dollars!=x.dollars
             OR e.total_paid_grant_count!=x.grants
          UNION ALL
          SELECT e.ein FROM foundation_enrichment_v2 e LEFT JOIN expected x ON x.ein=e.ein
          WHERE e.release_id=? AND x.ein IS NULL
            AND (e.total_paid_grant_dollars!=0 OR e.total_paid_grant_count!=0)
        ) SELECT COUNT(*) FROM mismatches
        """,
        (
            release["tax_year_start"],
            release["tax_year_end"],
            release["release_id"],
            release["release_id"],
        ),
    ).fetchone()[0]


def enrichment_gates(conn: sqlite3.Connection, release: sqlite3.Row) -> list[Gate]:
    release_id = release["release_id"]
    bad_buckets = conn.execute(
        """
        SELECT COUNT(*) FROM foundation_enrichment_v2 WHERE release_id=? AND (
          total_paid_grant_dollars != confirmed_christian_dollars
            + confirmed_nonchristian_dollars + unclassified_dollars
          OR confirmed_christian_dollars > total_paid_grant_dollars)
        """,
        (release_id,),
    ).fetchone()[0]
    accepting_without_evidence = conn.execute(
        "SELECT COUNT(*) FROM foundation_enrichment_v2 WHERE release_id=? "
        "AND application_status='Accepting Applications' "
        "AND application_status_has_evidence!=1",
        (release_id,),
    ).fetchone()[0]
    issues = conn.execute(
        "SELECT COUNT(*) FROM classification_resolution_issues WHERE release_id=?",
        (release["classification_release_id"],),
    ).fetchone()[0]
    return [
        gate("paid_grants_reconcile_to_enrichment", reconciliation_mismatches(conn, release)),
        gate("classification_buckets_reconcile", bad_buckets),
        gate("zero_unresolved_classification_conflicts", issues),
        gate("accepting_requires_affirmative_evidence", accepting_without_evidence),
    ]


def bmf_gates(conn: sqlite3.Connection) -> list[Gate]:
    sources = {row[0] for row in conn.execute("SELECT source_file FROM bmf.bmf_sources")}
    missing = len(set(REQUIRED_FILES) - sources)
    return [gate("all_four_bmf_regions_present", missing)]


def export_facts(path: Path) -> dict:
    rows = 0
    duplicates = 0
    paid_dollars = 0
    release_ids: set[str] = set()
    eins: set[str] = set()
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows += 1
            ein = row["ein"]
            if ein in eins:
                duplicates += 1
            eins.add(ein)
            release_ids.add(row["enrichment_release_id"])
            paid_dollars += int(float(row["total_paid_grant_dollars"] or 0))
    return {
        "rows": rows,
        "duplicates": duplicates,
        "paid_dollars": paid_dollars,
        "release_ids": release_ids,
    }


def export_gates(conn: sqlite3.Connection, release: sqlite3.Row, export_path: Path) -> list[Gate]:
    if not export_path.exists():
        return [Gate("export_exists", False, "missing", "export file must exist")]
    facts = export_facts(export_path)
    universe = conn.execute(
        "SELECT COUNT(*) FROM ("
        "SELECT ein FROM bmf.bmf_organizations "
        "WHERE CAST(foundation_code AS INTEGER) IN (2,3,4) "
        "OR CAST(pf_filing_req_code AS INTEGER)=1 "
        "UNION SELECT ein FROM canonical_filings WHERE tax_year BETWEEN ? AND ?)"
        ,
        (release["tax_year_start"], release["tax_year_end"]),
    ).fetchone()[0]
    source_dollars = conn.execute(
        "SELECT COALESCE(SUM(signed_amount),0) FROM paid_grants WHERE tax_year BETWEEN ? AND ?",
        (release["tax_year_start"], release["tax_year_end"]),
    ).fetchone()[0]
    release_mismatch = int(facts["release_ids"] != {release["release_id"]})
    return [
        Gate("export_exists", True, "present", "export file must exist"),
        gate("export_row_count_matches_universe", abs(facts["rows"] - universe)),
        gate("export_eins_are_unique", facts["duplicates"]),
        gate("export_release_id_matches", release_mismatch),
        gate("export_paid_dollars_reconcile", abs(facts["paid_dollars"] - source_dollars)),
    ]


def run_gates(db_path: Path, bmf_path: Path, release_id: str, export_path: Path) -> list[Gate]:
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("ATTACH DATABASE ? AS bmf", (f"file:{bmf_path.resolve()}?mode=ro",))
    release = release_row(conn, release_id)
    results = source_gates(conn)
    results.extend(enrichment_gates(conn, release))
    results.extend(bmf_gates(conn))
    results.extend(export_gates(conn, release, export_path))
    conn.close()
    return results


def main() -> None:
    args = parse_args()
    results = run_gates(args.db, args.bmf_db, args.enrichment_release, args.export)
    for result in results:
        print(f"{'PASS' if result.passed else 'FAIL'} {result.name}: {result.observed}")
    if not all(result.passed for result in results):
        raise SystemExit("Release gates failed; do not publish this build.")


if __name__ == "__main__":
    main()
