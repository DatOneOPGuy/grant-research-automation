import { Card, CardTitle } from '../components/ui/primitives'

const SECTIONS = [
  {
    title: 'Data Provenance',
    body: [
      'Foundation Explorer is a business-to-business intelligence platform built from public IRS records.',
      'The foundation universe is downloaded directly from all four official IRS EO BMF regions.',
      'Form 990-PF facts are parsed directly from official IRS TEOS XML archives; the ingestion pipeline does not scrape websites.',
    ],
  },
  {
    title: 'Proprietary Analysis',
    body: [
      'Recipient identity, classification evidence, and foundation rollups are generated inside company-controlled infrastructure.',
      'Every published release records source hashes, parser and policy versions, observed tax years, and reconciliation gates.',
    ],
  },
  {
    title: 'Third-Party Boundaries',
    body: [
      'We do not use ProPublica as a backend data source or API.',
      'Outbound links to public ProPublica organization pages are convenience links only. Clicking one leaves Foundation Explorer and contacts that third party directly.',
    ],
  },
  {
    // A vendor that publishes its corrections is the trust wedge the whole
    // product claims. This section is updated whenever an accuracy pass
    // changes published figures; hiding a restatement is how that trust dies.
    title: 'Corrections',
    body: [
      'September 2026: an internal accuracy audit of our own classifications found about $1.7B of giving wrongly presented as Christian, and we corrected it. The error classes: foreign government health ministries matching the word "ministry"; the secular NewYork-Presbyterian hospital system matching "presbyterian"; the town of Chapel Hill matching "chapel"; a Christian Science organization carried by an IRS category code; and one classification method (inferring a recipient\u2019s tradition from a funder\u2019s free-text grant purpose) that was retired entirely until it can pass the same validation gate our other methods pass.',
      'Every correction is recorded in the database itself, per recipient, with the reason \u2014 the same standard of evidence we apply to the classifications we keep. Aggregate Christian-giving figures shown in the product decreased by roughly 15% as a result. If a number matters to your decision, click into it: every figure still traces to specific grants on specific public filings.',
    ],
  },
  {
    title: 'Privacy Boundary',
    body: [
      'Build-time classification of public source records — organization names, EINs, and mission statements from public IRS filings — may use deterministic code and language models, which may include a commercial LLM API.',
      'Customer data — your searches, saved lists, and account activity — is never submitted to any third-party LLM API for classification or training.',
      'The demo stores saved EINs and filter state in browser storage. Its hosting provider processes ordinary requests needed to deliver the site.',
    ],
  },
]

export default function Trust() {
  return (
    <div className="max-w-5xl">
      <div className="flex items-start justify-between gap-6 mb-6">
        <div>
          <h1 className="font-display text-3xl font-semibold text-primary">
            Trust &amp; Data
          </h1>
          <p className="mt-2 text-sm text-muted leading-relaxed max-w-3xl">
            Customer-facing summary of where the data comes from, how it is
            processed, and how Foundation Explorer stays inside its third-party
            boundaries.
          </p>
        </div>
      </div>

      <Card className="mb-4">
        <CardTitle>Source documents</CardTitle>
        <div className="text-sm text-muted">
          Repo-root policy files:
          <span className="ml-2 font-medium text-primary">`TERMS.md`</span>,
          <span className="ml-2 font-medium text-primary">`PRIVACY.md`</span>,
          <span className="ml-2 font-medium text-primary">`DATA-SOURCES.md`</span>
        </div>
      </Card>

      <div className="grid gap-4">
        {SECTIONS.map((section) => (
          <Card key={section.title}>
            <CardTitle>{section.title}</CardTitle>
            <ul className="space-y-2 text-sm text-ink leading-relaxed list-disc pl-5">
              {section.body.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </Card>
        ))}
      </div>
    </div>
  )
}
