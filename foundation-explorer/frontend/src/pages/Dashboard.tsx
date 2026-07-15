import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { ArrowRight } from 'lucide-react'
import { apiGet } from '../lib/api'
import { money, num, taxWindow, titleCase } from '../lib/format'
import {
  Card, CardTitle, KPI, Skeleton, VerdictBadge,
} from '../components/ui/primitives'

export default function Dashboard() {
  const nav = useNavigate()
  const { data: stats } = useQuery({
    queryKey: ['stats'], queryFn: () => apiGet<any>('/api/foundations/stats'),
  })
  const { data: verify } = useQuery({
    queryKey: ['verify'],
    queryFn: () => apiGet<any[]>('/api/analytics/verification'),
  })
  const { data: lb } = useQuery({
    queryKey: ['leaderboards'],
    queryFn: () => apiGet<any>('/api/analytics/leaderboards'),
  })
  const { data: sc } = useQuery({
    queryKey: ['statechristian'],
    queryFn: () => apiGet<any[]>('/api/analytics/state-christian'),
  })
  const years = taxWindow(stats?.tax_year_start, stats?.tax_year_end)

  return (
    <div>
      <h1 className="font-display text-3xl font-semibold text-primary mb-1">
        Dashboard
      </h1>
      <p className="text-muted mb-6">
        Evidence-backed Christian grantmaking from IRS Form 990-PF filings,
        tax years {years}.
      </p>

      <div className="grid grid-cols-4 gap-4 mb-6">
        <KPI label="Private foundations"
          value={stats ? num(stats.total) : '…'}
          sub={stats ? `${num(stats.with_filings)} with filings` : ''} />
        <KPI label="Qualifying distributions"
          value={stats ? money(stats.qualifying_distributions) : '…'}
          sub="latest available filing per foundation" />
        <KPI label="Foundations giving to Christian causes"
          value={stats ? num(stats.confirmed_christian_foundations) : '…'} />
        <KPI label="Best-prospect universe"
          value={stats ? num(stats.best_prospects) : '…'}
          sub={stats ? `${money(stats.best_prospect_dollars)} addressable` : ''} />
      </div>

      {/* Best-prospect hero */}
      <div className="rounded-lg bg-primary text-white p-6 mb-6 flex items-center justify-between">
        <div>
          <div className="font-display text-2xl font-semibold text-accent">
            The Best-Prospect Universe
          </div>
          <p className="text-white/80 mt-2 max-w-2xl text-sm leading-relaxed">
            {stats ? num(stats.best_prospects) : '—'} foundations that accept
            applications (or take a first contact) and have given more than
            $100k to confirmed Christian recipients during {years} —
            {' '}{stats ? money(stats.best_prospect_dollars) : '—'} in
            addressable Christian giving.
          </p>
        </div>
        <button
          onClick={() => nav('/best-prospects')}
          className="shrink-0 flex items-center gap-2 bg-accent text-primary font-medium rounded-md px-5 py-2.5 hover:bg-accent/90">
          View best prospects <ArrowRight size={16} />
        </button>
      </div>

      {/* Verification table — verdict + evidence */}
      <Card className="mb-6">
        <CardTitle>Verification — known major Christian funders</CardTitle>
        <p className="text-sm text-muted mb-3">
          Every verdict is backed by the actual Christian organizations each
          foundation funds — recognizable names a fundraiser can verify.
        </p>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-muted border-b border-line">
              <th className="py-2">Funder</th>
              <th>Verdict</th>
              <th className="text-right">Christian orgs</th>
              <th className="text-right">Christian $ ({years})</th>
            </tr>
          </thead>
          <tbody>
            {verify?.map((v) => (
              <tr key={v.label} className="border-b border-line/60">
                <td className="py-2 font-medium">
                  {titleCase(v.foundation_name)}
                </td>
                <td><VerdictBadge verdict={v.verdict} /></td>
                <td className="text-right tabular text-muted">
                  {v.christian_recipient_count}
                </td>
                <td className="text-right tabular font-medium">
                  {money(v.christian_dollars_3yr)}
                </td>
              </tr>
            ))}
            {!verify && <tr><td colSpan={4}><Skeleton className="h-20" /></td></tr>}
          </tbody>
        </table>
      </Card>

      {/* Leaderboard by Christian dollars */}
      <div className="mb-6">
        <Leaderboard title={`Top 10 by confirmed Christian dollars (${years})`}
          rows={lb?.volume} metric="christian_dollars_3yr"
          fmt={money} onClick={(e) => nav(`/foundations?ein=${e}`)} />
      </div>

      {/* State christian giving */}
      <Card>
        <CardTitle>Christian giving by state (top 20)</CardTitle>
        {sc ? (
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={sc.slice(0, 20)}>
              <XAxis dataKey="state" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }}
                tickFormatter={(v) => money(v)} />
              <Tooltip formatter={(v) => money(Number(v))} />
              <Bar dataKey="christian_dollars" fill="#1a3a2e"
                radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : <Skeleton className="h-64" />}
      </Card>
    </div>
  )
}

function Leaderboard({ title, rows, metric, fmt, onClick }: {
  title: string; rows: any[] | undefined; metric: string
  fmt: (v: number) => string; onClick: (ein: string) => void
}) {
  return (
    <Card>
      <CardTitle>{title}</CardTitle>
      <table className="w-full text-sm">
        <tbody>
          {rows?.map((r, i) => (
            <tr key={r.ein}
              onClick={() => onClick(r.ein)}
              className="border-b border-line/60 hover:bg-canvas/70 cursor-pointer">
              <td className="py-1.5 pr-2 tabular text-muted w-6">{i + 1}</td>
              <td className="pr-2 font-medium max-w-56 truncate">
                {titleCase(r.foundation_name)}
              </td>
              <td className="pr-2 text-muted text-xs">{r.state}</td>
              <td className="text-right tabular font-medium text-scorehigh">
                {fmt(r[metric])}
              </td>
            </tr>
          ))}
          {!rows && <tr><td><Skeleton className="h-40" /></td></tr>}
        </tbody>
      </table>
    </Card>
  )
}
