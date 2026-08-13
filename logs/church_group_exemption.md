# Church group-exemption resolution — Step 2

_2026-08-13. Read-only. **Nothing was written.** The method does not clear its
gate on volume, and I stopped before production rather than writing 262 rows
and calling it a structural unlock._

## Verdict: the premise is largely false

The mechanism is sound and the guardrails work. The **data isn't there**.

Of 48,882 unresolved church recipients that carry usable geography, exactly
**262 (0.5%) match a BMF group-ruling subordinate** on name + city + state.
**48,558 (99.3%) have no match at all.**

The reason is structural, and it is the point of a group exemption: the parent
files on behalf of its subordinates, and the subordinate congregations are
frequently **not enumerated in the public BMF**. There are 397,020 subordinates
in the BMF against a US congregation population several times larger. The
churches we most need to resolve are precisely the ones a group ruling excuses
from individual listing.

## Step A — the opportunity

| measure | count | dollars |
|---|---:|---:|
| unresolved / collision recipients | 832,465 | — |
| church-pattern (word-boundary matched) | 62,641 | $2.566B |
| …with city + state on a grant | 48,882 | — |
| …without geography (cannot be matched safely) | 13,759 | — |

Word boundaries throughout; no `LIKE '%church%'`.

**Most of this population is already classified.** Of the 62,641:

| current | recipients | dollars |
|---|---:|---:|
| evangelical_protestant | 30,203 | $1,327.2M |
| catholic | 15,043 | $621.2M |
| unclassified | 10,159 | $300.8M |
| christian_unspecified | 3,599 | $157.3M |
| jewish | 2,097 | $72.8M |

So even a perfect church-resolution pass would mostly be **corroborating**
existing name-rule verdicts, not producing new ones. The genuinely
unclassified slice is $300.8M, and only a fraction of that is matchable.

## Step B — matching measured

| outcome | recipients | dollars |
|---|---:|---:|
| **unique** name+city+state match to a subordinate | **262** | **$26.4M** |
| ambiguous (several subordinates share the key) | 62 | — |
| no match in the BMF subordinate pool | 48,558 | — |

Of the 262: **234 are already classified** ($20.8M) and **28 are unclassified**
($5.6M).

I did not build an elaborate gold set. Exact normalized-name + exact-city +
exact-state matching against a group-ruling subordinate is inherently
high-precision — the Step 1 failure mode was loose *token containment*, not
exact triple matching. But the honest reason is simpler: **a validation
apparatus for 262 rows worth $26.4M, of which $5.6M is new information, is not
a good use of the gate.** The number that decides this is volume, not
precision.

## The tradition-inheritance trap fired, exactly as anticipated

The **single largest match is CHURCH OF SCIENTOLOGY INTERNATIONAL ($4.6M)**
under GEN 4168 — 17% of all matched dollars.

Had tradition been inherited from "member of a church group ruling", this
method's biggest single result would have classified Scientology as Christian.
The guardrail you specified — verify the parent's actual tradition, never treat
a group ruling or foundation code 10 as automatically Christian — is not
hypothetical. It is load-bearing on the top row.

Dominant parent rulings among the 262:

| GEN | subs | dollars | parent |
|---|---:|---:|---|
| 0928 | 97 | $12.2M | UNITED STATES CATHOLIC CONFERENCE |
| 2029 | 7 | $1.2M | CHILD EVANGELISM FELLOWSHIP INC |
| 8534 | 7 | $0.6M | PRESBYTERIAN CHURCH IN AMERICA |
| 2573 | 8 | $0.4M | GENERAL COUNCIL ON FINANCE & ADMIN OF THE UNITED METHODIST CHURCH |
| 9386 | 12 | $0.1M | EVANGELICAL LUTHERAN CHURCH IN AMERICA |
| **4168** | — | **$4.7M** | **CHURCH OF SCIENTOLOGY INTERNATIONAL — do NOT inherit** |

The Catholic Conference ruling (GEN 0928) is the only parent with meaningful
volume, and its tradition is unambiguous.

## Step C — not run

The gate I would apply is not precision but materiality. **262 rows / $26.4M,
with $5.6M of new classification signal, against a $4.33B identity-blocked
blind spot, is 0.13% of the problem.** Writing it would add ledger churn, a
new provenance path and an audit surface for a rounding error.

If you want it anyway, the safe subset is well defined: the ~97 Catholic
Conference subordinates plus the mainline Protestant rulings, geography
required, Scientology and any ambiguous parent excluded from tradition
inheritance. Say so and I will run exactly that.

## Honest remainder

| bucket | recipients | note |
|---|---:|---|
| no BMF subordinate match | 48,558 | the group ruling covers them without listing them |
| no geography on any grant | 13,759 | cannot be safely matched by any method |
| ambiguous key | 62 | several subordinates share name+city+state |

These stay `unresolved` and name-only. They are flagged, not guessed, and their
dollars still reconcile.

## What this means for the identity sequence

Three of three identity methods have now come in far below their premise:

1. **Filer-provided EINs** — the field does not exist. $0.
2. **Alias tranche 2** — $5.78B safely recoverable, not $14B; 63.5% of the
   parked proposals were wrong.
3. **Church group exemption** — $26.4M, not a structural unlock.

The consistent finding is that **the identity blind spot is not blocked by
insufficient matching effort. It is blocked by source data that never made
these recipients determinable.** A 990-PF names a recipient and a city; if that
organisation does not appear individually in the BMF, no amount of matching
against the BMF will find it.

I would stop treating identity as a recoverable-by-effort problem and instead
treat the unresolved pool as permanently name-only — which is what the
`unresolvable_structural` partition already encodes for 502,760 of them.
