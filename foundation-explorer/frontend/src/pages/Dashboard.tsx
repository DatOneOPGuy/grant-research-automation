import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight } from 'lucide-react'
import { fetchStatsV5 } from '../lib/apiV5'
import { money, num } from '../lib/format'
import { Card, CardTitle, KPI, Skeleton } from '../components/ui/primitives'
import { BucketBarLabeled } from '../components/foundations/BucketBar'

export default function Dashboard() {
  const nav = useNavigate()
  const { data: stats, isError } = useQuery({
    queryKey: ['v5stats'], queryFn: fetchStatsV5,
  })

  return (
    <div>
      <h1 className="font-display text-3xl font-semibold text-primary mb-1">
        Dashboard
      </h1>
      <p className="text-muted mb-6">
        Paid grants from IRS Form 990-PF filings,
        {' '}{stats?.window || 'TY2023–2024'}.
      </p>

      {isError && (
        <div className="mb-6 rounded-md border border-scoremid/40 bg-amber-50 px-4 py-2.5 text-sm text-scoremid">
          Could not reach the v5 API at localhost:8000 — start the backend to
          load dashboard numbers.
        </div>
      )}

      <div className="grid grid-cols-4 gap-4 mb-6">
        <KPI label="Private foundations"
          value={stats ? num(stats.foundations) : '…'}
          sub={stats ? `${num(stats.active)} active in the window` : ''} />
        <KPI label="Paid grant dollars"
          value={stats ? money(stats.paid) : '…'}
          sub={stats?.window || ''} />
        <KPI label="Recipient organizations"
          value={stats ? num(stats.recipients) : '…'}
          sub={stats ? `${num(stats.with_mission)} with 990 mission text` : ''} />
        <KPI label="Christian dollars"
          value={stats ? money(stats.christian) : '…'}
          sub="classified recipients only" />
      </div>

      {/* Four-bucket honesty split: unclassified dollars stay visible. */}
      <Card className="mb-6">
        <CardTitle>Where the paid dollars went</CardTitle>
        {stats ? (
          <>
            <BucketBarLabeled b={{
              christian: stats.christian,
              nonchristian: stats.nonchristian,
              unclassified: stats.unclassified,
              daf: stats.daf,
              nonclassifiable: stats.nonclassifiable,
            }} />
            <p className="text-xs text-muted mt-3">
              Unclassified dollars are grants to recipients we have not yet
              classified — they are shown, never hidden. DAF dollars are
              pass-throughs to donor-advised funds whose final destination is
              not public. Not-attributable dollars are grants the filing never
              tied to a named organisation at all — patient-assistance
              programs protected by HIPAA, recipient lists filed as PDF
              attachments, unitemized schedules — so there is nothing to
              classify, in either direction.
            </p>
          </>
        ) : <Skeleton className="h-16" />}
      </Card>

      <div className="rounded-lg bg-primary text-white p-6 mb-6 flex items-center justify-between">
        <div>
          <div className="font-display text-2xl font-semibold text-accent">
            Explore the foundations
          </div>
          <p className="text-white/80 mt-2 max-w-2xl text-sm leading-relaxed">
            Slice {stats ? num(stats.foundations) : '—'} foundations by
            recipient faith tradition, giving behavior, geography,
            reachability, and data quality — every verdict backed by the real
            grants underneath.
          </p>
        </div>
        <button onClick={() => nav('/foundations')}
          className="shrink-0 flex items-center gap-2 bg-accent text-primary font-medium rounded-md px-5 py-2.5 hover:bg-accent/90">
          Open Foundation Explorer <ArrowRight size={16} />
        </button>
      </div>

      {stats?.identity_run && (
        <div className="text-xs text-muted border-t border-line pt-3">
          Data release: identity run {stats.identity_run} · window
          {' '}{stats.window}
        </div>
      )}
    </div>
  )
}
