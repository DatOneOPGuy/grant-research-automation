// Small shared pieces for the foundation detail tabs. Kept in one place so
// every tab renders a stat, a bar row and an empty state identically.
import { money } from '../../../lib/format'

export function Stat({ label, value, hint }: {
  label: string; value: string; hint?: string
}) {
  return (
    <div className="border border-line/70 rounded-md px-3 py-2">
      <div className="text-[11px] text-muted uppercase tracking-wide">
        {label}
      </div>
      <div className="text-lg font-semibold text-ink tabular mt-0.5">
        {value}
      </div>
      {hint && <div className="text-[11px] text-muted mt-0.5">{hint}</div>}
    </div>
  )
}

export function SectionTitle({ children, note }: {
  children: React.ReactNode; note?: string
}) {
  return (
    <div className="mb-2">
      <div className="text-xs font-semibold text-ink uppercase tracking-wide">
        {children}
      </div>
      {note && (
        <p className="text-[11px] text-muted mt-0.5 leading-snug max-w-xl">
          {note}
        </p>
      )}
    </div>
  )
}

/** A labelled horizontal bar. `christian` renders as a distinct leading
 *  segment so a mixed row reads without a legend. */
export function BarRow({ label, dollars, christian = 0, max, sub, title }: {
  label: string; dollars: number; christian?: number; max: number
  sub?: string; title?: string
}) {
  const pct = (n: number) => `${Math.max((n / max) * 100, 0)}%`
  return (
    <div className="flex items-center gap-3 text-sm" title={title}>
      {/* title so a clipped label is still readable on hover. The truncate
          itself already worked here -- flex items are blockified, so the width
          and overflow apply to a <span> like this one. */}
      <span title={label}
        className="block w-36 truncate text-muted shrink-0">{label}</span>
      <div className="flex-1 h-3 bg-line/40 rounded overflow-hidden">
        <div className="h-full flex">
          <div className="h-full bg-primary/80" style={{ width: pct(christian) }} />
          <div className="h-full bg-scorehigh/60"
            style={{ width: pct(dollars - christian) }} />
        </div>
      </div>
      <span className="w-20 text-right tabular font-medium shrink-0">
        {money(dollars)}
      </span>
      {sub !== undefined && (
        <span className="w-16 text-right text-[11px] text-muted shrink-0 tabular">
          {sub}
        </span>
      )}
    </div>
  )
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="text-sm text-muted">{children}</div>
}
