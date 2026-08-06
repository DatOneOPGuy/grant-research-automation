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
  nonclassifiable_dollars: number
  classifiable_dollars: number
  classified_dollars: number
  // null means "nothing could be classified" -- never render this as 0%.
  pct_christian: number | null
  auth_christian_dollars: number
  pct_christian_auth: number | null
  unattributable_reason: string | null
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
  reason: string | null
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
export const COVERAGE_BANDS = ['High', 'Moderate', 'Low', 'Not Classifiable']

// ---- geographic regions ----------------------------------------------------
// Census divisions plus a domain-specific "Bible Belt" grouping that maps to
// how faith-based fundraisers actually think about territory. Each expands to
// state codes for the `state` / `gives_to_state` filters.
export const US_REGIONS: [string, string[]][] = [
  ['Northeast', ['CT', 'ME', 'MA', 'NH', 'RI', 'VT', 'NJ', 'NY', 'PA']],
  ['Southeast', ['AL', 'AR', 'FL', 'GA', 'KY', 'LA', 'MS', 'NC', 'SC',
    'TN', 'VA', 'WV']],
  ['Midwest', ['IL', 'IN', 'IA', 'KS', 'MI', 'MN', 'MO', 'NE', 'ND',
    'OH', 'SD', 'WI']],
  ['Southwest', ['AZ', 'NM', 'OK', 'TX']],
  ['West', ['AK', 'CA', 'CO', 'HI', 'ID', 'MT', 'NV', 'OR', 'UT', 'WA', 'WY']],
  ['Bible Belt', ['AL', 'AR', 'GA', 'KY', 'LA', 'MS', 'MO', 'NC', 'OK',
    'SC', 'TN', 'TX', 'VA', 'WV']],
]

// ---- presets ---------------------------------------------------------------
// Each preset is a full filter state (applied over defaults) — a curated
// starting point a fundraiser can then refine. Ordered by how often they'd
// reach for it.
export type Preset = { id: string; label: string; hint: string
  filters: Partial<V5Filters> }
export const PRESETS: Preset[] = [
  {
    id: 'reachable-christian',
    label: 'Reachable Christian funders',
    hint: 'Give to Christian orgs, accept applications or contact, non-micro',
    filters: {
      tradition: [ANY_CHRISTIAN], min_tradition_dollars: '50000',
      application_status: ['Accepting Applications', 'Contact First'],
      has_contact: true, exclude_micro: true, exclude_testamentary: true,
      sort: 'christian',
    },
  },
  {
    id: 'high-confidence-christian',
    label: 'High-confidence Christian',
    hint: 'Only NTEE / church-code / GEN / human-confirmed Christian giving',
    filters: {
      tradition: [ANY_CHRISTIAN], tier: 'authoritative',
      min_tradition_recipients: '3', coverage_band: ['High', 'Moderate'],
      sort: 'christian',
    },
  },
  {
    id: 'accepting',
    label: 'Accepting applications',
    hint: 'Foundations with affirmative application evidence, non-micro',
    filters: {
      application_status: ['Accepting Applications'], exclude_micro: true,
    },
  },
  {
    id: 'catholic',
    label: 'Catholic funders',
    hint: 'Give to Catholic-classified recipients',
    filters: { tradition: ['catholic'], min_tradition_dollars: '50000',
      sort: 'christian' },
  },
  {
    id: 'evangelical',
    label: 'Evangelical funders',
    hint: 'Give to Evangelical / Protestant recipients',
    filters: { tradition: ['evangelical_protestant'],
      min_tradition_dollars: '50000', sort: 'christian' },
  },
  {
    id: 'major',
    label: 'Major funders ($1M+)',
    hint: 'Large grantmakers, excluding trusts and pass-through DAFs',
    filters: {
      min_paid: '1000000', exclude_testamentary: true, daf: 'exclude',
      sort: 'paid',
    },
  },
]

