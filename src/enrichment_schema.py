"""Release-scoped schema for paid-grant foundation enrichment."""

ENRICHMENT_POLICY_VERSION = "paid-canonical-grants-v1"

ENRICHMENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS enrichment_releases (
    release_id TEXT PRIMARY KEY,
    identity_run_id TEXT NOT NULL,
    classification_release_id TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    tax_year_start INTEGER NOT NULL,
    tax_year_end INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('building','published','failed')),
    created_at_utc TEXT NOT NULL,
    published_at_utc TEXT
);
CREATE TABLE IF NOT EXISTS foundation_enrichment_v2 (
    release_id TEXT NOT NULL REFERENCES enrichment_releases(release_id),
    ein TEXT NOT NULL,
    latest_tax_year INTEGER,
    latest_object_id TEXT,
    latest_qualifying_distributions INTEGER,
    total_paid_grant_dollars INTEGER NOT NULL,
    total_paid_grant_count INTEGER NOT NULL,
    confirmed_christian_dollars INTEGER NOT NULL,
    confirmed_nonchristian_dollars INTEGER NOT NULL,
    unclassified_dollars INTEGER NOT NULL,
    classification_coverage REAL NOT NULL,
    coverage_quality TEXT NOT NULL,
    christian_recipient_count INTEGER NOT NULL,
    christian_grant_count INTEGER NOT NULL,
    most_recent_christian_year INTEGER,
    typical_christian_grant INTEGER,
    largest_christian_grant INTEGER,
    predominant_tradition TEXT,
    verdict TEXT NOT NULL,
    application_status TEXT NOT NULL,
    application_status_has_evidence INTEGER NOT NULL CHECK (
        application_status_has_evidence IN (0,1)
    ),
    has_recent_filing INTEGER NOT NULL CHECK (has_recent_filing IN (0,1)),
    has_grant_data INTEGER NOT NULL CHECK (has_grant_data IN (0,1)),
    has_contact_info INTEGER NOT NULL CHECK (has_contact_info IN (0,1)),
    has_application_details INTEGER NOT NULL CHECK (has_application_details IN (0,1)),
    has_website INTEGER NOT NULL CHECK (has_website IN (0,1)),
    is_actively_giving INTEGER NOT NULL CHECK (is_actively_giving IN (0,1)),
    is_testamentary_trust INTEGER NOT NULL CHECK (is_testamentary_trust IN (0,1)),
    is_small_fund INTEGER NOT NULL CHECK (is_small_fund IN (0,1)),
    PRIMARY KEY (release_id, ein),
    CHECK (
        total_paid_grant_dollars = confirmed_christian_dollars
            + confirmed_nonchristian_dollars + unclassified_dollars
    ),
    CHECK (confirmed_christian_dollars <= total_paid_grant_dollars)
);
CREATE TABLE IF NOT EXISTS foundation_christian_evidence_v2 (
    release_id TEXT NOT NULL REFERENCES enrichment_releases(release_id),
    ein TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    recipient_name TEXT NOT NULL,
    recipient_ein TEXT,
    identity_status TEXT NOT NULL,
    classification TEXT NOT NULL,
    confidence REAL NOT NULL,
    evidence_method TEXT NOT NULL,
    total_paid_dollars INTEGER NOT NULL,
    grant_count INTEGER NOT NULL,
    most_recent_tax_year INTEGER NOT NULL,
    PRIMARY KEY (release_id, ein, entity_id)
);
CREATE INDEX IF NOT EXISTS idx_enrich_release_ein
    ON foundation_enrichment_v2(release_id, ein);
CREATE INDEX IF NOT EXISTS idx_enrich_release_verdict
    ON foundation_enrichment_v2(release_id, verdict);
CREATE INDEX IF NOT EXISTS idx_evidence_release_ein
    ON foundation_christian_evidence_v2(release_id, ein, total_paid_dollars DESC);
CREATE TRIGGER IF NOT EXISTS published_enrichment_no_update
BEFORE UPDATE ON foundation_enrichment_v2
WHEN (SELECT status FROM enrichment_releases WHERE release_id=OLD.release_id)='published'
BEGIN SELECT RAISE(ABORT, 'published enrichment is immutable'); END;
CREATE TRIGGER IF NOT EXISTS published_enrichment_no_delete
BEFORE DELETE ON foundation_enrichment_v2
WHEN (SELECT status FROM enrichment_releases WHERE release_id=OLD.release_id)='published'
BEGIN SELECT RAISE(ABORT, 'published enrichment is immutable'); END;
CREATE TRIGGER IF NOT EXISTS published_foundation_evidence_no_update
BEFORE UPDATE ON foundation_christian_evidence_v2
WHEN (SELECT status FROM enrichment_releases WHERE release_id=OLD.release_id)='published'
BEGIN SELECT RAISE(ABORT, 'published foundation evidence is immutable'); END;
CREATE TRIGGER IF NOT EXISTS published_foundation_evidence_no_delete
BEFORE DELETE ON foundation_christian_evidence_v2
WHEN (SELECT status FROM enrichment_releases WHERE release_id=OLD.release_id)='published'
BEGIN SELECT RAISE(ABORT, 'published foundation evidence is immutable'); END;
DROP VIEW IF EXISTS current_foundation_enrichment;
CREATE VIEW current_foundation_enrichment AS
SELECT e.* FROM foundation_enrichment_v2 e
JOIN enrichment_releases r ON r.release_id=e.release_id
WHERE r.status='published' AND r.published_at_utc=(
  SELECT MAX(published_at_utc) FROM enrichment_releases WHERE status='published'
);
DROP VIEW IF EXISTS current_christian_evidence;
CREATE VIEW current_christian_evidence AS
SELECT e.* FROM foundation_christian_evidence_v2 e
JOIN enrichment_releases r ON r.release_id=e.release_id
WHERE r.status='published' AND r.published_at_utc=(
  SELECT MAX(published_at_utc) FROM enrichment_releases WHERE status='published'
);
"""
