# Deep accuracy audit — name-rule classifications, both directions

_2026-08-10. Read-only. No reclassification, no ledger writes. Every fix below
is proposed, not applied._

Swept all **587 literals** across **19 regex lists** against the full
**1,188,588** distinct recipient names.

## Summary

The recurring bug family is real but **much narrower than the sweep first
suggests**. 314 literals match inside longer words and 282 of those change a
verdict — but almost all are legitimate inflections (`college`→`colleges`,
`ministr`→`ministries`, `evangel`→`evangelistic`). Filtering to leaks where
the matched word is *not* an inflection leaves a handful of genuine defects.

The most damaging finding is not a place name. It is **`care net` matching
"care network"**, which classifies **Abortion Care Network as evangelical
Protestant** — the precise inverse of reality, since Care Net is an
anti-abortion pregnancy-centre network.

## 1. Substring / boundary leaks (Step 1)

| list | literal | leaks into | recipients | dollars | direction |
|---|---|---|---:|---:|---|
| PROTESTANT | `care net` | care network, care netwk | 87 | **$10.3M** | **false positive** |
| CHRISTIAN_SIGNAL | `christian` | christiana, christianbook | 10 | $3.5M | false positive |
| JEWISH | `rabbi` | rabbit | 106 | $2.3M | misattribution |
| SECULAR | `opera` | operation, operations, operating | 1,368 | $156.8M | suppression risk |
| SECULAR | `hospital` | hospitality, hospitalier | 335 | $17.2M | suppression risk |
| SECULAR | `land trust` | land trustees | 1 | $0.2M | suppression risk |

Everything else that leaked was an inflection and is behaving correctly.

### 1a. `care net` — the worst finding

87 recipients, $10.3M, all currently `evangelical_protestant/rule`:

- **$5,521,246 — ABORTION CARE NETWORK**
- $1,870,009 — SANTA BARBARA WILDLIFE CARE NETWORK
- $365,100 — HOSPICE CARE NETWORK
- $358,037 — NEIGHBORLY CARE NETWORK INC
- $284,100 — HEALTH CARE NETWORK INC

A domain expert who sees Abortion Care Network flagged as an evangelical
recipient will not trust anything else in the product. This is the
highest-priority fix in the report.

### 1b. `christian` → "christiana"

**CHRISTIANA CARE HEALTH SYSTEM** ($937,935 plus three related rows) is a
secular Delaware health system named for the Christiana River. Currently
`christian_unspecified`.

Do **not** blanket-strip: `CHRISTIANBOOK INTERNATIONAL OUTREACH` ($2.2M) is
genuinely Christian and carries NTEE evidence, so it survives any name-rule
change anyway.

### 1c. `rabbi` → "rabbit"

106 recipients, $2.3M classified **jewish** — "The Rabbit Hole" ($1,040,135),
"THE RABBIT ROOM", "GREAT LAKES RABBITS SANCTUARY". Embarrassing, but it does
not inflate the Christian numbers; it misattributes to another tradition.

### 1d. `opera` / `hospital` — a suppression mechanism, not a wrong answer

These fire the SECULAR override on "Operation", "Operations", "Operating",
"Hospitality". The resulting verdict is usually *right by accident* (Operation
Kindness really is secular), so no visible error today. The risk is
directional: any genuinely Christian organisation with those words is forced
secular. Already visible in the data — **BLANCHET HOUSE OF HOSPITALITY**
($783,119) and **CENTRAL CITY HOSPITALITY HOUSE** ($810,500) are Catholic
Worker hospitality houses currently `secular`.

## 2. Place and proper names (Step 2)

Beyond `christiana` above, **nothing new**. The place-name list from the
previous audit was re-tested and the guards added this session hold: San/Santa
cities, Sacramento, Los Angeles, Trinity, Providence-as-place, Bethlehem,
Nazareth, Concord and the St-as-street cases all classify correctly. Corpus
Christi and the Louisiana civil parishes are fixed and their religious
counterparts (`CORPUS CHRISTI CHURCH`, `Assumption Parish Catholic Church`)
are intact.

Reporting that plainly rather than padding the list: this class is done.

## 3. False negatives (Step 3) — the valuable direction

4,884 recipients carry an unambiguous Christian term but no Christian verdict.
Raw that is $313.9M, but the number decomposes into very different things:

| class | recipients | dollars | verdict |
|---|---:|---:|---|
| rule does not fire (no strong literal) | 4,179 | $147.3M | mixed — see below |
| YMCA / YWCA | 1,137 | $74.9M | **your call** |
| SECULAR override beats religious signal | 106 | $45.8M | **real defect** |
| National Christian Foundation variants | 14 | $32.1M | **your call** (DAF) |
| identity typed `individual` | 906 | $13.4M | **identity bug, not classification** |
| rule fires, no verdict stored | 18 | $0.3M | small, real |

### 3a. SECULAR beats a genuine religious signal — the Boston-College problem in reverse

Exactly what you predicted. 106 recipients, $45.8M:

- **$5,314,169 — LATIN AMERICAN BIBLE INST COLLEGE** → `secular`, because
  `college` outranks "Bible Institute"
- $4,927,964 — CHRIST HOSPITAL FOUNDATION → `secular`, `hospital` beats
  "Christ"
- $11,317,213 — MUSEUM OF THE BIBLE INC → `secular`, `museum` beats "Bible"
- $14,383,441 — THE CHURCH OF JESUS CHRIST OF LATTER-DAY SAINTS → correctly
  non-Christian for this taxonomy (Mormon); listed for completeness

