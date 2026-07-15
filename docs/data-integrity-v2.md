# Data Integrity Architecture v2

## Objective

The v2 path rebuilds the factual substrate before any model-assisted
classification. It runs in parallel with the legacy database so a failed build
cannot corrupt the active customer release.

## 1. Filing Provenance and Canonicalization

`src.rebuild_database` parses every source XML into `data/grants_v2.db` and
retains:

- IRS object ID, source path, SHA-256, index metadata, return type, EIN, tax
  year, tax-period end, return timestamp, amendment indicator, parser version,
  parse status, and parse error.
- Foundation facts keyed to the source object ID.
- Every grant row with schedule type, source XPath, row ordinal, recipient
  fields, original amount text, signed amount, and amount status.

Only Return Type `990PF` is eligible for foundation facts. The canonical policy
selects one filing for each EIN and tax year by normalized return timestamp,
then amendment indicator, then object ID. Other versions remain in the database
as superseded filings.

Paid and future-approved schedules are separate. `paid_grants` contains only
canonical rows marked `paid`, with a positive signed amount. Zero, negative,
missing, and invalid amounts remain in `paid_adjustments`; future commitments
remain in `future_approved_grants`.

## 2. Recipient Identity

`src.recipient_identity` creates a recipient mention from conservative normalized
name, city, state, and country. Legal terms such as `foundation`, `trust`, and
`church` are retained. Paid-grant rows link to mentions by a stable digest.

The resolver uses all four official BMF regions and ranks candidates:

1. Reported recipient EIN.
2. Exact normalized name, city, and state.
3. Exact normalized name and state.
4. Exact normalized name nationally.

Only a unique best candidate is selected. Ties become collision records; names
without a safe candidate remain unresolved. No fuzzy match silently becomes an
identity.

## 3. Classification Evidence

Classification is an immutable evidence ledger, not a mutable recipient label.
Each item records entity ID, class, confidence, method, source rule or NTEE code,
model and prompt metadata where applicable, reason, source record, run ID, and
timestamp.

Resolution priority is human review, IRS NTEE, deterministic rule, documented
model evidence, then legacy evidence. Evidence below its method confidence floor
does not resolve. Equal-priority contradictory labels produce an unresolved
issue rather than an arbitrary answer.

The default v2 release adds direct IRS NTEE and deterministic name-rule evidence
only. It does not run an LLM. Legacy evidence is optional and remains visibly
lower priority.

## 4. Foundation Enrichment

Each enrichment release names its identity run, classification release, policy
version, and actual tax-year window. Foundation metrics reconcile positive paid
grant dollars into exactly three buckets:

- confirmed Christian;
- confirmed non-Christian; and
- unclassified.

The release stores dollar coverage and a High/Moderate/Low quality band
internally. A strong customer verdict requires at least $100,000 of confirmed
Christian paid grants and at least three distinct confirmed Christian recipient
entities. Evidence rows retain recipient name, EIN where resolved, identity
status, classification, method, confidence, dollars, count, and most recent year.

Application status is conservative. `Accepting Applications` requires meaningful
application instructions, deadline, or restrictions. Contact details alone yield
`Contact First`; an empty XML group yields `Unknown`; explicit preselection or
no-unsolicited language yields `Invite Only`.

## 5. Release Gates and Manifest

Publication fails unless all gates pass:

- canonical customer filings are Form 990-PF only;
- the paid view contains positive paid rows only;
- exactly one canonical filing exists per EIN and tax year;
- paid source dollars and counts reconcile exactly to enrichment;
- Christian, non-Christian, and unclassified buckets reconcile exactly;
- classification releases contain zero unresolved conflicts;
- `Accepting Applications` always has affirmative filing evidence;
- all four BMF regions are present;
- export row count equals the BMF private-foundation universe;
- export EINs are unique and carry one expected release ID; and
- export paid dollars reconcile exactly to source paid grants.

The JSON manifest records source hashes, parser versions, parse statuses, tax
years, canonical and superseded counts, paid/future/adjustment rows and dollars,
identity collisions, classification methods, coverage, verdicts, export SHA-256,
and every gate result.

## Operational Constraint

A complete rebuild needs substantially more free disk space than the legacy
database because raw provenance, superseded filings, identity candidates,
classification evidence, indexes, and SQLite scratch space are retained. Run
`python3 -m src.rebuild_database --preflight-only` to print the full projection.
The rebuild refuses to start when that conservative disk gate fails; there is no
production bypass.
