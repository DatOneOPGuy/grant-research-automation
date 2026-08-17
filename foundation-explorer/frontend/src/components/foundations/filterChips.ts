// Derives the removable chip list from a filter state. Kept out of the
// component file so React Fast Refresh keeps working, and so the Filters
// button's badge and the chip row are computed by the same code -- the count
// and the chips can never disagree.
import { traditionLabel, type V5Filters } from '../../lib/apiV5'
import { money } from '../../lib/format'

export type Chip = { id: string; label: string; onRemove: () => void }

function statesLabel(arr: string[]): string {
  return arr.length <= 4 ? arr.join(', ')
    : `${arr.slice(0, 3).join(', ')} +${arr.length - 3}`
}

// Derive one removable chip per active (non-default) filter dimension.
export function buildChips(
  f: V5Filters, set: (patch: Partial<V5Filters>) => void,
): Chip[] {
  const chips: Chip[] = []
  f.tradition.forEach((t) => chips.push({
    id: `tr-${t}`, label: traditionLabel(t),
    onRemove: () => set({ tradition: f.tradition.filter((x) => x !== t) }),
  }))
  if (f.tier === 'authoritative') chips.push({
    id: 'tier', label: 'High-confidence only',
    onRemove: () => set({ tier: 'any' }),
  })
  const moneyScalars: [keyof V5Filters, string][] = [
    ['min_tradition_dollars', '≥ %v to tradition'],
    ['min_paid', 'Paid ≥ %v'], ['max_paid', 'Paid ≤ %v'],
    ['min_median', 'Median ≥ %v'], ['max_median', 'Median ≤ %v'],
    ['min_assets', 'Assets ≥ %v'], ['max_assets', 'Assets ≤ %v'],
    ['min_revenue', 'Revenue ≥ %v'],
  ]
  moneyScalars.forEach(([k, tpl]) => {
    if (f[k]) chips.push({
      id: k, label: tpl.replace('%v', money(Number(f[k]))),
      onRemove: () => set({ [k]: '' }),
    })
  })
  const countScalars: [keyof V5Filters, string][] = [
    ['min_tradition_recipients', '≥ %v recipients of tradition'],
    ['min_grants', '≥ %v grants'],
  ]
  countScalars.forEach(([k, tpl]) => {
    if (f[k]) chips.push({
      id: k, label: tpl.replace('%v', String(f[k])),
      onRemove: () => set({ [k]: '' }),
    })
  })
  if (f.min_coverage) chips.push({
    id: 'cov', label: `Coverage ≥ ${f.min_coverage}%`,
    onRemove: () => set({ min_coverage: '' }),
  })
  if (f.active_year) chips.push({
    id: 'yr', label: `Active ${f.active_year}`,
    onRemove: () => set({ active_year: '' }),
  })
  if (f.recipient_search.trim()) chips.push({
    id: 'rs', label: `Recipient: “${f.recipient_search.trim()}”`,
    onRemove: () => set({ recipient_search: '' }),
  })
  if (f.state.length) chips.push({
    id: 'st', label: `Located in: ${statesLabel(f.state)}`,
    onRemove: () => set({ state: [] }),
  })
  if (f.gives_to_state.length) chips.push({
    id: 'gts', label: `Gives to: ${statesLabel(f.gives_to_state)}`,
    onRemove: () => set({ gives_to_state: [] }),
  })
  f.application_status.forEach((s) => chips.push({
    id: `as-${s}`, label: s,
    onRemove: () => set({
      application_status: f.application_status.filter((x) => x !== s) }),
  }))
  f.coverage_band.forEach((b) => chips.push({
    id: `cb-${b}`, label: `${b} coverage`,
    onRemove: () => set({
      coverage_band: f.coverage_band.filter((x) => x !== b) }),
  }))
  const bools: [keyof V5Filters, string][] = [
    ['has_website', 'Has website'], ['has_email', 'Has email'],
    ['has_contact', 'Has contact'],
    ['exclude_testamentary', 'No testamentary trusts'],
    ['exclude_micro', 'No micro-funds'],
  ]
  bools.forEach(([k, label]) => {
    if (f[k]) chips.push({ id: k, label, onRemove: () => set({ [k]: false }) })
  })
  if (f.daf !== 'include') chips.push({
    id: 'daf', label: f.daf === 'exclude' ? 'Exclude DAFs' : 'DAFs only',
    onRemove: () => set({ daf: 'include' }),
  })
  return chips
}


/** How many filter dimensions are currently applied. Shown on the Filters
 *  button so a collapsed panel never hides that the list is narrowed. */
export function activeFilterCount(f: V5Filters): number {
  return buildChips(f, () => {}).length
}