// ---- filter state ----------------------------------------------------------
// Numeric fields are kept as strings ('' = unset) so text inputs and URL
// round-tripping stay trivial; they are parsed when building query params.
export type V5Filters = {
  tradition: string[]
  tier: 'any' | 'authoritative' | 'mission'
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
  gives_to_state: string[]
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
  min_christian: string
  min_pct_christian: string
  include_inactive: boolean
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
  gives_to_state: [],
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
  // No default Christian-dollar floor. A $50k floor was tried and hid 27,759
  // foundations that genuinely fund Christian work under that amount -- real
  // prospects, since a $10k grant matters to a small nonprofit. It also bought
  // nothing: sorting is % Christian desc with christian_dollars desc as the
  // tie-break, so large funders already lead each percentage band and the top
  // of the list is identical with or without the floor.
  min_christian: '',
  min_pct_christian: '',
  include_inactive: false,
  sort: 'pct_christian',
  order: 'desc',
}

const LIST_KEYS = ['tradition', 'state', 'gives_to_state',
  'application_status', 'coverage_band'] as const
const NUM_KEYS = ['min_tradition_dollars', 'min_tradition_recipients',
  'min_paid', 'max_paid', 'min_median', 'max_median', 'min_grants',
  'min_assets', 'max_assets', 'min_revenue', 'min_coverage',
  'min_christian', 'min_pct_christian'] as const
const BOOL_KEYS = ['has_website', 'has_email', 'has_contact',
  'exclude_testamentary', 'exclude_micro', 'include_inactive'] as const

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
  const tier = sp.get('tier')
  if (tier === 'authoritative' || tier === 'mission') f.tier = tier
  NUM_KEYS.forEach((k) => { const v = sp.get(k); if (v) f[k] = v })
  BOOL_KEYS.forEach((k) => { if (sp.get(k) === 'true') f[k] = true })
  f.active_year = sp.get('active_year') || ''
  f.recipient_search = sp.get('recipient_search') || ''
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

// --- pages beyond the foundations explorer ----------------------------------

export type GrantsExplorerRow = {
  grantee_name: string
  city: string | null
  state: string | null
  amount: number
  tax_year: number
  purpose: string | null
  entity_id: string | null
  ein: string
  foundation_name: string
  tradition: string | null
  identity_status: string | null
}

export function fetchGrantsV5(qs: string): Promise<{
  total: number; total_dollars: number; rows: GrantsExplorerRow[]
}> {
  return getV5(`/api/v5/grants?${qs}`)
}

export type RecipientRowV5 = {
  entity_id: string
  name: string
  ein: string | null
  identity_status: string
  tradition: string | null
  method: string | null
  confidence: number | null
  reason: string | null
  is_daf: boolean
  total_received: number
  funder_count: number
  has_mission: boolean
}

export function fetchRecipientsV5(qs: string): Promise<{
  total: number; rows: RecipientRowV5[]
}> {
  return getV5(`/api/v5/recipients?${qs}`)
}

export function fetchRecipientsStatsV5(): Promise<{
  by_tradition: { tradition: string; recipients: number; dollars: number }[]
  by_method: { method: string; recipients: number }[]
  by_identity: { identity_status: string; recipients: number; dollars: number }[]
}> {
  return getV5('/api/v5/recipients-stats')
}

export function fetchStateBreakdownV5(): Promise<{
  state: string; foundations: number; paid: number; christian: number
}[]> {
  return getV5('/api/v5/analytics/state-breakdown')
}

export type TopFunderV5 = {
  ein: string; foundation_name: string; city: string | null
  state: string | null; paid_2324: number; christian_dollars: number
  coverage_pct: number; coverage_band: string
  application_status: string | null; recipient_count: number
}

export function fetchTopFundersV5(limit = 100, by = 'christian'):
  Promise<TopFunderV5[]> {
  return getV5(`/api/v5/analytics/top-funders?limit=${limit}&by=${by}`)
}

export function fetchYearlyTrendsV5(): Promise<{
  tax_year: number; grants: number; paid: number
  foundations: number; christian: number
}[]> {
  return getV5('/api/v5/analytics/yearly-trends')
}

export type DataQualityV5 = {
  totals: Record<string, number>
  coverage_bands: { coverage_band: string; foundations: number; paid: number }[]
  unattributable_reasons: { reason: string; foundations: number; dollars: number }[]
  identity: { identity_status: string; recipients: number; dollars: number }[]
  methods: { method: string; recipients: number }[]
  window: string
}

export function fetchDataQualityV5(): Promise<DataQualityV5> {
  return getV5('/api/v5/analytics/data-quality')
}
