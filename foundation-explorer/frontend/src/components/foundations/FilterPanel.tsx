import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import type { FoundationFilterState } from '../../lib/api'
import { US_STATES } from '../../lib/format'

const TRADITIONS = ['Evangelical/Protestant', 'Catholic', 'Orthodox']
const ORG_COUNTS: [string, number | undefined][] = [
  ['Any', undefined], ['3+', 3], ['10+', 10], ['25+', 25],
]
const CHRISTIAN_MINS: [string, number | undefined][] = [
  ['Any', undefined], ['$100k+', 100000], ['$1M+', 1000000],
  ['$10M+', 10000000],
]
const TYPICAL: [string, string][] = [
  ['lt10k', 'Under $10k'], ['10k-50k', '$10k–50k'],
  ['50k-250k', '$50k–250k'], ['gte250k', '$250k+'],
]
const LARGEST: [string, number | undefined][] = [
  ['Any', undefined], ['$50k+', 50000], ['$250k+', 250000], ['$1M+', 1000000],
]
const STATUSES = ['Accepting Applications', 'Contact First']
const REGIONS = ['northeast', 'southeast', 'midwest', 'southwest', 'west']
const SIZES: [string, string][] = [
  ['lt100k', '<$100k'], ['100k-1m', '$100k–1M'],
  ['1m-10m', '$1M–10M'], ['gte10m', '$10M+'],
]
const ASSETS: [string, string][] = [
  ['lt1m', '<$1M'], ['1m-10m', '$1M–10M'],
  ['10m-100m', '$10M–100M'], ['gte100m', '$100M+'],
]

type Props = {
  filters: FoundationFilterState
  onChange: (f: FoundationFilterState) => void
}

