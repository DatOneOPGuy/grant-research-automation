import type { FoundationFilterState } from '../../lib/api'
import { US_STATES } from '../../lib/format'

const VERDICTS: [string, string][] = [
  ['strong', 'Funds Christian organizations'],
  ['some', 'Some Christian giving'],
  ['any', 'Any Christian giving'],
]
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

  const toggle = (key: 'sizes' | 'states', v: string) => {
    const cur = filters[key]
    set({ [key]: cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v] })
  }

  return (
    <div className="w-64 shrink-0">
      <Section title="Christian Giving">
        <div className="text-xs text-muted mb-1">Verdict</div>
        {VERDICTS.map(([v, label]) => (
          <label key={v}
            className="flex items-center gap-2 text-sm py-0.5 cursor-pointer">
            <input type="radio" name="verdict" checked={filters.verdict === v}
              onChange={() => set({ verdict: v })} className="accent-primary" />
            {label}
          </label>
        ))}
        <div className="text-xs text-muted mb-1 mt-3">
          Min Christian $ (3yr)
        </div>
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
        <div className="mt-3">
          <Check label="Recently active (2024 grants)"
            checked={filters.recently_active}
            onChange={(v) => set({ recently_active: v })} />
        </div>
      </Section>

      <Section title="Reachability">
        <div className="text-xs text-muted mb-2">
          Default shows foundations you can approach (accepting or contact
          first).
        </div>
        <Check label="Include invite-only foundations"
          checked={filters.include_invite}
          onChange={(v) => set({ include_invite: v })} />
        <div className="mt-2 pt-2 border-t border-line/60">
          <Check label="Has contact person" checked={filters.has_contact}
            onChange={(v) => set({ has_contact: v })} />
          <Check label="Has website" checked={filters.has_website}
            onChange={(v) => set({ has_website: v })} />
          <Check label="Has phone" checked={filters.has_phone}
            onChange={(v) => set({ has_phone: v })} />
        </div>
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
