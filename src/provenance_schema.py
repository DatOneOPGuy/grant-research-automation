"""SQLite schema for the provenance-preserving IRS filing rebuild."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

SCHEMA_VERSION = "2.1.0"
CANONICAL_POLICY_VERSION = "latest-return-timestamp-v1"

CORE_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS filings (
    object_id TEXT PRIMARY KEY,
    source_path TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    return_id TEXT,
    filing_type TEXT,
    index_year INTEGER,
    index_tax_period TEXT,
    index_return_type TEXT,
    dln TEXT,
    xml_batch_id TEXT,
    ein TEXT,
    return_type TEXT,
    tax_year INTEGER,
    tax_period_end TEXT,
    return_timestamp_raw TEXT,
    return_timestamp_utc TEXT,
    is_amended INTEGER NOT NULL DEFAULT 0 CHECK (is_amended IN (0, 1)),
    parser_version TEXT NOT NULL,
    parse_status TEXT NOT NULL CHECK (parse_status IN (
        'parsed', 'excluded_return_type', 'invalid_identity', 'parse_error'
    )),
    error_message TEXT,
    parsed_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS foundation_filings (
    object_id TEXT PRIMARY KEY REFERENCES filings(object_id),
    ein TEXT NOT NULL,
    tax_year INTEGER NOT NULL,
    organization_name TEXT,
    city TEXT,
    state TEXT,
    country TEXT,
    assets_eoy INTEGER,
    qualifying_distributions INTEGER,
    contributions_paid INTEGER,
    total_revenue INTEGER,
    website TEXT,
    phone TEXT,
    invite_only INTEGER CHECK (invite_only IN (0, 1)),
    contact_person TEXT,
    contact_address TEXT,
    contact_phone TEXT,
    contact_email TEXT,
    application_format TEXT,
    deadlines TEXT,
    restrictions TEXT,
    has_application_info INTEGER NOT NULL DEFAULT 0
        CHECK (has_application_info IN (0, 1))
);

CREATE TABLE IF NOT EXISTS grant_transactions (
    grant_id TEXT PRIMARY KEY,
    object_id TEXT NOT NULL REFERENCES filings(object_id),
    ein TEXT NOT NULL,
    tax_year INTEGER NOT NULL,
    schedule_type TEXT NOT NULL
        CHECK (schedule_type IN ('paid', 'future_approved')),
    source_xpath TEXT NOT NULL,
    row_ordinal INTEGER NOT NULL,
    recipient_name TEXT,
    recipient_ein_raw TEXT,
    recipient_city TEXT,
    recipient_state TEXT,
    recipient_country TEXT,
    recipient_foundation_status TEXT,
    is_foreign INTEGER NOT NULL CHECK (is_foreign IN (0, 1)),
    amount_text TEXT,
    signed_amount INTEGER,
    amount_status TEXT NOT NULL
        CHECK (amount_status IN ('positive', 'zero', 'negative', 'missing', 'invalid')),
    purpose TEXT,
    UNIQUE (object_id, source_xpath, row_ordinal)
);

CREATE TABLE IF NOT EXISTS canonical_filings (
    ein TEXT NOT NULL,
    tax_year INTEGER NOT NULL,
    object_id TEXT NOT NULL REFERENCES filings(object_id),
    policy_version TEXT NOT NULL,
    selection_reason TEXT NOT NULL,
    selected_at_utc TEXT NOT NULL,
    PRIMARY KEY (ein, tax_year)
);
"""

INDEX_SCHEMA = """
CREATE INDEX IF NOT EXISTS idx_filings_ein_year
    ON filings(ein, tax_year);
CREATE INDEX IF NOT EXISTS idx_filings_status
    ON filings(parse_status, return_type);
CREATE INDEX IF NOT EXISTS idx_grants_object
    ON grant_transactions(object_id);
CREATE INDEX IF NOT EXISTS idx_grants_ein_year
    ON grant_transactions(ein, tax_year);
CREATE INDEX IF NOT EXISTS idx_grants_recipient_location
    ON grant_transactions(recipient_name, recipient_state, recipient_city);
CREATE INDEX IF NOT EXISTS idx_grants_schedule_amount
    ON grant_transactions(schedule_type, amount_status);
"""

