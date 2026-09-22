/** Lab 3 — Card browser.
 *
 *  The middle path: keep browsing power, lose the rail. All filters live in
 *  one slim bar above a card grid — the Airbnb shape. Tests whether the
 *  table itself is part of what overwhelms, independent of filter count.
 *
 *  Reads ?preset= from the URL so Lab 5's big intent buttons can land here
 *  pre-filtered.
 */
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import DetailPanel from '../../components/foundations/DetailPanel'
import { ANY_CHRISTIAN, CHRISTIAN_TRADITIONS } from '../../lib/apiV5'
import { US_STATES, num } from '../../lib/format'
import { FoundationCard, LabBanner, useLab } from './shared'

const PRESETS: Record<string, Partial<State>> = {
  open: { accepting: true },
  international: { international: true },
  big: { sort: 'christian' },
}

type State = {
  denom: string
  state: string
  accepting: boolean
  international: boolean
  sort: 'christian' | 'paid' | 'median'
}

export default function LabCards() {
  const [params] = useSearchParams()
  const preset = PRESETS[params.get('preset') ?? ''] ?? {}
  const [s, setS] = useState<State>({
    denom: ANY_CHRISTIAN, state: '', accepting: false, international: false,
    sort: 'christian', ...preset,
  })
  const [page, setPage] = useState(0)
  const [selected, setSelected] = useState<string | null>(null)
  const set = (patch: Partial<State>) => { setS((p) => ({ ...p, ...patch })); setPage(0) }

  const { data, isFetching } = useLab({
    tradition: s.denom,
    gives_to_state: s.state,
    application_status: s.accepting ? 'Accepting Applications' : '',
    min_benchmarks: s.international ? '1' : '',
    sort: s.sort,
  }, 24, page)

  return (
    <div>
      <LabBanner testing="one slim filter bar + cards instead of rail + table" />

      <div className="flex items-end justify-between mb-3">
        <h1 className="font-display text-3xl font-semibold text-primary">
          Browse funders
        </h1>
        <span className="text-sm text-muted">
          {data ? `${num(data.total)} match` : '…'}
          {isFetching && <Loader2 size={13}
            className="ml-2 inline animate-spin" />}
        </span>
      </div>

      {/* The whole filter surface. Two selects, two toggles, one sort. */}
      <div className="sticky top-0 z-10 -mx-2 mb-5 flex flex-wrap items-center
        gap-2 rounded-xl border border-line bg-surface/95 px-3 py-2.5
        shadow-sm backdrop-blur">
        <select value={s.denom} onChange={(e) => set({ denom: e.target.value })}
          className="rounded-lg border border-line bg-surface px-2.5 py-1.5
            text-sm focus:outline-none focus:border-honey-500">
          <option value={ANY_CHRISTIAN}>Any Christian giving</option>
          {CHRISTIAN_TRADITIONS.map(([v, l]) => (
            <option key={v} value={v}>{l}</option>
          ))}
          <option value="">All foundations</option>
        </select>
        <select value={s.state} onChange={(e) => set({ state: e.target.value })}
          className="rounded-lg border border-line bg-surface px-2.5 py-1.5
            text-sm focus:outline-none focus:border-honey-500">
          <option value="">Gives anywhere</option>
          {US_STATES.map((st) => (
            <option key={st} value={st}>Gives in {st}</option>
          ))}
        </select>
        <Toggle on={s.accepting} onClick={() => set({ accepting: !s.accepting })}>
          I can apply
        </Toggle>
        <Toggle on={s.international}
          onClick={() => set({ international: !s.international })}>
          International
        </Toggle>
        <div className="ml-auto flex items-center gap-1.5 text-sm">
          <span className="text-xs text-muted">Sort</span>
          <select value={s.sort}
            onChange={(e) => set({ sort: e.target.value as State['sort'] })}
            className="rounded-lg border border-line bg-surface px-2 py-1.5
              text-sm focus:outline-none focus:border-honey-500">
            <option value="christian">Most Christian giving</option>
            <option value="paid">Biggest overall</option>
            <option value="median">Largest typical grant</option>
          </select>
        </div>
      </div>

      <div className={`grid gap-3 sm:grid-cols-2 lg:grid-cols-3
        min-[1700px]:grid-cols-4 ${isFetching ? 'opacity-60' : ''}`}>
        {(data?.rows ?? []).map((f) => (
          <FoundationCard key={f.ein} f={f} onOpen={setSelected} />
        ))}
      </div>

      {data && data.total > 24 && (
        <div className="mt-6 flex justify-center gap-3 text-sm">
          <button onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="rounded-lg border border-line px-4 py-2
              hover:bg-canvas disabled:opacity-40">
            Previous
          </button>
          <button onClick={() => setPage((p) => p + 1)}
            disabled={(page + 1) * 24 >= data.total}
            className="rounded-lg border border-line px-4 py-2
              hover:bg-canvas disabled:opacity-40">
            More funders
          </button>
        </div>
      )}

      {selected && (
        <DetailPanel ein={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}

function Toggle({ on, onClick, children }: {
  on: boolean; onClick: () => void; children: React.ReactNode
}) {
  return (
    <button onClick={onClick}
      className={`rounded-full border px-3 py-1.5 text-sm transition-colors
        ${on ? 'border-primary bg-primary text-white'
          : 'border-line bg-surface text-muted hover:text-ink'}`}>
      {children}
    </button>
  )
}
