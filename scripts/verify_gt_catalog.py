"""Run every GT-error-catalog row through the fixed rule classifier.

Each row was cataloged BECAUSE the old rules got it wrong, so 'before' is
0/48 by construction. This reports how many now resolve correctly, which
still miss, and spot-checks that the fixes created no new false positives.
Read-only: never touches the database.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.recipient_taxonomy import infer_legacy_tradition

# (name, acceptable_labels) — acceptable includes None where the honest rule
# outcome is "no signal, leave uncategorized" instead of a wrong catholic.
CATALOG = [
    ("ST GEORGE MALANKARA ORTHODOX CHURCH", {"orthodox_christian"}),
    ("ST PETER'S EVANGELICAL LUTHERAN CHURCH AND SCHOOL", {"evangelical_protestant"}),
    ("ST JOHN MISSIONARY BAPTIST CHURCH WPB", {"evangelical_protestant"}),
    ("ST BARNABAS PRESBYTERIAN", {"evangelical_protestant"}),
    ("SAINT PAUL'S EVANGELICAL LUTHERAN CHURCH", {"evangelical_protestant"}),
    ("ST STEPHEN'S LUTHERAN CHURCH - BEAVER DAM (NON CASH AAPL 67 SH)", {"evangelical_protestant"}),
    ("ST STEPHENS EPSICOPAL CHURCH", {"evangelical_protestant"}),  # (sic) typo in data
    ("ST PETER'S EPISCOPAL", {"evangelical_protestant"}),
    ("SAINT MARGARET'S EPISCOPAL CHURCH", {"evangelical_protestant"}),
    ("ST PAUL LUTHERAN SCHOOL - GRAFTON", {"evangelical_protestant"}),
    ("EPISCOPAL DIOCESE OF SW FLORIDA", {"evangelical_protestant"}),
    ("THE EPISCOPAL DIOCESE OF AR", {"evangelical_protestant"}),
    ("ST LUKES EPISCOPAL", {"evangelical_protestant"}),
    ("CHAPEL OF THE HOLY CROSS LUTHERAN C", {"evangelical_protestant"}),
    ("ST MARK'S AME ZION CHURCH FOOD PANTRY MINISTRY", {"evangelical_protestant"}),
    ("ST JAMES UNITED METHODIST CHURCH", {"evangelical_protestant"}),
    ("ST PAUL'S BAPTIST CHURCH", {"evangelical_protestant"}),
    ("Heritage Christian University", {"evangelical_protestant"}),
    ("REVIVE COLLEGE CHURCH", {"evangelical_protestant"}),
    ("AUGUSTANA COLLEGE CROSS COUNTRY", {"secular"}),
    ("OREGON ST UNIV FBO MORGAN LEBLANC", {"secular", None}),
    ("IOWA ST UNIV FBO EMILY CASPERS", {"secular", None}),
    ("KENNESAW ST UNIV FBO EMILY MATTHEWS", {"secular", None}),
    ("NORTH CAROLINA ST UNIV FBO KERA", {"secular", None}),
    ("ST LOUIS CHILDREN'S HOSPITAL KIDSTRUCTION", {"secular", None}),
    ("St Petersburg Theatre", {"secular", None}),
    ("C G JUNG SOCIETY OF ST LOUIS", {"secular", None}),
    ("GO ST LOUIS MARATHON", {"secular", None}),
    ("ST LOUIS FIREFIGHTERS COMMUNITY OUTREACH", {"secular", None}),
    ("ST LOUIS QUEER SUPPORT & HEALING", {"secular", None}),
    ("BOYS HOPE-GIRLS HOPE OF ST LOUIS", {"secular", None}),
    ("CHARITYVEST - WASHINGTON UNIVERSITY IN ST LOUIS", {"secular", None}),
    ("HUGS ST JOHNS COUNTY", {"secular", None}),
    ("ST JOSEPH COUNTY PARKS AND RECREATION", {"secular", None}),
    ("Domestic Sexual Abuse Services St Joseph County", {"secular", None}),
    ("FRIENDS OF THE ANIMAL CLINIC OF ST JOSEPH", {"secular", None}),
    ("ST SIMON ISLAND ATHLETIC ASSOCIATION", {"secular", None}),
    ("UF HEALTH ST JOHNS FOUNDATION", {"secular", None}),
    ("92ND ST Y - SECURITY FUND", {"jewish", "secular", None}),
    ("Georgetown Island Education Foundation", {"secular", None}),
    ("GEORGETOWN LAW - NIGHT OWL FUND", {"secular", None}),
    ("GEORGETOWN COUNTY BOYS MENTOR GROUP", {"secular", None}),
    ("UNITED WAY OF MARQUETTE COUNTY", {"secular"}),
    ("BIG BROTHERS BIG SISTERS OF ORANGE COUNT", {"secular"}),
    ("BIG BROTHERS BIG SISTERS OF TAMPA B", {"secular"}),
    ("TAY PHUONG MONASTERY", {"other_religion"}),
    ("ST NEKTARIOS MONASTERY", {"orthodox_christian"}),
    ("St Lukes Antichian Orthodox Church", {"orthodox_christian"}),  # (sic)
    ("MEHNAZ FATIMA EDUCATION AND WELFARE", {"muslim", "secular", None}),
    ("ST JUDE CHILCREN'S RESEARCH HOSPITAL", {"secular"}),  # (sic)
    ("ST VINCENT'S INSTITUTE OF MEDICAL RESEARCH", {"secular"}),
    ("COMMUNITY OF JESUS CRUCIFIED - PRIEST BROTHER AND SISTER SERVANTS", {"catholic"}),
]

# Fixes must not break rows the old rules got RIGHT.
REGRESSIONS = [
    ("Sisters of Mercy", "catholic"),
    ("Little Sisters of the Poor", "catholic"),
    ("St. Joseph Hospital", "catholic"),  # plain saint hospital IS Catholic
    ("Saint Raymond's High School for Boys", "catholic"),
    ("Catholic Charities of Denver", "catholic"),
    ("Diocese of Brooklyn", "catholic"),
    ("Marquette University", "catholic"),
    ("Georgetown University", "catholic"),
    ("St Vincent de Paul Society", "catholic"),
    ("Our Lady of Fatima Shrine", "catholic"),
    ("First Baptist Church", "evangelical_protestant"),
    ("Grace Lutheran Church", "evangelical_protestant"),
    ("Temple Israel", "jewish"),
    ("Congregation Beth Jacob", "jewish"),
    ("Islamic Center of America", "muslim"),
    ("Greek Orthodox Archdiocese", "orthodox_christian"),
    ("United Way of Greater Atlanta", "secular"),
    ("Boys and Girls Club of Tampa", "secular"),
]


def main() -> None:
    fixed, still_wrong = [], []
    for name, acceptable in CATALOG:
        got = infer_legacy_tradition(name)
        (fixed if got in acceptable else still_wrong).append((name, got, acceptable))

    print(f"=== GT catalog: {len(fixed)}/{len(CATALOG)} rows now resolve acceptably ===")
    print("\n--- Still wrong ---" if still_wrong else "\n--- None still wrong ---")
    for name, got, acceptable in still_wrong:
        want = "/".join(sorted(str(a) for a in acceptable))
        print(f"  {name!r}: got {got!r}, wanted {want}")

    print("\n=== Regression spot-checks (must all pass) ===")
    failures = 0
    for name, want in REGRESSIONS:
        got = infer_legacy_tradition(name)
        status = "ok" if got == want else "REGRESSION"
        if got != want:
            failures += 1
            print(f"  {status}: {name!r} -> {got!r} (wanted {want!r})")
    print(f"{len(REGRESSIONS) - failures}/{len(REGRESSIONS)} regression checks pass")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
