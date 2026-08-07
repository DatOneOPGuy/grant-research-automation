"""Static v5 dataset for the Netlify review build.

Netlify serves static files, but the Explorer normally filters and sorts
server-side. So this dumps a sampled dataset that the frontend's static
adapter filters client-side, using the same semantics as the API.

Honesty rules carried over from the live product:
  - headline aggregates (stats, analytics, data quality) are computed over the
    FULL database, so every number the reviewer sees is real. Only the
    browsable rows are sampled.
  - pct_christian stays NULL where nothing could be classified; it is never
    coerced to 0, because that would assert the giving is non-Christian.
  - display_name is used for unattributable recipients, so nothing renders as
    "GRANTS" or a HIPAA placeholder string.

Output: frontend/public/demo-v5/
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "explorer_v5.db"
OUT = Path(__file__).resolve().parent.parent / "frontend" / "public" / "demo-v5"

FOUNDATION_SAMPLE = 2500      # browsable foundations
GRANTS_PER_FOUNDATION = 60
RECIPIENTS_PER_FOUNDATION = 40
GRANTS_SAMPLE = 4000          # grants explorer page
RECIPIENTS_SAMPLE = 4000      # recipients page

FOUNDATION_COLUMNS = """
    ein, name, city, state, paid_2324, grant_count_2324, recipient_count,
    median_grant, christian_dollars, nonchristian_dollars,
    unclassified_dollars, daf_dollars, nonclassifiable_dollars,
    classifiable_dollars, classified_dollars, pct_christian,
    auth_christian_dollars, pct_christian_auth, unattributable_reason,
    coverage_pct, coverage_band, application_status, website, assets,
    revenue, is_testamentary, is_micro
