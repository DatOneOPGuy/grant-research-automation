"""Extract Part XIV line 2 (OnlyContriToPreselectedInd) per EIN from 990-PF XMLs."""

import csv
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from lxml import etree

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
INPUT_CSV = Path(__file__).resolve().parent.parent / "inviteonly.csv"
OUTPUT_CSV = Path(__file__).resolve().parent.parent / "inviteonlyvalues.csv"
EIN_COL_INDEX = 8  # 9th column in inviteonly.csv


def parse_one(path_str: str):
    """Return (ein, tax_year, is_invite_only) or None."""
    try:
        tree = etree.parse(path_str)
        root = tree.getroot()
    except Exception:
        return None

    tag = root.tag
    ns = {"irs": tag.split("}")[0][1:]} if "}" in tag else {}

    def ftext(xp):
        el = root.find(xp, ns) if ns else root.find(xp)
        return el.text.strip() if el is not None and el.text else ""

    ein = ftext(".//irs:Filer/irs:EIN") or ftext(".//irs:EIN")
    if not ein:
        return None

    tax_year = ftext(".//irs:TaxYr") or ftext(".//irs:TaxYear")
    try:
        tax_year = int(tax_year)
    except ValueError:
        tax_year = 0

    val = ftext(".//irs:OnlyContriToPreselectedInd")
    is_invite_only = val.strip().upper() == "X"
    return ein.strip(), tax_year, is_invite_only


def build_ein_map():
    files = [str(p) for p in RAW_DIR.glob("*.xml")]
    print(f"Scanning {len(files)} XML files...", file=sys.stderr)
    latest: dict[str, tuple[int, bool]] = {}

    with ProcessPoolExecutor() as ex:
        futures = [ex.submit(parse_one, f) for f in files]
        for i, fut in enumerate(as_completed(futures), 1):
            if i % 2000 == 0:
                print(f"  parsed {i}/{len(files)}", file=sys.stderr)
            res = fut.result()
            if not res:
                continue
            ein, year, flag = res
            prev = latest.get(ein)
            if prev is None or year > prev[0]:
                latest[ein] = (year, flag)
    return latest


def main():
    ein_map = build_ein_map()
    print(f"Got Part XIV data for {len(ein_map)} EINs", file=sys.stderr)

    hits = misses = 0
    with INPUT_CSV.open(newline="", encoding="utf-8") as fin, \
            OUTPUT_CSV.open("w", newline="", encoding="utf-8") as fout:
        reader = csv.reader(fin)
        writer = csv.writer(fout)
        for row in reader:
            if len(row) <= EIN_COL_INDEX:
                writer.writerow(row + [""])
                misses += 1
                continue
            ein = row[EIN_COL_INDEX].strip().zfill(9)
            entry = ein_map.get(ein) or ein_map.get(row[EIN_COL_INDEX].strip())
            if entry is None:
                writer.writerow(row + [""])
                misses += 1
            else:
                writer.writerow(
                    row + ["Invite Only" if entry[1] else "Not Invite Only"]
                )
                hits += 1

    print(
        f"Wrote {OUTPUT_CSV.name}: {hits} matched, {misses} no 990 found",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
