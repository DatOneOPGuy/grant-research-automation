"""Independently verify backfilled profile fields against raw XMLs.

Regex over raw text (no lxml/xpath) on a random sample of filings,
compared to the foundations table — same dual-parser pattern as
verify_inviteonly.py.
"""

import random
import re
import sqlite3
import sys
from pathlib import Path

from src.config import DB_PATH, RAW_DIR
from src.profile_fields import format_phone, normalize_website

SAMPLE_SIZE = 60

RE = {
    'ein': re.compile(r"<(?:\w+:)?Filer>.*?<(?:\w+:)?EIN>(\d{9})</",
                      re.S),
    'taxyr': re.compile(r"<(?:\w+:)?TaxYr>(\d{4})</"),
    'website': re.compile(r"<(?:\w+:)?WebsiteAddressTxt>([^<]*)</"),
    'filer_block': re.compile(r"<(?:\w+:)?Filer>.*?</(?:\w+:)?Filer>",
                              re.S),
    'officer_block': re.compile(
        r"<(?:\w+:)?BusinessOfficerGrp>.*?</(?:\w+:)?BusinessOfficerGrp>",
        re.S),
    'preparer_block': re.compile(
        r"<(?:\w+:)?Preparer(?:Person|Firm)Grp>.*?"
        r"</(?:\w+:)?Preparer(?:Person|Firm)Grp>", re.S),
    'any_phone': re.compile(r"<(?:\w+:)?PhoneNum>([^<]*)</"),
    'revenue': re.compile(r"<(?:\w+:)?TotalRevAndExpnssAmt>([^<]*)</"),
    'invite': re.compile(
        r"<(?:\w+:)?OnlyContriToPreselectedInd>([^<]*)</"),
    'contact': re.compile(
        r"<(?:\w+:)?ApplicationSubmissionInfoGrp>.*?"
        r"<(?:\w+:)?RecipientPersonNm>([^<]*)</", re.S),
}


def regex_phone(text: str) -> str:
    """Filer phone, else officer phone, else any non-preparer phone."""
    for block_key in ('filer_block', 'officer_block'):
        block = RE[block_key].search(text)
        if block:
            m = RE['any_phone'].search(block.group(0))
            if m:
                return m.group(1).strip()
    stripped = RE['preparer_block'].sub('', text)
    m = RE['any_phone'].search(stripped)
    return m.group(1).strip() if m else ''


def regex_fields(text: str) -> dict | None:
    ein = RE['ein'].search(text)
    yr = RE['taxyr'].search(text)
    if not ein or not yr:
        return None

    def grab(key):
        m = RE[key].search(text)
        return m.group(1).strip() if m else ''

    return {
        'ein': ein.group(1),
        'tax_year': int(yr.group(1)),
        'website': normalize_website(grab('website')),
        'phone': format_phone(regex_phone(text)),
        'revenue': int(float(grab('revenue'))) if grab('revenue') else None,
        'invite_only': 1 if grab('invite').upper() == 'X' else 0,
        'contact_person': grab('contact'),
    }


def main():
    files = list(Path(RAW_DIR).glob('*.xml'))
    random.seed(42)
    sample = random.sample(files, SAMPLE_SIZE)

    conn = sqlite3.connect(DB_PATH)
    checked = matched = mismatched = missing = 0
    fields = ['website', 'phone', 'revenue', 'invite_only',
              'contact_person']

    for path in sample:
        xml = regex_fields(path.read_text(errors='ignore'))
        if not xml:
            continue
        row = conn.execute(
            f"SELECT {', '.join(fields)} FROM foundations "
            f"WHERE ein = ? AND tax_year = ?",
            (xml['ein'], xml['tax_year']),
        ).fetchone()
        if row is None:
            missing += 1
            continue
        checked += 1
        db = dict(zip(fields, row))
        diffs = [
            f"{f}: xml={xml[f]!r} db={db[f]!r}"
            for f in fields if xml[f] != db[f]
        ]
        if diffs:
            mismatched += 1
            print(f"MISMATCH {xml['ein']}/{xml['tax_year']} "
                  f"({path.name}): {'; '.join(diffs)}")
        else:
            matched += 1

    print(f"\nChecked {checked} filings: {matched} matched, "
          f"{mismatched} mismatched, {missing} not in DB")
    conn.close()
    sys.exit(1 if mismatched else 0)


if __name__ == '__main__':
    main()
