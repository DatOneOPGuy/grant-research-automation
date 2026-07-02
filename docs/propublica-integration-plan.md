# Christian Foundation Database — ProPublica Integration Plan

**Status: BUILT (2026-07-02).** All Phase 2 modules implemented and
verified against the on-disk test bed. Outstanding: full-universe XML
download (~30 GB, blocked on disk space), ProPublica gap-fill sweep
(~4.7 h throttled), LLM classification pass (needs ANTHROPIC_API_KEY).
Universe correction: the true "130k" is all private foundations on the
BMF (139,965); NTEE-T alone covers only 61k of them.

Source spec: `Christian Foundation Database (2).docx` (client doc, four
steps). Goal: a national database of **private foundations only**, scored
for Christian-donor alignment, with application/contact info per foundation.

**Year scope: tax years 2023, 2024, and 2025 only. Do not go earlier than
2023.** (Current pipeline covers 2023–24; add the 2025 e-file index.)

---

## Phase 1 — what is already built (initial work)

The existing pipeline, built and verified against tax years 2023–2024:

1. **IRS data acquisition**: pulled the IRS 990 e-file indexes, filtered to
   Form 990-PF (private foundations), downloaded ~20,600 full XML filings
   (`downloader.py`, `download_xmls.py`).
2. **Structured parsing**: every filing parsed into a SQLite database
   (`parser.py`) — foundation header (name, city, state, assets,
   distributions), the complete Part XV grant list (recipient name,
   city/state/country, foreign flag, amount, purpose), and charitable
   activity descriptions.
3. **Grantee fingerprint matching** (`matcher.py`, `config.py`): fuzzy
   matching with name normalization, abbreviation expansion, and a manual
   alias map against 53 target Christian organizations (Samaritan's Purse,
   World Vision, Cru, Wycliffe, YWAM, …).
4. **Opportunity scoring** (`scorer.py`): weighted score — grantee matches
   35%, Christian keywords 30% (3 clusters: religious identity, mission/
   outreach, geography), international giving 25%, focus area 10%, with a
   recency multiplier — producing the ranked ~10,800-row match CSVs.
5. **Invite-only detection**: 990-PF Part XIV line 2
   (`OnlyContriToPreselectedInd`) extracted per foundation
   (`extract_inviteonly.py`) and independently verified against the raw
   XMLs with a second, separate parser (`verify_inviteonly.py`) — the
   "Invite Only" / "Not Invite Only" column in `inviteonlyvalues.csv`.

## Phase 2 — what this plan adds

1. **Full national universe**: from ~10.8k matched rows to the ProPublica
   "Philanthropy, Voluntarism and Grantmaking Foundations" 130k, filtered
   to private foundations only (~110k active). Rebuilt locally from the
   IRS BMF (NTEE group T ∩ 990-PF filers); DAFs drop out automatically.
2. **2025 filings** added alongside 2023–24 (year floor stays at 2023).
3. **New contact/qualification columns per foundation**: website, phone,
   ProPublica profile link, invite-only vs accepting-applications, and for
   accepting foundations the Part XIV 2a–2d block — contact person &
   address (& email when present), application format, deadlines,
   restrictions.
4. **New financial/footprint columns**: total revenue (990-PF Part I line
   12) and the list of all states the foundation has given to across its
   filings.
5. **Faith-Based Giving Detector**: classify every grant recipient once
   into faith categories (recipient knowledge base + tag inheritance),
   then compute a dollar-weighted, evidence-based Faith Alignment Score
   per foundation with the client's weights and tiers.
6. **Expanded Christian search criteria**: denominations, theological
   vocabulary, NTEE X-codes, and a larger grantee fingerprint list —
   demoted to secondary signals behind actual giving history.
7. **ProPublica API gap-filler** for paper filers with no e-file XML.

## Existing infrastructure → Phase 2 leverage

