import { useQuery } from '@tanstack/react-query'
import { fetchDataQualityV5 } from '../lib/apiV5'
import { money, num, TAX_WINDOW_LABEL } from '../lib/format'
import { Card, CardTitle, Skeleton } from '../components/ui/primitives'

const REASON_LABELS: Record<string, string> = {
  hipaa: 'Individual patients (HIPAA-protected)',
  foreign_4948: 'Foreign private foundation (IRC §4948(b))',
  pdf_attachment: 'Recipient list filed as a PDF attachment',
  not_itemized: 'Recipients not itemized in the filing',
  '(none)': 'Other',
}

function Bar({ value, total }: { value: number; total: number }) {
  const pct = total > 0 ? (value / total) * 100 : 0
  return (
    <div className="h-2 bg-canvas rounded overflow-hidden w-full">
      <div className="h-full bg-primary" style={{ width: `${pct}%` }} />
    </div>
  )
}

export default function DataQuality() {
  const { data } = useQuery({
    queryKey: ['v5quality'], queryFn: fetchDataQualityV5,
  })

  if (!data) {
    return <div><h1 className="font-display text-3xl font-semibold
      text-primary mb-4">Data Quality</h1><Skeleton className="h-96" /></div>
  }

  const t = data.totals
  const contactFields: [string, number][] = [
    ['Phone', t.with_phone], ['Website', t.with_website],
    ['Contact person', t.with_contact_person], ['Email', t.with_email],
  ]

  return (
    <div>
      <h1 className="font-display text-3xl font-semibold text-primary mb-1">
        Data Quality
      </h1>
      <p className="text-sm text-muted mb-4">
        What we know, what we don’t, and why. Paid grants, tax years{' '}
        {TAX_WINDOW_LABEL}.
      </p>

      <Card className="mb-4">
        <CardTitle>Where the dollars stand</CardTitle>
        <p className="text-xs text-muted mt-1 mb-3">
          Coverage is measured against {money(t.classifiable)} of giving to
          identifiable organizations — not against the {money(t.paid)} total,
          because {money(t.nonclassifiable)} was never attributed to an
          organization by the filing itself.
        </p>
        <table className="w-full text-sm">
          <tbody>
            {([
              ['Classified Christian', t.christian],
              ['Classified non-Christian', t.nonchristian],
              ['DAF / pass-through', t.daf],
              ['Classifiable, not yet classified', t.unclassified],
              ['Not attributable per the filing', t.nonclassifiable],
            ] as [string, number][]).map(([label, v]) => (
              <tr key={label} className="border-b border-line/60">
                <td className="py-2 pr-3">{label}</td>
                <td className="text-right tabular pr-3 whitespace-nowrap">
                  {money(v)}
                </td>
                <td className="text-right tabular pr-3 text-muted w-16">
                  {((v / t.paid) * 100).toFixed(1)}%
                </td>
                <td className="w-40"><Bar value={v} total={t.paid} /></td>
              </tr>
            ))}
            <tr className="font-medium">
              <td className="py-2">Total paid</td>
              <td className="text-right tabular pr-3">{money(t.paid)}</td>
              <td /><td />
            </tr>
          </tbody>
        </table>
      </Card>

      <div className="grid md:grid-cols-2 gap-4 mb-4">
        <Card>
          <CardTitle>Coverage bands</CardTitle>
          <table className="w-full text-sm mt-2">
            <tbody>
              {data.coverage_bands.map((b) => (
                <tr key={b.coverage_band} className="border-b border-line/60">
                  <td className="py-2">{b.coverage_band}</td>
                  <td className="text-right tabular pr-3">
                    {num(b.foundations)}
                  </td>
                  <td className="text-right tabular text-muted">
                    {money(b.paid)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-xs text-muted mt-2">
            “Not Classifiable” means the filing named no recipients we could
            attribute — it is not a gap in our work.
          </p>
        </Card>

        <Card>
          <CardTitle>Why dollars are unattributable</CardTitle>
          <table className="w-full text-sm mt-2">
            <tbody>
              {data.unattributable_reasons.map((r) => (
                <tr key={r.reason} className="border-b border-line/60">
                  <td className="py-2 pr-2">
                    {REASON_LABELS[r.reason] || r.reason}
                  </td>
                  <td className="text-right tabular pr-3 whitespace-nowrap">
                    {num(r.foundations)}
                  </td>
                  <td className="text-right tabular text-muted
                    whitespace-nowrap">{money(r.dollars)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>

      <div className="grid md:grid-cols-2 gap-4 mb-4">
        <Card>
          <CardTitle>Recipient identity resolution</CardTitle>
          <table className="w-full text-sm mt-2">
            <tbody>
              {data.identity.map((r) => (
                <tr key={r.identity_status} className="border-b border-line/60">
                  <td className="py-2 capitalize">
                    {r.identity_status.replace('_', ' ')}
                  </td>
                  <td className="text-right tabular pr-3">
                    {num(r.recipients)}
                  </td>
                  <td className="text-right tabular text-muted">
                    {money(r.dollars)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>

        <Card>
          <CardTitle>Classification evidence by method</CardTitle>
          <p className="text-xs text-muted mt-1 mb-2">
            Deterministic methods outrank mission-text inference, so a
            model-derived label never overrides IRS-derived evidence.
          </p>
          <table className="w-full text-sm">
            <tbody>
              {data.methods.map((m) => (
                <tr key={m.method} className="border-b border-line/60">
                  <td className="py-2">{m.method}</td>
                  <td className="text-right tabular">{num(m.recipients)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>

      <Card>
        <CardTitle>Contact-field coverage</CardTitle>
        <p className="text-xs text-muted mt-1 mb-2">
          Across all {num(t.foundations)} foundations. Email is inherently thin
          — most 990-PF filings do not include one.
        </p>
        <table className="w-full text-sm">
          <tbody>
            {contactFields.map(([label, v]) => (
              <tr key={label} className="border-b border-line/60">
                <td className="py-2">{label}</td>
                <td className="text-right tabular pr-3">{num(v)}</td>
                <td className="text-right tabular pr-3 text-muted w-16">
                  {((v / t.foundations) * 100).toFixed(0)}%
                </td>
                <td className="w-40"><Bar value={v} total={t.foundations} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  )
}
