# The "historically affiliated, functionally secular" class

_2026-08-13. Read-only investigation. Nothing reclassified, no ledger writes.
The treatment in section 3 is proposed, not applied._

## Headline: the class is real, and much smaller than the SMU examples suggest

You are right that SMU, TCU and Duke are neither cleanly Christian nor cleanly
secular. But when membership is required to rest on **evidence** rather than on
the shape of a name, the evidenced class is **13 recipients / $0.190B — 1.7% of
Christian dollars**, not the sweeping category the seed cases imply.

A further **1,158 recipients / $0.252B** fit the *pattern* but have no mission
text, so I cannot demonstrate functional secularity for them. Calling them mixed
would be exactly the name-based guessing this project keeps finding bugs in.

## 1. How the candidates separate

Starting pool: recipients classified Christian whose name carries a
denominational signal AND an institution word, excluding congregations,
ministries, seminaries and divinity schools — **1,249 recipients / $0.626B**.

| bucket | recipients | dollars | verdict |
|---|---:|---:|---|
| **A** deterministic religious evidence | 65 | $0.049B | **stays Christian** |
| **B** mission text confirms Christian | 11 | $0.114B | **stays Christian** |
| **C** mission text abstained | 2 | $0.022B | leave alone |
| **D** mission text says secular | **13** | **$0.190B** | **MIXED candidate** |
| **E** name only, no mission verdict | 1,158 | $0.252B | unverifiable |

**Deterministic evidence is what cleanly separates genuinely-Christian from
mixed.** Bucket A holds a live group ruling or church code — Gwynedd Mercy,
California Lutheran, Dominican University, Williams Baptist, Benedictine
College. A denomination still formally claims them. Bucket B is confirmed by
the institution's own mission statement — Indiana Wesleyan, Abilene Christian,
Catholic University of America, Trevecca Nazarene, Lubbock Christian.

Neither is swept into "mixed". That was the main risk you flagged and the
evidence handles it without judgement calls.

## 2. The evidenced mixed class (bucket D)

| received | recipient | mission text says | conf |
|---:|---|---|---:|
| $123,594,414 | SOUTHERN METHODIST UNIVERSITY | secular | 85 |
| $24,427,101 | TEXAS CHRISTIAN UNIVERSITY | secular | 85 |
| $7,040,030 | THE METHODIST HOSPITAL | secular | 85 |
| $5,829,747 | WESLEYAN COLLEGE | secular | 55 |
| $4,998,326 | ILLINOIS WESLEYAN UNIVERSITY | secular | 92 |
| $4,004,159 | HOUSTON CHRISTIAN UNIVERSITY | secular | 85 |

### Boundary cases I am NOT confident about — your call

- **HOUSTON CHRISTIAN UNIVERSITY** ($4.0M) — formerly Houston Baptist
  University, still Baptist-affiliated with a required Christian core
  curriculum. The mission text is silent on faith, but I think this is
  genuinely Christian and does **not** belong in the mixed class.
- **WESLEYAN COLLEGE** ($5.8M, confidence 55) — low confidence, and Wesleyan
  College (Georgia) retains a Methodist relationship.
- **WESLEYAN UNIVERSITY** ($19.7M, bucket C) — the Connecticut university is
  fully secular today despite its Methodist founding. It is currently
  classified Christian by name rule, which is arguably a plain error rather
  than a mixed case.

## 3. Proposed treatment — a third state, not a third guess

### Representation

Add `affiliation_status` alongside the tradition verdict, not inside it:

- `active` — deterministic evidence or mission text confirms a live religious
  identity (buckets A and B). Counts as Christian.
- `historical` — denominational heritage with evidence of secular operation
  (bucket D). **Does not count as Christian dollars.**
- `unknown` — pattern fits but no evidence either way (bucket E). Counts as
  today, flagged as unverified.

This keeps the tradition field meaning what it says and puts the nuance in a
field built for it, rather than inventing a fourth tradition value that every
downstream filter would have to learn.

### Display

> **Southern Methodist University** — Methodist heritage, secular operation
> *Mission statement describes "education through research and teaching" with
> no stated faith purpose. 0.0% of grants received carry a religious purpose.*

The fundraiser sees the real picture and makes the call, consistent with the
product's stance everywhere else: show the evidence, don't decide for them.

### Effect on the Christian-dollar math

Moving bucket D out of Christian: **−$0.190B, from $11.472B to $11.282B, a
1.7% reduction.** Effect on the actionable set is negligible — these are
recipients, and the foundations funding them mostly clear the threshold on
other giving.

**This is a correction toward honesty, not a loss.** A foundation funding SMU
athletics is not a Christian funder, and today we count it as one.

## 4. Grant purpose is the right unit for mixed institutions

Measured directly, and it settles the Duke/Perkins question:

| institution | total grants | religious-purpose grants | share of dollars |
|---|---:|---:|---:|
| SOUTHERN METHODIST UNIVERSITY | 1,043 / $123.6M | 4 / $0.1M | **0.0%** |
| DUKE UNIVERSITY | 1,203 / $276.3M | 5 / $10.6M | 3.8% |
| TEXAS CHRISTIAN UNIVERSITY | 319 / $24.4M | 0 | 0% |
| THE METHODIST HOSPITAL | 9 / $7.0M | 0 | 0% |
| NEW YORK-PRESBYTERIAN HOSPITAL | 134 / $61.3M | 0 | 0% |

SMU receives $123.6M and **0.0%** of it is religiously directed — but a $20,000
grant "towards the Caren and Vin Prothro Organ for Perkins Chapel" genuinely
is. Duke's $10.6M includes "THRIVING IN MINISTRY INITIATIVE" and an endowed
professorship in the Office of Black Church Studies.

**Proposal: at a `historical`-affiliation institution, surface Christian-directed
grants individually via `grant_purpose` without labelling the institution.**
The anti-over-claim gate already built for Phase 2 does exactly this — Duke is
held at 3.8% while Duke Divinity School (a separate entity, 72.5%) is written.
No new mechanism is required; it needs only to be applied to this class.

### One noise case to handle first

SMU's religious-purpose matches include *"Scholarship for Christian Moyano"* —
**a person's first name**. Word boundaries are correct here and it still
matched, because "Christian" is a legitimate word. Personal-name detection is
needed before grant purpose drives any display at institution level.

## 5. What I recommend

1. **Approve bucket D as `historical`** — 13 recipients, but review Houston
   Christian and Wesleyan College first; I think at least one does not belong.
2. **Leave bucket E alone.** 1,158 recipients / $0.252B fit the pattern but
   there is no evidence of secular operation. Guessing from names is the
   failure mode this project keeps correcting.
3. **Look at Wesleyan University separately** — likely a plain name-rule error
   rather than a mixed case.
4. **Apply the existing grant_purpose gate** to surface sub-unit gifts, after
   adding personal-name filtering.

The honest summary: the class is real, the evidence supports 13 members today,
and the route to more of them is mission text — not a better name heuristic.
