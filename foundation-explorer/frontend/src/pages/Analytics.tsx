import { useQuery } from '@tanstack/react-query'
import {
  Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { apiGet } from '../lib/api'
import { money, num, scoreColor } from '../lib/format'
import { Badge, Card, CardTitle, Skeleton } from '../components/ui/primitives'

export default function Analytics() {
  const { data: states } = useQuery({
    queryKey: ['statebreakdown'],
    queryFn: () => apiGet<any[]>('/api/analytics/state-breakdown'),
  })
  const { data: top } = useQuery({
    queryKey: ['top100'],
    queryFn: () => apiGet<any[]>('/api/analytics/top-funders?limit=100'),
  })
  const { data: trends } = useQuery({
    queryKey: ['trends'],
    queryFn: () => apiGet<any[]>('/api/analytics/yearly-trends'),
  })

  return (
    <div>
      <h1 className="font-display text-3xl font-semibold text-primary mb-6">
        Analytics
      </h1>

      <div className="grid grid-cols-2 gap-4 mb-6">
        <Card>
          <CardTitle>Foundations by state (top 15)</CardTitle>
          {states ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={states.slice(0, 15)}>
                <XAxis dataKey="state" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => num(Number(v))} />
                <Bar dataKey="foundations" fill="#1a3a2e"
                  radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <Skeleton className="h-60" />}
        </Card>
        <Card>
          <CardTitle>Faith funders (score ≥ 40) by state (top 15)</CardTitle>
          {states ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={[...states]
                .sort((a, b) => b.faith_funders - a.faith_funders)
                .slice(0, 15)}>
                <XAxis dataKey="state" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => num(Number(v))} />
                <Bar dataKey="faith_funders" fill="#c9a961"
                  radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <Skeleton className="h-60" />}
        </Card>
      </div>

      <Card className="mb-6">
        <CardTitle>Grant dollars by tax year</CardTitle>
        {trends ? (
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={trends}>
              <XAxis dataKey="tax_year" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }}
                tickFormatter={(v) => money(v)} />
              <Tooltip formatter={(v) => money(Number(v))} />
              <Bar dataKey="dollars" fill="#2d5a3d" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : <Skeleton className="h-48" />}
      </Card>

      <Card className="mb-6">
        <CardTitle>How the composite score works</CardTitle>
        <p className="text-sm text-muted mb-3">
          <strong>Composite Score = 40% × Percentage Christian Giving + 60% ×
          log-scaled Christian Dollar Volume.</strong> The volume component
          means a large foundation moving real money to Christian causes
          outranks a tiny memorial trust giving 100% to one church.
        </p>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div className="border border-line rounded p-3">
            <div className="font-medium">Small trust — 100% Christian</div>
            <div className="text-muted">$10k total, all to one ministry</div>
            <div className="mt-1">Percentage: 100 · Volume: ~20 →
              <span className="font-medium text-scoremid"> composite ≈ 52</span></div>
          </div>
          <div className="border border-line rounded p-3">
            <div className="font-medium">Large foundation — 15% Christian</div>
            <div className="text-muted">$100M total, $15M to Christian causes</div>
            <div className="mt-1">Percentage: 15 · Volume: ~86 →
              <span className="font-medium text-scorehigh"> composite ≈ 58</span></div>
          </div>
        </div>
      </Card>

      <Card>
        <CardTitle>Top 100 Christian funders</CardTitle>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-muted border-b border-line">
              <th className="py-2 pr-3">#</th>
              <th className="pr-3">Foundation</th>
              <th className="pr-3">Location</th>
              <th className="text-right pr-3">Score</th>
              <th className="text-right pr-3">Faith giving</th>
              <th className="text-right pr-3">% of giving</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {top?.map((f, i) => (
              <tr key={f.ein} className="border-b border-line/60">
                <td className="py-1.5 pr-3 tabular text-muted">{i + 1}</td>
                <td className="pr-3 font-medium max-w-72 truncate">
                  {f.foundation_name}
                </td>
                <td className="pr-3 text-muted">
                  {f.city}, {f.state}
                </td>
                <td className="text-right pr-3">
                  <Badge className={scoreColor(f.faith_alignment_score)}>
                    {f.faith_alignment_score}
                  </Badge>
                </td>
                <td className="text-right tabular pr-3">
                  {money(f.faith_giving)}
                </td>
                <td className="text-right tabular pr-3">
                  {f.christian_giving_pct}%
                </td>
                <td className="text-xs text-muted">
                  {f.application_status || '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  )
}
