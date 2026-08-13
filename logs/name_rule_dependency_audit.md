# Name-rule dependency & accuracy audit

_2026-08-12. Read-only measurement. Nothing reclassified, no ledger writes, no
fixes applied. Full population: 1,302,051 recipients, 343,522 with evidence,
590,055 name-rule evidence rows._

## Headline: the distrust is half right, and the wrong half is the interesting one

**Where a name rule can be graded against evidence we trust more, it agrees
99.06% of the time (18,380 of 18,555).** When it asserts a religious
tradition it is 99.3–100% accurate, and the total measured false-positive
exposure is **11 recipients / $0.27M**. On that axis the distrust is
overcalibrated.

**But 64.8% of Christian dollars and 43.8% of the actionable set rest on a
name rule with nothing behind it.** That is the real finding: not that name
rules are inaccurate, but that the product is heavily *dependent* on them, in a
population we cannot currently check.

## Part 1 — Dependency

All 323,388 classified recipients, by evidence structure:

| bucket | recipients | share | dollars | share |
|---|---:|---:|---:|---:|
| (a) no name rule involved | 48,653 | 15.0% | $49.50B | 40.1% |
| (b) name rule corroborated by ≥1 independent tier | 18,204 | 5.6% | $2.03B | 1.6% |
| **(c) name rule is the SOLE evidence** | **256,356** | **79.3%** | **$71.87B** | **58.2%** |
| (d) name rule contradicted by a higher tier | 175 | 0.1% | $0.16B | 0.1% |

Bucket (d) confirms precedence works: in every case the higher tier wins the
final verdict. Spot-checked — MARIAN UNIVERSITY ($34.9M), ALVERNO COLLEGE,
UNIVERSITY OF SAN DIEGO and UNIVERSITY OF DAYTON are all name-ruled *secular*
and all resolve **catholic** via `group_exemption`.

### The exposure number

| measure | total | name-rule-only | on stronger evidence |
|---|---:|---:|---:|
| Christian grant dollars | $11.472B | **$7.431B (64.8%)** | $4.042B (35.2%) |
| Actionable "sellable core" foundations | 1,346 | **589 lost (43.8%)** | **757 survive (56.2%)** |

**If every name-only classification vanished, 56% of the actionable product
would still stand on stronger evidence.** That is the honest answer to "how
much rests on names".

## Part 2 — Accuracy where checkable

18,555 recipients carry both a name-rule classification and at least one
independent-tier classification (human / ntee / church_code_name /
group_exemption / llm-mission / grant_purpose).

| rule said | checkable | agree | FP | FN | precision | $-weighted |
|---|---:|---:|---:|---:|---:|---:|
| evangelical_protestant | 10,450 | 10,444 | 6 | 0 | **99.94%** | 99.98% |
| catholic | 3,703 | 3,701 | 2 | 0 | **99.95%** | 100.00% |
| jewish | 2,251 | 2,243 | 0 | 8 | 99.64% | 99.31% |
| christian_unspecified | 975 | 972 | 3 | 0 | 99.69% | 99.77% |
| other_religion | 428 | 425 | 0 | 3 | 99.30% | 99.90% |
| muslim | 364 | 362 | 0 | 2 | 99.45% | 99.99% |
| orthodox_christian | 216 | 216 | 0 | 0 | 100.00% | 100.00% |
| christian_science | 11 | 10 | 0 | 1 | 90.91% | 97.99% |
| mormon_lds | 7 | 5 | 0 | 2 | 71.43% | 99.79% |
| **secular** | **150** | **2** | **0** | **148** | **1.33%** | 0.85% |

**OVERALL: 99.06%.**

### The "secular" row is selection bias, not a 1.33% failure rate

It would be easy to report "name rules are 1% accurate at secular" and it would
be wrong. **All 165 false negatives are supported by `group_exemption` (119)
and `ntee` (46) — two detectors that only ever fire on *religious*
organisations.** So the only secular-labelled recipients we can check are, by
construction, ones where religion-only evidence exists — i.e. where the rule
was wrong. The denominator is definitionally poisoned.

What the row *does* legitimately show: the name rule misses religiously
affiliated institutions whose names carry no religious word, and the ledger
catches them only when a group ruling or NTEE code exists. Top misses (all
correctly resolved by the higher tier):

| recipient | rule said | trusted evidence | dollars |
|---|---|---|---:|
| MARIAN UNIVERSITY | secular | group_exemption → catholic | $34,867,420 |
| ALVERNO COLLEGE | secular | group_exemption → catholic | $10,663,333 |
| UNIVERSITY OF SAN DIEGO | secular | group_exemption → catholic | $9,711,400 |
| CONCORDIA COLLEGE CORPORATION | secular | group_exemption → evangelical | $8,641,846 |
| GWYNEDD MERCY UNIVERSITY | secular | group_exemption → catholic | $7,699,599 |
| UNIVERSITY OF DAYTON | secular | group_exemption → catholic | $6,414,434 |

