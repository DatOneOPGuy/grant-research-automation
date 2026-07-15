# Foundation Explorer Data Pipeline

Foundation Explorer compiles a national private-foundation research database
from official IRS records. The pipeline downloads no ProPublica data and does
not scrape websites. ProPublica appears only as an optional outbound link.

## Current Release Scope

- Private foundations identified from all four IRS EO BMF regions.
- Form 990-PF filings downloaded directly from IRS TEOS XML archives.
- Observed tax years: 2023-2024. No 2025 tax-year data is represented.
- Customer giving metrics: positive grants paid during the year only.
- Future-approved commitments, zero rows, negative adjustments, superseded
  filings, non-990-PF returns, and ambiguous recipient identities remain
  separately auditable and do not silently enter paid metrics.

See [docs/data-integrity-v2.md](docs/data-integrity-v2.md) for the schema,
canonical-filing policy, recipient-identity process, evidence resolution, and
release gates. Legal and customer-facing source disclosures are in
[DATA-SOURCES.md](DATA-SOURCES.md), [PRIVACY.md](PRIVACY.md), and
[TERMS.md](TERMS.md).

## Development Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Run verification:

```bash
ruff check src tests
python3 -m pytest -q
```

## Provenance Rebuild

Build the complete BMF registry from the four already-downloaded IRS files:

```bash
python3 -m src.bmf_registry --rebuild
```

Run the conservative disk preflight, then reparse raw XML into a parallel v2
database. Neither command writes to `data/grants.db`:

```bash
python3 -m src.rebuild_database --preflight-only
python3 -m src.rebuild_database --output data/grants_v2.db --workers 4
```

Build and gate a release without any LLM classification pass:

```bash
python3 -m src.build_release_v2
```

That command resolves recipient identities, adds direct NTEE and deterministic
rule evidence, publishes foundation enrichment, streams
`foundation_database_v2.csv`, and writes a release manifest under
`data/releases/`. A failed integrity gate stops publication.

Legacy rule/NTEE evidence can be imported explicitly for comparison, but it is
not trusted by default because the legacy store used normalized name alone:

```bash
python3 -m src.build_release_v2 --include-legacy-evidence
```

## Explorer UI

The existing local Explorer remains on the last customer release until the v2
manifest passes. Backend and frontend startup instructions are in
[`foundation-explorer/README.md`](foundation-explorer/README.md).

## Repository Data Policy

Raw XML, SQLite databases, exports, BMF downloads, manifests containing source
paths, and environment files are local artifacts and must not be committed.
Before every commit, inspect staged files and verify that no secrets or local
data are included.
