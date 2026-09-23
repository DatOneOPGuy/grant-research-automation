/** Lab 5 — Intent home.
 *
 *  A first screen that routes by what the user WANTS, not by what the data
 *  contains. Three big doors, each landing on the card browser
 *  pre-filtered, plus a short "what is this" in one breath. Tests whether a
 *  landing page beats a dashboard for a first-time user — the current
 *  Dashboard leads with aggregate analytics no new user asked for.
 */
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Globe2, HeartHandshake, Send } from 'lucide-react'
import { fetchStatsV5 } from '../../lib/apiV5'
import { money, num } from '../../lib/format'
import { SlidersHorizontal } from 'lucide-react'
import { LabBanner } from './shared'

const DOORS = [
  {
    to: '/lab/cards?preset=open',
    icon: Send,
    title: 'Funders I can apply to now',
    blurb: 'Foundations with open applications — the list you can act on this month.',
  },
  {
    to: '/lab/cards?preset=international',
    icon: Globe2,
    title: 'Funders of international ministry',
    blurb: 'Foundations already giving to Wycliffe, Compassion, CURE and 50+ more.',
  },
  {
    to: '/lab/cards?preset=big',
    icon: HeartHandshake,
    title: 'The biggest Christian funders',
    blurb: 'Ranked by real dollars to Christian work — not by what their names say.',
  },
] as const

export default function LabStart() {
  const { data: stats } = useQuery({
    queryKey: ['v5stats'], queryFn: fetchStatsV5, staleTime: Infinity,
  })

  return (
    <div className="mx-auto max-w-3xl">
      <LabBanner testing="an intent-driven first screen instead of an analytics dashboard" />

      <div className="mt-10 text-center">
        <h1 className="font-display text-4xl font-semibold leading-tight
          text-primary">
          Who funds work like yours?
        </h1>
        <p className="mx-auto mt-3 max-w-xl text-muted">
          We read every grant in{' '}
          <span className="font-medium text-ink">
            {stats ? num(stats.foundations) : '…'} foundations'
          </span>{' '}
          IRS filings —{' '}
          <span className="font-medium text-ink">
            {stats ? money(stats.christian) : '…'}
          </span>{' '}
          to Christian work — so you can search by what they actually fund.
        </p>
      </div>

      <div className="mt-10 grid gap-4">
        {DOORS.map((d) => (
          <Link key={d.to} to={d.to}
            className="group flex items-center gap-5 rounded-2xl border
              border-line bg-surface p-5 shadow-sm transition-all
              hover:border-honey-400 hover:shadow-md">
            <span className="flex h-12 w-12 shrink-0 items-center
              justify-center rounded-xl bg-honey-100 text-honey-700">
              <d.icon size={22} />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block font-display text-lg font-semibold
                text-primary">
                {d.title}
              </span>
              <span className="block text-sm text-muted">{d.blurb}</span>
            </span>
            <ArrowRight size={18} className="shrink-0 text-muted
              transition-transform group-hover:translate-x-1
              group-hover:text-honey-700" />
          </Link>
        ))}
      </div>

      <div className="mt-6 text-center">
        <Link to="/lab/cards?adv=1"
          className="inline-flex items-center gap-1.5 text-sm text-muted
            underline underline-offset-4 hover:text-ink">
          <SlidersHorizontal size={13} />
          I know exactly what I want — open the advanced filters
        </Link>
      </div>

      <p className="mt-4 text-center text-xs text-muted">
        Every number traces to a specific grant on a specific public IRS
        filing. When we don't know something, we say so.
      </p>
    </div>
  )
}
