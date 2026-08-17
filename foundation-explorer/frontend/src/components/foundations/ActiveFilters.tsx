import { X } from 'lucide-react'
import type { V5Filters } from '../../lib/apiV5'
import { buildChips } from './filterChips'

export default function ActiveFilters({ filters, onChange, onClearAll }: {
  filters: V5Filters
  onChange: (f: V5Filters) => void
  onClearAll: () => void
}) {
  const set = (patch: Partial<V5Filters>) => onChange({ ...filters, ...patch })
  const chips = buildChips(filters, set)
  if (!chips.length) return null
  return (
    <div className="flex flex-wrap items-center gap-1.5 mb-4 p-3 bg-canvas/60 border border-line rounded-lg">
      <span className="text-xs font-semibold uppercase tracking-wide text-muted mr-1">
        Active filters
      </span>
      {chips.map((c) => (
        <button key={c.id} onClick={c.onRemove}
          className="flex items-center gap-1 text-xs bg-primary/10 text-primary border border-primary/30 rounded-full pl-2.5 pr-1.5 py-1 hover:bg-primary/20">
          {c.label}
          <X size={12} />
        </button>
      ))}
      <button onClick={onClearAll}
        className="text-xs text-muted underline ml-1 hover:text-ink">
        Clear all
      </button>
    </div>
  )
}
