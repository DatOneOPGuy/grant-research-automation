import type { FoundationFilterState } from '../../lib/api'
import { US_STATES } from '../../lib/format'

const STATUSES = ['Accepting Applications', 'Invite Only', 'Unknown']
const SIZES: [string, string][] = [
  ['lt100k', '<$100k'], ['100k-1m', '$100k–1M'],
  ['1m-10m', '$1M–10M'], ['gte10m', '$10M+'],
]
const CHRISTIAN_MINS: [string, number | undefined][] = [
  ['Any', undefined], ['$100k+', 100000], ['$1M+', 1000000],
  ['$10M+', 10000000],
]

type Props = {
  filters: FoundationFilterState
  onChange: (f: FoundationFilterState) => void
}

function Section({ title, children }: {
  title: string; children: React.ReactNode
}) {
  return (
    <div className="border-b border-line pb-4 mb-4">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted mb-2">
        {title}
      </div>
      {children}
    </div>
  )
}

function Check({ label, checked, onChange }: {
  label: string; checked: boolean; onChange: (v: boolean) => void
}) {
  return (
    <label className="flex items-center gap-2 text-sm py-0.5 cursor-pointer">
      <input type="checkbox" checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="accent-primary" />
      {label}
    </label>
  )
}

export default function FilterPanel({ filters, onChange }: Props) {
  const set = (patch: Partial<FoundationFilterState>) =>
    onChange({ ...filters, ...patch, page: 1 })

  const toggle = (key: 'status' | 'sizes' | 'states', v: string) => {
    const cur = filters[key]
    set({ [key]: cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v] })
  }

  return (
    <div className="w-64 shrink-0">
      <Section title="Faith Alignment">
        <div className="text-xs text-muted mb-1">Composite score</div>
        <div className="flex items-center gap-2 mb-3 text-sm">
          <input type="number" min={0} max={100} placeholder="Min"
            className="w-16 border border-line rounded px-2 py-1"
            value={filters.score_min ?? ''}
            onChange={(e) => set({ score_min: e.target.value === '' ? undefined
              : Number(e.target.value) })} />
          <span className="text-muted">to</span>
          <input type="number" min={0} max={100} placeholder="Max"
            className="w-16 border border-line rounded px-2 py-1"
            value={filters.score_max ?? ''}
            onChange={(e) => set({ score_max: e.target.value === '' ? undefined
              : Number(e.target.value) })} />
        </div>
        <div className="text-xs text-muted mb-1">Min % Christian giving</div>
        <input type="number" min={0} max={100} placeholder="e.g. 25"
          className="w-full border border-line rounded px-2 py-1 text-sm mb-3"
          value={filters.pct_min ?? ''}
          onChange={(e) => set({ pct_min: e.target.value === '' ? undefined
            : Number(e.target.value) })} />
        <div className="text-xs text-muted mb-1">Min Christian $ (3yr)</div>
        <div className="flex flex-wrap gap-1">
          {CHRISTIAN_MINS.map(([label, v]) => (
            <button key={label} onClick={() => set({ christian_min: v })}
              className={`text-xs rounded-full px-2 py-0.5 border ${
                filters.christian_min === v
                  ? 'bg-primary text-white border-primary'
                  : 'border-line text-muted'}`}>
              {label}
            </button>
          ))}
        </div>
      </Section>

      <Section title="Application Access">
        {STATUSES.map((s) => (
          <Check key={s} label={s} checked={filters.status.includes(s)}
            onChange={() => toggle('status', s)} />
        ))}
        <Check label="Has contact person" checked={filters.has_contact}
          onChange={(v) => set({ has_contact: v })} />
        <Check label="Has website" checked={filters.has_website}
          onChange={(v) => set({ has_website: v })} />
        <Check label="Has phone" checked={filters.has_phone}
          onChange={(v) => set({ has_phone: v })} />
      </Section>

      <Section title="Basic Info">
        <select className="w-full border border-line rounded px-2 py-1 text-sm mb-2"
          value=""
          onChange={(e) => e.target.value && toggle('states', e.target.value)}>
          <option value="">Add state…</option>
          {US_STATES.filter((s) => !filters.states.includes(s)).map((s) => (
            <option key={s} value={s}>{s}</option>))}
        </select>
        {filters.states.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-2">
            {filters.states.map((s) => (
              <button key={s} onClick={() => toggle('states', s)}
                className="text-xs bg-primary text-white rounded-full px-2 py-0.5">
                {s} ×
              </button>))}
          </div>
        )}
        {SIZES.map(([v, label]) => (
          <Check key={v} label={label} checked={filters.sizes.includes(v)}
            onChange={() => toggle('sizes', v)} />
        ))}
        <div className="mt-2 pt-2 border-t border-line/60">
          <Check label="Include testamentary trusts"
            checked={filters.include_trusts}
            onChange={(v) => set({ include_trusts: v })} />
          <Check label="Include micro-funds (<$10k)"
            checked={filters.include_small}
            onChange={(v) => set({ include_small: v })} />
        </div>
      </Section>
    </div>
  )
}
