import { useState } from 'react'
import type { ReactNode } from 'react'
import { ChevronDown, ChevronRight, Info, Sparkles } from 'lucide-react'
import {
  ANY_CHRISTIAN, APPLICATION_STATUSES, CHRISTIAN_TRADITIONS, COVERAGE_BANDS,
  defaultV5Filters, OTHER_TRADITIONS, PRESETS, US_REGIONS, type V5Filters,
} from '../../lib/apiV5'
import { US_STATES } from '../../lib/format'

type Props = {
  filters: V5Filters
  onChange: (f: V5Filters) => void
}

function Section({ title, children, defaultOpen = true }: {
  title: string; children: ReactNode; defaultOpen?: boolean
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
  label: ReactNode; checked: boolean; onChange: (v: boolean) => void
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

function NumInput({ value, onChange, placeholder }: {
  value: string; onChange: (v: string) => void; placeholder: string
}) {
  return (
    <input inputMode="numeric" placeholder={placeholder} value={value}
      onChange={(e) => onChange(e.target.value.replace(/[^0-9]/g, ''))}
      className="w-full border border-line rounded px-2 py-1 text-sm bg-surface" />
  )
}

function Range({ label, lo, hi, onLo, onHi }: {
  label: string; lo: string; hi: string
  onLo: (v: string) => void; onHi: (v: string) => void
}) {
  return (
    <div className="mb-2">
      <div className="text-xs text-muted mb-1">{label}</div>
      <div className="flex items-center gap-1">
        <NumInput value={lo} onChange={onLo} placeholder="Min $" />
        <span className="text-muted text-xs">–</span>
        <NumInput value={hi} onChange={onHi} placeholder="Max $" />
      </div>
    </div>
  )
}

// State picker with one-click region groupings. `onSet` replaces the whole
// list so region toggles can add/remove many states at once.
function StateMultiSelect({ values, onSet }: {
  values: string[]; onSet: (next: string[]) => void
}) {
  const toggleState = (s: string) =>
    onSet(values.includes(s) ? values.filter((x) => x !== s) : [...values, s])
  const toggleRegion = (states: string[]) => {
    const allOn = states.every((s) => values.includes(s))
    onSet(allOn
      ? values.filter((s) => !states.includes(s))
      : [...new Set([...values, ...states])])
  }
  return (
    <>
      <div className="flex flex-wrap gap-1 mb-1.5">
        {US_REGIONS.map(([name, states]) => {
          const allOn = states.every((s) => values.includes(s))
          return (
            <button key={name} onClick={() => toggleRegion(states)}
              title={states.join(', ')}
              className={`text-[11px] rounded-full px-2 py-0.5 border transition-colors ${
                allOn
                  ? 'bg-primary text-white border-primary'
                  : 'bg-canvas text-muted border-line hover:border-primary/60'}`}>
              {name}
            </button>)
        })}
      </div>
      <select className="w-full border border-line rounded px-2 py-1 text-sm mb-1 bg-surface"
        value=""
        onChange={(e) => e.target.value && toggleState(e.target.value)}>
        <option value="">Add state…</option>
        {US_STATES.filter((s) => !values.includes(s)).map((s) => (
          <option key={s} value={s}>{s}</option>))}
      </select>
      {values.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-1">
          {values.map((s) => (
            <button key={s} onClick={() => toggleState(s)}
              className="text-xs bg-primary text-white rounded-full px-2 py-0.5">
              {s} ×
            </button>))}
          <button onClick={() => onSet([])}
            className="text-xs text-muted underline px-1">clear</button>
        </div>
      )}
    </>
  )
}

const CHRISTIAN_KEYS = CHRISTIAN_TRADITIONS.map(([k]) => k)

export default function FilterPanel({ filters, onChange }: Props) {
  const set = (patch: Partial<V5Filters>) => onChange({ ...filters, ...patch })
  const toggleIn = (
    key: 'tradition' | 'state' | 'application_status' | 'coverage_band',
    v: string,
  ) => {
    const cur = filters[key]
    set({ [key]: cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v] })
  }
  // "Any Christian" is a parent of the specific Christian traditions: picking
  // it clears the children (and vice versa) so the query stays unambiguous.
  const toggleAnyChristian = (on: boolean) => {
    const rest = filters.tradition.filter(
      (t) => t !== ANY_CHRISTIAN && !CHRISTIAN_KEYS.includes(t))
    set({ tradition: on ? [ANY_CHRISTIAN, ...rest] : rest })
  }
  const toggleChristian = (t: string) => {
    const cur = filters.tradition.filter((x) => x !== ANY_CHRISTIAN)
    set({ tradition: cur.includes(t)
      ? cur.filter((x) => x !== t) : [...cur, t] })
  }

  // A preset is "active" when the current filters equal that preset applied
  // over defaults (ignoring sort/order, which the user may re-sort freely).
  const presetActive = (pf: Partial<V5Filters>) => {
    const target = { ...defaultV5Filters, ...pf }
    return (Object.keys(defaultV5Filters) as (keyof V5Filters)[])
      .filter((k) => k !== 'sort' && k !== 'order')
      .every((k) => JSON.stringify(filters[k]) === JSON.stringify(target[k]))
  }
  const applyPreset = (pf: Partial<V5Filters>) =>
    onChange({ ...defaultV5Filters, ...pf })

  return (
    <div className="w-60 shrink-0">
      <div className="mb-4">
        <div className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-muted mb-2">
          <Sparkles size={13} /> Presets
        </div>
        <div className="flex flex-col gap-1">
          {PRESETS.map((p) => {
            const active = presetActive(p.filters)
            return (
              <button key={p.id} onClick={() => applyPreset(p.filters)}
                title={p.hint}
                className={`text-left text-sm rounded-md px-2.5 py-1.5 border transition-colors ${
                  active
                    ? 'bg-primary/10 border-primary text-primary font-medium'
                    : 'bg-surface border-line hover:border-primary/50'}`}>
                {p.label}
              </button>)
          })}
        </div>
      </div>

      <Section title="Recipient Faith">
        <Check label={<span className="font-medium">Any Christian</span>}
          checked={filters.tradition.includes(ANY_CHRISTIAN)}
          onChange={toggleAnyChristian} />
        <div className="pl-4 border-l border-line/60 ml-1.5">
          {CHRISTIAN_TRADITIONS.map(([k, label]) => (
            <Check key={k} label={label}
              checked={filters.tradition.includes(k)}
              onChange={() => toggleChristian(k)} />
          ))}
        </div>
        <div className="mt-1.5">
          {OTHER_TRADITIONS.map(([k, label]) => (
            <Check key={k} label={label}
              checked={filters.tradition.includes(k)}
              onChange={() => toggleIn('tradition', k)} />
          ))}
        </div>
        <div className="mt-2 pt-2 border-t border-line/60">
          <Check
            label={<span title="Counts only NTEE codes, church codes, group exemptions, and human review — excludes name-rule guesses">
              High-confidence evidence only (NTEE/church-code/GEN/human)
            </span>}
            checked={filters.tier === 'authoritative'}
            onChange={(v) => set({ tier: v ? 'authoritative' : 'any' })} />
        </div>
        <div className="text-xs text-muted mb-1 mt-2">
          Min $ to selected tradition
        </div>
        <NumInput value={filters.min_tradition_dollars}
          onChange={(v) => set({ min_tradition_dollars: v })}
          placeholder="e.g. 100000" />
        <div className="text-xs text-muted mb-1 mt-2">
          Min # recipients of tradition
        </div>
        <NumInput value={filters.min_tradition_recipients}
          onChange={(v) => set({ min_tradition_recipients: v })}
          placeholder="e.g. 3" />
      </Section>

      <Section title="Giving">
        <Range label="Total paid (2023–24)"
          lo={filters.min_paid} hi={filters.max_paid}
          onLo={(v) => set({ min_paid: v })}
          onHi={(v) => set({ max_paid: v })} />
        <Range label="Median grant"
          lo={filters.min_median} hi={filters.max_median}
          onLo={(v) => set({ min_median: v })}
          onHi={(v) => set({ max_median: v })} />
        <div className="text-xs text-muted mb-1">Min grant count</div>
        <NumInput value={filters.min_grants}
          onChange={(v) => set({ min_grants: v })} placeholder="e.g. 10" />
        <div className="text-xs text-muted mb-1 mt-2">Active in year</div>
        <select className="w-full border border-line rounded px-2 py-1 text-sm bg-surface"
          value={filters.active_year}
          onChange={(e) => set({ active_year: e.target.value })}>
          <option value="">Either year</option>
          <option value="2023">2023</option>
          <option value="2024">2024</option>
        </select>
        <div className="text-xs text-muted mb-1 mt-2">
          Gave to a recipient named…
        </div>
        <input placeholder="e.g. Young Life"
          className="w-full border border-line rounded px-2 py-1 text-sm bg-surface"
          value={filters.recipient_search}
          onChange={(e) => set({ recipient_search: e.target.value })} />
      </Section>

      <Section title="Geography" defaultOpen={false}>
        <div className="text-xs text-muted mb-1">Foundation located in</div>
        <StateMultiSelect values={filters.state}
          onSet={(next) => set({ state: next })} />
        <div className="text-xs text-muted mb-1 mt-3">
          Gives to organizations in
        </div>
        <StateMultiSelect values={filters.gives_to_state}
          onSet={(next) => set({ gives_to_state: next })} />
      </Section>

      <Section title="Reachability" defaultOpen={false}>
        <div className="text-xs text-muted mb-1">Application status</div>
        {APPLICATION_STATUSES.map((s) => (
          <Check key={s} label={s}
            checked={filters.application_status.includes(s)}
            onChange={() => toggleIn('application_status', s)} />
        ))}
        <div className="mt-1 pt-1 border-t border-line/60">
          <Check label="Has website" checked={filters.has_website}
            onChange={(v) => set({ has_website: v })} />
          <Check label="Has email" checked={filters.has_email}
            onChange={(v) => set({ has_email: v })} />
          <Check label="Has contact person" checked={filters.has_contact}
            onChange={(v) => set({ has_contact: v })} />
        </div>
      </Section>

      <Section title="Foundation" defaultOpen={false}>
        <Range label="Total assets"
          lo={filters.min_assets} hi={filters.max_assets}
          onLo={(v) => set({ min_assets: v })}
          onHi={(v) => set({ max_assets: v })} />
        <div className="text-xs text-muted mb-1">Min revenue</div>
        <NumInput value={filters.min_revenue}
          onChange={(v) => set({ min_revenue: v })} placeholder="Min $" />
        <div className="mt-2 pt-2 border-t border-line/60">
          <Check label="Exclude testamentary trusts"
            checked={filters.exclude_testamentary}
            onChange={(v) => set({ exclude_testamentary: v })} />
          <Check label="Exclude micro-funds"
            checked={filters.exclude_micro}
            onChange={(v) => set({ exclude_micro: v })} />
        </div>
        <div className="text-xs text-muted mb-1 mt-2">Donor-advised funds</div>
        {([['include', 'Include DAFs'], ['exclude', 'Exclude DAFs'],
          ['only', 'DAFs only']] as const).map(([v, label]) => (
          <label key={v}
            className="flex items-center gap-2 text-sm py-0.5 cursor-pointer">
            <input type="radio" name="daf" className="accent-primary"
              checked={filters.daf === v}
              onChange={() => set({ daf: v })} />
            {label}
          </label>
        ))}
      </Section>

      <Section title="Data Quality" defaultOpen={false}>
        <div className="flex items-center gap-1 text-xs text-muted mb-1">
          Coverage band
          <span title="Coverage = % of this foundation's paid dollars with a classified recipient">
            <Info size={12} />
          </span>
        </div>
        {COVERAGE_BANDS.map((b) => (
          <Check key={b} label={b}
            checked={filters.coverage_band.includes(b)}
            onChange={() => toggleIn('coverage_band', b)} />
        ))}
        <div className="text-xs text-muted mb-1 mt-2">
          Min coverage: {filters.min_coverage || 0}%
        </div>
        <input type="range" min={0} max={100} step={5}
          className="w-full accent-primary"
          value={Number(filters.min_coverage) || 0}
          onChange={(e) => set({
            min_coverage: e.target.value === '0' ? '' : e.target.value })} />
      </Section>
    </div>
  )
}