The existing `RELIGIOUS_WORD` escape hatch (church / chapel / christian /
ministry) protects "Heritage Christian University" but has no entry for
**bible, gospel, seminary, theological, diocese, catholic, baptist**.

### 3b. Identity mis-typing — a new finding, not a classifier bug

906 recipients / $13.4M are typed `identity_status = individual`, so this
session's Fix 1 correctly declines to give a person a religious tradition.
But several are plainly organisations:

- $4,204,565 — Southeastern Baptist Theological Seminary
- $1,756,500 — Catholic Education Foundation
- $1,170,000 — EVANGELICAL BAPTIST CHURCH

The classification logic is right; the **identity pipeline mis-typed them**.
Fixing this in the classifier would be wrong. It belongs with the identity
work, and it is evidence that `individual` typing needs its own audit.

### 3c. Genuine misses where no literal fires

- $7,200,022 — INST CHRIST KING SOVEREIGN PRIEST (Institute of Christ the
  King Sovereign Priest — a Catholic society)
- $3,388,733 — THE LEGION OF CHRIST INCORPORATE (Catholic religious order)
- $2,795,000 — Christian Aid (foreign)

## 4. Evidence precedence (Step 4)

**No mis-prioritised verdicts found.**

- 5,378 entities carry more than one distinct classification across methods.
  In every sampled case the higher-priority tier wins as designed
  (`ntee`/`church_code_name` 80 > `group_exemption` 75 > `rule` 70 > `llm` 50).
- The v3 retraction mechanism from this session is clean: **1,529 rows,
  1,529 distinct entities, one run**, no duplicates.
- 24 retracted entities also carry deterministic evidence (12 ntee, 10
  church_code_name, 2 group_exemption). Those verdicts correctly survive,
  because retracting a rule row cannot outrank a higher tier.

## 5. Ranked catalog

| # | class | direction | recipients | dollars | embarrassment |
|---|---|---|---:|---:|---|
| 1 | `care net` → care network | false positive | 87 | $10.3M | **severe** — Abortion Care Network as evangelical |
| 2 | SECULAR beats bible/seminary | false negative | 106 | $45.8M | high — real Christian colleges called secular |
| 3 | `christian` → christiana | false positive | 10 | $1.3M | moderate |
| 4 | `rabbi` → rabbit | misattribution | 106 | $2.3M | moderate — rabbit rescues as Jewish |
| 5 | `hospital`/`opera` suppression | latent | 1,703 | $174.0M | low today, structural |
| 6 | identity typed `individual` | false negative | 906 | $13.4M | not a classifier fix |

Every one of these is in the **default view**; all rest on name-rule evidence,
which the "high-confidence only" toggle already excludes.

## 6. Proposed fixes — NOT APPLIED

**Fix A — `care net` requires a boundary.** Change the literal to `care net `
(trailing-space guard), which the repaired `_rx()` now honours. Clears 87 false
positives including Abortion Care Network. Zero risk to genuine Care Net
affiliates, which appear as "Care Net" standalone.

**Fix B — extend `RELIGIOUS_WORD`** with `bible`, `gospel`, `seminary`,
`theological`, `diocese`, `catholic`, `baptist`. This is the existing escape
hatch that already stops `SECULAR` from stripping "Heritage Christian
University"; it simply lacks these terms. Recovers Latin American Bible
Institute and similar. Low risk — it only *prevents* a secular override,
never creates a Christian label on its own.

**Fix C — `christiana` place guard**, mirroring `CATHOLIC_PLACE`: "Christiana"
followed by care/health/hospital/river is a Delaware place name.

**Fix D — `rabbi` requires a boundary** (`rabbi `), preserving rabbinate /
rabbinic / rabbinical via separate literals if needed.

**Fix E — `opera` and `hospital` require boundaries.** Larger blast radius
(1,703 recipients), and today's verdicts are mostly right by accident, so I
would sequence this *after* A–D and re-measure rather than bundling it.

## 7. Flagged for your decision — do not auto-decide

- **YMCA / YWCA** (1,137 recipients, $74.9M). Nominally "Young Men's Christian
  Association", functionally secular community organisations in most of the
  US. Whether your partner's clients would consider a YMCA a Christian funding
  target is a domain question, not a code question. This is the single largest
  swing item in the audit.
- **National Christian Foundation variants** (14, $32.1M). A genuinely
  Christian donor-advised fund. Currently treated as DAF pass-through and
  excluded from Christian totals. Defensible either way.
- **MUSEUM OF THE BIBLE** ($11.3M) and **CHRIST HOSPITAL FOUNDATION** ($4.9M).
  Christian-founded, arguably secular in operation.
- **Providence** — still outstanding from the previous audit, untouched.

## 8. Estimated net effect if A–D are applied

- Christian dollars: **−$11.6M** (false positives leaving) **+$45.8M**
  (suppressed Christian orgs returning) ≈ **net +$34M**, roughly +0.3% on
  $10.87B.
- Sellable core: expected to move by single digits. These are recipient-level
  corrections that mostly change *which* foundations carry Christian dollars,
  not how many clear the $50k threshold.
- The value here is not the dollar movement. It is that Abortion Care Network
  stops being an evangelical recipient and Latin American Bible Institute
  stops being secular — both of which a domain expert would spot immediately.
