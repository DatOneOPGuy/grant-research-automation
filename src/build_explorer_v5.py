"""Build the Explorer v5 read model from the v5 identity + evidence ledger.

One query-optimized SQLite file (data/explorer_v5.db) serving the filter
product: paid grants only, tax years 2023-2024, honest identity and
classification status on every row. Rebuilt from scratch each run; the
pipeline database is opened read-only.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

from src import country_codes

PIPELINE_DB = Path("data/grants_v2.db")
BMF_DB = Path("data/bmf_registry.db")
OUT_DB = Path("data/explorer_v5.db")
CHRISTIAN = ("evangelical_protestant", "catholic", "orthodox_christian",
             "christian_unspecified")
AUTHORITATIVE = ("human", "ntee", "church_code_name", "group_exemption")
DAF_PATTERN = re.compile(
    r"\b(donor advised|charitable gift fund|giving fund|philanthropic tr(ust)?|"
    r"donors? trust|fidelity charitable|schwab charitable|vanguard charitable|"
    r"american online giving|national christian foundation|american endowment|"
    r"national philanthropic)\b")
TESTAMENTARY = re.compile(r"\b(tuw|tua|uw|testamentary|crut|crat|charitable remainder)\b")

# Identity dispositions excluded from the coverage denominator. Coverage answers
# "of the dollars that went to identifiable organizations we could in principle
# classify, how many did we classify" -- so it must not penalize a foundation
# for dollars the filing itself never attributed to an organization.
#
#   unattributable -- the 990-PF names no recipient: "INDIVIDUAL PATIENT
#     PROGRAMS", "Eligible Patients (See Schedule #2)", "HIPPA REGULATIONS
#     PREVENT THE LISTING OF NAMES", "See Statement 17", "ATCH 4". $58.46B and
#     0.0% classified, because there is nothing there to classify -- by us or
#     by anyone.
#   individual -- grants to natural persons (scholarships, hardship and patient
#     aid). Real dispositions, but a religious tradition is a property of an
#     organization; it cannot attach to a person. $3.60B, 4.1% classified.
#
# Deliberately NOT excluded, because each is a genuine coverage gap we could
# close and hiding it would overstate our coverage:
#   foreign ($10.26B, 23.3%) -- real organizations, classifiable from name and
#     mission text. Overseas mission agencies live here, so this gap is
#     product-relevant for a Christian-donor tool and must stay visible.
#   government ($6.12B, 56.2%) -- identifiable public bodies, classifiable.
#   collision ($4.28B, 65.3%) -- ambiguous identity is our unfinished work.
#   unresolved ($48.25B, 36.5%) -- the core remaining gap; excluding it would
#     make the product look finished when it is not.
NONCLASSIFIABLE_STATUSES = ("unattributable", "individual")

# Why a recipient could not be attributed, matched on the markers the filer
# actually wrote. Verified against raw XML in logs/parser_recipient_audit.md:
# in every case the string below is the filer's own text, not a parse failure.
# Order matters -- HIPAA and 4948 are legal non-disclosure and must win over
# the generic "see attached" test, which many of them also match.
REASON_RULES = (
    ("hipaa", re.compile(
        r"hipaa|hippa|health insurance portability|patient|confidential|"
        r"cannot be listed|not be disclosed", re.I)),
    ("foreign_4948", re.compile(r"4948", re.I)),
    ("pdf_attachment", re.compile(
        r"see\s+attach|attached\s+(pdf|schedule|statement|list)|see\s+schedule|"
        r"see\s+statement|see\s+below|see\s+part|attachment|\bpdf\b|\bstmt\b|"
        r"^\W*(grants?|various|totals?|n/?a|none|other|continued|"
        r"miscellaneous|contributions?|schedule)\W*$", re.I)),
)
REASON_LABELS = {
    "hipaa": "[Individual patients — HIPAA protected]",
    "foreign_4948": "[Foreign foundation — recipients not itemized]",
    "pdf_attachment": "[Recipients filed as PDF attachment]",
    "not_itemized": "[Recipients not itemized in the filing]",
}


def unattributable_reason(name: str | None) -> str:
    for reason, pattern in REASON_RULES:
        if pattern.search(name or ""):
            return reason
    return "not_itemized"

# One canonical definition of "this grant left the country", used by every
# aggregate so the figures cannot drift apart. Union rather than intersection:
# some filers give a foreign address element with no country code, others a
# country code inside a domestic address block. Requiring both would drop real
# international giving; requiring either can at worst over-include a
# mis-keyed domestic row, which the country breakdown makes visible.
DOMESTIC_SQL = ", ".join(f"'{code}'" for code in sorted(country_codes.DOMESTIC))
FOREIGN_SQL = (f"(g.is_foreign=1 OR (COALESCE(g.recipient_country,'') != '' "
               f"AND g.recipient_country NOT IN ({DOMESTIC_SQL})))")

SCHEMA = """
CREATE TABLE foundations (
    ein TEXT PRIMARY KEY, name TEXT, city TEXT, state TEXT,
    assets INTEGER, revenue INTEGER, website TEXT, phone TEXT,
    contact_person TEXT, contact_email TEXT,
    application_status TEXT, latest_tax_year INTEGER,
    paid_2324 INTEGER DEFAULT 0, grant_count_2324 INTEGER DEFAULT 0,
    recipient_count INTEGER DEFAULT 0, median_grant INTEGER,
    -- International giving. foreign_dollars is the union of "non-domestic
    -- country code" and "filing used a foreign-address element": either is
    -- sufficient evidence the money left the country, and requiring both
    -- would silently drop grants whose filer supplied one but not the other.
    foreign_dollars INTEGER DEFAULT 0,
    foreign_grant_count INTEGER DEFAULT 0,
    -- Countries we could actually NAME. Lower than the number of distinct
    -- codes seen, because untrustworthy codes resolve to NULL by design.
    foreign_country_count INTEGER DEFAULT 0,
    -- Denormalised "Kenya, Uganda, India" for list rendering without a join.
    foreign_top_countries TEXT,
    -- Christian giving that went abroad. The headline number for a client
    -- funding indigenous overseas mission work.
    foreign_christian_dollars INTEGER DEFAULT 0,
    pct_foreign REAL,
    christian_dollars INTEGER DEFAULT 0, nonchristian_dollars INTEGER DEFAULT 0,
    unclassified_dollars INTEGER DEFAULT 0, daf_dollars INTEGER DEFAULT 0,
    nonclassifiable_dollars INTEGER DEFAULT 0,
    classifiable_dollars INTEGER DEFAULT 0,
    -- Christian as a share of CLASSIFIED dollars, not of total giving.
    -- Unclassified dollars are unknown, not non-Christian, so dividing by the
    -- total would understate every foundation and punish low-coverage ones.
    -- NULL (not 0) when nothing could be classified, so the UI can say
    -- "no classifiable giving" rather than the false claim "0% Christian".
    classified_dollars INTEGER DEFAULT 0,
    pct_christian REAL,
    -- The rigor dial. NOT "Christian share of authoritative-tier dollars":
    -- the authoritative methods (NTEE religion codes, church code, group
    -- exemption) only ever fire on RELIGIOUS organizations -- there is no
    -- `secular` among them -- so that denominator is religious-only and
    -- averages 81.4% Christian against 26.9% on the full basis, with 20,414
    -- of 25,760 foundations pinned at exactly 100%. Labelling that "%
    -- Christian" would overstate every foundation.
    -- Instead: Christian dollars carrying AUTHORITATIVE evidence, over the
    -- SAME full classified denominator. Turning rigor on can then only lower
    -- the number, which is the honest direction for a confidence dial.
    auth_christian_dollars INTEGER DEFAULT 0,
    pct_christian_auth REAL,
    -- Why this foundation's dollars could not be attributed. Display only:
    -- drives the message shown to the user, never a dollar figure or verdict.
    unattributable_reason TEXT,
    -- Application submission deadlines from 990-PF Part XV. There is no date
    -- on an individual grant, so a foundation's GIVING cannot be placed in a
    -- season; when it accepts APPLICATIONS can be, and that is what a
    -- fundraiser plans around.
    --   deadline_kind  : dated | rolling | none | unparseable | NULL (not stated)
    --   deadline_months: readable CSV, e.g. "3,9"
    --   deadline_mask  : bitmask, month N = bit N-1, for indexed range queries
    deadline_kind TEXT,
    deadline_months TEXT,
    deadline_mask INTEGER DEFAULT 0,
    deadline_text TEXT,
    coverage_pct REAL DEFAULT 0, coverage_band TEXT DEFAULT 'Low',
    is_testamentary INTEGER DEFAULT 0, is_micro INTEGER DEFAULT 0,
    active_2023 INTEGER DEFAULT 0, active_2024 INTEGER DEFAULT 0
);
CREATE TABLE tradition_stats (
    ein TEXT, tradition TEXT, tier TEXT,
    dollars INTEGER, recipients INTEGER,
    PRIMARY KEY (ein, tradition, tier)
);
CREATE TABLE recipient_states (
    ein TEXT, state TEXT, dollars INTEGER, PRIMARY KEY (ein, state));
