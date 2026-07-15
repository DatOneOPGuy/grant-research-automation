# Data Sources and Methodology

Foundation Explorer is a B2B research product built from publicly available
United States federal tax-exempt-organization records.

## Official Sources

1. **IRS Exempt Organization Business Master File (EO BMF).** We download all
   four official regional CSV files directly from `irs.gov`. The BMF establishes
   the organization universe and supplies EIN, legal name, location, foundation
   code, filing requirement, tax period, and NTEE classification where present.
2. **IRS Tax Exempt Organization Search (TEOS) XML archives.** We download
   machine-readable Form 990-PF returns directly from official IRS archives.
   These filings supply foundation profiles, qualifying distributions,
   application information, and grant schedules.

The ingestion pipeline does not scrape websites. It does not use ProPublica or
another nonprofit aggregator as a data source.

## Processing Method

- Each XML source is retained with its IRS object ID, SHA-256 digest, return
  type, tax year, return timestamp, amendment indicator, parser version, and
  source path.
- Only Form 990-PF returns enter the private-foundation dataset.
- One canonical filing is selected deterministically for each EIN and tax year.
  Superseded and amended filings remain auditable rather than being deleted.
- Paid grants and grants approved for future payment are stored separately.
  Customer giving metrics use only positive, canonical, paid-grant rows.
- Recipient identity uses reported EIN where available, then conservative
  name-and-location matching against the complete EO BMF. Ambiguous matches are
  flagged rather than forced.
- Classification evidence is immutable and versioned. Evidence can come from
  IRS NTEE codes, deterministic rules, documented human review, or a named local
  model run. Conflicts remain unresolved until a release policy can resolve them.
- Customer verdicts are backed by the actual reported recipients, amounts, and
  years. They are research aids, not guarantees of current eligibility or fit.

The current release window is tax years 2023-2024. A later filing year is not
represented until source returns for that year have been ingested and pass the
same release gates.

## ProPublica Boundary

Foundation Explorer does not call the ProPublica Nonprofit Explorer API, ingest
its data, or scrape its pages. A foundation record may contain an ordinary
outbound hyperlink to a public ProPublica organization page as a convenience.
Following that link leaves Foundation Explorer and is governed by the third
party's own terms and privacy practices.

## Ownership

Underlying IRS facts remain public records. Foundation Explorer claims rights
only in its original software, database selection and arrangement, identity
resolution, classification evidence, derived analytics, release manifests, and
presentation. Copyright and database-right questions should be evaluated by
qualified counsel for each distribution jurisdiction.
