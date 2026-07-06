import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../lib/api'
import { money, num } from '../lib/format'
import { Card, CardTitle, Skeleton } from '../components/ui/primitives'

function CoverageBar({ label, value, total }: {
  label: string; value: number; total: number
}) {
  const pct = total ? (value / total) * 100 : 0
  return (
    <div className="mb-3">
      <div className="flex justify-between text-sm mb-1">
        <span>{label}</span>
        <span className="tabular text-muted">
          {num(value)} ({pct.toFixed(1)}%)
        </span>
      </div>
      <div className="h-2 bg-line/50 rounded-full overflow-hidden">
        <div className="h-full bg-primary rounded-full"
          style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export default function DataQuality() {
  const { data } = useQuery({
    queryKey: ['dq'],
    queryFn: () => apiGet<any>('/api/analytics/data-quality'),
  })

  if (!data) return <Skeleton className="h-96" />
  const u = data.universe
  const p = data.pipeline

  return (
    <div>
      <h1 className="font-display text-3xl font-semibold text-primary mb-6">
        Data Quality
      </h1>

      <div className="grid grid-cols-2 gap-4 mb-6">
        <Card>
          <CardTitle>Field coverage (of {num(u.total)} foundations)</CardTitle>
          <CoverageBar label="Has 2023–2025 filing" value={u.with_filings}
            total={u.total} />
          <CoverageBar label="Application status known" value={u.with_status}
            total={u.total} />
          <CoverageBar label="Phone" value={u.with_phone} total={u.total} />
          <CoverageBar label="Revenue" value={u.with_revenue}
            total={u.total} />
          <CoverageBar label="Faith score" value={u.scored} total={u.total} />
          <CoverageBar label="States-given-to" value={u.with_states}
            total={u.total} />
          <CoverageBar label="Website" value={u.with_website}
            total={u.total} />
          <CoverageBar label="Contact person" value={u.with_contact}
            total={u.total} />
          <CoverageBar label="Contact email" value={u.with_email}
            total={u.total} />
        </Card>
        <div className="space-y-4">
          <Card>
            <CardTitle>Pipeline reconciliation</CardTitle>
            <table className="w-full text-sm">
              <tbody>
                {[
                  ['Foundation filings parsed', num(p.foundation_filings)],
                  ['Grants parsed', num(p.grants)],
                  ['Grant dollars', money(p.grant_dollars)],
                  ['Distinct recipients', num(p.recipients)],
                  ['Recipients tagged (seed/rule/LLM)',
                    num(p.recipients_tagged)],
                  ['Pending LLM ($5k+ threshold)',
                    num(p.recipients_pending_llm_5k)],
                ].map(([label, v]) => (
                  <tr key={label as string} className="border-b border-line/60">
                    <td className="py-2 text-muted">{label}</td>
                    <td className="text-right tabular font-medium">{v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
          <Card>
            <CardTitle>Flagged foundations</CardTitle>
            <table className="w-full text-sm">
              <tbody>
                <tr className="border-b border-line/60">
                  <td className="py-2 text-muted">Testamentary / memorial trusts</td>
                  <td className="text-right tabular font-medium">
                    {num(u.testamentary_trusts)}</td>
                </tr>
                <tr>
                  <td className="py-2 text-muted">Micro-funds (&lt;$10k/yr)</td>
                  <td className="text-right tabular font-medium">
                    {num(u.small_funds)}</td>
                </tr>
              </tbody>
            </table>
            <p className="text-xs text-muted mt-2">
              Excluded from prospect views by default.
            </p>
          </Card>
          <Card>
            <CardTitle>Scope &amp; caveats</CardTitle>
            <ul className="text-sm text-muted leading-relaxed list-disc pl-4 space-y-1">
              <li><strong>Private foundations only</strong> (Form 990-PF).
                Donor-advised-fund sponsors like the National Christian
                Foundation file Form 990 and are out of scope by design.</li>
              <li>Rule-based Christian classification is loose — Catholic health
                infrastructure gets tagged, so some large secular funders appear
                on volume lists. An LLM classification pass will refine this.</li>
              <li>Data current as of 2023–2025 filings.</li>
            </ul>
          </Card>
        </div>
      </div>
    </div>
  )
}
