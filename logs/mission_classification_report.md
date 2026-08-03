# Mission-Text Classification Report

_Generated 2026-08-03 by the mission-text downstream sequence._

## Pipeline artifacts

- Classification run: `classify-20260803T200117-2b10509e` (method=llm, engine `fable-5-mission-text`)
- Classification release: `classification-20260803T200119-c05b6a4f` (337,103 entities resolved, 919 resolution issues)
- Identity run: `identity-20260715T164705Z`
- Read model rebuilt: `data/explorer_v5.db` (mission tier: 55,215 tradition_stats rows / $44.19B; 34,833 recipients via llm)

## Batches loaded

- Input batches: 234 | Result batches: 234 | Missing after guard: 0
- Predictions parsed across all batches: 37,133
- Evidence rows written (method=llm, priority 50, floor 0.7): **35,599**
- `unknown` predictions skipped (no evidence): 1,534
- Bad labels (not in taxonomy): 0
- Below-floor rows written but non-resolving (conf < 0.70): 754

## Reconciliation vs the 37,293 name-neutral target

`mission_targets` = matched-BMF entities, currently unclassified, with canonical mission text.
Total = 37,293 (37,281 strictly name-neutral; 12 carry a faith-signal name).

| Metric | Count | % of 37,293 |
|---|---:|---:|
| Target entities | 37,293 | 100.00% |
| Got a mission classification (llm evidence, any conf) | 35,599 | 95.46% |
| No mission classification | 1,694 | 4.54% |
| -- of which `unknown` (model abstained, skipped) | 1,534 | 4.11% |
| -- of which never predicted (batch 0080 defect, see anomaly) | 160 | 0.43% |

**Coverage: 95.46%** of the 37,293 target received a mission classification.
All 35,599 llm evidence rows land 1:1 on target entities (no off-target writes).

## Tradition breakdown (distinct target entities, llm evidence written)

| Tradition | Written (any conf) | Resolving (conf ≥ 0.70) |
|---|---:|---:|
| secular | 33,834 | 33,417 |
| christian_unspecified | 990 | 771 |
| jewish | 276 | 247 |
| evangelical_protestant | 176 | 172 |
| other_religion | 173 | 92 |
| catholic | 101 | 100 |
| muslim | 18 | 16 |
| christian_science | 18 | 18 |
| orthodox_christian | 9 | 8 |
| mormon_lds | 4 | 4 |
| **TOTAL classified** | **35,599** | **34,845** |

## Christian summary

Christian = core read-model tiers (evangelical_protestant, catholic, orthodox_christian, christian_unspecified).

- Christian entities newly classified (any conf): **1,276**
- Christian entities that actually resolve (conf ≥ 0.70): **1,051**
- Broad Christian (incl. christian_science 18, mormon_lds 4): 1,298 written

## Anomalies

1. **Malformed result `batch_0080.json` (repaired).** Its 160 rows were serialized as
   4-element arrays `[id, tradition, confidence, reason]` instead of objects, which
   crashed the loader. Normalized in place to the standard object shape (original saved
   as `batch_0080.json.listbak`). No entities lost in the repair.
2. **Batch 0080 / 0069 id mismatch (pre-existing classify-phase defect).** The *content* of
   `batch_0080.json` is actually the classifications for **batch 0069's** 160 input entities
   (all 160 result ids belong to input batch 0069, zero overlap with batch 0080's inputs).
   Consequences:
   - Batch 0069 was effectively classified twice; the two result sets agree on tradition for
     all 160/160 entities, and because evidence is keyed by entity_id the duplicate rows are
     identical — no conflicting or double-counted evidence entered the ledger.
   - Batch 0080's own 160 input entities were **never classified** — these are exactly the
     160 "never predicted" target entities in the reconciliation above.
   - Net effect on coverage: -0.43 percentage points (160 / 37,293). Within guard tolerance.
   - Remediation (future): re-run the fan-out for batch 0080's true input set and reload;
     evidence is append-only so a top-up load will fill these 160 gaps cleanly.

