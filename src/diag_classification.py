"""Fix 1 diagnostic: measure how much grant money is unclassified.

For every foundation (over grants in the DB), split total grant dollars
(Part XV) into confirmed-Christian, confirmed-non-Christian, and
unclassified, then report the unclassified-rate distribution. Reusable:
re-run after each classifier change to watch the gap close.
"""

import json
import sqlite3
from collections import defaultdict

from src.config import DB_PATH
from src.faith_config import CONFIDENCE_MIN, FAITH_TAGS
from src.matcher import normalize

FAITH_TAG_SET = set(FAITH_TAGS)


def load_tags(conn):
    """name_norm -> (has_christian, has_any_tag)."""
    lookup = {}
    for norm, tags_json in conn.execute(
        "SELECT name_norm, tags FROM recipients"
    ):
        tags = [t for t in json.loads(tags_json or '[]')
                if t.get('confidence', 0) >= CONFIDENCE_MIN]
        if not tags:
            lookup[norm] = (False, False)
            continue
        names = {t['name'] for t in tags}
        # a recipient tagged only 'Secular'/'Non-Christian' counts as
        # confirmed non-Christian
        is_christian = bool(names & FAITH_TAG_SET)
        lookup[norm] = (is_christian, True)
    return lookup


def pctile(sorted_vals, p):
    if not sorted_vals:
        return 0.0
    i = min(len(sorted_vals) - 1, int(p * len(sorted_vals)))
    return sorted_vals[i]


def run():
    conn = sqlite3.connect(DB_PATH)
    tags = load_tags(conn)

    christian = defaultdict(int)
    nonchristian = defaultdict(int)
    unclassified = defaultdict(int)
    total = defaultdict(int)
    for ein, name, amount in conn.execute(
        "SELECT ein, grantee_name, amount FROM grants WHERE grantee_name != ''"
    ):
        amount = amount or 0
        ein = ein.zfill(9)
        total[ein] += amount
        is_chr, has_tag = tags.get(normalize(name), (False, False))
        if is_chr:
            christian[ein] += amount
        elif has_tag:
            nonchristian[ein] += amount
        else:
            unclassified[ein] += amount

    rates = []
    funder_rates = []  # foundations with any confirmed Christian giving
    over50 = 0
    for ein, tot in total.items():
        if tot <= 0:
            continue
        rate = unclassified[ein] / tot
        rates.append(rate)
        if rate > 0.5:
            over50 += 1
        if christian[ein] > 0:
            funder_rates.append(rate)

    rates.sort()
    funder_rates.sort()
    n = len(rates)

    print("=" * 62)
    print("CLASSIFICATION DIAGNOSTIC")
    print("=" * 62)
    print(f"Foundations with grants: {n:,}")
    print(f"Mean unclassified rate:   {sum(rates) / n * 100:.1f}%")
    print(f"Median unclassified rate: {pctile(rates, 0.5) * 100:.1f}%")
    print(f"Foundations >50% unclassified: {over50:,} "
          f"({over50 / n * 100:.1f}%)")
    print(f"\nChristian-funder list ({len(funder_rates):,} foundations "
          f"with confirmed Christian giving):")
    print(f"  Mean unclassified rate:   "
          f"{sum(funder_rates) / max(1, len(funder_rates)) * 100:.1f}%")
    print(f"  Median unclassified rate: "
          f"{pctile(funder_rates, 0.5) * 100:.1f}%")
    print(f"  Median classification coverage: "
          f"{(1 - pctile(funder_rates, 0.5)) * 100:.1f}%")
    print("\nUnclassified-rate histogram (all foundations):")
    buckets = [0] * 10
    for r in rates:
        buckets[min(9, int(r * 10))] += 1
    for i, c in enumerate(buckets):
        bar = '#' * int(c / max(buckets) * 40)
        print(f"  {i*10:3d}-{i*10+10:3d}%  {c:7,}  {bar}")

    tot_all = sum(total.values())
    print(f"\nDollar-weighted (all grant $): "
          f"christian={sum(christian.values())/tot_all*100:.1f}%  "
          f"nonchristian={sum(nonchristian.values())/tot_all*100:.1f}%  "
          f"unclassified={sum(unclassified.values())/tot_all*100:.1f}%")
    conn.close()


if __name__ == '__main__':
    run()
