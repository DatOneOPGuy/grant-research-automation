// Typed client for the v5 API (paid grants, TY2023–2024).
export const V5_BASE = 'http://localhost:8000'

export type StatsV5 = {
  foundations: number
  active: number
  paid: number
  christian: number
  nonchristian: number
  unclassified: number
  daf: number
  recipients: number
  with_mission: number
  window: string
  identity_run: string
}

export type FoundationRowV5 = {
  ein: string
  name: string
  city: string | null
  state: string | null
  paid_2324: number
  grant_count_2324: number
  recipient_count: number
  median_grant: number | null
  christian_dollars: number
  nonchristian_dollars: number
  unclassified_dollars: number
  daf_dollars: number
  coverage_pct: number
  coverage_band: string
  application_status: string | null
  website: string | null
  assets: number | null
  revenue: number | null
  is_testamentary: boolean
  is_micro: boolean
}

export type FoundationsResponseV5 = { total: number; rows: FoundationRowV5[] }

export type TraditionRollupV5 = {
  tradition: string
  tier: string
  dollars: number
  recipients: number
}

export type FoundationRecipientV5 = {
  entity_id: string
  name: string
  recipient_ein: string | null
  identity_status: string
  tradition: string | null
  method: string | null
  confidence: number | null
  is_daf: boolean
  has_mission: boolean
  dollars: number
  grants: number
  last_year: number
}

export type StateDollarsV5 = { state: string; dollars: number }

export type FoundationDetailV5 = {
  foundation: FoundationRowV5
  traditions: TraditionRollupV5[]
  recipients: FoundationRecipientV5[]
  states: StateDollarsV5[]
}

export type GrantRowV5 = {
  recipient_name: string
  recipient_city: string | null
  recipient_state: string | null
  amount: number
  tax_year: number
  purpose: string | null
  entity_id: string | null
  tradition: string | null
  identity_status: string | null
}

export type RecipientDetailV5 = {
  recipient: {
    entity_id: string
    ein: string | null
    name: string
    identity_status: string
    tradition: string | null
    method: string | null
    confidence: number | null
    is_daf: boolean
    mission_text: string | null
    website: string | null
    total_received: number
    funder_count: number
  }
  funders: { ein: string; name: string; dollars: number; grants: number; last_year: number }[]
}

// ---- tradition vocabulary --------------------------------------------------
export const CHRISTIAN_TRADITIONS: [string, string][] = [
  ['evangelical_protestant', 'Evangelical / Protestant'],
  ['catholic', 'Catholic'],
  ['orthodox_christian', 'Orthodox'],
  ['christian_unspecified', 'Christian (unspecified)'],
]
export const OTHER_TRADITIONS: [string, string][] = [
  ['jewish', 'Jewish'],
  ['muslim', 'Muslim'],
  ['mormon_lds', 'Mormon / LDS'],
  ['christian_science', 'Christian Science'],
  ['other_religion', 'Other religion'],
  ['secular', 'Secular'],
  ['unclassified', 'Unclassified'],
]
export const ANY_CHRISTIAN = 'any_christian'

const TRADITION_LABELS: Record<string, string> = Object.fromEntries([
  ...CHRISTIAN_TRADITIONS, ...OTHER_TRADITIONS, [ANY_CHRISTIAN, 'Any Christian'],
])
export function traditionLabel(t: string | null | undefined): string {
  if (!t) return 'Unclassified'
  return TRADITION_LABELS[t] || t
}

export const APPLICATION_STATUSES = [
  'Accepting Applications', 'Contact First', 'Invite Only', 'Unknown',
]
export const COVERAGE_BANDS = ['High', 'Moderate', 'Low']

// ---- filter state ----------------------------------------------------------
// Numeric fields are kept as strings ('' = unset) so text inputs and URL
// round-tripping stay trivial; they are parsed when building query params.
export type V5Filters = {
  tradition: string[]
  tier: 'any' | 'authoritative'
  min_tradition_dollars: string
  min_tradition_recipients: string
  min_paid: string
  max_paid: string
  min_median: string
  max_median: string
  min_grants: string
  active_year: string // '' | '2023' | '2024'
  recipient_search: string
  state: string[]
  gives_to_state: string
  application_status: string[]
  has_website: boolean
  has_email: boolean
  has_contact: boolean
  min_assets: string
  max_assets: string
  min_revenue: string
  exclude_testamentary: boolean
  exclude_micro: boolean
  daf: 'include' | 'exclude' | 'only'
  coverage_band: string[]
  min_coverage: string
  sort: string
  order: 'asc' | 'desc'
}