| Component | What it does today | How it carries Phase 2 |
|---|---|---|
| `downloader.py` / `download_xmls.py` | Pulls IRS index CSVs per year, then streams the monthly TEOS zips and extracts **only** target filings by OBJECT_ID; skips files already on disk (resumable); reports missing EINs | Scaling to 130k is a bigger target list, not new code: swap the matches-derived EIN list for the BMF universe list, add the 2025 zip URLs. Selective extraction means we never store the full multi-hundred-GB IRS dump |
| `parser.py` | Namespace-tolerant 990-PF XML → SQLite (`foundations`, `grants`, `charitable_activities`, indexed) | Every new field (website, phone, 2a–2d, revenue) is one more XPath in the same parse pass. `states_given_to` is a `GROUP BY` over the `grants` table that already stores recipient state. The grants rows (name + purpose + amount + year) are exactly the input the Faith-Based Giving Detector classifies |
| `matcher.py` | Name normalization, abbreviation expansion, FKA/DBA stripping, alias map, fuzzy match with geo tiebreak | Reused verbatim to dedupe grant recipients into the recipient knowledge base — same messy-990-name problem. Tag inheritance ("classify Billy Graham once") only works if name variants collapse to one canonical recipient, which is precisely what this module does |
| `scorer.py` | Component-based scoring (grantee/keyword/international/focus) with config-driven weights, cluster bonuses, recency multiplier | The Faith Alignment Score drops in as a new component set in the same framework: weights in `config.py`, one function per component, same output writer |
| `extract_inviteonly.py` + `verify_inviteonly.py` | Parallel (ProcessPoolExecutor) Part XIV line 2 extraction, plus an **independent second parser** that verifies a random sample | Line 2 logic folds into `parser.py`; the dual-parser verification pattern becomes the QA template for every new extracted field (2a–2d, revenue) at 110k scale |
| `config.py` | Centralized keywords, aliases, weights, years, paths | Expanded Christian criteria, new score weights, and the 2025 index year are config edits, not architecture changes |
| Data on hand | 20.6k parsed XMLs + populated `grants.db` | A free development test bed: build and validate every Phase 2 feature against real filings before paying for the full-country download |

---

## Universe definition: the ProPublica 130k, private foundations only

