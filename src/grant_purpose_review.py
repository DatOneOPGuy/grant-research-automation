"""Phase 1: the grant-purpose contradiction review queue. Read-only.

Surfaces recipients where the funder's own stated purpose for a grant either
disagrees with the recipient's classification, or supplies a signal we do not
otherwise have. Writes no evidence and mutates nothing -- a human decides each
case.

Ranking encodes the anti-over-claim principle that also gates Phase 2. A
recipient whose religious-purpose grants are a majority of its dollars, or come
from two or more independent funders, is a strong candidate for a real
classification error (Baylor, Pepperdine, Andrews are name-invisible Christian
institutions no name rule can reach). A single religious-purpose grant from a
single funder is weak: it is more likely a restricted gift to a sub-unit -- the
Duke pattern, where a Divinity School grant says nothing about the university.

Reads data/explorer_v5.db and data/grants_v2.db. Writes only the report.
"""

from __future__ import annotations

import argparse
import collections
import sqlite3
import sys
import time
from pathlib import Path

from src.grant_purpose_signal import christian_signal, quote

EXPLORER = Path("data/explorer_v5.db")
REPORT = Path("logs/grant_purpose_contradictions.md")
CHRISTIAN = ("evangelical_protestant", "catholic", "orthodox_christian",
             "christian_unspecified")
# Sub-unit words: a religious grant to one of these inside a larger secular
# organisation is a restricted gift, not a statement about the whole body.
SUBUNIT = ("divinity", "seminary", "chapel", "campus ministry", "school of "
           "theology", "chaplain", "religious studies", "center for faith")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def collect(conn: sqlite3.Connection) -> dict:
    """Aggregate religious-purpose grants per recipient."""
    per = collections.defaultdict(lambda: {
        "religious_dollars": 0, "religious_grants": 0, "funders": set(),
        "quotes": [], "name": None, "tradition": None, "method": None,
        "identity": None, "total_dollars": 0})
    scanned = 0
    for (entity_id, amount, purpose, funder_ein, funder_name, tradition,
         method, name, identity, total) in conn.execute("""
            SELECT g.entity_id, g.amount, g.purpose, g.funder_ein, f.name,
                   r.tradition, r.method, r.name, r.identity_status,
                   r.total_received
            FROM grants g
            JOIN foundations f ON f.ein = g.funder_ein
            LEFT JOIN recipients r ON r.entity_id = g.entity_id"""):
        scanned += 1
        if scanned % 500_000 == 0:
            log(f"  scanned {scanned:,} grants")
        signal = christian_signal(purpose)
        if not signal:
            continue
        row = per[entity_id]
        row["religious_dollars"] += amount or 0
        row["religious_grants"] += 1
        row["funders"].add(funder_ein)
        row["name"] = name
        row["tradition"] = tradition
        row["method"] = method
        row["identity"] = identity
        row["total_dollars"] = total or 0
        if len(row["quotes"]) < 4:
            row["quotes"].append((funder_name, quote(purpose), amount or 0))
    log(f"  scanned {scanned:,} grants; recipients with a signal: {len(per):,}")
    return per


def strength(row: dict) -> tuple[str, str]:
    """(rank, why) -- the anti-over-claim test, used for ranking here and as a
    hard gate in Phase 2."""
    multi_funder = len(row["funders"]) >= 2
    majority = (row["total_dollars"] > 0
                and row["religious_dollars"] * 2 > row["total_dollars"])
    if multi_funder and majority:
        return "A", f"{len(row['funders'])} funders and majority of dollars"
    if multi_funder:
        return "B", f"{len(row['funders'])} independent funders"
    if majority:
        return "C", "majority of this recipient's dollars"
    return "D", "single funder, minority of dollars"


def is_subunit(row: dict) -> bool:
    blob = " ".join(q[1] for q in row["quotes"]).lower()
    return any(word in blob for word in SUBUNIT)