function Section({ title, children, defaultOpen = true }: {
  title: string; children: React.ReactNode; defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border-b border-line pb-3 mb-3">
      <button onClick={() => setOpen(!open)}
        className="flex items-center gap-1 w-full text-xs font-semibold uppercase tracking-wide text-muted mb-2">
        {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        {title}
      </button>
      {open && children}
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

function Pills({ options, value, onPick }: {
  options: [string, number | undefined][]
  value: number | undefined; onPick: (v: number | undefined) => void
}) {
  return (
    <div className="flex flex-wrap gap-1">
      {options.map(([label, v]) => (
        <button key={label} onClick={() => onPick(v)}
          className={`text-xs rounded-full px-2 py-0.5 border ${
            value === v ? 'bg-primary text-white border-primary'
              : 'border-line text-muted'}`}>
          {label}
        </button>
      ))}
    </div>
  )
}

export default function FilterPanel({ filters, onChange }: Props) {
  const set = (patch: Partial<FoundationFilterState>) =>
    onChange({ ...filters, ...patch, page: 1 })
  const toggleIn = (key: 'traditions' | 'typical_sizes' | 'status'
    | 'states' | 'sizes' | 'asset_buckets', v: string) => {
    const cur = filters[key]
    set({ [key]: cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v] })
  }

  return (
    <div className="w-64 shrink-0">
      <Section title="Christian Giving">
        <div className="text-xs text-muted mb-1"># Christian orgs funded</div>
        <Pills options={ORG_COUNTS} value={filters.min_orgs}
          onPick={(v) => set({ min_orgs: v })} />
        <div className="text-xs text-muted mb-1 mt-3">Min Christian $ (3yr)</div>
        <Pills options={CHRISTIAN_MINS} value={filters.christian_min}
          onPick={(v) => set({ christian_min: v })} />
        <div className="text-xs text-muted mb-1 mt-3">Tradition focus</div>
        {TRADITIONS.map((t) => (
          <Check key={t} label={t} checked={filters.traditions.includes(t)}
            onChange={() => toggleIn('traditions', t)} />
        ))}
        <div className="mt-2">
          <Check label="Recently active (2024 grants)"
            checked={filters.recently_active}
            onChange={(v) => set({ recently_active: v })} />
        </div>
      </Section>

      <Section title="Grant Size">
        <div className="text-xs text-muted mb-1">Typical grant size</div>
        <div className="flex flex-wrap gap-1">
          {TYPICAL.map(([v, label]) => (
            <button key={v} onClick={() => toggleIn('typical_sizes', v)}
              className={`text-xs rounded-full px-2 py-0.5 border ${
                filters.typical_sizes.includes(v)
                  ? 'bg-primary text-white border-primary'
                  : 'border-line text-muted'}`}>
              {label}
            </button>
          ))}
        </div>
        <div className="text-xs text-muted mb-1 mt-3">
          Largest single Christian grant
        </div>
        <Pills options={LARGEST} value={filters.largest_min}
          onPick={(v) => set({ largest_min: v })} />
      </Section>

      <Section title="Reachability">
        <div className="text-xs text-muted mb-1">Accepts</div>
        {STATUSES.map((s) => (
          <Check key={s} label={s} checked={filters.status.includes(s)}
            onChange={() => toggleIn('status', s)} />
        ))}
        <div className="mt-1 pt-1 border-t border-line/60">
          <Check label="Has contact person" checked={filters.has_contact}
            onChange={(v) => set({ has_contact: v })} />
          <Check label="Has website" checked={filters.has_website}
            onChange={(v) => set({ has_website: v })} />
          <Check label="Has phone" checked={filters.has_phone}
            onChange={(v) => set({ has_phone: v })} />
          <Check label="Has application deadline info"
            checked={filters.has_deadline}
            onChange={(v) => set({ has_deadline: v })} />
        </div>
      </Section>

      <Section title="Geography" defaultOpen={false}>
        <div className="text-xs text-muted mb-1">Region</div>
        <div className="flex flex-wrap gap-1 mb-3">
          {REGIONS.map((r) => (
            <button key={r}
              onClick={() => set({ region: filters.region === r ? '' : r })}
              className={`text-xs rounded-full px-2 py-0.5 border capitalize ${
                filters.region === r ? 'bg-primary text-white border-primary'
                  : 'border-line text-muted'}`}>
              {r}
            </button>
          ))}
        </div>
        <div className="text-xs text-muted mb-1">Located in state</div>
        <select className="w-full border border-line rounded px-2 py-1 text-sm mb-2"
          value=""
          onChange={(e) => e.target.value && toggleIn('states', e.target.value)}>
          <option value="">Add state…</option>
          {US_STATES.filter((s) => !filters.states.includes(s)).map((s) => (
            <option key={s} value={s}>{s}</option>))}
        </select>
        {filters.states.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-2">
            {filters.states.map((s) => (
              <button key={s} onClick={() => toggleIn('states', s)}
                className="text-xs bg-primary text-white rounded-full px-2 py-0.5">
                {s} ×
              </button>))}
          </div>
        )}
        <div className="text-xs text-muted mb-1 mt-2">
          Gives to organizations in
        </div>
        <select className="w-full border border-line rounded px-2 py-1 text-sm"
          value={filters.gives_in_state}
          onChange={(e) => set({ gives_in_state: e.target.value })}>
          <option value="">Any state</option>
          {US_STATES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </Section>

      <Section title="Foundation Profile" defaultOpen={false}>
        <div className="text-xs text-muted mb-1">Total distributions</div>
        {SIZES.map(([v, label]) => (
          <Check key={v} label={label} checked={filters.sizes.includes(v)}
            onChange={() => toggleIn('sizes', v)} />
        ))}
        <div className="text-xs text-muted mb-1 mt-2">Total assets</div>
        {ASSETS.map(([v, label]) => (
          <Check key={v} label={label}
            checked={filters.asset_buckets.includes(v)}
            onChange={() => toggleIn('asset_buckets', v)} />
        ))}
        <div className="mt-2 pt-2 border-t border-line/60">
          <Check label="Actively giving (latest year)"
            checked={filters.actively_giving}
            onChange={(v) => set({ actively_giving: v })} />
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
