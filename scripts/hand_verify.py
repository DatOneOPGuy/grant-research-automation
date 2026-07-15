"""Side-by-side hand-verification of v2 parsed data against raw IRS XML.

Deliberately re-extracts from the raw XML with xml.etree (an independent
implementation from the lxml-based provenance parser) so agreement means two
different readers of the form concur, not that one parser agrees with itself.
Read-only everywhere.
"""

from __future__ import annotations

import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path

DB = Path("data/grants_v2.db")
PAID_TAGS = {"GrantOrContributionPdDurYrGrp", "GrantOrContriPaidDuringYear"}
FUTURE_TAGS = {"GrantOrContriApprvForFutGrp"}


def strip(tag: str) -> str:
    return tag.split("}")[-1]


def find_text(element, name: str) -> str:
    for item in element.iter():
        if strip(item.tag) == name and item.text and item.text.strip():
            return item.text.strip()
    return ""


def xml_grant_summary(path: str) -> dict:
    root = ET.parse(path).getroot()
    paid_total = future_total = paid_rows = future_rows = 0
    samples = []
    for element in root.iter():
        tag = strip(element.tag)
        if tag not in PAID_TAGS and tag not in FUTURE_TAGS:
            continue
        raw = find_text(element, "Amt") or find_text(element, "Amount")
        try:
            amount = int(float(raw)) if raw else 0
        except ValueError:
            amount = 0
        if tag in PAID_TAGS:
            if amount > 0:
                paid_total += amount
                paid_rows += 1
            if len(samples) < 5 and amount > 0:
                name = (find_text(element, "BusinessNameLine1Txt")
                        or find_text(element, "RecipientPersonNm"))
                line2 = find_text(element, "BusinessNameLine2Txt")
                samples.append({
                    "name": f"{name} {line2}".strip(),
                    "city": find_text(element, "CityNm"),
                    "state": find_text(element, "StateAbbreviationCd"),
                    "country": find_text(element, "CountryCd"),
                    "status": find_text(element, "RecipientFoundationStatusTxt"),
                    "amount": amount,
                })
        elif amount > 0:
            future_total += amount
            future_rows += 1
    return {
        "paid_rows": paid_rows, "paid_total": paid_total,
        "future_rows": future_rows, "future_total": future_total,
        "samples": samples,
        "amended": find_text(root, "AmendedReturnInd"),
        "invite_only": find_text(root, "OnlyContriToPreselectedInd"),
        "app_format": find_text(root, "FormAndInfoAndMaterialsTxt")[:60],
        "deadlines": find_text(root, "SubmissionDeadlinesTxt")[:60],
    }


def v2_summary(conn: sqlite3.Connection, ein: str, tax_year: int) -> dict | None:
    filing = conn.execute(
        """SELECT c.object_id, f.source_path, f.is_amended
           FROM canonical_filings c JOIN filings f USING(object_id)
           WHERE c.ein=? AND c.tax_year=?""",
        (ein, tax_year),
    ).fetchone()
    if filing is None:
        return None
    object_id, source_path, is_amended = filing
    paid_rows, paid_total = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(signed_amount),0) FROM grant_transactions "
        "WHERE object_id=? AND schedule_type='paid' AND amount_status='positive'",
        (object_id,),
    ).fetchone()
    future_rows, future_total = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(signed_amount),0) FROM grant_transactions "
        "WHERE object_id=? AND schedule_type='future_approved' AND amount_status='positive'",
        (object_id,),
    ).fetchone()
    samples = conn.execute(
        "SELECT recipient_name, recipient_city, recipient_state, recipient_country, "
        "recipient_foundation_status, signed_amount FROM grant_transactions "
        "WHERE object_id=? AND schedule_type='paid' AND amount_status='positive' "
        "ORDER BY row_ordinal LIMIT 5",
        (object_id,),
    ).fetchall()
    application = conn.execute(
        "SELECT invite_only, application_format, deadlines FROM foundation_filings "
        "WHERE object_id=?", (object_id,),
    ).fetchone()
    versions = conn.execute(
        "SELECT COUNT(*) FROM filings WHERE ein=? AND tax_year=? AND parse_status='parsed'",
        (ein, tax_year),
    ).fetchone()[0]
    return {
        "object_id": object_id, "source_path": source_path,
        "is_amended": is_amended, "versions": versions,
        "paid_rows": paid_rows, "paid_total": paid_total,
        "future_rows": future_rows, "future_total": future_total,
        "samples": samples, "application": application,
    }