def main() -> None:
    ap = argparse.ArgumentParser(prog="python3 -m src.grant_purpose_review",
                                 description=__doc__)
    ap.add_argument("--limit-per-section", type=int, default=40)
    args = ap.parse_args()

    started = time.monotonic()
    conn = sqlite3.connect(f"file:{EXPLORER.resolve()}?mode=ro", uri=True)
    per = collect(conn)
    conn.close()

    contradictions, newsignal, corroborate = [], [], []
    for entity_id, row in per.items():
        rank, why = strength(row)
        item = {**row, "entity_id": entity_id, "rank": rank, "why": why,
                "subunit": is_subunit(row), "funders": len(row["funders"])}
        if row["tradition"] in CHRISTIAN:
            corroborate.append(item)
        elif row["tradition"] is None:
            newsignal.append(item)
        else:
            contradictions.append(item)

    def order(items):
        return sorted(items, key=lambda i: (i["rank"], -i["religious_dollars"]))

    contradictions, newsignal = order(contradictions), order(newsignal)
    corroborate = order(corroborate)
    REPORT.parent.mkdir(exist_ok=True)
    with REPORT.open("w") as out:
        write_report(out, contradictions, newsignal, corroborate,
                     args.limit_per_section)
    log(f"wrote {REPORT}")
    for label, items in (("contradictions", contradictions),
                         ("new signal", newsignal),
                         ("corroborating", corroborate)):
        strong = [i for i in items if i["rank"] in ("A", "B", "C")]
        log(f"  {label:<14}{len(items):>6} recipients "
            f"(${sum(i['religious_dollars'] for i in items)/1e6:,.1f}M) | "
            f"strong A-C: {len(strong):,}")
    log(f"done in {time.monotonic() - started:,.0f}s")


def write_report(out, contradictions, newsignal, corroborate, limit) -> None:
    def money(value): return f"${value:,.0f}"

    def section(title, items, note):
        out.write(f"\n## {title}\n\n{note}\n\n")
        out.write("| rank | recipient | current | funders | religious $ | "
                  "share of recipient $ | funder's own words |\n")
        out.write("|---|---|---|---:|---:|---:|---|\n")
        for i in items[:limit]:
            share = (f"{100 * i['religious_dollars'] / i['total_dollars']:.0f}%"
                     if i["total_dollars"] else "n/a")
            first = i["quotes"][0] if i["quotes"] else ("", "", 0)
            flag = " **[sub-unit?]**" if i["subunit"] else ""
            out.write(
                f"| {i['rank']} | {str(i['name'])[:38]}{flag} | "
                f"{i['tradition'] or 'unclassified'} ({i['method'] or '-'}) | "
                f"{i['funders']} | {money(i['religious_dollars'])} | {share} | "
                f"*{first[1][:110]}* |\n")

    out.write("""# Grant-purpose contradiction review queue

_Phase 1. Read-only: nothing here has been reclassified and no evidence has
been written. Every row is a human decision._

Matching is word-boundary anchored and excludes boilerplate, government
ministries, organisational-mission phrasing and other-faith vocabulary.

**Rank** encodes the anti-over-claim test:

- **A** — two or more independent funders *and* a majority of the recipient's
  dollars. Strongest evidence of a real classification error.
- **B** — two or more independent funders. Independent corroboration.
- **C** — majority of the recipient's dollars, one funder.
- **D** — single funder, minority of dollars. Weak: most likely a restricted
  gift to a sub-unit, not a statement about the organisation.

**[sub-unit?]** marks quotes naming a divinity school, seminary, chapel or
campus ministry — the Duke pattern, where a religious grant targets one part of
an otherwise secular institution. These are *genuinely mixed*, not errors.
""")
    section("1. Contradictions — recipient classified non-Christian",
            contradictions,
            "The funder describes the grant in explicitly Christian terms but "
            "the recipient is classified secular or another tradition. Rank A "
            "and B are the likely real errors — name-invisible Christian "
            "institutions that no name rule can reach.")
    section("2. New signal — recipient currently unclassified", newsignal,
            "No verdict today. The funder's purpose is the only Christian "
            "signal we hold for these.")
    section("3. Corroboration — recipient already classified Christian",
            corroborate,
            "No action needed. Listed because the quoted purpose is an "
            "auditable, name-independent justification a grant writer can show "
            "a client.")


if __name__ == "__main__":
    main()
