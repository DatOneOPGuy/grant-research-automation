export type FoundationRow = {
  ein: string
  foundation_name: string
  city: string | null
  state: string | null
  distributions: number | null
  assets: number | null
  christian_dollars_3yr: number | null
  total_giving_3yr: number | null
  verdict: string | null
  christian_preview: string | null
  christian_recipient_count: number | null
  most_recent_christian_year: number | null
  predominant_tradition: string | null
  typical_grant_size: number | null
  largest_christian_grant: number | null
  application_status: string | null
  is_testamentary_trust: number | null
  is_small_fund: number | null
  data_found: string
  propublica_url: string
  latest_tax_year: number | null
}

export type Paged<T> = {
  total: number
  page: number
  page_size: number
  rows: T[]
}

export type FoundationFilterState = {
  q: string
  // Christian giving depth
  min_orgs?: number
  christian_min?: number
  recently_active: boolean
  traditions: string[]
  // grant-size behavior
  typical_sizes: string[]
  largest_min?: number
  // reachability
  include_invite: boolean
  status: string[]
  has_contact: boolean
  has_website: boolean
  has_phone: boolean
  has_deadline: boolean
  // geography
  states: string[]
  region: string
  gives_in_state: string
  // foundation profile
  sizes: string[]
  asset_buckets: string[]
  actively_giving: boolean
  include_trusts: boolean
  include_small: boolean
  // meta
  preset: string
  sort: string
  direction: 'asc' | 'desc'
  page: number
  page_size: number
}

export const defaultFilters: FoundationFilterState = {
  q: '',
  recently_active: false,
  traditions: [],
  typical_sizes: [],
  include_invite: false,
  status: [],
  has_contact: false,
  has_website: false,
  has_phone: false,
  has_deadline: false,
  states: [],
  region: '',
  gives_in_state: '',
  sizes: [],
  asset_buckets: [],
  actively_giving: false,
  include_trusts: false,
  include_small: false,
  preset: '',
  sort: '',
  direction: 'desc',
  page: 1,
  page_size: 50,
}

const LIST_KEYS = ['states', 'traditions', 'typical_sizes', 'status',
  'sizes', 'asset_buckets'] as const
const BOOL_KEYS = ['recently_active', 'include_invite', 'has_contact',
  'has_website', 'has_phone', 'has_deadline', 'actively_giving',
  'include_trusts', 'include_small'] as const
const NUM_KEYS = ['min_orgs', 'christian_min', 'largest_min'] as const

export function filterParams(f: FoundationFilterState): URLSearchParams {
  const p = new URLSearchParams()
  if (f.q) p.set('q', f.q)
  LIST_KEYS.forEach((k) => f[k].forEach((v) => p.append(k, v)))
  NUM_KEYS.forEach((k) => {
    if (f[k] !== undefined) p.set(k, String(f[k]))
  })
  BOOL_KEYS.forEach((k) => { if (f[k]) p.set(k, 'true') })
  if (f.region) p.set('region', f.region)
  if (f.gives_in_state) p.set('gives_in_state', f.gives_in_state)
  if (f.preset) p.set('preset', f.preset)
  if (f.sort) p.set('sort', f.sort)
  p.set('direction', f.direction)
  p.set('page', String(f.page))
  p.set('page_size', String(f.page_size))
  return p
}

// Count active filters (everything except paging/sort/search meta).
export function activeFilterChips(f: FoundationFilterState):
  { key: string; label: string; clear: Partial<FoundationFilterState> }[] {
  const chips: { key: string; label: string;
    clear: Partial<FoundationFilterState> }[] = []
  f.traditions.forEach((t) => chips.push({
    key: `trad-${t}`, label: t,
    clear: { traditions: f.traditions.filter((x) => x !== t) },
  }))
  f.typical_sizes.forEach((t) => chips.push({
    key: `typ-${t}`, label: `Grant size ${t}`,
    clear: { typical_sizes: f.typical_sizes.filter((x) => x !== t) },
  }))
  f.status.forEach((s) => chips.push({
    key: `st-${s}`, label: s,
    clear: { status: f.status.filter((x) => x !== s) },
  }))
  f.states.forEach((s) => chips.push({
    key: `state-${s}`, label: s,
    clear: { states: f.states.filter((x) => x !== s) },
  }))
  f.sizes.forEach((s) => chips.push({
    key: `sz-${s}`, label: `Size ${s}`,
    clear: { sizes: f.sizes.filter((x) => x !== s) },
  }))
  f.asset_buckets.forEach((s) => chips.push({
    key: `as-${s}`, label: `Assets ${s}`,
    clear: { asset_buckets: f.asset_buckets.filter((x) => x !== s) },
  }))
  if (f.min_orgs) chips.push({ key: 'orgs', label: `${f.min_orgs}+ orgs`,
    clear: { min_orgs: undefined } })
  if (f.christian_min) chips.push({ key: 'cmin',
    label: `Christian $${f.christian_min / 1000}k+`,
    clear: { christian_min: undefined } })
  if (f.largest_min) chips.push({ key: 'lmin',
    label: `Largest $${f.largest_min / 1000}k+`,
    clear: { largest_min: undefined } })
  if (f.region) chips.push({ key: 'region', label: f.region,
    clear: { region: '' } })
  if (f.gives_in_state) chips.push({ key: 'gis',
    label: `Gives in ${f.gives_in_state}`, clear: { gives_in_state: '' } })
  if (f.recently_active) chips.push({ key: 'ra', label: 'Recently active',
    clear: { recently_active: false } })
  if (f.actively_giving) chips.push({ key: 'ag', label: 'Actively giving',
    clear: { actively_giving: false } })
  for (const [k, label] of [['has_contact', 'Has contact'],
    ['has_website', 'Has website'], ['has_phone', 'Has phone'],
    ['has_deadline', 'Has deadline']] as const) {
    if (f[k]) chips.push({ key: k, label, clear: { [k]: false } })
  }
  return chips
}

// Demo mode: single build works on localhost (real backend) and Netlify
// (bundled static JSON). Override with ?demo=1 / ?live=1.
function detectDemo(): boolean {
  const params = new URLSearchParams(location.search)
  if (params.get('demo') === '1') return true
  if (params.get('live') === '1') return false
  const h = location.hostname
  return h !== 'localhost' && h !== '127.0.0.1' && h !== '[::1]'
}

export const DEMO = detectDemo()

export async function apiGet<T>(path: string): Promise<T> {
  if (DEMO) {
    const { demoGet } = await import('./demoApi')
    return demoGet(path)
  }
  const res = await fetch(path)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}
