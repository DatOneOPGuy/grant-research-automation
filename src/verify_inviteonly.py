"""Independently verify inviteonlyvalues.csv against raw XMLs for a sample.

Uses an independent parser (regex on raw text instead of lxml/xpath) so a
match shows the extractor and verifier agree on the underlying file.
"""

import csv
import random
import re
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
OUTPUT_CSV = ROOT / "inviteonlyvalues.csv"
EIN_COL = 8
SAMPLE_SIZE = 50

EIN_RE = re.compile(r"<(?:[a-zA-Z0-9]+:)?EIN>\s*(\d{9})\s*</")
TAXYR_RE = re.compile(r"<(?:[a-zA-Z0-9]+:)?TaxYr>\s*(\d{4})\s*</")
PRESEL_RE = re.compile(
    r"<(?:[a-zA-Z0-9]+:)?OnlyContriToPreselectedInd>([^<]*)</"
)


def scan(path_str: str):
    try:
        text = Path(path_str).read_text(errors="ignore")
    except Exception:
        return None
    m = EIN_RE.search(text)
    if not m:
        return None
    ein = m.group(1)
    yr_m = TAXYR_RE.search(text)
    year = int(yr_m.group(1)) if yr_m else 0
    pres_m = PRESEL_RE.search(text)
    flag = bool(pres_m and pres_m.group(1).strip().upper() == "X")
    return ein, year, flag, path_str


def build_map():
    files = [str(p) for p in RAW_DIR.glob("*.xml")]
    print(f"Indexing {len(files)} XMLs (regex pass)...", file=sys.stderr)
    latest: dict[str, tuple[int, bool, str]] = {}
    with ProcessPoolExecutor() as ex:
        for i, fut in enumerate(
            as_completed([ex.submit(scan, f) for f in files]), 1
        ):
            if i % 4000 == 0:
                print(f"  {i}/{len(files)}", file=sys.stderr)
            res = fut.result()
            if not res:
                continue
            ein, year, flag, path = res
            prev = latest.get(ein)
            if prev is None or year > prev[0]:
                latest[ein] = (year, flag, path)
    return latest


def main():
    rows = []
    with OUTPUT_CSV.open(newline="", encoding="utf-8") as f:
        for r in csv.reader(f):
            if len(r) > EIN_COL and r[-1] in ("Invite Only", "Not Invite Only"):
                rows.append(r)

    random.seed(42)
    sample = random.sample(rows, SAMPLE_SIZE)
    sample_eins = {r[EIN_COL].strip() for r in sample}

    ein_map = build_map()

    matched = mismatched = missing = 0
    print(f"\nVerifying {SAMPLE_SIZE} random EINs...\n")
    print(f"{'EIN':<11} {'Year':<5} {'CSV says':<17} {'XML says':<17} OK")
    print("-" * 70)

    for row in sample:
        ein = row[EIN_COL].strip()
        csv_val = row[-1]
        entry = ein_map.get(ein) or ein_map.get(ein.zfill(9))
        if entry is None:
            print(f"{ein:<11} {'-':<5} {csv_val:<17} {'<no xml>':<17} ?")
            missing += 1
            continue
        year, flag, path = entry
        xml_val = "Invite Only" if flag else "Not Invite Only"
        ok = xml_val == csv_val
        print(
            f"{ein:<11} {year:<5} {csv_val:<17} {xml_val:<17} "
            f"{'OK' if ok else 'MISMATCH'}"
        )
        if ok:
            matched += 1
        else:
            mismatched += 1
            print(f"   -> {Path(path).name}")

    _ = sample_eins  # silence unused
    print("-" * 70)
    print(f"Matched: {matched}  Mismatched: {mismatched}  Missing: {missing}")


if __name__ == "__main__":
    main()