CREATE TABLE recipients (
    entity_id TEXT PRIMARY KEY, ein TEXT, name TEXT,
    identity_status TEXT, tradition TEXT, method TEXT, confidence REAL,
    reason TEXT,
    is_daf INTEGER DEFAULT 0, mission_text TEXT, website TEXT,
    total_received INTEGER DEFAULT 0, funder_count INTEGER DEFAULT 0,
    -- Clean label shown instead of the raw filing string. Rendering a
    -- recipient as "GRANTS" or "Under the Health Insurance Portability and
    -- Account" reads as a broken product; the ledger row is untouched.
    display_name TEXT,
    unattributable_reason TEXT,
    -- Internal bookkeeping from src.recipient_partition, not a user-facing
    -- dimension: recipients are evidence about a foundation, not the product.
    disposition TEXT
);
CREATE TABLE frs (
    ein TEXT, entity_id TEXT, dollars INTEGER, grants INTEGER,
    last_year INTEGER, PRIMARY KEY (ein, entity_id)
);
CREATE TABLE grants (
    id INTEGER PRIMARY KEY, funder_ein TEXT, entity_id TEXT,
    recipient_name TEXT, recipient_city TEXT, recipient_state TEXT,
    amount INTEGER, tax_year INTEGER, purpose TEXT,
    -- Raw filing code (FIPS 10-4, not ISO -- see src/country_codes.py) and
    -- its verified display name. country_name is NULL when the code cannot be
    -- trusted, which the UI shows as Unspecified rather than guessing.
    recipient_country TEXT, country_name TEXT,
    -- Parser flag: the filing used a foreign-address element. Kept alongside
    -- the country code because the two disagree on ~thousands of rows and a
    -- researcher deserves to see either signal.
    is_foreign INTEGER DEFAULT 0
);
-- Per-foundation destination breakdown, for the detail panel and the country
-- filter. Materialised because deriving it per request means scanning 3M
-- grant rows.
CREATE TABLE foundation_countries (
    ein TEXT, country_code TEXT, country_name TEXT,
    dollars INTEGER, grants INTEGER, christian_dollars INTEGER DEFAULT 0,
    PRIMARY KEY (ein, country_code)
);
"""

INDEXES = """
CREATE INDEX idx_f_state ON foundations(state);
CREATE INDEX idx_f_paid ON foundations(paid_2324);
CREATE INDEX idx_f_app ON foundations(application_status);
CREATE INDEX idx_f_cov ON foundations(coverage_band);
CREATE INDEX idx_f_pct ON foundations(pct_christian);
CREATE INDEX idx_f_chr ON foundations(christian_dollars);
CREATE INDEX idx_f_active ON foundations(paid_2324, pct_christian);
CREATE INDEX idx_f_deadline ON foundations(deadline_mask);
CREATE INDEX idx_f_foreign ON foundations(foreign_dollars);
CREATE INDEX idx_f_fgn_chr ON foundations(foreign_christian_dollars);
CREATE INDEX idx_g_country ON grants(recipient_country);
CREATE INDEX idx_ts_lookup ON tradition_stats(tradition, tier, dollars);
CREATE INDEX idx_ts_ein ON tradition_stats(ein);
CREATE INDEX idx_rs_state ON recipient_states(state, dollars);
CREATE INDEX idx_r_name ON recipients(name);
CREATE INDEX idx_r_tradition ON recipients(tradition);
"""


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


@contextlib.contextmanager
def build_lock():
    """Refuse to start if another rebuild holds the lock.

    Two concurrent rebuilds previously overlapped: open_dbs() unlinks and
    recreates OUT_DB, so the second run destroyed the first run's file
    mid-write and left a hot journal behind. O_EXCL makes that unrepeatable.
    """
    lock = OUT_DB.with_suffix(".build.lock")
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise SystemExit(
            f"another rebuild is in progress (lock held: {lock}). "
            f"If no build is running, the previous one died -- verify no "
            f"python process is writing {OUT_DB}, then delete the lock."
        ) from None
    try:
        os.write(fd, f"pid={os.getpid()} started={time.ctime()}\n".encode())
        os.close(fd)
        yield
    finally:
        lock.unlink(missing_ok=True)


def open_dbs() -> tuple[sqlite3.Connection, str, str]:
    # Remove the sidecars alongside the db. SQLite binds -journal/-wal/-shm to
    # the *filename*, so a leftover journal from an interrupted run would be
    # replayed into the freshly created file and corrupt it.
    OUT_DB.unlink(missing_ok=True)
    for suffix in ("-journal", "-wal", "-shm"):
        OUT_DB.with_name(OUT_DB.name + suffix).unlink(missing_ok=True)
    # uri=True on the primary connection so the file: ATTACH URIs below are
    # parsed as URIs rather than literal filenames.
    out = sqlite3.connect(f"file:{OUT_DB.resolve()}", uri=True)
    out.executescript(SCHEMA)
    out.execute("ATTACH DATABASE ? AS p",
                (f"file:{PIPELINE_DB.resolve()}?mode=ro",))
    out.execute("ATTACH DATABASE ? AS bmf",
                (f"file:{BMF_DB.resolve()}?mode=ro",))
    run_id = out.execute(
        "SELECT run_id FROM p.identity_runs ORDER BY created_at_utc DESC LIMIT 1"
    ).fetchone()[0]
    release_id = out.execute(
        "SELECT release_id FROM p.classification_releases "
        "WHERE identity_run_id=? AND status='published' "
        "ORDER BY created_at_utc DESC LIMIT 1", (run_id,)).fetchone()[0]
    log(f"identity run {run_id} | classification release {release_id}")
    return out, run_id, release_id


def build_recipients(out: sqlite3.Connection, run_id: str, release_id: str) -> None:
    log("recipients: entities + resolutions + canonical mission text…")
    out.execute("""
        INSERT INTO recipients (entity_id, ein, name, identity_status,
                                tradition, method, confidence, reason)
        SELECT e.entity_id, e.bmf_ein, e.canonical_name, e.identity_status,
               r.classification, ev.evidence_method, r.confidence, ev.reason
        FROM p.recipient_entities e
        LEFT JOIN p.classification_resolutions r
          ON r.release_id=? AND r.entity_id=e.entity_id
        LEFT JOIN p.classification_evidence ev ON ev.evidence_id=r.evidence_id
        WHERE e.run_id=?
    """, (release_id, run_id))
    # Canonical mission doc per EIN: latest tax year, amended preferred.
    out.execute("""
        CREATE TEMP TABLE best_doc AS
        SELECT ein, mission_text, website FROM (
          SELECT ein, mission_text, website,
                 ROW_NUMBER() OVER (PARTITION BY ein ORDER BY tax_year DESC,
                     is_amended DESC, object_id DESC) AS rn
          FROM p.r990_documents WHERE parse_status='parsed')
        WHERE rn=1
    """)
    out.execute("CREATE INDEX temp.idx_bd ON best_doc(ein)")
    out.execute("""
        UPDATE recipients SET
          mission_text=(SELECT mission_text FROM best_doc d WHERE d.ein=recipients.ein),
          website=(SELECT website FROM best_doc d WHERE d.ein=recipients.ein)
        WHERE ein IS NOT NULL
    """)
    # A natural person or a filing placeholder cannot hold a religious
    # tradition. 17,114 `individual` and 170 `unattributable` entities picked
    # one up from a recipient-name rule firing on a personal name. The
    # evidence ledger is immutable and append-only, so the stray rows stay on
    # the record; the read model simply declines to present them as verdicts.
    # Materialize + index locally rather than probing the attached table: its
    # primary key is (identity_run_id, entity_id), so a correlated lookup by
    # entity_id alone cannot use it and degrades to a scan per row. That turned
    # a 4-minute rebuild into a 20-minute one before this was fixed.
    out.execute("""
        CREATE TEMP TABLE disp AS
        SELECT entity_id, disposition FROM p.recipient_dispositions
    """)
    out.execute("CREATE INDEX temp.idx_disp ON disp(entity_id)")
    out.execute("""
        UPDATE recipients SET disposition=(
            SELECT d.disposition FROM disp d
            WHERE d.entity_id=recipients.entity_id)
        WHERE identity_status IN ('unresolved','collision')
    """)
    # Display layer for dollars the filing never attributed. Sets a clean label
    # and the per-recipient reason; changes no dollar figure, coverage value or
    # verdict.
    rows = out.execute(
        f"SELECT entity_id, name FROM recipients "  # noqa: S608
        f"WHERE identity_status IN {NONCLASSIFIABLE_STATUSES}").fetchall()
    labelled = [(unattributable_reason(name),
                 REASON_LABELS[unattributable_reason(name)], entity_id)
                for entity_id, name in rows]
    out.executemany(
        "UPDATE recipients SET unattributable_reason=?, display_name=? "
        "WHERE entity_id=?", labelled)
    log(f"recipients: labelled {len(labelled):,} unattributable recipients")
    stray = out.execute(f"""
        UPDATE recipients SET tradition=NULL, method=NULL, confidence=NULL,
               reason=NULL
        WHERE identity_status IN {NONCLASSIFIABLE_STATUSES}
          AND tradition IS NOT NULL
    """).rowcount
    log(f"recipients: cleared {stray:,} stray traditions on "
        f"individual/unattributable entities")
    for entity_id, name in out.execute(
            "SELECT entity_id, name FROM recipients").fetchall():
        if DAF_PATTERN.search((name or "").lower()):
            out.execute("UPDATE recipients SET is_daf=1 WHERE entity_id=?",
                        (entity_id,))
    out.commit()
    n, daf = out.execute(
        "SELECT COUNT(*), SUM(is_daf) FROM recipients").fetchone()
    log(f"recipients: {n:,} ({daf:,} DAF sponsors flagged)")


def build_country_map(out: sqlite3.Connection) -> None:
    """Materialise the verified code->name map as a table.

    A Python UDF would be correct but is measurably slow across 3M grant rows
    (the standing project lesson about scalar functions in joins), so the map
    becomes a joinable table instead. Codes deliberately left unnamed --
    ambiguous ones and the OC catch-all -- are simply absent, so the LEFT JOIN
    yields NULL and the product says Unspecified.
    """
    out.execute("CREATE TEMP TABLE country_map (code TEXT PRIMARY KEY, "
                "name TEXT)")
    named = dict(country_codes.FIPS)
    named.update(country_codes.OVERRIDES)
    for code in country_codes.AMBIGUOUS | country_codes.UNSPECIFIED:
        named.pop(code, None)
    out.executemany("INSERT INTO country_map VALUES (?,?)", named.items())
    log(f"country map: {len(named):,} codes resolvable to a name "
        f"({len(country_codes.AMBIGUOUS)} held ambiguous, "
        f"{len(country_codes.UNSPECIFIED)} filer catch-all)")


def build_grants(out: sqlite3.Connection, run_id: str) -> None:
    log("grants: paid 2023-2024 receipt rows…")
    build_country_map(out)
    out.execute("""
        INSERT INTO grants (funder_ein, entity_id, recipient_name,
                            recipient_city, recipient_state, amount,
                            tax_year, purpose, recipient_country,
                            country_name, is_foreign)
        SELECT t.ein, em.entity_id, g.display_name, g.city, g.state,
               g.signed_amount, g.tax_year, t.purpose,
               UPPER(TRIM(COALESCE(t.recipient_country,''))),
               cm.name,
               CASE WHEN COALESCE(t.is_foreign,0)=1 THEN 1 ELSE 0 END
        FROM p.grant_norm g
        JOIN p.grant_transactions t ON t.grant_id=g.grant_id
        JOIN p.recipient_entity_mentions em
          ON em.run_id=g.run_id AND em.mention_id=g.mention_id
        LEFT JOIN country_map cm
          ON cm.code = UPPER(TRIM(COALESCE(t.recipient_country,'')))
        WHERE g.run_id=? AND g.tax_year IN (2023, 2024)
    """, (run_id,))
    out.commit()
    log(f"grants: {out.execute('SELECT COUNT(*) FROM grants').fetchone()[0]:,} rows")


def build_rollups(out: sqlite3.Connection) -> None:
    log("rollups: foundation x recipient, recipient totals, states…")
    # Index the receipt table before any GROUP BY / correlated pass over it.
    out.execute("CREATE INDEX idx_g_funder ON grants(funder_ein, tax_year)")
    out.execute("CREATE INDEX idx_g_entity ON grants(entity_id)")
    # The grants explorer pages by amount. Without this every page sorts all
    # 3M rows: the endpoint measured 11.5s and dropped to 53ms once it
    # existed, so losing it in a rebuild would look like the page breaking.
    out.execute("CREATE INDEX idx_g_amount ON grants(amount DESC)")
    out.execute("""
        INSERT INTO frs
        SELECT funder_ein, entity_id, SUM(amount), COUNT(*), MAX(tax_year)
        FROM grants GROUP BY 1, 2
    """)
    # The correlated recipient-totals UPDATE needs this or it goes quadratic
    # over 1.3M recipients x 2.5M frs rows (the standing project lesson).
    out.execute("CREATE INDEX idx_frs_entity ON frs(entity_id)")
    out.execute("""
        UPDATE recipients SET
          total_received=COALESCE((SELECT SUM(dollars) FROM frs
                                   WHERE frs.entity_id=recipients.entity_id), 0),
          funder_count=COALESCE((SELECT COUNT(*) FROM frs
                                 WHERE frs.entity_id=recipients.entity_id), 0)
    """)
    out.execute("""
        INSERT INTO recipient_states
        SELECT funder_ein, recipient_state, SUM(amount) FROM grants
        -- US states, DC and territories only. The field carries whatever the
        -- filing typed, which includes foreign regions (ARUSHA, ONTARIO,
        -- KIGALI); listing those under "US recipients by state" is simply
        -- false, and international giving is reported on its own tab.
        WHERE recipient_state IN (
            'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL',
            'IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT',
            'NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI',
            'SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC','PR',
            'VI','GU','AS','MP')
        GROUP BY 1, 2
    """)
    out.commit()


def build_foundation_countries(out: sqlite3.Connection) -> None:
    """Per-foundation destination rollup, plus the denormalised top-country
    string the list view renders.

    Rows whose code could not be trusted are grouped under a single
    `(unspecified)` bucket rather than dropped, so the dollars still reconcile
    to foundations.foreign_dollars.
    """
    log("foundations: international destination rollup…")
    out.execute(f"""
        INSERT INTO foundation_countries
            (ein, country_code, country_name, dollars, grants,
             christian_dollars)
        SELECT g.funder_ein,
               CASE WHEN g.country_name IS NULL THEN '(unspecified)'
                    ELSE g.recipient_country END,
               COALESCE(g.country_name, 'Unspecified'),
               SUM(g.amount), COUNT(*),
               SUM(CASE WHEN r.identity_status NOT IN {NONCLASSIFIABLE_STATUSES}
                        AND r.is_daf=0 AND r.tradition IN
                     ('evangelical_protestant','catholic','orthodox_christian',
                      'christian_unspecified') THEN g.amount ELSE 0 END)
        FROM grants g JOIN recipients r ON r.entity_id=g.entity_id
        WHERE {FOREIGN_SQL}
        GROUP BY 1, 2, 3
    """)
    out.execute("CREATE INDEX idx_fc_ein ON foundation_countries(ein, dollars)")
    out.execute("CREATE INDEX idx_fc_code "
                "ON foundation_countries(country_code, dollars)")
    out.commit()
    # Named countries only in the count and the label: "3 countries" must not
    # be inflated by the unspecified bucket.
    out.execute("""
        CREATE TEMP TABLE fc_named AS
        SELECT ein, COUNT(*) AS n FROM foundation_countries
        WHERE country_code != '(unspecified)' GROUP BY 1
    """)
    out.execute("CREATE INDEX temp.idx_fcn ON fc_named(ein)")
    out.execute("""
        UPDATE foundations SET foreign_country_count =
            COALESCE((SELECT n FROM fc_named WHERE fc_named.ein=foundations.ein), 0)
    """)
    labels = {}
    for ein, name in out.execute("""
            SELECT ein, country_name FROM foundation_countries
            WHERE country_code != '(unspecified)'
            ORDER BY ein, dollars DESC"""):
        bucket = labels.setdefault(ein, [])
        if len(bucket) < 4:
            bucket.append(name)
    out.executemany("UPDATE foundations SET foreign_top_countries=? WHERE ein=?",
                    [(", ".join(names), ein) for ein, names in labels.items()])
    out.commit()
    rows, eins = out.execute(
        "SELECT COUNT(*), COUNT(DISTINCT ein) FROM foundation_countries"
    ).fetchone()
    log(f"foundations: {rows:,} destination rows across {eins:,} foundations")


def build_foundations(out: sqlite3.Connection) -> None:
    log("foundations: base facts from canonical filings…")
    out.execute("""
        INSERT INTO foundations (ein, name, city, state, assets, revenue,
            website, phone, contact_person, contact_email,
            application_status, latest_tax_year)
        SELECT f.ein, f.organization_name, f.city, f.state, f.assets_eoy,
               f.total_revenue, f.website, f.phone, f.contact_person,
               f.contact_email,
               CASE WHEN f.invite_only=1 THEN 'Invite Only'
                    WHEN COALESCE(f.application_format,'') != ''
                      OR COALESCE(f.deadlines,'') != ''
                      OR COALESCE(f.restrictions,'') != ''
                      THEN 'Accepting Applications'
                    WHEN COALESCE(f.contact_person,'') != ''
                      OR COALESCE(f.contact_email,'') != ''
                      THEN 'Contact First'
                    ELSE 'Unknown' END,
               f.tax_year
        FROM p.foundation_filings f
        JOIN (SELECT ein, MAX(tax_year) AS ty FROM p.canonical_filings
              GROUP BY ein) latest
          ON latest.ein=f.ein AND latest.ty=f.tax_year
        JOIN p.canonical_filings c ON c.ein=f.ein AND c.tax_year=f.tax_year
          AND c.object_id=f.object_id
    """)
    out.commit()
    log("foundations: giving aggregates + tradition stats + coverage…")
    out.execute("""
        CREATE TEMP TABLE agg AS
        SELECT g.funder_ein AS ein,
          SUM(g.amount) AS paid, COUNT(*) AS n,
          COUNT(DISTINCT g.entity_id) AS recips,
          MAX(CASE WHEN g.tax_year=2023 THEN 1 ELSE 0 END) AS a23,
          MAX(CASE WHEN g.tax_year=2024 THEN 1 ELSE 0 END) AS a24,
          -- The three classified buckets count classifiable recipients only.
          -- 17,114 `individual` and 170 `unattributable` recipients carry a
          -- stray tradition from a name rule -- $24.8M of it Christian, which
          -- is a person named by the filing, not a Christian organization.
          -- Counting those would both inflate the headline Christian figure
          -- and double-count against nonclassifiable_dollars, leaving the
          -- buckets overlapping instead of partitioning paid_2324.
          SUM(CASE WHEN r.identity_status NOT IN {statuses}
                   AND r.is_daf=1 THEN g.amount ELSE 0 END) AS daf,
          SUM(CASE WHEN r.identity_status NOT IN {statuses}
                   AND r.is_daf=0 AND r.tradition IN
                ('evangelical_protestant','catholic','orthodox_christian',
                 'christian_unspecified') THEN g.amount ELSE 0 END) AS chr,
          SUM(CASE WHEN r.identity_status NOT IN {statuses}
                   AND r.is_daf=0 AND r.tradition IN
                ('jewish','muslim','mormon_lds','christian_science',
                 'other_religion','secular','nonchristian_unspecified')
              THEN g.amount ELSE 0 END) AS nonchr,
          -- dollars the filing never attributed to an organization
          SUM(CASE WHEN r.identity_status IN {statuses}
              THEN g.amount ELSE 0 END) AS nonclass,
          -- classified dollars, counted only over classifiable recipients so
          -- the ratio below can never exceed 100%
          SUM(CASE WHEN r.identity_status NOT IN {statuses}
                   AND (r.tradition IS NOT NULL OR r.is_daf=1)
              THEN g.amount ELSE 0 END) AS class_num,
          -- International giving. The predicate is the UNION of the two
          -- independent signals (see foundations.foreign_dollars).
          SUM(CASE WHEN {foreign} THEN g.amount ELSE 0 END) AS fgn,
          SUM(CASE WHEN {foreign} THEN 1 ELSE 0 END) AS fgn_n,
          SUM(CASE WHEN {foreign} AND r.identity_status NOT IN {statuses}
                   AND r.is_daf=0 AND r.tradition IN
                ('evangelical_protestant','catholic','orthodox_christian',
                 'christian_unspecified') THEN g.amount ELSE 0 END) AS fgn_chr
        FROM grants g JOIN recipients r ON r.entity_id=g.entity_id
        GROUP BY 1
    """.format(statuses=str(NONCLASSIFIABLE_STATUSES), foreign=FOREIGN_SQL))
    out.execute("CREATE INDEX temp.idx_agg ON agg(ein)")
    out.execute("""
        UPDATE foundations SET
          paid_2324=COALESCE((SELECT paid FROM agg WHERE agg.ein=foundations.ein),0),
          grant_count_2324=COALESCE((SELECT n FROM agg WHERE agg.ein=foundations.ein),0),
          recipient_count=COALESCE((SELECT recips FROM agg WHERE agg.ein=foundations.ein),0),
          active_2023=COALESCE((SELECT a23 FROM agg WHERE agg.ein=foundations.ein),0),
          active_2024=COALESCE((SELECT a24 FROM agg WHERE agg.ein=foundations.ein),0),
          daf_dollars=COALESCE((SELECT daf FROM agg WHERE agg.ein=foundations.ein),0),
          christian_dollars=COALESCE((SELECT chr FROM agg WHERE agg.ein=foundations.ein),0),
          nonchristian_dollars=COALESCE((SELECT nonchr FROM agg WHERE agg.ein=foundations.ein),0),
          nonclassifiable_dollars=COALESCE(
              (SELECT nonclass FROM agg WHERE agg.ein=foundations.ein),0),
          foreign_dollars=COALESCE(
              (SELECT fgn FROM agg WHERE agg.ein=foundations.ein),0),
          foreign_grant_count=COALESCE(
              (SELECT fgn_n FROM agg WHERE agg.ein=foundations.ein),0),
          foreign_christian_dollars=COALESCE(
              (SELECT fgn_chr FROM agg WHERE agg.ein=foundations.ein),0)
    """)
    # NULL rather than 0 when a foundation gave nothing, matching the
    # pct_christian convention: "no giving" is not "0% international".
    out.execute("""
        UPDATE foundations SET pct_foreign = CASE
            WHEN paid_2324 > 0
              THEN ROUND(100.0 * foreign_dollars / paid_2324, 1)
            ELSE NULL END
    """)
    build_foundation_countries(out)
    # unclassified_dollars now means "classifiable, but we have not classified
    # it" -- the honest remaining work. Dollars the filing anonymized are held
    # separately in nonclassifiable_dollars, not counted as our failure.
    out.execute("""
        UPDATE foundations SET
          classifiable_dollars = paid_2324 - nonclassifiable_dollars,
          unclassified_dollars = paid_2324 - nonclassifiable_dollars
                                 - COALESCE((SELECT class_num FROM agg
                                             WHERE agg.ein=foundations.ein),0),
          coverage_pct = CASE
            WHEN paid_2324 - nonclassifiable_dollars > 0 THEN
              ROUND(100.0 * COALESCE((SELECT class_num FROM agg
                                      WHERE agg.ein=foundations.ein),0)
                    / (paid_2324 - nonclassifiable_dollars), 1)
            ELSE 0 END
    """)
    # A foundation whose entire giving was anonymized by its own filing has no
    # classifiable dollars at all. Calling that 'Low' coverage would read as our
    # failure, so it gets its own band rather than being ranked against
    # foundations we genuinely under-classified.
    out.execute("""
        UPDATE foundations SET
          classified_dollars = christian_dollars + nonchristian_dollars,
          pct_christian = CASE
            WHEN christian_dollars + nonchristian_dollars > 0
              THEN ROUND(100.0 * christian_dollars
                         / (christian_dollars + nonchristian_dollars), 1)
            ELSE NULL END
    """)
    # Authoritative-tier ratio, materialised and indexed rather than probed per
    # row: a correlated subquery over frs here is the shape that previously
    # turned a 4-minute rebuild into a 20-minute one.
    out.execute(f"""
        CREATE TEMP TABLE auth_mix AS
        SELECT f.ein,
          SUM(CASE WHEN r.tradition IN {CHRISTIAN}
              THEN f.dollars ELSE 0 END) AS chr,
          SUM(CASE WHEN r.tradition IS NOT NULL
                   AND r.tradition NOT IN {CHRISTIAN}
              THEN f.dollars ELSE 0 END) AS nonchr
        FROM frs f JOIN recipients r ON r.entity_id=f.entity_id
        WHERE r.is_daf=0 AND r.method IN {AUTHORITATIVE}
        GROUP BY f.ein
    """)
    out.execute("CREATE INDEX temp.idx_auth ON auth_mix(ein)")
    out.execute("""
        UPDATE foundations SET
          auth_christian_dollars = COALESCE(
              (SELECT chr FROM auth_mix a WHERE a.ein=foundations.ein), 0)
    """)
    out.execute("""
        UPDATE foundations SET
          pct_christian_auth = CASE
            WHEN classified_dollars > 0
              THEN ROUND(100.0 * auth_christian_dollars
                         / classified_dollars, 1)
            ELSE NULL END
    """)
    # Application deadlines: materialised locally then indexed, rather than a
    # correlated probe into the attached database.
    out.execute("""
        CREATE TEMP TABLE dl AS
        SELECT ein, kind, months_json, raw_text FROM p.foundation_deadlines
    """)
    out.execute("CREATE INDEX temp.idx_dl ON dl(ein)")
    deadlines = []
    for ein, kind, months_json, raw in out.execute(
            "SELECT ein, kind, months_json, raw_text FROM dl"):
        months = json.loads(months_json or "[]")
        mask = 0
        for month in months:
            mask |= 1 << (month - 1)
        deadlines.append((kind, ",".join(str(m) for m in months) or None,
                          mask, (raw or "")[:200], ein))
    out.executemany(
        "UPDATE foundations SET deadline_kind=?, deadline_months=?, "
        "deadline_mask=?, deadline_text=? WHERE ein=?", deadlines)
    log(f"foundations: {len(deadlines):,} application deadlines applied")

    # Foundation-level reason = the reason accounting for the most
    # nonclassifiable dollars at that foundation, so the message shown matches
    # where the money actually went.
    out.execute("""
        CREATE TEMP TABLE reason_rank AS
        SELECT g.funder_ein AS ein, r.unattributable_reason AS reason,
               SUM(g.amount) AS d
        FROM grants g JOIN recipients r ON r.entity_id=g.entity_id
        WHERE r.unattributable_reason IS NOT NULL
        GROUP BY 1, 2
    """)
    out.execute("CREATE INDEX temp.idx_rr ON reason_rank(ein, d)")
    out.execute("""
        UPDATE foundations SET unattributable_reason=(
            SELECT reason FROM reason_rank rr WHERE rr.ein=foundations.ein
            ORDER BY rr.d DESC LIMIT 1)
        WHERE nonclassifiable_dollars > 0
    """)
    out.execute("""
        UPDATE foundations SET
          coverage_band = CASE
            WHEN paid_2324 > 0 AND classifiable_dollars <= 0
              THEN 'Not Classifiable'
            WHEN coverage_pct >= 80 THEN 'High'
            WHEN coverage_pct >= 50 THEN 'Moderate'
            ELSE 'Low' END,
          is_micro = CASE WHEN paid_2324 < 50000 THEN 1 ELSE 0 END
    """)
    for ein, name in out.execute(
            "SELECT ein, name FROM foundations").fetchall():
        if TESTAMENTARY.search(f" {(name or '').lower()} "):
            out.execute(
                "UPDATE foundations SET is_testamentary=1 WHERE ein=?", (ein,))
    out.commit()


def build_tradition_stats(out: sqlite3.Connection) -> None:
    log("tradition stats (authoritative and any tiers)…")
    for tier, method_filter in (
        ("authoritative",
         "r.method IN ('human','ntee','church_code_name','group_exemption')"),
        ("mission", "r.method='llm'"),
        ("any", "r.tradition IS NOT NULL"),
    ):
        out.execute(f"""
            INSERT OR REPLACE INTO tradition_stats
            SELECT f.ein, r.tradition, '{tier}', SUM(f.dollars), COUNT(*)
            FROM frs f JOIN recipients r ON r.entity_id=f.entity_id
            WHERE {method_filter} AND r.is_daf=0
            GROUP BY 1, 2
        """)
    out.execute("""
        INSERT OR REPLACE INTO tradition_stats
        SELECT f.ein, 'unclassified', 'any', SUM(f.dollars), COUNT(*)
        FROM frs f JOIN recipients r ON r.entity_id=f.entity_id
        WHERE r.tradition IS NULL GROUP BY 1
    """)
    out.commit()


def median_grants(out: sqlite3.Connection) -> None:
    log("median grant per foundation (streaming)…")
    current, amounts, updates = None, [], []
    for ein, amount in out.execute(
            "SELECT funder_ein, amount FROM grants ORDER BY funder_ein"):
        if ein != current:
            if current is not None and amounts:
                amounts.sort()
                updates.append((amounts[len(amounts) // 2], current))
            current, amounts = ein, []
        amounts.append(amount)
    if current is not None and amounts:
        amounts.sort()
        updates.append((amounts[len(amounts) // 2], current))
    out.executemany("UPDATE foundations SET median_grant=? WHERE ein=?", updates)
    out.commit()


def main() -> None:
    # Parse before doing anything: open_dbs() deletes OUT_DB, so an unrecognized
    # flag (notably --help) must not fall through into a destructive rebuild.
    argparse.ArgumentParser(
        prog="python3 -m src.build_explorer_v5",
        description=("Rebuild data/explorer_v5.db from scratch out of the v5 "
                     "identity + evidence ledger. Takes no options; the "
                     "existing read model is deleted and recreated."),
    ).parse_args()
    started = time.monotonic()
    with build_lock():
        out, run_id, release_id = open_dbs()
        build_recipients(out, run_id, release_id)
        build_grants(out, run_id)
        build_rollups(out)
        build_foundations(out)
        build_tradition_stats(out)
        median_grants(out)
        log("indexing…")
        out.executescript(INDEXES)
        out.execute("PRAGMA main.optimize")
        out.commit()
    stats = {
        "foundations": out.execute("SELECT COUNT(*) FROM foundations").fetchone()[0],
        "with 23-24 giving": out.execute(
            "SELECT COUNT(*) FROM foundations WHERE paid_2324>0").fetchone()[0],
        "recipients": out.execute("SELECT COUNT(*) FROM recipients").fetchone()[0],
        "grants": out.execute("SELECT COUNT(*) FROM grants").fetchone()[0],
        "paid $": out.execute("SELECT SUM(paid_2324) FROM foundations").fetchone()[0],
        "christian $": out.execute(
            "SELECT SUM(christian_dollars) FROM foundations").fetchone()[0],
        "unclassified $ (classifiable)": out.execute(
            "SELECT SUM(unclassified_dollars) FROM foundations").fetchone()[0],
        "nonclassifiable $ (anonymized by filing)": out.execute(
            "SELECT SUM(nonclassifiable_dollars) FROM foundations").fetchone()[0],
        "with mission text": out.execute(
            "SELECT COUNT(*) FROM recipients WHERE mission_text!=''").fetchone()[0],
        "international $": out.execute(
            "SELECT SUM(foreign_dollars) FROM foundations").fetchone()[0],
        "international christian $": out.execute(
            "SELECT SUM(foreign_christian_dollars) FROM foundations").fetchone()[0],
        "foundations giving abroad": out.execute(
            "SELECT COUNT(*) FROM foundations WHERE foreign_dollars>0").fetchone()[0],
        "countries named": out.execute(
            "SELECT COUNT(DISTINCT country_code) FROM foundation_countries "
            "WHERE country_code!='(unspecified)'").fetchone()[0],
        "international $ we could not place": out.execute(
            "SELECT COALESCE(SUM(dollars),0) FROM foundation_countries "
            "WHERE country_code='(unspecified)'").fetchone()[0],
    }
    for key, value in stats.items():
        log(f"  {key}: {value:,}")
    log(f"done in {time.monotonic() - started:,.0f}s -> {OUT_DB}")


if __name__ == "__main__":
    main()
