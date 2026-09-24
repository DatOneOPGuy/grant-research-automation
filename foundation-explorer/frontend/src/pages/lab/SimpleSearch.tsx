/** Lab 1 — One box.
 *
 *  The opposite extreme from the current 240px filter rail: a single search
 *  box, three toggle chips, nothing else. If Emily's "less buttons" is taken
 *  literally, this is the floor — and testing it tells us which controls are
 *  actually missed when they're gone.
 */
import { useEffect, useState } from 'react'
import { Loader2, Search } from 'lucide-react'
import DetailPanel from '../../components/foundations/DetailPanel'
import { num } from '../../lib/format'
import { AdvancedButton, AdvancedDrawer, CauseSelect, FoundationCard,
  LabBanner, useAdvanced, useLab } from './shared'

const CHIPS = [
  { key: 'accepting', label: 'I can apply' },
  { key: 'international', label: 'Funds international ministries' },
  { key: 'christian', label: 'Christian giving first' },
] as const
type ChipKey = (typeof CHIPS)[number]['key']

export default function LabSimpleSearch() {
  const [q, setQ] = useState('')
  const [debounced, setDebounced] = useState('')
  const [on, setOn] = useState<Record<ChipKey, boolean>>({
    accepting: false, international: false, christian: true,
  })
  const [selected, setSelected] = useState<string | null>(null)
  const [cause, setCause] = useState('')
  const adv = useAdvanced()

  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 300)
    return () => clearTimeout(t)
  }, [q])

  const { data, isFetching } = useLab({
    search: debounced,
    ntee: cause,
    application_status: on.accepting ? 'Accepting Applications' : '',
    min_benchmarks: on.international ? '1' : '',
    sort: on.christian ? 'christian' : 'paid',
    ...adv.params,
  })

  return (
    <div className="mx-auto max-w-3xl">
      <LabBanner testing="one search box + three chips instead of a filter rail" />

      <h1 className="font-display text-3xl font-semibold text-primary
        text-center mt-6">
        Find your funders.
      </h1>
      <p className="text-center text-sm text-muted mt-1 mb-6">
        {data ? `${num(data.total)} foundations` : '…'} — start typing, or just
        flip a chip.
      </p>

      <div className="relative">
        <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2
          text-honey-600 pointer-events-none" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Foundation name…"
          aria-label="Search foundations"
          className="w-full rounded-2xl border border-honey-300/70 bg-surface
            py-3.5 pl-11 pr-12 text-base shadow-sm placeholder:text-muted/60
            focus:outline-none focus:ring-2 focus:ring-honey-400/40
            focus:border-honey-500" />
        {isFetching && (
          <Loader2 size={16} className="absolute right-4 top-1/2
            -translate-y-1/2 animate-spin text-muted" />
        )}
      </div>

      <div className="mt-3 flex flex-wrap justify-center gap-2">
        {CHIPS.map((c) => (
          <button key={c.key}
            onClick={() => setOn((s) => ({ ...s, [c.key]: !s[c.key] }))}
            className={`rounded-full border px-3.5 py-1.5 text-sm
              transition-colors ${on[c.key]
                ? 'border-primary bg-primary text-white'
                : 'border-line bg-surface text-muted hover:text-ink'}`}>
            {c.label}
          </button>
        ))}
        <CauseSelect value={cause} onChange={setCause} />
        <AdvancedButton adv={adv} />
      </div>

      <div className="mt-8 grid gap-3 sm:grid-cols-2">
        {(data?.rows ?? []).map((f) => (
          <FoundationCard key={f.ein} f={f} onOpen={setSelected} />
        ))}
      </div>
      {data && data.rows.length === 0 && (
        <div className="mt-10 text-center text-sm text-muted">
          Nothing matches — try fewer chips or a shorter name.
        </div>
      )}

      <AdvancedDrawer adv={adv} />
      {selected && (
        <DetailPanel ein={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}