"""


def shard_for(entity_id: str) -> str:
    """Deterministic 2-hex bucket. Must match shardFor() in apiV5.ts."""
    total = 0
    for char in entity_id:
        total = (total * 31 + ord(char)) % 4096
    return f"{total % 128:02x}"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def dump(name: str, data) -> None:
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, default=str, separators=(",", ":")))
    size = path.stat().st_size / 1024
    if size > 40:
        log(f"  {name}: {size:,.0f} KB")


def main() -> None:
    started = time.monotonic()
    conn = connect()

    # --- browsable sample: the foundations worth reviewing -----------------
    # Ranked by Christian dollars so the sample is the product's actual value,
    # then padded with large secular funders so the reviewer can see the
    # honest low-percentage cases too, not a curated success reel.
    rows = conn.execute(f"""
        SELECT {FOUNDATION_COLUMNS} FROM foundations
        WHERE paid_2324 > 0 AND christian_dollars > 0
        ORDER BY christian_dollars DESC LIMIT ?""",
        (FOUNDATION_SAMPLE - 500,)).fetchall()
    eins = {r["ein"] for r in rows}
    extra = conn.execute(f"""
        SELECT {FOUNDATION_COLUMNS} FROM foundations
        WHERE paid_2324 > 0 AND christian_dollars = 0
        ORDER BY paid_2324 DESC LIMIT 500""").fetchall()
    foundations = [dict(r) for r in rows] + [
        dict(r) for r in extra if r["ein"] not in eins]
    dump("foundations.json", foundations)
    log(f"foundations sampled: {len(foundations):,}")

    # --- per-foundation detail --------------------------------------------
    sample_eins = [f["ein"] for f in foundations]
    for index, ein in enumerate(sample_eins, 1):
        base = conn.execute(
            f"SELECT {FOUNDATION_COLUMNS} FROM foundations WHERE ein=?",
            (ein,)).fetchone()
        traditions = conn.execute(
            "SELECT tradition, tier, dollars, recipients FROM tradition_stats "
            "WHERE ein=? ORDER BY dollars DESC", (ein,)).fetchall()
        recipients = conn.execute("""
            SELECT r.entity_id, COALESCE(r.display_name, r.name) AS name,
                   r.ein AS recipient_ein, r.identity_status, r.tradition,
                   r.method, r.confidence, r.reason, r.is_daf,
                   (r.mission_text IS NOT NULL AND r.mission_text != '')
                       AS has_mission,
                   frs.dollars, frs.grants, frs.last_year
            FROM frs JOIN recipients r ON r.entity_id=frs.entity_id
            WHERE frs.ein=? ORDER BY frs.dollars DESC LIMIT ?""",
            (ein, RECIPIENTS_PER_FOUNDATION)).fetchall()
        states = conn.execute(
            "SELECT state, dollars FROM recipient_states WHERE ein=? "
            "ORDER BY dollars DESC", (ein,)).fetchall()
        grants = conn.execute("""
            SELECT COALESCE(r.display_name, g.recipient_name)
                       AS recipient_name,
                   g.recipient_city, g.recipient_state, g.amount, g.tax_year,
                   g.purpose, g.entity_id, r.tradition, r.identity_status
            FROM grants g LEFT JOIN recipients r ON r.entity_id=g.entity_id
            WHERE g.funder_ein=? ORDER BY g.amount DESC LIMIT ?""",
            (ein, GRANTS_PER_FOUNDATION)).fetchall()
        dump(f"foundation/{ein}.json", {
            "foundation": dict(base),
            "traditions": [dict(r) for r in traditions],
            "recipients": [dict(r) for r in recipients],
            "states": [dict(r) for r in states],
            "grants": [dict(r) for r in grants],
        })
        if index % 500 == 0:
            log(f"  detail {index:,}/{len(sample_eins):,}")

    # --- aggregates: computed over the FULL database -----------------------
    stats = conn.execute("""
        SELECT COUNT(*) AS foundations, SUM(paid_2324 > 0) AS active,
               SUM(paid_2324) AS paid, SUM(christian_dollars) AS christian,
               SUM(nonchristian_dollars) AS nonchristian,
               SUM(unclassified_dollars) AS unclassified,
               SUM(daf_dollars) AS daf FROM foundations""").fetchone()
    recip = conn.execute(
        "SELECT COUNT(*), SUM(mission_text IS NOT NULL AND mission_text!='') "
        "FROM recipients").fetchone()
    dump("stats.json", {**dict(stats), "recipients": recip[0],
                        "with_mission": recip[1],
                        "window": "paid grants, tax years 2023-2024",
                        "identity_run": "identity-20260715T164705Z"})

    dump("analytics/state-breakdown.json", [dict(r) for r in conn.execute("""
        SELECT state, COUNT(*) AS foundations, SUM(paid_2324) AS paid,
               SUM(christian_dollars) AS christian FROM foundations
        WHERE state IS NOT NULL AND state != '' AND paid_2324 > 0
        GROUP BY state ORDER BY paid DESC""")])
    dump("analytics/top-funders.json", [dict(r) for r in conn.execute("""
        SELECT ein, name AS foundation_name, city, state, paid_2324,
               christian_dollars, coverage_pct, coverage_band,
               application_status, recipient_count FROM foundations
        WHERE christian_dollars > 0
        ORDER BY christian_dollars DESC LIMIT 100""")])
    dump("analytics/yearly-trends.json", [dict(r) for r in conn.execute("""
        SELECT g.tax_year, COUNT(*) AS grants, SUM(g.amount) AS paid,
               COUNT(DISTINCT g.funder_ein) AS foundations,
               SUM(CASE WHEN r.tradition IN ('evangelical_protestant',
                   'catholic','orthodox_christian','christian_unspecified')
                   AND r.is_daf=0 THEN g.amount ELSE 0 END) AS christian
        FROM grants g LEFT JOIN recipients r ON r.entity_id=g.entity_id
        GROUP BY g.tax_year ORDER BY g.tax_year""")])

    totals = conn.execute("""
        SELECT COUNT(*) AS foundations, SUM(paid_2324 > 0) AS with_giving,
               SUM(paid_2324) AS paid,
               SUM(classifiable_dollars) AS classifiable,
               SUM(nonclassifiable_dollars) AS nonclassifiable,
               SUM(christian_dollars) AS christian,
               SUM(nonchristian_dollars) AS nonchristian,
               SUM(unclassified_dollars) AS unclassified,
               SUM(daf_dollars) AS daf,
               SUM(website IS NOT NULL AND website != '') AS with_website,
               SUM(phone IS NOT NULL AND phone != '') AS with_phone,
               SUM(contact_email IS NOT NULL AND contact_email != '')
                   AS with_email,
               SUM(contact_person IS NOT NULL AND contact_person != '')
                   AS with_contact_person FROM foundations""").fetchone()
    dump("analytics/data-quality.json", {
        "totals": dict(totals),
        "coverage_bands": [dict(r) for r in conn.execute(
            "SELECT coverage_band, COUNT(*) AS foundations, "
            "SUM(paid_2324) AS paid FROM foundations WHERE paid_2324>0 "
            "GROUP BY 1 ORDER BY foundations DESC")],
        "unattributable_reasons": [dict(r) for r in conn.execute(
            "SELECT COALESCE(unattributable_reason,'(none)') AS reason, "
            "COUNT(*) AS foundations, SUM(nonclassifiable_dollars) AS dollars "
            "FROM foundations WHERE nonclassifiable_dollars>0 "
            "GROUP BY 1 ORDER BY dollars DESC")],
        "identity": [dict(r) for r in conn.execute(
            "SELECT identity_status, COUNT(*) AS recipients, "
            "SUM(total_received) AS dollars FROM recipients "
            "GROUP BY 1 ORDER BY dollars DESC")],
        "methods": [dict(r) for r in conn.execute(
            "SELECT method, COUNT(*) AS recipients FROM recipients "
            "WHERE tradition IS NOT NULL GROUP BY 1 "
            "ORDER BY recipients DESC")],
        "window": "paid grants, tax years 2023-2024",
    })
    dump("recipients-stats.json", {
        "by_tradition": [dict(r) for r in conn.execute(
            "SELECT COALESCE(tradition,'unclassified') AS tradition, "
            "COUNT(*) AS recipients, SUM(total_received) AS dollars "
            "FROM recipients WHERE total_received>0 "
            "GROUP BY 1 ORDER BY dollars DESC")],
        "by_method": [dict(r) for r in conn.execute(
            "SELECT COALESCE(method,'(none)') AS method, "
            "COUNT(*) AS recipients FROM recipients "
            "WHERE tradition IS NOT NULL GROUP BY 1 ORDER BY recipients DESC")],
        "by_identity": [dict(r) for r in conn.execute(
            "SELECT identity_status, COUNT(*) AS recipients, "
            "SUM(total_received) AS dollars FROM recipients "
            "GROUP BY 1 ORDER BY dollars DESC")],
    })

    # --- browsable grants / recipients samples ----------------------------
    dump("grants.json", [dict(r) for r in conn.execute("""
        SELECT COALESCE(r.display_name, g.recipient_name) AS grantee_name,
               g.recipient_city AS city, g.recipient_state AS state,
               g.amount, g.tax_year, g.purpose, g.entity_id,
               f.ein, f.name AS foundation_name, r.tradition,
               r.identity_status
        FROM grants g JOIN foundations f ON f.ein=g.funder_ein
        LEFT JOIN recipients r ON r.entity_id=g.entity_id
        ORDER BY g.amount DESC LIMIT ?""", (GRANTS_SAMPLE,))])
    dump("recipients.json", [dict(r) for r in conn.execute("""
        SELECT r.entity_id, COALESCE(r.display_name, r.name) AS name, r.ein,
               r.identity_status, r.tradition, r.method, r.confidence,
               r.reason, r.is_daf, r.total_received, r.funder_count,
               (r.mission_text IS NOT NULL AND r.mission_text != '')
                   AS has_mission
        FROM recipients r WHERE r.total_received > 0
        ORDER BY r.total_received DESC LIMIT ?""", (RECIPIENTS_SAMPLE,))])

    # --- recipient detail: mission text is the product's core evidence ------
    # Every recipient referenced anywhere in the sample gets a record, sharded
    # so the browser fetches ~60 KB instead of the whole 3 MB corpus. Without
    # this the mission drill-down has nothing to read, which is exactly the
    # evidence a reviewer needs to judge whether a classification is credible.
    referenced: set[str] = set()
    for path in (OUT / "foundation").glob("*.json"):
        for row in json.loads(path.read_text())["recipients"]:
            referenced.add(row["entity_id"])
    sample_recipient_ids = {
        r["entity_id"] for r in json.loads(
            (OUT / "recipients.json").read_text())}
    referenced |= sample_recipient_ids

    conn.execute("CREATE TEMP TABLE want(id TEXT PRIMARY KEY)")
    conn.executemany("INSERT OR IGNORE INTO want VALUES (?)",
                     [(i,) for i in referenced])
    shards: dict[str, dict] = {}
    for row in conn.execute("""
            SELECT r.entity_id, COALESCE(r.display_name, r.name) AS name,
                   r.ein, r.identity_status, r.tradition, r.method,
                   r.confidence, r.reason, r.is_daf, r.mission_text,
                   r.website, r.total_received, r.funder_count
            FROM recipients r JOIN want w ON w.id = r.entity_id"""):
        shards.setdefault(shard_for(row["entity_id"]), {})[
            row["entity_id"]] = {"recipient": dict(row), "funders": []}
    # Funders only for the browsable recipient sample -- carrying them for all
    # 46k referenced recipients would add tens of MB for rows nobody opens.
    for entity_id in sample_recipient_ids:
        funders = conn.execute("""
            SELECT frs.ein, f.name, frs.dollars, frs.grants, frs.last_year
            FROM frs JOIN foundations f ON f.ein=frs.ein
            WHERE frs.entity_id=? ORDER BY frs.dollars DESC LIMIT 15""",
            (entity_id,)).fetchall()
        bucket = shards.get(shard_for(entity_id), {})
        if entity_id in bucket:
            bucket[entity_id]["funders"] = [dict(r) for r in funders]
    for name, payload in shards.items():
        dump(f"recipient/{name}.json", payload)
    with_mission = sum(
        1 for b in shards.values() for v in b.values()
        if v["recipient"].get("mission_text"))
    log(f"recipient records: {len(referenced):,} across {len(shards)} shards "
        f"({with_mission:,} carry mission text)")

    # Totals the static adapter reports, so counts stay truthful even though
    # only a sample is browsable.
    dump("meta.json", {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sample": True,
        "foundations_in_sample": len(foundations),
        "foundations_total": stats["foundations"],
        "foundations_with_giving": stats["active"],
        "grants_in_sample": GRANTS_SAMPLE,
        "grants_total": conn.execute(
            "SELECT COUNT(*) FROM grants").fetchone()[0],
        "recipients_in_sample": RECIPIENTS_SAMPLE,
        "recipients_total": recip[0],
        "window": "paid grants, tax years 2023-2024",
    })
    conn.close()
    total = sum(p.stat().st_size for p in OUT.rglob("*.json"))
    log(f"total payload: {total / 1024 / 1024:,.1f} MB "
        f"across {len(list(OUT.rglob('*.json'))):,} files")
    log(f"done in {time.monotonic() - started:,.0f}s -> {OUT}")


if __name__ == "__main__":
    main()
