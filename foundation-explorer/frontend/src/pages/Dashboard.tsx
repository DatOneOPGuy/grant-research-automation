import { useQuery } from '@tanstack/react-query'
import {
  Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import { apiGet } from '../lib/api'
import { money, num } from '../lib/format'
import { Card, CardTitle, KPI, Skeleton } from '../components/ui/primitives'

export default function Dashboard() {
  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: () => apiGet<any>('/api/foundations/stats'),
  })
  const { data: scoreDist } = useQuery({
    queryKey: ['scoredist'],
    queryFn: () => apiGet<any[]>('/api/analytics/score-distribution'),
  })
  const { data: sizeDist } = useQuery({
    queryKey: ['sizedist'],
    queryFn: () => apiGet<any[]>('/api/analytics/size-distribution'),
  })
  const { data: top } = useQuery({
    queryKey: ['top10'],
    queryFn: () => apiGet<any[]>('/api/analytics/top-funders?limit=10'),
  })

  const appData = stats ? [
    { name: 'Invite Only', value: stats.invite_only, fill: '#b8860b' },
    { name: 'Accepting', value: stats.accepting, fill: '#2d5a3d' },
    {
      name: 'Unknown',
      value: stats.total - stats.invite_only - stats.accepting,
      fill: '#9ca3af',
    },
  ] : []

  return (
    <div>
      <h1 className="font-display text-3xl font-semibold text-primary mb-6">
        Dashboard
      </h1>

      <div className="grid grid-cols-4 gap-4 mb-6">
        <KPI label="Private foundations"
          value={stats ? num(stats.total) : '…'} />
        <KPI label="Grants tracked"
          value={stats ? num(stats.total_grants) : '…'}
          sub={stats ? `${money(stats.total_grants_dollars)} total` : ''} />
        <KPI label="Faith-scored foundations"
          value={stats ? num(stats.scored) : '…'} />
        <KPI label="High alignment (score ≥ 60)"
          value={stats ? num(stats.high_alignment) : '…'} />
      </div>

      <div className="grid grid-cols-2 gap-4 mb-6">
        <Card>
          <CardTitle>Faith Alignment Score distribution</CardTitle>
          {scoreDist ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={scoreDist}>
                <XAxis dataKey="bucket" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} scale="sqrt" />
                <Tooltip formatter={(v) => num(Number(v))} />
                <Bar dataKey="n" fill="#1a3a2e" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <Skeleton className="h-52" />}
        </Card>
        <Card>
          <CardTitle>Foundation size (total distributions)</CardTitle>
          {sizeDist ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={sizeDist}>
                <XAxis dataKey="bucket" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => num(Number(v))} />
                <Bar dataKey="n" fill="#c9a961" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <Skeleton className="h-52" />}
        </Card>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-6">
        <Card>
          <CardTitle>Top 10 by Faith Alignment</CardTitle>
          <table className="w-full text-sm">
            <tbody>
              {top?.map((f) => (
                <tr key={f.ein} className="border-b border-line/60">
                  <td className="py-1.5 pr-2 font-medium max-w-64 truncate">
                    {f.foundation_name}
                  </td>
                  <td className="text-muted pr-2">{f.state}</td>
                  <td className="text-right tabular font-medium text-scorehigh">
                    {f.faith_alignment_score}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
        <Card>
          <CardTitle>Application status</CardTitle>
          {stats ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={appData} dataKey="value" nameKey="name"
                  innerRadius={55} outerRadius={85} paddingAngle={2}>
                  {appData.map((d) => (
                    <Cell key={d.name} fill={d.fill} />
                  ))}
                </Pie>
                <Tooltip formatter={(v) => num(Number(v))} />
              </PieChart>
            </ResponsiveContainer>
          ) : <Skeleton className="h-52" />}
          <div className="flex justify-center gap-4 text-xs text-muted">
            {appData.map((d) => (
              <span key={d.name} className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full inline-block"
                  style={{ background: d.fill }} />
                {d.name} ({num(d.value)})
              </span>
            ))}
          </div>
        </Card>
      </div>

      {stats && (
        <Card>
          <CardTitle>Data coverage</CardTitle>
          <div className="grid grid-cols-4 gap-4 text-sm">
            {[
              ['Have 2023–2025 filings', stats.with_filings],
              ['Have contact person', stats.with_contact],
              ['Have phone', stats.with_phone],
              ['Have website', stats.with_website],
            ].map(([label, v]) => (
              <div key={label as string}>
                <div className="tabular font-medium">
                  {num(v as number)}{' '}
                  <span className="text-muted font-normal">
                    ({(((v as number) / stats.total) * 100).toFixed(0)}%)
                  </span>
                </div>
                <div className="text-xs text-muted">{label}</div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}
