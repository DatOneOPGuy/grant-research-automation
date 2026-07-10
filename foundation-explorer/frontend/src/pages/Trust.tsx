import { Card, CardTitle } from '../components/ui/primitives'

const SECTIONS = [
  {
    title: 'Data Provenance',
    body: [
      'Foundation Explorer is a business-to-business intelligence platform built from public IRS records.',
      'The foundation universe is derived from the IRS Business Master File.',
      '990-PF filing data is extracted directly from official IRS TEOS XML archives.',
    ],
  },
  {
    title: 'Proprietary Analysis',
    body: [
      'Our classification logic, evidence rollups, and prospecting scores are generated locally inside our own infrastructure.',
      'The compiled database and derived analytics are original outputs of our internal methodology.',
    ],
  },
  {
    title: 'Third-Party Boundaries',
    body: [
      'We do not use ProPublica as a backend data source or API.',
      'Outbound links to public ProPublica organization pages are provided only as a convenience reference for users.',
    ],
  },
  {
    title: 'Privacy Boundary',
    body: [
      'We do not send user payloads or source records to commercial third-party LLM APIs for processing or model training.',
      'The platform is designed to operate within a controlled, company-managed environment.',
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