This is the same family as Baylor/Pepperdine from the grant-purpose audit:
**name-invisible religious institutions**. Where a group ruling exists we catch
them; where it doesn't, we do not.

### All 11 false positives, in full

Total $272,065 — small enough to list completely:

| dollars | rule said | trusted said | recipient |
|---:|---|---|---|
| $75,000 | christian_unspecified | ntee: jewish | AMERICANS OF FAITH |
| $72,250 | evangelical_protestant | ntee: jewish | SHALSHELET SEMINARY INC |
| $60,000 | evangelical_protestant | ntee: jewish | EUROPE CAMPUS MINISTRY |
| $24,000 | evangelical_protestant | ntee: jewish | FINAL FRONTIER MINISTRIES INC |
| $20,000 | christian_unspecified | ntee: jewish | CHEVRA KADISHA-SINAI MEMORIAL CHAPEL |
| $10,000 | evangelical_protestant | ntee: jewish | MISSIONS OF MERCY |
| $5,000 | evangelical_protestant | ntee: jewish | SHALOM MINISTRIES INC |
| $5,000 | christian_unspecified | ntee: other_religion | RAMANAND VISHWA HITKARINI PARISHAD |
| $1,000 | catholic | ntee: other_religion | GIAC NGAN MONASTERY |
| $1,000 | evangelical_protestant | ntee: jewish | DEVAR EMET MESSIANIC JEWISH OUTREACH |
| $815 | catholic | ntee: other_religion | BRAHMA VIHARA MONASTERY |

Nine of eleven are the Messianic-Jewish / Hebrew-Christian boundary, which is
genuinely contested rather than a coding bug. Two are Buddhist monasteries
caught by Catholic monastery vocabulary — a real but tiny pattern.

**No literal shows error concentration on the `cru` / `care net` scale.** The
next-cru is not visible in this data.

## Part 3 — The blind spot: name-only, unverifiable

Recipients classified by name rule with **no independent evidence available**:

| | recipients | dollars |
|---|---:|---:|
| Christian | **97,428** | **$7.431B** |
| non-Christian | 158,928 | $64.443B |

Corroboration reachability for the Christian blind spot, ranked by dollars:

| route | recipients | dollars |
|---|---:|---:|
| **needs identity resolution first** | 86,746 | $4.332B |
| **already has mission text on disk — unused** | **1,630** | **$2.212B** |
| no route identified | 2,297 | $0.546B |
| 990 mission pull (resolved EIN) | 6,755 | $0.341B |

The second row is the finding worth acting on: **1,630 recipients holding
$2.212B already have 990 mission text sitting in the database, but their
classification still rests on the name alone.** They were never in a mission
batch. That is $2.2B of corroboration available at zero acquisition cost.

89% of the blind spot by count sits behind identity resolution — consistent
with everything else this project has measured.

## Part 4 — Extrapolation, with its limits stated

Measured false-positive rate on religious labels where checkable: **11 / 18,405
= 0.06%**. Naively applied to the 97,428 name-only Christian recipients, that
predicts ~58 false positives and **~$4.5M of misattributed dollars** out of
$7.431B.

**I do not think that number should be trusted, and here is why.** The
extrapolation requires the checkable and uncheckable populations to be similar.
They are not:

- **89% of the blind spot is identity-unresolved**, versus a checkable set that
  is almost entirely resolved (independent evidence requires a matched EIN).
- Blind-spot recipients are smaller and more obscure: $7.431B across 97,428
  recipients (~$76k each) against the checkable set's much higher per-recipient
  dollars.
- Independent evidence exists *because* an organisation is registered,
  matched and often religious. Absence of it correlates with being harder to
  identify at all.

So the true error rate in the blind spot is probably **higher** than 0.06%,
and I cannot bound it from this data. The honest statement is: **where we can
check name rules they are 99%+ accurate, and we cannot check the 64.8% of
Christian dollars that matter most.**

## Recommendations — proposed, not applied

1. **Classify the 1,630 recipients that already have mission text** ($2.212B).
   Zero acquisition cost, uses the validated classifier, and directly converts
   name-only dollars into corroborated dollars. Highest value per effort by a
   wide margin.
2. **990 mission pull for the 6,755 resolved-EIN recipients** ($0.341B). Modest
   dollars but a clean, bounded job.
3. **Identity resolution remains the dominant constraint** — 86,746 recipients
   / $4.332B cannot be corroborated by any route until they are resolved. This
   is the same conclusion the coverage and Schedule-O audits reached.
4. **Do not "fix" the name rules on this evidence.** No literal shows
   `cru`-scale error concentration, and the measured false-positive exposure is
   $0.27M. Effort belongs in corroboration, not in rule surgery.
5. Consider adding the Messianic-Jewish boundary and Buddhist-monastery
   vocabulary to the review list — 11 recipients, $0.27M, low priority, and
   partly a genuine definitional question rather than a bug.

## What this does not tell you

Nothing here validates name rules on the population that matters most. It
validates them on the subset where we happened to have something better — which
is exactly the subset where we needed them least.
