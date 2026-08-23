import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { sectorLabel, type SectorStat } from '../../lib/apiV5'
import { money } from '../../lib/format'

export type Buckets = {
  christian: number
  nonchristian: number
  unclassified: number
  daf: number
}

const SEGMENTS: { key: keyof Buckets; label: string; cls: string }[] = [
  { key: 'christian', label: 'Christian', cls: 'bg-scorehigh' },
  { key: 'nonchristian', label: 'Non-Christian', cls: 'bg-slate-400' },
  { key: 'unclassified', label: 'Unclassified', cls: 'bg-amber-400' },
  { key: 'daf', label: 'DAF pass-through', cls: 'bg-purple-400' },
]

// Mini stacked bar for table rows: christian / nonchristian / unclassified /
// DAF split of paid dollars. Unclassified is always shown — never hidden.
export function BucketBar({ b, className = '' }: {
  b: Buckets; className?: string
}) {
  const total = b.christian + b.nonchristian + b.unclassified + b.daf
  if (total <= 0) {
    return <div className={`h-2 rounded bg-line/60 ${className}`}
      title="No paid dollars in window" />
  }
  const tip = SEGMENTS
    .map((s) => `${s.label}: ${money(b[s.key])}`)
    .join(' · ')
  return (
    <div className={`flex h-2 rounded overflow-hidden bg-line/40 ${className}`}
      title={tip}>
      {SEGMENTS.map((s) => b[s.key] > 0 && (
        <div key={s.key} className={s.cls}
          style={{ width: `${(b[s.key] / total) * 100}%` }} />
      ))}
    </div>
  )
}

// Large bar for the detail header, with $ labels underneath.
//
// The Non-Christian figure is the one that provokes a question -- it is the
// largest number on most foundations and says nothing about what was funded --
// so when a sector breakdown exists it opens right here rather than making
// the reader hunt for it further down the page.
export function BucketBarLabeled({ b, sectors = [] }: {
  b: Buckets
  sectors?: SectorStat[]
}) {
  const [open, setOpen] = useState(false)
  const causes = sectors.filter((s) => s.dollars > 0)
  const expandable = causes.length > 0 && b.nonchristian > 0

  return (
    <div>
      <BucketBar b={b} className="h-3" />
      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs">
        {SEGMENTS.map((s) => {
          const swatch = (
            <span className={`inline-block w-2.5 h-2.5 rounded-sm ${s.cls}`} />
          )
          const body = (
            <>
              {swatch}
              {s.label}: <span className="tabular font-medium text-ink">
                {money(b[s.key])}
              </span>
            </>
          )
          if (s.key !== 'nonchristian' || !expandable) {
            return (
              <span key={s.key} className="flex items-center gap-1.5 text-muted">
                {body}
              </span>
            )
          }
          return (
            <button key={s.key} onClick={() => setOpen((o) => !o)}
              aria-expanded={open}
              title="What did the non-Christian giving fund?"
              className="flex items-center gap-1.5 text-muted hover:text-ink
                underline decoration-dotted underline-offset-4">
              {body}
              {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            </button>
          )
        })}
      </div>

      {open && expandable && (
        <div className="mt-2 rounded-md border border-line bg-canvas p-2.5">
          <div className="text-[10px] uppercase tracking-wide text-muted mb-1.5">
            What the non-Christian giving funded
          </div>
          <div className="grid grid-cols-2 gap-x-5 gap-y-1 text-xs">
            {causes.map((s) => (
              <div key={s.sector} className="flex items-baseline gap-2">
                <span className="flex-1 truncate text-muted">
                  {sectorLabel(s.sector)}
                  {s.sector === 'regranting' && (
                    <span title="Money passed to another grantmaker; where it
                      landed after that is not in this filing."
                      className="text-scoremid"> *</span>
                  )}
                </span>
                <span className="tabular text-ink">{money(s.dollars)}</span>
                <span className="tabular text-muted w-9 text-right">
                  {Math.round((100 * s.dollars) / b.nonchristian)}%
                </span>
              </div>
            ))}
          </div>
          {causes.some((s) => s.sector === 'regranting') && (
            <div className="text-[10px] text-muted mt-2">
              * passed to another grantmaker — the eventual cause is not in
              this filing
            </div>
          )}
        </div>
      )}
    </div>
  )
}
