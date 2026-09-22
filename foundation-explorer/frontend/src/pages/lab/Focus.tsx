/** Lab 4 — The quiet table.
 *
 *  For users who DO want a table (Emily does), the minimal one: four
 *  plain-language columns, two sorts, filters folded into a single drawer
 *  that opens on demand. Tests how much of the current table's power
 *  survives losing five columns and every sub-label.
 */
import { useState } from 'react'
import { ChevronDown, SlidersHorizontal } from 'lucide-react'
import DetailPanel from '../../components/foundations/DetailPanel'
import { ANY_CHRISTIAN, CHRISTIAN_TRADITIONS } from '../../lib/apiV5'
import { US_STATES, money, num, titleCase } from '../../lib/format'
import { LabBanner, applyPhrase, focusPhrase, placeOf, useLab } from './shared'

export default function LabFocus() {
  const [denom, setDenom] = useState(ANY_CHRISTIAN)
  const [state, setState] = useState('')
  const [accepting, setAccepting] = useState(false)
  const [international, setInternational] = useState(false)
  const [sort, setSort] = useState<'christian' | 'median'>('christian')
  const [drawer, setDrawer] = useState(false)
  const [page, setPage] = useState(0)
  const [selected, setSelected] = useState<string | null>(null)

  const { data, isFetching } = useLab({
    tradition: denom,
    gives_to_state: state,
    application_status: accepting ? 'Accepting Applications' : '',
    min_benchmarks: international ? '1' : '',
    sort,
  }, 30, page)

  const active = [state && `gives in ${state}`, accepting && 'open to apply',
    international && 'international'].filter(Boolean).join(' · ')

  return (
    <div className="mx-auto max-w-4xl">
      <LabBanner testing="a four-column, plain-language table with one filter drawer" />

      <div className="flex items-end justify-between mb-3">
        <div>
          <h1 className="font-display text-3xl font-semibold text-primary">
            Funders
          </h1>
          <div className="text-sm text-muted mt-0.5">
            {data ? num(data.total) : '…'} foundations
            {active && <span> · {active}</span>}
          </div>
        </div>
        <button onClick={() => setDrawer((d) => !d)}
          className={`flex items-center gap-2 rounded-lg border px-3 py-1.5
            text-sm ${drawer
              ? 'border-primary/30 bg-primary/5 text-primary'
              : 'border-line text-muted hover:text-ink'}`}>
          <SlidersHorizontal size={14} /> Narrow it down
          <ChevronDown size={13}
            className={`transition-transform ${drawer ? 'rotate-180' : ''}`} />
        </button>
      </div>

      {drawer && (
        <div className="mb-4 grid gap-3 rounded-xl border border-line
          bg-surface p-4 sm:grid-cols-2">
          <label className="text-xs text-muted">
            Kind of giving
            <select value={denom} onChange={(e) => { setDenom(e.target.value); setPage(0) }}
              className="mt-1 w-full rounded-lg border border-line px-2.5
                py-2 text-sm text-ink focus:outline-none
                focus:border-honey-500">
              <option value={ANY_CHRISTIAN}>Any Christian giving</option>
              {CHRISTIAN_TRADITIONS.map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
              <option value="">Everything</option>
            </select>
          </label>
          <label className="text-xs text-muted">
            Gives grants in
            <select value={state} onChange={(e) => { setState(e.target.value); setPage(0) }}
              className="mt-1 w-full rounded-lg border border-line px-2.5
                py-2 text-sm text-ink focus:outline-none
                focus:border-honey-500">
              <option value="">Anywhere</option>
              {US_STATES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm text-ink">
            <input type="checkbox" checked={accepting}
              onChange={(e) => { setAccepting(e.target.checked); setPage(0) }}
              className="accent-primary" />
            Only funders I can apply to
          </label>
          <label className="flex items-center gap-2 text-sm text-ink">
            <input type="checkbox" checked={international}
              onChange={(e) => { setInternational(e.target.checked); setPage(0) }}
              className="accent-primary" />
            Funds international ministries
          </label>
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-line bg-surface">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b-2 border-honey-300 bg-honey-50/60
              text-left text-xs text-muted">
              <th className="py-2.5 px-4 font-medium">Foundation</th>
              <th className="px-3 font-medium">
                <SortBtn on={sort === 'christian'}
                  onClick={() => setSort('christian')}>
                  Christian giving
                </SortBtn>
              </th>
              <th className="px-3 font-medium">
                <SortBtn on={sort === 'median'}
                  onClick={() => setSort('median')}>
                  Typical grant
                </SortBtn>
              </th>
              <th className="px-3 font-medium">Can you apply?</th>
            </tr>
          </thead>
          <tbody className={isFetching ? 'opacity-60' : ''}>
            {(data?.rows ?? []).map((f) => {
              const focus = focusPhrase(f)
              const apply = applyPhrase(f.application_status)
              return (
                <tr key={f.ein} onClick={() => setSelected(f.ein)}
                  className="cursor-pointer border-b border-line/60
                    hover:bg-canvas">
                  <td className="py-2.5 px-4">
                    <div className="font-medium text-primary">
                      {titleCase(f.name)}
                    </div>
                    <div className="text-xs text-muted">{placeOf(f)}</div>
                  </td>
                  <td className="px-3">
                    <div className="tabular font-medium">
                      {money(f.christian_dollars)}
                    </div>
                    <div className={`text-xs ${focus.strong
                      ? 'text-scorehigh' : 'text-muted'}`}>
                      {focus.label}
                    </div>
                  </td>
                  <td className="px-3 tabular whitespace-nowrap">
                    {f.median_grant ? money(f.median_grant) : '—'}
                  </td>
                  <td className="px-3">
                    <span className={`text-xs font-medium ${
                      apply.open === true ? 'text-scorehigh'
                        : apply.open === false ? 'text-muted' : 'text-muted/60'}`}>
                      {apply.label}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {data && data.total > 30 && (
        <div className="mt-4 flex justify-center gap-3 text-sm">
          <button onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="rounded-lg border border-line px-4 py-2
              hover:bg-canvas disabled:opacity-40">Previous</button>
          <button onClick={() => setPage((p) => p + 1)}
            disabled={(page + 1) * 30 >= data.total}
            className="rounded-lg border border-line px-4 py-2
              hover:bg-canvas disabled:opacity-40">Next</button>
        </div>
      )}

      {selected && (
        <DetailPanel ein={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}

function SortBtn({ on, onClick, children }: {
  on: boolean; onClick: () => void; children: React.ReactNode
}) {
  return (
    <button onClick={onClick}
      className={`flex items-center gap-1 hover:text-ink
        ${on ? 'text-ink' : ''}`}>
      {children}{on && ' ↓'}
    </button>
  )
}