export const defaultV5Filters: V5Filters = {
  tradition: [],
  tier: 'any',
  min_tradition_dollars: '',
  min_tradition_recipients: '',
  min_paid: '',
  max_paid: '',
  min_median: '',
  max_median: '',
  min_grants: '',
  active_year: '',
  recipient_search: '',
  state: [],
  gives_to_state: '',
  application_status: [],
  has_website: false,
  has_email: false,
  has_contact: false,
  min_assets: '',
  max_assets: '',
  min_revenue: '',
  exclude_testamentary: false,
  exclude_micro: false,
  daf: 'include',
  coverage_band: [],
  min_coverage: '',
  sort: 'paid',
  order: 'desc',
}

const LIST_KEYS = ['tradition', 'state', 'application_status',
  'coverage_band'] as const
const NUM_KEYS = ['min_tradition_dollars', 'min_tradition_recipients',
  'min_paid', 'max_paid', 'min_median', 'max_median', 'min_grants',
  'min_assets', 'max_assets', 'min_revenue', 'min_coverage'] as const
const BOOL_KEYS = ['has_website', 'has_email', 'has_contact',
  'exclude_testamentary', 'exclude_micro'] as const

// Build API query params (also used verbatim for URL sharing).
export function v5FilterParams(f: V5Filters): URLSearchParams {
  const p = new URLSearchParams()
  LIST_KEYS.forEach((k) => { if (f[k].length) p.set(k, f[k].join(',')) })
  if (f.tier !== 'any') p.set('tier', f.tier)
  NUM_KEYS.forEach((k) => {
    const n = Number(f[k])
    if (f[k] !== '' && Number.isFinite(n)) p.set(k, String(Math.round(n)))
  })
  BOOL_KEYS.forEach((k) => { if (f[k]) p.set(k, 'true') })
  if (f.active_year) p.set('active_year', f.active_year)
  if (f.recipient_search.trim()) p.set('recipient_search', f.recipient_search.trim())
  if (f.gives_to_state) p.set('gives_to_state', f.gives_to_state)
  if (f.daf !== 'include') p.set('daf', f.daf)
  if (f.sort !== defaultV5Filters.sort) p.set('sort', f.sort)
  if (f.order !== defaultV5Filters.order) p.set('order', f.order)
  return p
}

// Restore filter state from a shared URL query string.
export function v5FiltersFromParams(sp: URLSearchParams): V5Filters {
  const f: V5Filters = { ...defaultV5Filters }
  LIST_KEYS.forEach((k) => {
    const v = sp.get(k)
    if (v) f[k] = v.split(',').filter(Boolean)
  })
  if (sp.get('tier') === 'authoritative') f.tier = 'authoritative'
  NUM_KEYS.forEach((k) => { const v = sp.get(k); if (v) f[k] = v })
  BOOL_KEYS.forEach((k) => { if (sp.get(k) === 'true') f[k] = true })
  f.active_year = sp.get('active_year') || ''
  f.recipient_search = sp.get('recipient_search') || ''
  f.gives_to_state = sp.get('gives_to_state') || ''
  const daf = sp.get('daf')
  if (daf === 'exclude' || daf === 'only') f.daf = daf
  f.sort = sp.get('sort') || defaultV5Filters.sort
  f.order = sp.get('order') === 'asc' ? 'asc' : defaultV5Filters.order
  return f
}

// ---- fetchers ---------------------------------------------------------------
async function getV5<T>(path: string): Promise<T> {
  const res = await fetch(`${V5_BASE}${path}`)
  if (!res.ok) throw new Error(`v5 API ${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export function fetchStatsV5(): Promise<StatsV5> {
  return getV5('/api/v5/stats')
}

export function fetchFoundationsV5(
  queryString: string, limit = 500, offset = 0,
): Promise<FoundationsResponseV5> {
  const p = new URLSearchParams(queryString)
  p.set('limit', String(limit))
  p.set('offset', String(offset))
  return getV5(`/api/v5/foundations?${p.toString()}`)
}

export function fetchFoundationDetailV5(ein: string): Promise<FoundationDetailV5> {
  return getV5(`/api/v5/foundations/${ein}`)
}

export function fetchFoundationGrantsV5(
  ein: string, limit = 100, offset = 0,
): Promise<{ rows: GrantRowV5[] }> {
  return getV5(`/api/v5/foundations/${ein}/grants?limit=${limit}&offset=${offset}`)
}

export function fetchRecipientV5(entityId: string): Promise<RecipientDetailV5> {
  return getV5(`/api/v5/recipients/${entityId}`)
}
