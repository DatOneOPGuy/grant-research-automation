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
export function BucketBarLabeled({ b }: { b: Buckets }) {
  return (
    <div>
      <BucketBar b={b} className="h-3" />
      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs">
        {SEGMENTS.map((s) => (
          <span key={s.key} className="flex items-center gap-1.5 text-muted">
            <span className={`inline-block w-2.5 h-2.5 rounded-sm ${s.cls}`} />
            {s.label}: <span className="tabular font-medium text-ink">
              {money(b[s.key])}
            </span>
          </span>
        ))}
      </div>
    </div>
  )
}