The starting universe is exactly what the client checks in ProPublica's
search UI: **Nonprofit Category = "Philanthropy, Voluntarism and Grantmaking
Foundations" (130K)**. That category is NTEE major group **T**, and
ProPublica derives it from the IRS Business Master File (BMF) — so we can
reproduce the same 130k list locally without scraping (ProPublica's search
API caps paging well below 130k, so the site itself can't be bulk-harvested).

Build steps:

1. **Download the IRS BMF** (free CSVs, updated monthly) and filter
   `NTEE_CD` starting with `T` → the same ~130k orgs the UI shows.
2. **Private foundations only** (per client): keep BMF `FOUNDATION` codes
   02/03/04 (private operating/non-operating foundations) and/or EINs that
   file **Form 990-PF** — the definitive private-foundation marker. This
   drops the public charities, community foundations, and DAF sponsors that
   share category T.
3. **DAF exclusion (~1.1k)** is automatic once we require 990-PF: DAF
   sponsoring orgs are public charities filing Form 990, so none survive
   step 2.
4. **Active only (~110k)**: being listed in the current BMF already means
   IRS-recognized/active; additionally flag foundations whose latest 990-PF
   is older than 3 tax years as `stale` rather than deleting them.

Every org in the final list carries its ProPublica profile link, so the
client can click through to the exact pages they browse today.

## Step 2 — Part XIV analysis (application info)

Part XIV line 2 checked = invite-only ("contributes only to preselected
organizations") → client must call first. Not checked = accepting
applications, and the foundation fills in lines 2a–2d, which live in the
XML under `ApplicationSubmissionInfoGrp` (verified in our raw files):

| Line | Field | XML element |
|---|---|---|
| 2 | Invite-only flag | `OnlyContriToPreselectedInd` (already extracted by `extract_inviteonly.py`) |
| 2a | Contact person | `RecipientPersonNm` + `RecipientUSAddress` + `RecipientPhoneNum` (+ `RecipientEmailAddressTxt` when present) |
| 2b | Application format | `FormAndInfoAndMaterialsTxt` |
| 2c | Deadlines | `SubmissionDeadlinesTxt` |
| 2d | Restrictions | `RestrictionsOnAwardsTxt` |

Coverage in current 20.6k raw XMLs: ~21% have the 2a–2d block, ~5% include
an email. That's expected — invite-only foundations skip 2a–2d, so line 2
and the application block are complementary: every foundation ends up
either `Invite Only (call first)` or `Accepting Applications` with contact
person / format / deadlines / restrictions columns.

The 2a phone (`RecipientPhoneNum`) is the **application contact's** phone —
better than a generic number. Fallbacks for the phone column, in order:
2a `RecipientPhoneNum` → header `Filer/PhoneNum` (present in nearly every
filing) → blank.

## Step 3 — Website discovery

1. First source: `WebsiteAddressTxt` from the 990-PF header (present in
   most filings; normalize `N/A`/`NONE` to blank).
2. For foundations with no usable value: a web-search pass (name + city +
   "foundation") — batched, cached, and run only for foundations above a
   score threshold so we don't search 100k shell foundations with no web
   presence. Most small family foundations genuinely have no website.

Note: ProPublica's API exposes **neither website nor phone** (verified
against API v2 docs) — both must come from the 990 XML, matching the
client's "or from 990" instruction.

## Step 4 — Faith-Based Giving Detector (flagship)

Classify what a foundation actually *funds*, not what its name sounds like.
The client doc's architecture is sound and matches how our pipeline already
stores data (a `grants` table with recipient name/city/state/amount/purpose):

1. **Recipient knowledge base** (new table `recipients`): one row per
   distinct grantee (normalized name — reuse the existing normalization/
   alias machinery in `matcher.py`), with category tags + confidence.
   Classify each recipient **once**; every foundation that ever gave to it
   inherits the tags. Seed it with the client doc's table (Samaritan's
   Purse, Wycliffe, FCA, Compassion, Catholic Charities, Prison Fellowship,
   Cru, YWAM, Joshua Fund, WorldVenture, …) plus our 53 target orgs.
