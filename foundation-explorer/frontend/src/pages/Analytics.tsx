import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  fetchStateBreakdownV5, fetchTopFundersV5, fetchYearlyTrendsV5,
} from '../lib/apiV5'
import { money, num, TAX_WINDOW_LABEL, titleCase } from '../lib/format'
import { Card, CardTitle, Skeleton } from '../components/ui/primitives'

export default function Analytics() {
  const { data: states } = useQuery({
    queryKey: ['v5states'], queryFn: fetchStateBreakdownV5,
  })
  const { data: top } = useQuery({
    queryKey: ['v5topFunders'], queryFn: () => fetchTopFundersV5(100),
  })
  const { data: trends } = useQuery({
    queryKey: ['v5trends'], queryFn: fetchYearlyTrendsV5,
  })

  const maxPaid = states?.[0]?.paid ?? 1

  return (
    <div>
      <h1 className="font-display text-3xl font-semibold text-primary mb-1">
        Analytics
      </h1>
      <p className="text-sm text-muted mb-4">
        Paid grants, tax years {TAX_WINDOW_LABEL}.
      </p>

      <Card className="mb-4">
        <CardTitle>Yearly totals</CardTitle>
        {!trends && <Skeleton className="h-24 mt-2" />}
        {trends && (
          <table className="w-full text-sm mt-2">
            <thead>
              <tr className="text-left text-xs text-muted border-b border-line">
                <th className="py-2">Tax year</th>
                <th className="text-right">Foundations</th>
                <th className="text-right">Grants</th>
                <th className="text-right">Paid</th>
                <th className="text-right">Christian</th>
              </tr>
            </thead>
            <tbody>
              {trends.map((t) => (
                <tr key={t.tax_year} className="border-b border-line/60">
                  <td className="py-2 font-medium">{t.tax_year}</td>
                  <td className="text-right tabular">{num(t.foundations)}</td>
                  <td className="text-right tabular">{num(t.grants)}</td>
                  <td className="text-right tabular">{money(t.paid)}</td>
                  <td className="text-right tabular">{money(t.christian)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card className="mb-4">
        <CardTitle>Giving by foundation state</CardTitle>
        {!states && <Skeleton className="h-64 mt-2" />}
        {states && (
          <div className="overflow-x-auto max-h-96 overflow-y-auto mt-2">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-surface">
                <tr className="text-left text-xs text-muted border-b border-line">
                  <th className="py-2">State</th>
                  <th className="text-right">Foundations</th>
                  <th className="text-right">Paid</th>
                  <th className="text-right">Christian</th>
                  <th className="w-40" />
                </tr>
              </thead>
              <tbody>
                {states.map((s) => (
                  <tr key={s.state} className="border-b border-line/60">
                    <td className="py-1.5 font-medium">{s.state}</td>
                    <td className="text-right tabular">{num(s.foundations)}</td>
                    <td className="text-right tabular">{money(s.paid)}</td>
                    <td className="text-right tabular pr-3">
                      {money(s.christian)}
                    </td>
                    <td>
                      <div className="h-2 bg-canvas rounded overflow-hidden">
                        <div className="h-full bg-primary"
                          style={{ width: `${(s.paid / maxPaid) * 100}%` }} />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card>
        <CardTitle>Top 100 Christian funders</CardTitle>
        <p className="text-xs text-muted mt-1 mb-2">
          Ranked by classified Christian dollars. Coverage shows how much of
          each foundation’s identifiable giving we have classified.
        </p>
        {!top && <Skeleton className="h-64" />}
        {top && (
          <div className="overflow-x-auto max-h-[32rem] overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-surface">
                <tr className="text-left text-xs text-muted border-b border-line">
                  <th className="py-2">#</th>
                  <th>Foundation</th>
                  <th>Location</th>
                  <th className="text-right">Christian</th>
                  <th className="text-right">Paid</th>
                  <th className="text-right">Coverage</th>
                  <th>Applications</th>
                </tr>
              </thead>
              <tbody>
                {top.map((f, i) => (
                  <tr key={f.ein} className="border-b border-line/60">
                    <td className="py-1.5 text-muted tabular">{i + 1}</td>
                    <td className="pr-3 font-medium">
                      <Link to={`/foundations?ein=${f.ein}`}
                        className="hover:underline">
                        {titleCase(f.foundation_name)}
                      </Link>
                    </td>
                    <td className="pr-3 text-muted whitespace-nowrap">
                      {f.city && `${titleCase(f.city)}, `}{f.state}
                    </td>
                    <td className="text-right tabular pr-3">
                      {money(f.christian_dollars)}
                    </td>
                    <td className="text-right tabular pr-3">
                      {money(f.paid_2324)}
                    </td>
                    <td className="text-right tabular pr-3">
                      {Math.round(f.coverage_pct)}%
                    </td>
                    <td className="text-muted text-xs">
                      {f.application_status}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