VIEW_SCHEMA = """
DROP VIEW IF EXISTS canonical_foundations;
CREATE VIEW canonical_foundations AS
SELECT ff.*, f.tax_period_end, f.return_timestamp_utc, f.is_amended,
       f.object_id AS source_object_id, f.source_sha256
FROM canonical_filings c
JOIN foundation_filings ff ON ff.object_id = c.object_id
JOIN filings f ON f.object_id = c.object_id;

DROP VIEW IF EXISTS canonical_grants;
CREATE VIEW canonical_grants AS
SELECT g.*
FROM canonical_filings c
JOIN grant_transactions g ON g.object_id = c.object_id;

DROP VIEW IF EXISTS paid_grants;
CREATE VIEW paid_grants AS
SELECT * FROM canonical_grants
WHERE schedule_type = 'paid' AND amount_status = 'positive';

DROP VIEW IF EXISTS paid_adjustments;
CREATE VIEW paid_adjustments AS
SELECT * FROM canonical_grants
WHERE schedule_type = 'paid' AND amount_status != 'positive';

DROP VIEW IF EXISTS future_approved_grants;
CREATE VIEW future_approved_grants AS
SELECT * FROM canonical_grants
WHERE schedule_type = 'future_approved';

DROP VIEW IF EXISTS superseded_filings;
CREATE VIEW superseded_filings AS
SELECT f.* FROM filings f
LEFT JOIN canonical_filings c ON c.object_id = f.object_id
WHERE f.parse_status = 'parsed' AND c.object_id IS NULL;

-- Read-only API compatibility over the v2 canonical paid-grant substrate.
DROP VIEW IF EXISTS foundations;
CREATE VIEW foundations AS
SELECT ein,organization_name,city,state,country,assets_eoy AS assets,
       qualifying_distributions AS distributions,
       CASE WHEN EXISTS (
         SELECT 1 FROM paid_grants g
         WHERE g.ein=canonical_foundations.ein
           AND g.tax_year=canonical_foundations.tax_year
       ) THEN 1 ELSE 0 END AS has_grants,
       tax_year,website,phone,total_revenue AS revenue,invite_only,
       contact_person,contact_address,contact_phone,contact_email,
       application_format,deadlines,restrictions,has_application_info
FROM canonical_foundations;

DROP VIEW IF EXISTS grants;
CREATE VIEW grants AS
SELECT grant_id AS id,ein,recipient_name AS grantee_name,
       recipient_city AS city,recipient_state AS state,
       recipient_country AS country,is_foreign,signed_amount AS amount,
       purpose,tax_year,schedule_type
FROM paid_grants;

DROP VIEW IF EXISTS charitable_activities;
CREATE VIEW charitable_activities AS
SELECT NULL AS id,ein,'' AS description,0 AS expenses,tax_year
FROM canonical_foundations WHERE 0;
"""


def configure_connection(conn: sqlite3.Connection) -> None:
    """Apply build-time settings without weakening committed-data durability."""
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA temp_store = MEMORY")


def create_schema(conn: sqlite3.Connection) -> None:
    """Create the v2 tables, indexes, and compatibility-free audit views."""
    configure_connection(conn)
    conn.executescript(CORE_SCHEMA)
    conn.executescript(INDEX_SCHEMA)
    conn.executescript(VIEW_SCHEMA)
    conn.execute(
        "INSERT OR REPLACE INTO schema_metadata(key, value) VALUES (?, ?)",
        ("schema_version", SCHEMA_VERSION),
    )
    conn.commit()


def canonicalize_filings(conn: sqlite3.Connection) -> int:
    """Select one deterministic latest accepted filing per EIN and tax year."""
    selected_at = datetime.now(UTC).isoformat()
    conn.execute("DELETE FROM canonical_filings")
    conn.execute(
        """
        INSERT INTO canonical_filings
            (ein, tax_year, object_id, policy_version,
             selection_reason, selected_at_utc)
        SELECT ein, tax_year, object_id, ?,
               'latest return timestamp; amended flag and object ID break ties', ?
        FROM (
            SELECT ein, tax_year, object_id,
                   ROW_NUMBER() OVER (
                       PARTITION BY ein, tax_year
                       ORDER BY COALESCE(return_timestamp_utc, '') DESC,
                                is_amended DESC, object_id DESC
                   ) AS canonical_rank
            FROM filings
            WHERE parse_status = 'parsed' AND return_type = '990PF'
        ) ranked
        WHERE canonical_rank = 1
        """,
        (CANONICAL_POLICY_VERSION, selected_at),
    )
    count = conn.execute("SELECT COUNT(*) FROM canonical_filings").fetchone()[0]
    conn.commit()
    return count