2. **Classification**: batch LLM calls (Claude API) returning JSON tags
   from the fixed vocabulary: Christian Ministry, Church, Bible
   Translation, Evangelism, Church Planting, Pregnancy Center, Christian
   School, International Missions, Disaster Relief, Jewish Ministry,
   Faith-Based Education, Rescue Mission, Youth Ministry, Medical Missions,
   plus non-faith tags (Human Trafficking, Homelessness, Food Security,
   Agriculture) so secular giving is measured too. Confidence 0–100; only
   tags ≥ 70 count toward scoring.

   **$5,000 classification threshold.** LLM-classify a recipient only if
   it received at least one $5,000+ grant (equivalently: max grant ≥ $5k
   across the dataset); treat sub-threshold grants as noise. Measured on
   the current 963k parsed grants: 46.9% of grant rows are under $5k but
   carry only **0.6% of total dollars**, and the threshold cuts distinct
   recipient names to classify from ~334k to ~189k (before normalization
   dedups further). Since the score is dollar-weighted, the accuracy cost
   is bounded at well under a point. Two carve-outs keep the blind spot
   negligible:
   - **Rule-based tags still apply to all grants** regardless of size —
     name patterns like "…Baptist Church…", "…Ministries…", "…Catholic…"
     cost nothing, so a small family foundation giving $2k each to ten
     churches still registers as a strong Christian funder.
   - **Knowledge-base inheritance applies to all grants** — once a
     recipient is classified (from anyone's $5k+ grant), sub-threshold
     grants to it inherit the tags for free.
   Unclassified sub-threshold dollars stay in the total-giving
   denominator as neutral (no faith evidence either way).
3. **Unknown recipients**: name + grant purpose usually suffices; for
   ambiguous ones ("Hope for Tomorrow Ministries") add IRS BMF/ProPublica
   lookup by name, then classify. Defer web-search enrichment to a later
   pass, again gated by foundation score.
4. **Faith Alignment Score** (per foundation, client's weights):

   | Component | Weight |
   |---|---|
   | Gives to explicitly Christian organizations | 40% |
   | Gives to churches or denominations | 15% |
   | Funds missions / international ministry | 15% |
   | Funds evangelism / church planting | 10% |
   | Funds Christian education | 10% |
   | Consistent faith-based giving (every available year) | 10% |

   Each component is dollar-weighted (% of total giving, not grant count)
   and computed over the available tax years. Tiers: 95–100 Dedicated
   Christian Funder / 80–94 Strong / 60–79 Regular / 40–59 Occasional /
   <40 No Significant Pattern. Also render the ★1–5 display variant.
   Every score traces back to actual grants on the 990-PF — transparent
   and auditable, per the client doc.

   Year scope is fixed at **2023–2025** (client instruction: do not go
   earlier than 2023), so the client doc's "5+ years" consistency
   component becomes "faith-based giving in every available year
   (2023, 2024, 2025)" — max 3 data points per foundation.

5. Keyword matching (existing `scorer.py` clusters, expanded with
   denominations/theological vocabulary) becomes a **secondary signal** for
   foundations with thin grant history; grant-recipient evidence always
   outranks name keywords. NTEE X20/X21/X22 codes (via ProPublica lookup)
   remain a useful tertiary signal.

## Per-foundation output columns (new)

`website`, `phone`, `application_status` (Invite Only / Accepting
Applications), `contact_person`, `contact_address`, `contact_email`,
`application_format`, `deadlines`, `restrictions`, `revenue`,
`states_given_to`, `faith_alignment_score`, `faith_tier`,
`faith_categories`, `christian_giving_pct`, `years_of_faith_giving`,
`propublica_url`, `active`.

- **`revenue`**: 990-PF Part I line 12 total revenue —
  `TotalRevAndExpnssAmt` in the XML (present in ~86% of current raw
  filings; ProPublica filing field `totrevenue` as fallback). Take the
  latest tax year's value.
- **`states_given_to`**: distinct recipient states across all of the
  foundation's parsed grants (2023–2025), sorted, semicolon-joined — a
  single aggregation over the existing `grants` table
  (`SELECT DISTINCT state ... GROUP BY ein`). Foreign giving already has
  its own flag/country field.

`propublica_url` is pure string formatting — no API call:
`https://projects.propublica.org/nonprofits/organizations/{EIN}`.

## ProPublica's actual role

- **Profile link column** on every row (derived from EIN).
- **Gap-filler** for paper filers with no e-file XML: org lookup
  `GET /api/v2/organizations/{ein}.json` (free, no key; throttle ~1 req/s,
  cache to disk). Emit name/city/state/EIN/link with `data_found = No`.
- **NTEE codes** for the tertiary Christian signal and active/defunct hints.

Everything else — invite-only flag, 2a–2d contact info, phone, website,
grants for the giving detector — comes from the IRS 990-PF XMLs directly.

## Implementation order (when we wire it in)

1. **Parser fields**: website, phone, invite-only, 2a–2d → `parser.py` +
   schema; backfill from the existing 20.6k XMLs. Fold in
   `extract_inviteonly.py`.
2. **ProPublica link + new columns** in the CSV writer.
3. **Full-country download**: build the universe list (BMF NTEE-T ∩
   private foundations, ~130k → ~110k active), pull each EIN's 990-PF XMLs
   from the 2023–2025 e-file indexes (add 2025 to `IRS_YEARS`), parse
   (keep `active`/`stale` flag logic here).
4. **Recipient knowledge base + classifier**: rule-tag obvious names, seed
   known orgs, LLM-classify the rest, dollar-weighted Faith Alignment Score.
5. **ProPublica API gap-filler + NTEE enrichment** (only runtime API usage).
6. **Website discovery fallback** for high-scoring foundations without
   `WebsiteAddressTxt`.

Misc: `Ethos360` in `config.py` is almost certainly a typo for **Ethnos360**
(formerly New Tribes Mission) — fix during step 4 seeding.
