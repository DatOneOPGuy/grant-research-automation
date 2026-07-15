"""SQLite schema for immutable, release-scoped recipient classification."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS classification_runs (
    run_id TEXT PRIMARY KEY,
    identity_run_id TEXT NOT NULL,
    method TEXT NOT NULL,
    engine_name TEXT,
    engine_digest TEXT,
    prompt_hash TEXT,
    config_json TEXT NOT NULL,
    created_at_utc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS classification_evidence (
    evidence_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES classification_runs(run_id),
    identity_run_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    classification TEXT NOT NULL,
    is_christian INTEGER NOT NULL CHECK (is_christian IN (0,1)),
    confidence REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    evidence_method TEXT NOT NULL,
    source_rule_id TEXT,
    source_ntee_code TEXT,
    model_name TEXT,
    model_digest TEXT,
    prompt_hash TEXT,
    reason TEXT,
    source_record_json TEXT NOT NULL,
    created_at_utc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS classification_releases (
    release_id TEXT PRIMARY KEY,
    identity_run_id TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('building','published','failed')),
    created_at_utc TEXT NOT NULL,
    published_at_utc TEXT
);
CREATE TABLE IF NOT EXISTS classification_resolutions (
    release_id TEXT NOT NULL REFERENCES classification_releases(release_id),
    identity_run_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL REFERENCES classification_evidence(evidence_id),
    classification TEXT NOT NULL,
    is_christian INTEGER NOT NULL CHECK (is_christian IN (0,1)),
    confidence REAL NOT NULL,
    resolution_policy TEXT NOT NULL,
    resolved_at_utc TEXT NOT NULL,
    PRIMARY KEY (release_id, entity_id)
);
CREATE TABLE IF NOT EXISTS classification_resolution_issues (
    release_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    issue_type TEXT NOT NULL,
    details_json TEXT NOT NULL,
    PRIMARY KEY (release_id, entity_id, issue_type)
);
CREATE INDEX IF NOT EXISTS idx_evidence_entity
    ON classification_evidence(identity_run_id, entity_id);
CREATE INDEX IF NOT EXISTS idx_resolution_entity
    ON classification_resolutions(release_id, entity_id);
CREATE TRIGGER IF NOT EXISTS evidence_no_update
BEFORE UPDATE ON classification_evidence BEGIN
  SELECT RAISE(ABORT, 'classification evidence is immutable');
END;
CREATE TRIGGER IF NOT EXISTS evidence_no_delete
BEFORE DELETE ON classification_evidence BEGIN
  SELECT RAISE(ABORT, 'classification evidence is immutable');
END;
CREATE TRIGGER IF NOT EXISTS resolution_no_update
BEFORE UPDATE ON classification_resolutions BEGIN
  SELECT RAISE(ABORT, 'classification resolutions are immutable');
END;
CREATE TRIGGER IF NOT EXISTS resolution_no_delete
BEFORE DELETE ON classification_resolutions BEGIN
  SELECT RAISE(ABORT, 'classification resolutions are immutable');
END;
DROP VIEW IF EXISTS current_classifications;
CREATE VIEW current_classifications AS
SELECT r.* FROM classification_resolutions r
JOIN classification_releases rel ON rel.release_id=r.release_id
WHERE rel.status='published' AND rel.published_at_utc=(
  SELECT MAX(published_at_utc) FROM classification_releases
  WHERE status='published' AND identity_run_id=rel.identity_run_id
);
"""
