// What the non-Christian money actually funded.
//
// "97% non-Christian" is a true statement that answers nothing. A Christian
// youth charity is not helped by knowing a funder is mostly non-Christian; it
// is helped by knowing that funder gives to youth work, or that the money went
// to other grantmakers and its destination is not yet knowable.
import { useState } from 'react'
import { ChevronDown, ChevronRight, Info } from 'lucide-react'
import { sectorLabel, type SectorStat } from '../../../lib/apiV5'
import { money } from '../../../lib/format'
import { BarRow, Empty, SectionTitle } from './parts'

// Sectors that do not describe a cause. Kept out of the main list and
// reported separately, so a foundation whose "giving" is mostly a transfer to
// another grantmaker cannot look like a diversified funder.
const NOT_A_CAUSE = new Set(['regranting', 'unknown'])

/** Rough steer on how much of a sector rests on evidence we would defend. */
function strength(confidence: Record<string, number>) {
  const total = Object.values(confidence).reduce((a, b) => a + b, 0)
  if (!total) return null
  const high = (confidence.high ?? 0) / total
  if (high >= 0.8) return null            // unremarkable; say nothing
  const weak = ((confidence.low ?? 0) + (confidence.none ?? 0)) / total
  return weak >= 0.5 ? 'mostly inferred' : 'partly inferred'
}

export default function SectorBreakdown({ sectors }: {
  sectors: SectorStat[]
}) {
  const [open, setOpen] = useState(false)
  if (!sectors.length) return null

  const causes = sectors.filter((s) => !NOT_A_CAUSE.has(s.sector))
  const regranting = sectors.find((s) => s.sector === 'regranting')
  const unknown = sectors.find((s) => s.sector === 'unknown')
  const total = sectors.reduce((sum, s) => sum + s.dollars, 0)
  const causeTotal = causes.reduce((sum, s) => sum + s.dollars, 0)
  const max = Math.max(...causes.map((s) => s.dollars), 1)

  const shown = open ? causes : causes.slice(0, 6)
  const pct = (d: number) => (total > 0 ? Math.round((100 * d) / total) : 0)

  return (
    <div>
      <SectionTitle note="The non-Christian side of the ledger, broken down by
        cause area. Sectors come from the IRS Business Master File's NTEE code
        where the recipient could be matched to it; the rest are inferred from
        the organisation's name and marked as such.">
        Where the rest of the money went
      </SectionTitle>

      {causes.length ? (
        <div className="space-y-1.5 max-w-xl">
          {shown.map((s) => {
            const note = strength(s.confidence)
            return (
              <BarRow key={s.sector} label={sectorLabel(s.sector)}
                dollars={s.dollars} max={max}
                sub={[`${s.recipients.toLocaleString()} orgs`, note]
                  .filter(Boolean).join(' · ')} />
            )
          })}
          {causes.length > 6 && (
            <button onClick={() => setOpen((o) => !o)}
              className="flex items-center gap-1 text-xs text-primary
                hover:underline pt-1">
              {open
                ? <><ChevronDown size={13} /> Show fewer</>
                : <><ChevronRight size={13} /> {causes.length - 6} more
                    cause{causes.length - 6 === 1 ? '' : 's'}</>}
            </button>
          )}
        </div>
      ) : (
        <Empty>None of this foundation’s non-Christian giving went to an
          identifiable cause area.</Empty>
      )}

      {(regranting || unknown) && (
        <div className="mt-3 max-w-xl space-y-1.5 text-xs">
          {regranting && regranting.dollars > 0 && (
            <div className="flex items-start gap-2 rounded-md border
              border-accent/30 bg-accent/5 px-3 py-2">
              <Info size={13} className="text-scoremid shrink-0 mt-0.5" />
              <div>
                <span className="font-medium text-ink">
                  {money(regranting.dollars)}
                </span>{' '}
                <span className="text-muted">
                  ({pct(regranting.dollars)}% of this) went to other
                  grantmakers — foundations, community foundations and
                  fundraising intermediaries. Where it landed after that is
                  not in this filing, so it is counted here rather than
                  credited to any cause.
                </span>
              </div>
            </div>
          )}
          {unknown && unknown.dollars > 0 && (
            <div className="text-muted px-3">
              {money(unknown.dollars)} ({pct(unknown.dollars)}%) went to
              organisations we could not place in a sector — usually
              recipients the filing named too loosely to match against the
              IRS register.
            </div>
          )}
        </div>
      )}

      {causeTotal > 0 && (
        <div className="text-[11px] text-muted mt-2 max-w-xl">
          Percentages are of the {money(total)} that is not Christian giving,
          not of total giving.
        </div>
      )}
    </div>
  )
}