def check(label: str, form_value, v2_value) -> str:
    ok = form_value == v2_value
    return f"| {label} | {form_value} | {v2_value} | {'✅' if ok else '❌ MISMATCH'} |"


def verify(conn: sqlite3.Connection, ein: str, tax_year: int, note: str) -> None:
    data = v2_summary(conn, ein, tax_year)
    print(f"\n### EIN {ein} TY{tax_year} — {note}")
    if data is None:
        print("NO CANONICAL FILING FOUND — investigate")
        return
    xml = xml_grant_summary(data["source_path"])
    print(f"Canonical object {data['object_id']} "
          f"({data['versions']} parsed version(s), amended={data['is_amended']})")
    print("| Field | Form (independent read) | v2 DB | Match |")
    print("|---|---|---|---|")
    print(check("Paid rows", xml["paid_rows"], data["paid_rows"]))
    print(check("Paid $", xml["paid_total"], data["paid_total"]))
    print(check("Future rows", xml["future_rows"], data["future_rows"]))
    print(check("Future $", xml["future_total"], data["future_total"]))
    print(check("Amended flag", int(xml["amended"].upper() == "X"), data["is_amended"]))
    if data["application"]:
        invite, app_format, deadlines = data["application"]
        print(check("Invite-only flag", int(xml["invite_only"].upper() == "X"), invite))
        print(check("App format (60ch)", xml["app_format"], (app_format or "")[:60]))
        print(check("Deadlines (60ch)", xml["deadlines"], (deadlines or "")[:60]))
    for i, (form, db_row) in enumerate(zip(xml["samples"], data["samples"], strict=False), 1):
        name, city, state, country, status, amount = db_row
        print(check(f"Grant {i} name", form["name"], name))
        print(check(f"Grant {i} city/st", f"{form['city']}/{form['state']}",
                    f"{city}/{state}"))
        if form["country"]:
            print(check(f"Grant {i} country", form["country"], country))
        print(check(f"Grant {i} status", form["status"], status))
        print(check(f"Grant {i} amount", form["amount"], amount))


def main() -> None:
    conn = sqlite3.connect(f"file:{DB.resolve()}?mode=ro", uri=True, timeout=60)
    picks = [
        ("010541580", 2023, "amended return (canonical selection)"),
        ("010557030", 2023, "amended return #2"),
        ("562618866", 2023, "large future commitments + foreign recipients"),
        ("330930701", 2023, "strong Christian verdict (Cadigan)"),
        ("010211504", 2023, "Accepting Applications"),
        ("010636772", 2024, "church recipient (First Baptist Flushing)"),
    ]
    for ein, tax_year, note in picks:
        verify(conn, ein, tax_year, note)
    for sql, note in [
        ("SELECT ein, tax_year FROM canonical_grants WHERE is_foreign=1 "
         "AND amount_status='positive' AND tax_year>=2023 AND ein != '562618866' "
         "GROUP BY ein, tax_year ORDER BY COUNT(*) DESC LIMIT 1",
         "foreign recipients #2"),
        ("SELECT ein, tax_year FROM canonical_grants WHERE amount_status='negative' "
         "AND tax_year>=2023 GROUP BY ein, tax_year ORDER BY COUNT(*) DESC LIMIT 1",
         "negative adjustments"),
        ("SELECT ein, tax_year FROM canonical_grants WHERE schedule_type='paid' "
         "AND amount_status='positive' AND tax_year>=2023 GROUP BY ein, tax_year "
         "HAVING COUNT(*) BETWEEN 20 AND 60 ORDER BY ein LIMIT 1",
         "mid-size general"),
        ("SELECT ein, tax_year FROM canonical_grants WHERE schedule_type='paid' "
         "AND amount_status='positive' AND tax_year>=2023 GROUP BY ein, tax_year "
         "HAVING COUNT(*) BETWEEN 1 AND 5 ORDER BY ein DESC LIMIT 1",
         "small foundation"),
    ]:
        row = conn.execute(sql).fetchone()
        if row:
            verify(conn, row[0], row[1], note)


if __name__ == "__main__":
    main()
