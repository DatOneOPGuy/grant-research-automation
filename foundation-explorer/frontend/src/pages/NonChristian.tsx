// The non-Christian bucket, nationally.
//
// $107B reported as a single number is the largest figure in the product and
// the least useful: it says what the money was not. This page says what it
// was, and names the funders behind each cause, so a Christian charity can
// find the secular funder whose priorities happen to match theirs instead of
// filtering them all out on a label.
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown, ChevronRight, Info } from 'lucide-react'
import {
  fetchNonChristianOverview, sectorLabel, type NonChristianSector,
} from '../lib/apiV5'
import { money, num } from '../lib/format'
import DetailPanel from '../components/foundations/DetailPanel'
import { Skeleton } from '../components/ui/primitives'

// Not a cause: reported apart from the rest so a transfer to another
// grantmaker never reads as support for a cause area.
const NOT_A_CAUSE = new Set(['regranting', 'unknown'])

export default function NonChristian() {
  const [selected, setSelected] = useState<string | null>(null)
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['v5nonchristian'],
    queryFn: () => fetchNonChristianOverview(),
  })

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-10 w-96" />
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-12" />
        ))}
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="rounded-md border border-scoremid/40 bg-amber-50
        px-4 py-3 text-sm text-scoremid max-w-2xl">
        {error instanceof Error ? error.message : 'Could not load the overview.'}
      </div>
    )
  }

  const total = data.sectors.reduce((sum, s) => sum + s.dollars, 0)
  const causes = data.sectors.filter(
    (s) => !NOT_A_CAUSE.has(s.sector) && s.dollars > 0)
  const regranting = data.sectors.find((s) => s.sector === 'regranting')
  const unknown = data.sectors.find((s) => s.sector === 'unknown')
  const max = Math.max(...causes.map((s) => s.dollars), 1)

  const evidence = Object.fromEntries(
    data.evidence.map((e) => [e.confidence, e.dollars]))
  const evTotal = Object.values(evidence).reduce((a, b) => a + b, 0) || 1
  const highPct = Math.round((100 * (evidence.high ?? 0)) / evTotal)

  return (
    <div>
      <h1 className="font-display text-3xl font-semibold text-primary">
        Non-Christian funding
      </h1>
      <p className="text-sm text-muted mt-1 max-w-3xl">
        {money(total)} of 2023–24 paid giving went to organisations that are
        not Christian. That figure on its own says only what the money was
        not. Here is what it funded — and where a faith-based organisation
        might still be a fit.
      </p>

      <div className="mt-5 grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_20rem]
        gap-6 items-start">
        <div className="space-y-1.5">
          {causes.map((s) => (
            <SectorRow key={s.sector} s={s} max={max} total={total}
              onOpen={setSelected} />
          ))}
        </div>

        <aside className="space-y-3">
          {regranting && regranting.dollars > 0 && (
            <div className="rounded-lg border border-accent/30 bg-accent/5 p-3">
              <div className="flex items-center gap-1.5 text-xs font-medium
                text-scoremid mb-1">
                <Info size={13} /> Not a cause area
              </div>
              <div className="text-sm text-ink font-medium">
                {money(regranting.dollars)}
              </div>
              <p className="text-xs text-muted mt-1">
                {Math.round((100 * regranting.dollars) / total)}% of the
                non-Christian total went from one grantmaker to another —
                private foundations, community foundations and fundraising
                intermediaries. Where it landed after that is not in these
                filings, so it is held apart rather than credited to a cause.
              </p>
              {regranting.top_funders[0] && (
                <p className="text-xs text-muted mt-1.5">
                  Largest single flow:{' '}
                  <button onClick={() => setSelected(regranting.top_funders[0].ein)}
                    className="text-primary hover:underline">
                    {regranting.top_funders[0].name}
                  </button>{' '}
                  at {money(regranting.top_funders[0].dollars)}.
                </p>
              )}
            </div>
          )}

          <div className="rounded-lg border border-line bg-surface p-3">
            <div className="text-xs font-medium text-ink mb-1.5">
              How this was determined
            </div>
            <p className="text-xs text-muted">
              {highPct}% of these dollars carry a sector the IRS assigned, via
              the NTEE code on the Business Master File. The rest is inferred
              from the organisation’s name, or left unplaced.
            </p>
            <dl className="mt-2 space-y-0.5 text-xs">
              {[['high', 'IRS-assigned'], ['medium', 'IRS, name-matched'],
                ['low', 'inferred from name'], ['none', 'not placed']]
                .map(([key, label]) => (
                  <div key={key} className="flex justify-between gap-2">
                    <dt className="text-muted">{label}</dt>
                    <dd className="tabular text-ink">
                      {money(evidence[key] ?? 0)}
                    </dd>
                  </div>
                ))}
            </dl>
          </div>

          {unknown && unknown.dollars > 0 && (
            <p className="text-xs text-muted px-1">
              {money(unknown.dollars)} went to organisations that could not be
              placed in any sector — usually recipients the filing named too
              loosely to match against the IRS register.
            </p>
          )}
        </aside>
      </div>

      {selected && (
        <DetailPanel ein={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}

function SectorRow({ s, max, total, onOpen }: {
  s: NonChristianSector
  max: number
  total: number
  onOpen: (ein: string) => void
}) {
  const [open, setOpen] = useState(false)
  return (
    <div className="border border-line rounded-lg bg-surface">
      <button onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="w-full text-left px-3 py-2.5 hover:bg-canvas rounded-lg">
        <div className="flex items-baseline justify-between gap-3">
          <span className="flex items-center gap-1.5 font-medium text-ink">
            {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            {sectorLabel(s.sector)}
          </span>
          <span className="flex items-baseline gap-3 shrink-0">
            <span className="text-xs text-muted">
              {num(s.funders)} funders · {num(s.recipients)} orgs
            </span>
            <span className="tabular font-medium">{money(s.dollars)}</span>
            <span className="tabular text-xs text-muted w-10 text-right">
              {((100 * s.dollars) / total).toFixed(1)}%
            </span>
          </span>
        </div>
        <div className="mt-1.5 h-1.5 rounded bg-line/40 overflow-hidden">
          <div className="h-full bg-primary/60"
            style={{ width: `${(100 * s.dollars) / max}%` }} />
        </div>
      </button>

      {open && (
        <div className="px-3 pb-3 pt-1 border-t border-line/60">
          <div className="text-[10px] uppercase tracking-wide text-muted mb-1">
            Largest funders of this cause
          </div>
          <ol className="space-y-0.5">
            {s.top_funders.map((funder, i) => (
              <li key={funder.ein}
                className="flex items-baseline justify-between gap-3 text-sm">
                <button onClick={() => onOpen(funder.ein)}
                  className="truncate text-left hover:text-primary
                    hover:underline">
                  <span className="text-muted tabular mr-2">{i + 1}.</span>
                  {funder.name}
                </button>
                <span className="tabular text-muted shrink-0">
                  {money(funder.dollars)}
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  )
}
