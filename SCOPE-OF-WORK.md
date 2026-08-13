# DRAKE'S SOFTWARE SOLUTIONS
## Grant Research Automation — Scope of Work to Date
**Christian Aid Mission · Emily Fitchpatrick**

---

# Phase 1 — Completed · $1,250 · PAID

**The problem:** Instrumentl returned 10,787 foundation matches for Christian
Aid Mission with no way to filter, rank, or analyze them in bulk.

We built a custom data pipeline that matched every foundation to its IRS 990-PF
federal tax filings and analyzed their actual giving history. The deliverable
was a ranked, prioritized spreadsheet that turned weeks of manual research into
a list that could be worked top-to-bottom immediately.

### What the pipeline did

- **Matched 10,787 foundations to IRS federal tax filings** — 98.9% match rate
  using a custom fuzzy name-matching engine
- **Cross-referenced grant history against 53 peer Christian organizations** —
  Samaritan's Purse, World Vision, Wycliffe, CRU, BGEA and others
- **Scanned mission statements and grant descriptions** for faith-based and
  international development keywords
- **Detected application status** — open vs. invite-only, verified with two
  independent parsers
- **Scored every foundation** on Alignment Score (mission fit) and Opportunity
  Score (alignment + grant size)

**Status: complete and delivered. Paid in full.**

---

# Phase 2 — In Progress · $2,000

**The problem:** Phase 1 was limited to Instrumentl's pre-filtered results.
Phase 2 removes that dependency entirely and expands to every active private
foundation in the country.

## Important change: from spreadsheet to software

Phase 2 was originally scoped to deliver *"the same spreadsheet format as Phase
1, with all new columns added."* **It became clear during the build that a
spreadsheet could no longer hold the work.**

The reason is scale and evidence. Phase 1 analyzed 10,787 foundations against a
fixed list of 53 peer organizations. Phase 2 analyzes **3,012,118 individual
grants** to **1,302,051 distinct recipient organizations**. Every one of those
recipients had to be identified and classified, and every classification had to
carry the evidence behind it so it could be checked rather than trusted blindly.

A spreadsheet can show you a score. It cannot show you *why* — and "why" is
what a professional grant researcher actually needs before contacting a funder.

**Phase 2 is therefore delivered as Foundation Explorer, a working web
application**, rather than a spreadsheet. Everything originally promised as
columns is present, plus filtering, evidence drill-down, and export. CSV export
is included, so a spreadsheet can still be produced at any time.

## What was actually built

### The data foundation

| | |
|---|---|
| **123,113** | US private foundations, from all four IRS EO BMF regions |
| **94,984** | of those made grants in the covered window |
| **3,012,118** | individual grants analyzed |
| **$236.4 billion** | in grant dollars, reconciled to the filings |
| **1,302,051** | distinct grant recipients identified and classified |
| **Tax years 2023–2024** | every filing pulled directly from IRS TEOS XML archives |

No Instrumentl. No scraped data. Every figure traces to a signed federal tax
return.

### Faith-based giving detection — built and running

The core Phase 2 promise, delivered. Rather than matching against a fixed peer
list, the system examines every grant a foundation made and asks: *who actually
received this money, and are they Christian organizations?*

**124,352 Christian recipient organizations identified**, accounting for
**$11.47 billion** in Christian giving across the foundation universe.

Each recipient is classified once and reused permanently, exactly as scoped —
once an organization is identified, every foundation that funded it benefits
automatically.

### Classification is evidence-based, not keyword-based

This is the largest expansion beyond the original scope. Every classification
carries a source, and stronger sources override weaker ones:

| Evidence | What it is |
|---|---|
| **Human review** | A correction from your team — overrides everything else |
| **IRS activity codes** | Official NTEE religion codes on the recipient's IRS record |
| **Church registrations** | IRS house-of-worship coding |
| **Denominational group rulings** | A diocese or denomination formally covering the organization |
| **Organization's own mission statement** | Pulled from the recipient's own 990 filing |
| **Organization name** | Weakest tier — used only when nothing better exists |
| **The funder's stated grant purpose** | What the foundation itself said the money was for |

Every classification in the product displays the quoted evidence behind it.

### Honest coverage reporting

Foundation Explorer reports what it *cannot* determine as clearly as what it
can — a deliberate design decision, and the feature most likely to earn a
professional researcher's trust.

