# Foundation Explorer — Lifetime License

**Draft term sheet. Not legal advice.** This describes the commercial shape of
the offer in plain language. Have a lawyer convert it into an executable
agreement before it goes to a customer.

---

## 1. What the customer gets

A **perpetual, non-transferable licence** for one organisation to use
Foundation Explorer for internal prospect research, for as long as the product
is operated, in exchange for a single up-front fee.

The licence covers:

| | Included |
|---|---|
| **Software access** | Full use of the Explorer — search, filters, evidence view, saved lists, CSV export |
| **The compiled database** | ~124,000 US private foundations, their grants, recipient identities and classification evidence |
| **Annual data refresh** | One full data rebuild per calendar year, at no additional charge (see §3) |
| **Support** | Named-contact support during business hours (see §4) |
| **Product updates** | Improvements, corrections and new features released to all licensees |

## 2. What it does not cover

- **Redistribution or resale.** The compiled database and derived analysis may
  not be resold, republished, sub-licensed or shared outside the licensed
  organisation. IRS source facts are public; our compilation, identity
  resolution and classification evidence are not.
- **Additional seats or entities.** The licence covers one organisation. A
  parent, subsidiary or affiliate needs its own licence.
- **Custom development, bespoke data pulls, or consulting.** Quoted separately.
- **Guaranteed funding outcomes.** This is a research tool (see §6).

## 3. Annual data maintenance — what "refreshed each year" actually means

Once per calendar year the licensee receives a full rebuild:

1. **New IRS filings ingested.** Foundations file on staggered schedules and
   the IRS publishes continuously, so each year's rebuild adds filings that did
   not exist at the previous release.
2. **The tax-year window rolls forward.** The current release covers **tax
   years 2023–2024**. Each refresh advances that window.
3. **The foundation universe is re-pulled** from the IRS Business Master File,
   picking up newly formed foundations and removing terminated ones.
4. **Identity resolution and classification are re-run**, so accuracy
   improvements since the previous release apply to the whole database.
5. **A release manifest is issued** recording source files, versions, observed
   tax years and reconciliation checks, so the licensee can see exactly what
   changed.

**Timing.** Refreshes target a consistent annual month, announced at least 30
days ahead. IRS publication delays are outside our control and may shift a
release; we will communicate a revised date rather than ship an incomplete
rebuild.

**What we do not promise.** We cannot promise that a specific foundation's most
recent return will be present, because that depends on when the foundation
files and when the IRS publishes. Late filers arrive continuously and some
organisations file many months after their year end.

## 4. Support

- **Channel:** email to a named support address, plus scheduled calls for
  onboarding and after each annual refresh.
- **Hours:** business hours, US Eastern, excluding public holidays.
- **Response targets:** one business day for normal questions; same business
  day for the product being unreachable.
- **Included:** onboarding and training for the licensed team, help
  interpreting classification evidence and coverage figures, investigation of
  suspected data errors, and correction of confirmed errors in the next
  release or sooner where practical.
- **Not included:** grant-writing services, prospect strategy, or research
  performed on the customer's behalf.

## 5. Error reporting and correction

If the licensee believes a classification or foundation record is wrong, we
will investigate and, where confirmed, correct it. Corrections enter the
evidence ledger with provenance and are visible in the next release.

This matters more than it sounds: the classification model is built on evidence
tiers, and a domain expert's correction enters at the highest priority tier —
it overrides automated evidence rather than competing with it.

## 6. Accuracy: what is warranted and what is not

The licensee should read this section before signing.

**Warranted.** Foundation and grant dollar figures are transcribed from IRS
Form 990-PF filings and reconcile to those filings.

**Not warranted.** Religious classification of grant recipients is *derived
research output*, not an official determination. Specifically:

- Classifications rest on tiered evidence — IRS activity codes, denominational
  group rulings, organisations' own mission statements, recipient names, and
  funders' stated grant purposes.
- Where a classification can be independently cross-checked, methods agree
  approximately **99%** of the time.
- However, roughly **two-thirds of identified Christian giving rests on
  recipient-name evidence alone**, which cannot be independently verified,
  because the IRS filing frequently provides only a name and a city.
- The product displays the evidence and coverage behind every figure. The
  licensee is expected to use that, and to verify before outreach.

**No guarantee** that any foundation will accept, review or fund a request.

## 7. Term, and the honest limits of "lifetime"

The licence is perpetual for the licensee. It is bounded by the realities of
the product and the source data:

- **If the product is discontinued**, the licensee receives a final data export
  in a portable format and a minimum of 90 days' notice. A perpetual licence
  cannot promise perpetual operation of a service.
- **If the IRS materially changes** what it publishes, the format it publishes
  in, or its availability, the refresh scope may change. We will describe any
  such change rather than silently reduce coverage.
- **Support and refresh obligations run with the operating entity.** If the
  business is sold, obligations transfer to the acquirer.

## 8. Fees

A single up-front licence fee. No recurring subscription, no per-refresh
charge, no per-seat charge within the licensed organisation.

Fee to be inserted.

## 9. Governing terms

This licence incorporates the published `TERMS.md`, `PRIVACY.md` and
`DATA-SOURCES.md`. Where this document and those conflict, this document
governs for the licensee.

---

## Note to Drake — read before sending this out

Three things worth deciding first. None of them block the document; they change
what you are promising.

**1. The annual refresh pipeline does not exist yet.** Everything in the
database today is a one-off build. There is no scheduled job that pulls the
monthly BMF, ingests new filings, re-scores and re-exports. §3 commits you to
doing that every year, forever, for a single payment. Build it before you sign
anything with §3 in it — it is the same recommendation from the earlier
strategy review, and this licence turns it from "important" into "contractual".

**2. Lifetime pricing and perpetual obligation point in opposite directions.**
A one-time fee against an unbounded annual cost gets worse every year. The
customer's second refresh is pure cost to you. Consider either a lifetime
software licence with data maintenance sold separately as an annual
subscription, or a materially higher lifetime price that funds the ongoing
work. Your partner's $2,000/year instinct is a *subscription* number; the
lifetime equivalent is not $2,000.

**3. §6 is deliberately blunt.** It states the two-thirds name-only figure
explicitly. That is uncomfortable in a sales document and I would keep it: it
is accurate, the product already shows it on screen, and a domain expert will
discover it herself in the first week. Disclosing it up front is what makes the
rest of the accuracy claim credible.
