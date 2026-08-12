# Grant-purpose evidence — what the funder says about each grant

_2026-08-12. Read-only investigation. No reclassification, no ledger writes.
The design in section 4 is proposed, not applied._

**Answer to the first question: no, we have not built this.** Grant purpose has
never been used as evidence. Existing sources are recipient identity, name
rules, deterministic BMF evidence (NTEE / church code / group exemption), and
recipient-990 mission text.

## 1. Do we already have the purpose text? Yes — and no pull is needed

`grant_transactions.purpose` in `data/grants_v2.db` is **already populated for
all 3,012,118 grant rows**, captured by the existing 990-PF parser from
`GrantOrContributionPurposeTxt`. It already flows through to the read model.

**This is not a pull, and not even a re-parse.** The data is in the v2
substrate today. Nothing external is required.

## 2. How informative is it? Mostly boilerplate — reporting that plainly

Length distribution across all 3.01M grants:

| purpose length | grants | share | dollars |
|---|---:|---:|---:|
| under 12 chars | 537,872 | 17.9% | $25.7B |
| 12–30 chars | 1,735,922 | 57.6% | $91.3B |
| 30–80 chars | 589,428 | 19.6% | $93.8B |
| 80+ chars | 148,896 | 4.9% | $25.6B |

The most common values are pure boilerplate:

| purpose | grants | dollars |
|---|---:|---:|
| GENERAL SUPPORT | 201,014 | $9.85B |
| CHARITABLE | 100,011 | $3.70B |
| GENERAL | 89,276 | $3.42B |
| SCHOLARSHIP | 81,923 | $0.43B |
| GENERAL OPERATING | 74,602 | $2.85B |
| GENERAL OPERATING SUPPORT | 71,535 | $4.59B |
| UNRESTRICTED | 55,916 | $1.30B |

**So the honest headline: this is a low-yield field.** After excluding
boilerplate and requiring explicit religious language on a word boundary,
**25,116 grants (0.8% of all grants) / $1.32B** carry usable signal, touching
15,225 distinct recipients.

That is small. But the *composition* is what makes it worth building.

## 3. Where the value actually is

| bucket | grants | dollars | what it does |
|---|---:|---:|---|
| corroborates an existing Christian verdict | 15,224 | $837.2M | raises confidence, adds an auditable funder quote |
| recipient currently **unclassified** | 8,518 | $287.1M | **new signal** |
| **contradicts** the recipient's classification | 1,374 | **$192.1M** | **the most valuable bucket** |

### 3a. Contradictions find the false negatives nothing else caught

These are recipients classified **secular** whose funders describe the grant in
explicitly Christian terms:

| recipient | current | dollars | funder's own purpose text |
|---|---|---:|---|
| **BAYLOR UNIVERSITY** | secular | $7,300,624 | "CHARITABLE CONTRIBUTION FOR CHRISTIAN MINISTIRES" |
| **PEPPERDINE UNIVERSITY** | secular | $7,550,250 | "Christian Ministry Evangelism" |
| **ANDREWS UNIVERSITY** | secular | $6,486,224 | "STUDENT EVANGELISM IN THE MIDDLE EAST" |
| **GROVE CITY COLLEGE** | secular | $5,484,304 | "SUPPORT FINANCIAL AID AND COLLEGE MISSIONS" |

Baylor (Baptist), Pepperdine (Churches of Christ), Andrews (Seventh-day
Adventist) and Grove City are genuinely Christian institutions. The name rules
cannot reach them — their names contain no religious word, so the
`RELIGIOUS_WORD` fix from the last pass could not help. **The funder's stated
purpose is the only signal in our data that identifies them.**

This directly answers Emily's ask: verification independent of the recipient's
name.

### 3b. New signal on unclassified recipients

| recipient | dollars | purpose |
|---|---:|---|
| SISTER DULCE FOUNDATION | $2,942,349 | "TO PROVIDE FUNDS TO SUPPORT A MINISTRY THAT PRAYS WITH..." |
| International Cooperating Ministries | $2,512,000 | "TO SUPPORT THE MINISTRY OF THE ORGANIZATION" |
| CATALYST CHURCH NWA INC | $7,200,000 | "to support the building of a new sanctuary" |
| Duke Divinity School | $10,837,471 | "TO SUPPORT CONTINUING EDUCATION AT DUKE DIVINITY" |

## 4. Proposed design

### Recommendation: a new evidence method, `grant_purpose`, at priority 40

Below `llm`/mission (50), above the legacy tiers (30). Rationale:

- It is **weaker than mission text** as an identity signal, because it
  describes *one grant*, not the organisation. A recipient with one
  "Christian education" grant and ten secular ones is not a Christian
  organisation.
- It is **real, first-party, and auditable** — the funder wrote it on a signed
  federal return — so it deserves a place in the ledger rather than being a
  hidden confidence tweak.

Modelling it as a method (rather than only a confidence bump) keeps the
existing precedence machinery doing the work, and means a purpose-derived
verdict can never override NTEE, church code, GEN, a rule, or mission text.

### Aggregation rule — the anti-over-claim guard

A single purpose-tagged grant must **not** classify a recipient. Proposed:
emit `grant_purpose` evidence for a recipient only when religious-purpose
grants are **a majority of that recipient's grant dollars from that funder**,
or span **two or more distinct funders**. One grant in isolation becomes a
review item, not evidence.

### Strict-Christian discipline

Same rules that produced mission-text precision 1.000: explicit religious
language required, the **verbatim purpose sentence stored as the reason**,
abstain freely, no inference from the recipient's name.

### Contradictions are review items, never auto-resolved

The 1,374 contradiction grants should populate a review queue, not flip
anything. Some are real classification errors (Baylor). Some are genuinely
mixed organisations (Duke — the Divinity School is Christian, the university
is not). That distinction is a human call.

## 5. Two noise patterns the build must handle

Found while measuring, and they matter:

1. **"mission" / "missions" is far noisier in purpose text than in org names.**
   A foundation's own *organisational* mission is routinely described here:
   "TO SUPPORT THE MISSIONS AND OPERATIONS OF THE UNIVERSITY" (UC Berkeley,
   $14.0M) is not religious. `mission` must require corroboration; `missionary`
   and `missions` in an evangelistic phrase are safer.
2. **Substring matching bites again.** My first scan used SQL `LIKE '%CHRIST%'`
   and matched **"CHRISTOPH NABZDYK, MD"** in a Mayo Clinic research grant.
   Word boundaries are mandatory — this is the same failure family as the
   `cru` and Corpus Christi bugs.

## 6. Estimated reach if approved

- Recipients gaining a **new** corroborating Christian signal: up to **6,644**
  ($287.1M in the grants concerned), before the anti-over-claim rule is
  applied — expect materially fewer after it.
- Recipients whose existing Christian verdict gains an auditable funder quote:
  **8,795**.
- **Review queue: ~1,303 recipients / $192.1M** of contradictions, the highest-
  value output of the whole exercise.
- Effect on the actionable set: modest. Most of these recipients already sit at
  foundations that clear the threshold. The gain is **defensibility**, not
  volume — a grant writer can show the funder's own words.

## 7. Recommendation

Build it, but scope expectations honestly: **0.8% of grants carry usable
purpose language**, and this will not move the headline numbers much. Its value
is that it is the only source we have that (a) verifies independently of the
recipient's name, which is exactly what Emily asked for, and (b) surfaces
Christian institutions like Baylor and Pepperdine that no name-based rule can
reach.

I would sequence the **contradiction review queue first** — it is read-only,
needs no ledger changes, and produces immediate value for a domain expert to
audit.