- **71.5%** of identifiable giving has been classified
- Where a foundation's filing does not name its recipients — patient-assistance
  programs protected by federal privacy law, foreign foundations not required
  to itemize, or recipient lists filed as PDF attachments — the product says so
  in plain language instead of scoring the foundation as a failure
- **$62.1 billion** falls into that category and is excluded from coverage
  math rather than counted against anyone

### Contact and application data

| Field | Coverage |
|---|---|
| Phone number | 118,782 foundations (96%) |
| Website | pulled from the federal filing |
| Application status | 23,936 accepting applications; invite-only flagged |
| Contact person, address, deadlines, restrictions | where the filing provides them |
| States given to | complete list from actual grant history |
| Annual revenue and assets | from the federal filing |

### The application itself

Eight working pages: Dashboard, Best Prospects, Foundations explorer with
full filtering, Grants, Recipients, Analytics, Data Quality, and Saved lists
with CSV export.

Foundations can be sorted by **% Christian giving**, by absolute Christian
dollars, by total giving, or by typical grant size — and every row can be
opened to see the recipients and the evidence behind the classification.

---

## Accuracy — measured, not asserted

Independent verification work was performed across the full 1.19-million-name
recipient population:

- **99.06% agreement** between classification methods wherever a classification
  can be independently cross-checked
- The mission-statement classifier scores **100% precision** against a frozen,
  hand-labeled 313-organization test set, and is re-tested before every run
  using a planted-error self-test that must fail for the run to proceed
- **Roughly two-thirds of identified Christian giving rests on recipient-name
  evidence alone**, which cannot be independently verified because IRS filings
  frequently provide only a name and a city. The product shows which
  foundations these are rather than hiding the distinction.

### Confidence breakdown across the 94,984 active foundations

| | Foundations | Share |
|---|---:|---:|
| Confident Christian funders (independently verified) | 6,043 | 6.4% |
| Likely Christian (partly verified) | 17,288 | 18.2% |
| Possibly Christian (name evidence only) | 23,002 | 24.2% |
| No Christian giving found | 30,610 | 32.2% |
| Giving could not be classified from the filing | 18,041 | 19.0% |

---

## Corrections to the original Phase 2 scope

Stated plainly so the record is accurate:

- **Foundation count:** the original document said 130,000. The verified count
  of private foundations across all four IRS BMF regions is **123,113**, of
  which **94,984** actually made grants in the window.
- **Tax years:** the original document said 2023, 2024 and 2025. The delivered
  window is **2023–2024**. Tax-year 2025 returns largely do not exist yet at
  the IRS — "2025" in IRS index files refers to the submission year, not the
  tax year.
- **Phone numbers:** originally described as sourced from ProPublica. They are
  sourced **directly from the 990 filings**. ProPublica is used only as an
  outbound convenience link, never as a data source.
- **Giving history depth:** the faith score was described using a six-year
  example. The delivered window is two tax years, which is what the IRS has
  published in machine-readable form for the current cycle. Depth grows with
  each annual refresh.

---

## Work completed beyond the original Phase 2 scope

None of the following was in the original quote. It was built because the
accuracy of the product required it.

- **Recipient identity resolution** — matching 1.3 million messy recipient
  names to real organizations, with ambiguous cases flagged rather than guessed
- **An immutable evidence ledger** — every classification is recorded with its
  method, confidence, source and timestamp, and corrections supersede rather
  than overwrite, so the reasoning is fully auditable
- **Mission-statement classification** — reading recipients' own 990 mission
  text, including recovering text filed in Schedule O that standard parsing
  misses
- **Grant-purpose evidence** — using the funder's own stated purpose for a
  grant as independent confirmation
- **Multiple accuracy audits** — systematic testing that found and fixed real
  classification errors, including a regex fault that had been misclassifying
  animal-welfare charities as evangelical
- **Coverage honesty framework** — the distinction between "not Christian,"
  "we could not classify this," and "the filing never named the recipients"
- **Legal and disclosure documents** — terms of service, privacy policy and
  data-source disclosures

---

## Current status

**Phase 1:** complete, delivered, **paid ($1,250)**.

**Phase 2:** substantially complete and running. The application is live and
usable, the national database is built, and the faith-based giving detector is
operational. Remaining items are refinement rather than construction:

- Contact-data enrichment for the highest-value prospects
- Continued accuracy work on recipients identified by name alone
- An automated annual refresh pipeline

**Invoiced to date: $1,250 of $3,250.** Phase 2 ($2,000) outstanding.

---

drake@drakesdev.com · drakesdev.com · Drake's Software Solutions, LLC
