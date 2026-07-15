"""Build identity, classification, enrichment, export, gates, and manifest."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.classification_seed_v2 import run as classify
from src.export_v2 import run as export
from src.foundation_enrichment_v2 import run as enrich
from src.legacy_classification_import import run as import_legacy
from src.recipient_identity import run as resolve_identity
from src.release_manifest import build_manifest, write_manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("data/grants_v2.db"))
    parser.add_argument("--bmf-db", type=Path, default=Path("data/bmf_registry.db"))
    parser.add_argument("--legacy-db", type=Path, default=Path("data/grants.db"))
    parser.add_argument("--export", type=Path, default=Path("foundation_database_v2.csv"))
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--tax-year-start", type=int, default=2023)
    parser.add_argument("--tax-year-end", type=int)
    parser.add_argument("--identity-run")
    parser.add_argument("--classification-release")
    parser.add_argument("--include-legacy-evidence", action="store_true")
    return parser.parse_args()


def require_inputs(db_path: Path, bmf_path: Path) -> None:
    missing = [str(path) for path in (db_path, bmf_path) if not path.exists()]
    if missing:
        raise FileNotFoundError("Required release input missing: " + ", ".join(missing))


def run(args: argparse.Namespace) -> dict:
    require_inputs(args.db, args.bmf_db)
    if args.classification_release and not args.identity_run:
        raise ValueError("--classification-release requires --identity-run")
    identity_run = args.identity_run or resolve_identity(args.db, args.bmf_db)
    classification_release = args.classification_release or classify(
        args.db, args.bmf_db, identity_run
    )
    if args.include_legacy_evidence:
        _, classification_release = import_legacy(args.db, args.legacy_db, identity_run)
    enrichment_release = enrich(
        args.db,
        identity_run,
        classification_release,
        args.tax_year_start,
        args.tax_year_end,
    )
    export(args.db, args.bmf_db, args.export, enrichment_release)
    manifest = build_manifest(args.db, args.bmf_db, args.export, enrichment_release)
    manifest_path = args.manifest or Path("data/releases") / f"{enrichment_release}.json"
    write_manifest(manifest, manifest_path)
    if manifest["status"] != "passed":
        raise RuntimeError(f"Release gates failed; inspect {manifest_path}")
    return manifest


def main() -> None:
    manifest = run(parse_args())
    print(f"Release passed: {manifest['release_id']}")


if __name__ == "__main__":
    main()
